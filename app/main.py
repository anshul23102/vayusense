"""VayuSense web app — FastAPI dashboard + ADK agent chat."""
from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from agents.agent import root_agent
from agents import tools as data_tools
from agents.aqi import ARCHIVE_UNITS, category as aqi_category, overall_aqi
from agents.health_guidance import CONDITIONS, CONDITION_LABELS, GUIDANCE, citation as health_citation
from agents.solutions import citation as solutions_citation, get_solutions
from app import live

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="VayuSense")
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")

runner = InMemoryRunner(agent=root_agent, app_name="vayusense")


class AskBody(BaseModel):
    question: str
    session_id: str | None = None


@app.get("/", response_class=HTMLResponse)
def landing():
    return (ROOT / "app" / "templates" / "landing.html").read_text()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return (ROOT / "app" / "templates" / "index.html").read_text()


@app.get("/city/{slug}", response_class=HTMLResponse)
def city_page(slug: str):
    cities = json.loads(data_tools.list_cities())
    match = next((c for c in cities if c.lower() == slug.lower()), None)
    if match is None:
        return JSONResponse({"error": f"unknown city '{slug}'"}, status_code=404)
    html = (ROOT / "app" / "templates" / "index.html").read_text()
    return html.replace("let CITY='Delhi';", f"let CITY='{match}';")


@app.get("/api/cities")
def cities():
    return json.loads(data_tools.list_cities())


@app.get("/api/snapshot")
def snapshot(city: str = "Delhi"):
    return json.loads(data_tools.get_city_snapshot(city))


@app.get("/api/trend")
def trend(city: str = "Delhi", parameter: str = "pm25", days: int = 60):
    return json.loads(data_tools.get_trend(city, parameter, days))


@app.get("/api/stations")
def stations(city: str = "Delhi"):
    return json.loads(data_tools.get_worst_stations(city))


@app.get("/api/impact")
def impact(city: str = "Delhi"):
    return json.loads(data_tools.get_human_impact(city))


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
async def ask(body: AskBody):
    question = body.question.strip()
    if not question:
        return JSONResponse({"error": "Please type a question first."}, status_code=400)
    if len(question) > 500:
        return JSONResponse({"error": "That question is too long. Try something shorter."}, status_code=400)

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
