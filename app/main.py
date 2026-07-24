"""VayuSense web app — FastAPI dashboard + ADK agent chat."""
from __future__ import annotations

import io
import json
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from agents.agent import root_agent
from agents import tools as data_tools
from agents.aqi import ARCHIVE_UNITS, category as aqi_category, overall_aqi
from agents.health_guidance import CONDITIONS, CONDITION_LABELS, GUIDANCE, citation as health_citation
from agents.solutions import citation as solutions_citation, get_solutions
from app import card, data_sync, live, weather, wind

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="VayuSense")
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")

runner = InMemoryRunner(agent=root_agent, app_name="vayusense")


@app.middleware("http")
async def sync_processed_data(request: Request, call_next):
    # Cloud Run only allocates CPU during request handling by default, so a
    # free-running background thread (data_sync.start_background_sync) can
    # stall indefinitely between requests -- piggyback the TTL-gated check on
    # actual traffic instead. maybe_refresh() is a cheap no-op the vast
    # majority of calls (a single time.time() comparison); it only does real
    # work once per TTL window, and never raises.
    from starlette.concurrency import run_in_threadpool
    await run_in_threadpool(data_sync.maybe_refresh)
    return await call_next(request)


class AskBody(BaseModel):
    question: str
    session_id: str | None = None


# In-process sliding-window rate limit for the LLM-backed /api/ask endpoint --
# guards against a cost-bomb from unrestricted Gemini calls. Per-process only
# (fine for a single Cloud Run instance; not a distributed limiter).
ASK_RATE_LIMIT = 8          # max requests
ASK_RATE_WINDOW = 60        # per this many seconds, per client IP
_ask_hits: dict[str, deque] = defaultdict(deque)


def _rate_limited(client_id: str) -> bool:
    now = time.time()
    hits = _ask_hits[client_id]
    while hits and now - hits[0] > ASK_RATE_WINDOW:
        hits.popleft()
    if len(hits) >= ASK_RATE_LIMIT:
        return True
    hits.append(now)
    return False


@app.get("/", response_class=HTMLResponse)
def landing():
    return (ROOT / "app" / "templates" / "landing.html").read_text()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return (ROOT / "app" / "templates" / "summary.html").read_text()


@app.get("/city/{slug}", response_class=HTMLResponse)
def city_page(slug: str):
    cities = json.loads(data_tools.list_cities())
    match = next((c for c in cities if c.lower() == slug.lower()), None)
    if match is None:
        return JSONResponse({"error": f"unknown city '{slug}'"}, status_code=404)
    html = (ROOT / "app" / "templates" / "index.html").read_text()
    html = html.replace("let CITY='Delhi';", f"let CITY='{match}';")
    row = _city_aqi(match, allow_fetch=False)
    if row is not None:
        title = f"{match} air quality: {row['aqi']} AQI ({row['category']['label']}) | VayuSense"
        desc = (f"{match}'s AQI is {row['aqi']} ({row['category']['label']}), driven by "
                f"{row['dominant'].upper()}. Real-time, GPU-processed air quality intelligence.")
        image = f"/city/{slug.lower()}/card.png"
        meta = (
            f'<meta property="og:title" content="{title}">'
            f'<meta property="og:description" content="{desc}">'
            f'<meta property="og:image" content="{image}">'
            f'<meta property="og:type" content="website">'
            f'<meta name="twitter:card" content="summary_large_image">'
            f'<meta name="twitter:title" content="{title}">'
            f'<meta name="twitter:description" content="{desc}">'
            f'<meta name="twitter:image" content="{image}">'
        )
        html = html.replace("</head>", meta + "</head>")
    return html


@app.get("/city/{slug}/card.png")
def city_card(slug: str):
    cities = json.loads(data_tools.list_cities())
    match = next((c for c in cities if c.lower() == slug.lower()), None)
    if match is None:
        return JSONResponse({"error": f"unknown city '{slug}'"}, status_code=404)
    row = _city_aqi(match, allow_fetch=True)
    if row is None:
        return JSONResponse({"error": f"no data for city '{match}'"}, status_code=404)
    imp = json.loads(data_tools.get_human_impact(match))
    png = card.render_card(
        city=match, aqi=row["aqi"], category_key=row["category"]["key"],
        category_label=row["category"]["label"], dominant=row["dominant"],
        source=row["source"], updated=row["last_updated"],
        cigarettes_per_day=imp.get("cigarettes_per_day_equivalent", 0),
        years_lost=imp.get("estimated_life_expectancy_years_lost", 0),
    )
    return Response(content=png, media_type="image/png",
                     headers={"Cache-Control": "public, max-age=1800"})


@app.get("/api/cities")
def cities():
    return json.loads(data_tools.list_cities())


@app.get("/api/snapshot")
def snapshot(city: str = "Delhi"):
    snap = json.loads(data_tools.get_city_snapshot(city))
    # Overlay live concentrations where available, same live-preferred/
    # archive-fallback discipline as _city_aqi(), so this KPI strip never
    # shows a stale winter-archive reading next to a live hero AQI for the
    # same city.
    lv = live.get_live_city(city)
    if "pollutants" in snap:
        for entry in snap["pollutants"].values():
            entry["source"] = "archive"
        if lv:
            for param, m in lv["concs"].items():
                if param not in snap["pollutants"]:
                    continue
                entry = snap["pollutants"][param]
                value = round(float(m["value"]), 1)
                who = data_tools.WHO_24H.get(param)
                entry["daily_mean"] = value
                entry["times_who_limit"] = round(value / who, 1) if who else None
                entry["source"] = "live"
        # Recompute the overall AQI from the (possibly live-overlaid)
        # concentrations too, so it can never disagree with the per-
        # pollutant values sitting right next to it in this same response.
        concs = {p: v["daily_mean"] for p, v in snap["pollutants"].items()}
        units = {p: (lv["concs"][p]["unit"] if lv and p in lv["concs"] else ARCHIVE_UNITS.get(p))
                 for p in concs}
        try:
            aqi_val, dominant, _subs = overall_aqi(concs, units)
            snap["aqi"] = aqi_val
            snap["aqi_category"] = aqi_category(aqi_val)["label"]
            snap["aqi_dominant"] = dominant
            snap["aqi_basis"] = ("live measurements where available, archive fallback otherwise"
                                  if lv else "EPA-method AQI from daily averages")
        except ValueError:
            pass
    return snap


@app.get("/api/weather")
def weather_api(city: str = "Delhi"):
    w = weather.get_weather(city)
    if w is None:
        return JSONResponse({"error": f"no weather data for city '{city}'"}, status_code=404)
    return w


@app.get("/api/wind-grid")
def wind_grid_api():
    grid = wind.get_wind_grid()
    if grid is None:
        return JSONResponse({"error": "wind grid unavailable"}, status_code=503)
    return grid


@app.get("/api/city-coords")
def city_coords_api():
    return {city: [lat, lon] for city, (lat, lon) in weather.CITY_COORDS.items()}


@app.get("/api/trend")
def trend(city: str = "Delhi", parameter: str = "pm25", days: int = 60):
    return json.loads(data_tools.get_trend(city, parameter, days))


@app.get("/api/stations")
def stations(city: str = "Delhi"):
    return json.loads(data_tools.get_worst_stations(city))


@app.get("/api/impact")
def impact(city: str = "Delhi"):
    return json.loads(data_tools.get_human_impact(city))


@app.get("/api/yoy")
def yoy(city: str = "Delhi", window: int = 7):
    return json.loads(data_tools.get_year_over_year(city, window))


@lru_cache(maxsize=8)
def _yoy_ranking_cached(window: int) -> tuple:
    cities = json.loads(data_tools.list_cities())
    rows = []
    for c in cities:
        r = json.loads(data_tools.get_year_over_year(c, window))
        if "error" not in r:
            rows.append((c, r["pct_change"], r["current_period"]["avg_aqi"],
                          r["same_period_last_year"]["avg_aqi"], r["verdict"]))
    rows.sort(key=lambda t: t[1])
    return tuple(rows)


@app.get("/api/yoy_ranking")
def yoy_ranking(window: int = 7):
    rows = _yoy_ranking_cached(window)
    return {
        "window_days": window,
        "most_improved": [
            {"city": c, "pct_change": p, "current_avg_aqi": cur, "last_year_avg_aqi": ly, "verdict": v}
            for c, p, cur, ly, v in rows[:5]
        ],
        "most_worsened": [
            {"city": c, "pct_change": p, "current_avg_aqi": cur, "last_year_avg_aqi": ly, "verdict": v}
            for c, p, cur, ly, v in list(reversed(rows))[:5]
        ],
        "cities_compared": len(rows),
    }


@app.get("/api/forecast")
def forecast(city: str = "Delhi", parameter: str = "pm25", days: int = 3):
    return json.loads(data_tools.get_forecast(city, parameter, days))


@app.get("/api/forecast_bench")
def forecast_bench(city: str = "Delhi", parameter: str = "pm25"):
    return json.loads(data_tools.get_forecast_bench(city, parameter))


def _archive_concs(city: str) -> tuple[dict, dict, str] | None:
    df = data_tools._daily()
    d = df[df["city"].str.lower() == city.lower()]
    if d.empty:
        return None
    concs, latest = {}, None
    for param, grp in d.groupby("parameter"):
        row = grp.sort_values("date").iloc[-1]
        concs[param] = float(row["mean"])
        latest = row["date"] if latest is None or row["date"] > latest else latest
    return concs, dict(ARCHIVE_UNITS), str(latest.date())


def _city_aqi(city: str, allow_fetch: bool) -> dict | None:
    lv = live.get_live_city(city) if allow_fetch else live.peek_live_city(city)
    if lv:
        concs = {p: m["value"] for p, m in lv["concs"].items()}
        units = {p: m["unit"] for p, m in lv["concs"].items()}
        source, last_updated, basis = "live", lv["last_updated"], "latest measurements"
    else:
        arch = _archive_concs(city)
        if arch is None:
            return None
        concs, units, last_updated = arch
        source, basis = "archive", "EPA-method AQI from daily averages"
    try:
        aqi, dominant, subs = overall_aqi(concs, units)
    except ValueError:
        return None
    return {"city": city, "aqi": aqi, "category": aqi_category(aqi),
            "dominant": dominant, "sub_aqi": subs,
            "concs": {p: round(float(v), 1) for p, v in concs.items()},
            "units": units,
            "source": source, "last_updated": last_updated, "basis": basis}


@app.get("/api/aqi")
def city_aqi(city: str = "Delhi"):
    main_out = _city_aqi(city, allow_fetch=True)
    if main_out is None:
        return JSONResponse({"error": f"no data for city '{city}'"}, status_code=404)
    # Every ranking row goes through the SAME live-preferred/archive-fallback
    # path as the hero number, so a row's "source" always matches the data
    # that actually produced its "aqi" — no city can show a live hero number
    # while its own ranking row silently used a different (stale) basis.
    others = [c for c in json.loads(data_tools.list_cities()) if c.lower() != city.lower()]
    with ThreadPoolExecutor(max_workers=max(len(others), 1)) as pool:
        results = list(pool.map(lambda c: _city_aqi(c, allow_fetch=True), others))
    ranking = [{"city": main_out["city"], "aqi": main_out["aqi"],
                "category": main_out["category"]["label"],
                "dominant": main_out["dominant"], "source": main_out["source"]}]
    for c, row in zip(others, results):
        if row is None:
            continue
        ranking.append({"city": c, "aqi": row["aqi"], "category": row["category"]["label"],
                        "dominant": row["dominant"], "source": row["source"]})
    ranking.sort(key=lambda x: -x["aqi"])
    main_out["ranking"] = ranking
    main_out["ranking_basis"] = "live measurements where available (cached up to 45 min), EPA-method archive fallback otherwise"
    main_out["of"] = len(ranking)
    main_out["rank"] = next((i + 1 for i, r in enumerate(ranking)
                             if r["city"].lower() == city.lower()), None)
    return main_out


def invalidate_all_caches() -> None:
    """Called after a fresh parquet sync (app/data_sync.py) so every cache
    derived from the processed data -- here and in agents/tools.py -- picks
    up the new data on next access instead of serving stale in-memory rows."""
    data_tools.invalidate_caches()
    _daily_overall_cached.cache_clear()
    _yoy_ranking_cached.cache_clear()


@lru_cache(maxsize=32)
def _daily_overall_cached(city_key: str) -> tuple:
    df = data_tools._daily()
    d = df[df["city"].str.lower() == city_key]
    out = []
    for date, grp in d.groupby("date"):
        concs = dict(zip(grp["parameter"], grp["mean"].astype(float)))
        try:
            aqi, _dom, _subs = overall_aqi(concs, ARCHIVE_UNITS)
        except ValueError:
            continue
        out.append({"date": str(date.date()), "aqi": aqi,
                    "key": aqi_category(aqi)["key"]})
    out.sort(key=lambda x: x["date"])
    return tuple(tuple(sorted(o.items())) for o in out)


def _daily_overall(city: str) -> list[dict]:
    return [dict(t) for t in _daily_overall_cached(city.lower())]


@app.get("/api/calendar")
def calendar_api(city: str = "Delhi", year: int = 2025):
    days = _daily_overall(city)
    if not days:
        return {"error": f"no data for city '{city}'"}
    years = sorted({int(d["date"][:4]) for d in days})
    sel = [d for d in days if d["date"].startswith(f"{year}-")]
    return {"city": city, "year": year, "years_available": years,
            "basis": "EPA-method daily AQI from the archive", "days": sel}


@app.get("/api/monthly")
def monthly_api(city: str = "Delhi"):
    days = _daily_overall(city)
    if not days:
        return {"error": f"no data for city '{city}'"}
    by_month: dict[str, list[int]] = {}
    by_year: dict[int, list[int]] = {}
    for d in days:
        by_month.setdefault(d["date"][:7], []).append(d["aqi"])
        by_year.setdefault(int(d["date"][:4]), []).append(d["aqi"])
    months = [{"month": m, "avg_aqi": round(sum(v) / len(v)),
               "key": aqi_category(round(sum(v) / len(v)))["key"]}
              for m, v in sorted(by_month.items())]
    most = max(months, key=lambda m: m["avg_aqi"])
    least = min(months, key=lambda m: m["avg_aqi"])
    annual = [{"year": y, "avg_aqi": round(sum(v) / len(v))}
              for y, v in sorted(by_year.items())]
    change = round((annual[-1]["avg_aqi"] - annual[0]["avg_aqi"])
                   / annual[0]["avg_aqi"] * 100, 1) if len(annual) >= 2 else 0.0
    return {"city": city, "basis": "EPA-method daily AQI from the archive",
            "months": months,
            "most_polluted": {"month": most["month"], "avg_aqi": most["avg_aqi"]},
            "least_polluted": {"month": least["month"], "avg_aqi": least["avg_aqi"]},
            "annual": annual, "annual_change_pct": change}


@app.get("/api/export")
def export_data(city: str = "Delhi", format: str = "csv"):
    df = data_tools._daily()
    d = df[df["city"].str.lower() == city.lower()][
        ["date", "parameter", "mean", "max", "count", "roll7", "anomaly"]
    ].sort_values(["parameter", "date"])
    if d.empty:
        return JSONResponse({"error": f"no data for city '{city}'"}, status_code=404)
    d = d.rename(columns={"mean": "daily_mean", "max": "daily_max", "count": "n_readings",
                           "roll7": "rolling_7day_mean"})
    fname_base = f"vayusense_{city.lower()}_daily_archive"
    if format == "json":
        records = json.loads(d.to_json(orient="records", date_format="iso"))
        return JSONResponse({
            "city": city, "rows": len(records),
            "source": "OpenAQ archive (AWS Open Data), GPU-processed",
            "data": records,
        }, headers={"Content-Disposition": f'attachment; filename="{fname_base}.json"'})
    buf = io.StringIO()
    d.to_csv(buf, index=False)
    return Response(content=buf.getvalue(), media_type="text/csv",
                     headers={"Content-Disposition": f'attachment; filename="{fname_base}.csv"'})


@app.get("/api/health_guidance")
def health_guidance_api():
    return {"conditions": CONDITIONS, "labels": CONDITION_LABELS,
            "guidance": GUIDANCE, "citation": health_citation()}


@app.get("/api/solutions")
def solutions_api(category: str = "moderate"):
    try:
        solutions = get_solutions(category)
    except KeyError:
        return JSONResponse({"error": f"unknown category '{category}'"}, status_code=404)
    return {"category": category, "solutions": solutions, "citation": solutions_citation()}


@app.get("/api/benchmark")
def benchmark():
    f = ROOT / "benchmark" / "benchmark_results.json"
    if f.exists():
        return json.loads(f.read_text())
    return JSONResponse({"error": "benchmark not yet generated"}, status_code=404)


@app.post("/api/ask")
async def ask(body: AskBody, request: Request):
    question = body.question.strip()
    if not question:
        return JSONResponse({"error": "Please type a question first."}, status_code=400)
    if len(question) > 500:
        return JSONResponse({"error": "That question is too long. Try something shorter."}, status_code=400)
    client_id = request.client.host if request.client else "unknown"
    if _rate_limited(client_id):
        return JSONResponse(
            {"error": "You're asking questions faster than VayuSense can think. Please wait a moment and try again."},
            status_code=429,
        )

    try:
        session_id = body.session_id or str(uuid.uuid4())
        session = await runner.session_service.get_session(
            app_name="vayusense", user_id="web", session_id=session_id
        )
        if session is None:
            session = await runner.session_service.create_session(
                app_name="vayusense", user_id="web", session_id=session_id
            )
        content = types.Content(role="user", parts=[types.Part.from_text(text=question)])
        answer, analysis = "", ""
        async for event in runner.run_async(
            user_id="web", session_id=session.id, new_message=content
        ):
            if event.content and event.content.parts and event.content.parts[0].text:
                if event.author == "data_analyst":
                    analysis = event.content.parts[0].text
                else:
                    answer = event.content.parts[0].text
        if not (answer or analysis):
            return JSONResponse(
                {"error": "The agent didn't return an answer. Please try rephrasing your question."},
                status_code=502,
            )
        return {"answer": answer or analysis, "analysis": analysis, "session_id": session.id}
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            friendly = "VayuSense is getting a lot of questions right now (API rate limit). Please wait a few seconds and try again."
        else:
            friendly = "Something went wrong answering that question. Please try again in a moment."
        return JSONResponse({"error": friendly}, status_code=503)
