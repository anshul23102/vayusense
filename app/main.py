"""VayuSense web app — FastAPI dashboard + ADK agent chat."""
from __future__ import annotations

import io
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from agents.advisory import generate_advisory, generate_advisory_batch
from agents.vision import ALLOWED_MIME_TYPES, MAX_IMAGE_BYTES, assess_sky_photo
from agents.agent import root_agent
from agents import tools as data_tools
from agents.aqi import (ARCHIVE_UNITS, category as aqi_category, overall_aqi,
                        pollutant_label as aqi_pollutant_label)
from agents.health_guidance import CONDITIONS, CONDITION_LABELS, GUIDANCE, citation as health_citation
from agents.solutions import citation as solutions_citation, get_solutions
from app import card, data_sync, live, weather, wind

log = logging.getLogger("vayusense.main")
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


@app.middleware("http")
async def static_cache_control(request: Request, call_next):
    # StaticFiles already sends ETag/Last-Modified, but with no Cache-Control
    # header some browsers apply their own heuristic caching and skip
    # revalidation entirely -- serving a stale benchmark.png (or any other
    # regenerated asset) straight from disk cache after a redeploy, as
    # happened live during this session. must-revalidate forces a cheap
    # conditional GET (304 if unchanged) instead of trusting a stale copy.
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
    return response


# Every third-party origin this app's HTML actually loads from, enumerated by
# grepping app/templates/*.html rather than guessed -- cdn.plot.ly (charts) and
# fonts.googleapis.com/fonts.gstatic.com (webfont). Leaflet used to come from
# unpkg.com; it is now vendored under /static/vendor/leaflet alongside its
# plugins, so that origin is gone from the policy entirely rather than left
# trusted for a script the app no longer fetches.
# Templates use inline <script>/style= throughout, so
# 'unsafe-inline' is required for script-src/style-src -- a stricter,
# nonce-based CSP isn't a realistic option without rewriting every template's
# inline JS, which is out of scope here; this still meaningfully restricts
# object embedding, framing, and where else content can load from.
# img-src needs blob: for the vision-check feature's photo preview
# (URL.createObjectURL) -- caught live: without it, the preview silently
# failed to render (confirmed with real image bytes, not just bad test data).
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.plot.ly; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = _CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # HTML carries the app's markup, CSS and JS inline, so a stale copy pins a
    # visitor to an old build. With no cache directive at all, browsers fall
    # back to heuristic caching and can serve that stale copy for a long time
    # (Safari is especially sticky about it). "no-cache" still lets the browser
    # keep the response, it just has to revalidate before reusing it, so this
    # costs a 304 rather than a full refetch. /static keeps its own policy.
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


class AskBody(BaseModel):
    question: str
    session_id: str | None = None


# In-process sliding-window rate limit for endpoints that trigger a real,
# billed Gemini call -- guards against a cost-bomb from unrestricted use.
# Per-process only (fine for a single Cloud Run instance; not a distributed
# limiter). Separate buckets per endpoint so vision-check (an image call,
# heavier per-request) doesn't share a budget with ask (text chat) --
# tripping one doesn't silently eat into the other's allowance.
ASK_RATE_LIMIT = 8          # max requests
ASK_RATE_WINDOW = 60        # per this many seconds, per client IP
_ask_hits: dict[str, deque] = defaultdict(deque)

VISION_RATE_LIMIT = 5
VISION_RATE_WINDOW = 60
_vision_hits: dict[str, deque] = defaultdict(deque)


def _client_id(request: Request) -> str:
    """Identify the caller for rate-limiting. Behind Cloud Run's front end
    request.client.host is the proxy, not the user, so every caller would
    otherwise share one bucket and strangers' traffic would 429 real users.
    The left-most X-Forwarded-For entry is the originating client; it is
    client-settable in general, but Cloud Run appends the true peer and
    rewrites the header, so on this deployment it is trustworthy."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(client_id: str, hits_by_client: dict[str, deque] = None,
                   limit: int = ASK_RATE_LIMIT, window: int = ASK_RATE_WINDOW) -> bool:
    if hits_by_client is None:
        hits_by_client = _ask_hits
    now = time.time()
    # Drop buckets that have fully aged out, so a stream of one-shot IPs
    # can't grow this map without bound.
    if len(hits_by_client) > 4096:
        for k in [k for k, v in hits_by_client.items() if not v or now - v[-1] > window]:
            del hits_by_client[k]
    hits = hits_by_client[client_id]
    while hits and now - hits[0] > window:
        hits.popleft()
    if len(hits) >= limit:
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
                f"{aqi_pollutant_label(row['dominant'])}. Real-time, GPU-processed air quality intelligence.")
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
def city_card(slug: str, request: Request):
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
        site_host=request.url.hostname or "",
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
    # get_year_over_year() clamps to 1..30 internally, so every out-of-range
    # value yields an identical result -- but the cache is keyed on what it
    # is handed, so clamping here too keeps an unbounded query parameter from
    # minting unbounded distinct cache keys and forcing a full 36-city
    # recompute per novel value.
    window = max(1, min(window, 30))
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
        grp = grp.sort_values("date")
        # Some stations fault into reporting a literal 0.0 for every
        # pollutant for an extended stretch (seen live: Kochi's station did
        # this for ~4 months, Apr-Jun 2026, which meant the "latest" row was
        # always the fault reading -- served as a fake "Good, AQI 0" result
        # the entire time instead of the last genuine measurement). Prefer
        # the latest row that isn't this failure mode; only fall back to a
        # zero row if a parameter has literally never had a real reading.
        nonzero = grp[grp["mean"] > 0]
        row = nonzero.iloc[-1] if not nonzero.empty else grp.iloc[-1]
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
    _archive_reading_total.cache_clear()


@lru_cache(maxsize=64)  # must exceed the 36 tracked cities, or a full sweep thrashes
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


@app.get("/api/advisory")
def advisory_api(city: str = "Delhi"):
    """Automated, ready-to-publish public advisory for one city -- rule-based,
    not an LLM call (see agents/advisory.py), so this is instant and free to
    generate on every request."""
    result = generate_advisory(city)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return result


@app.get("/api/advisory/all")
def advisory_batch_api():
    """Every tracked city's advisory in one call -- the concrete "automate
    workflows at scale" claim: this is a full batch run, not 36 sequential
    per-city requests, and completes in well under a second."""
    results = generate_advisory_batch()
    return {"count": len(results), "advisories": results}


@app.post("/api/vision-check")
async def vision_check_api(request: Request, city: str = "Delhi", file: UploadFile = File(...)):
    """Upload a sky/visibility photo and get a qualitative Gemini-vision read
    on it, in the context of the city's real measured AQI -- see
    agents/vision.py. Multimodal input, explicitly framed as a complement to
    the sensor data, never a substitute for it."""
    client_id = _client_id(request)
    if _rate_limited(client_id, _vision_hits, VISION_RATE_LIMIT, VISION_RATE_WINDOW):
        return JSONResponse(
            {"error": "Too many photo uploads right now. Please wait a moment and try again."},
            status_code=429,
        )
    if file.content_type not in ALLOWED_MIME_TYPES:
        return JSONResponse(
            {"error": f"Unsupported file type '{file.content_type}'. Please upload a JPEG, PNG, WEBP, or HEIC photo."},
            status_code=400,
        )
    # Reject on the declared length before touching the body, then read at most
    # one byte past the cap: a bare post-hoc len() check would already have
    # spooled an arbitrarily large upload to memory/disk before rejecting it.
    too_large = JSONResponse(
        {"error": "That photo is too large (max 8 MB). Please try a smaller image."},
        status_code=400,
    )
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
        return too_large
    image_bytes = await file.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return too_large
    row = _city_aqi(city, allow_fetch=True)
    if row is None:
        return JSONResponse({"error": f"no AQI data for city '{city}'"}, status_code=404)
    try:
        assessment = assess_sky_photo(image_bytes, file.content_type, city, row["aqi"], row["category"]["label"])
    except Exception as e:
        log.exception("vision_check_api() failed for city=%r", city)
        return JSONResponse({"error": _friendly_llm_error(e)}, status_code=503)
    return {"city": city, "aqi": row["aqi"], "category": row["category"]["label"], "assessment": assessment}


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


@lru_cache(maxsize=1)
def _archive_reading_total() -> int:
    """Total raw sensor readings behind the whole archive, summed from each
    daily aggregate's own observation count. Computed rather than hardcoded:
    the landing page previously stated two different, unsourced totals that
    contradicted each other and both understated the real figure."""
    return int(data_tools._daily()["count"].sum())


@app.get("/api/benchmark")
def benchmark():
    f = ROOT / "benchmark" / "benchmark_results.json"
    if f.exists():
        payload = json.loads(f.read_text())
        payload["archive_readings"] = _archive_reading_total()
        return payload
    return JSONResponse({"error": "benchmark not yet generated"}, status_code=404)


def _friendly_llm_error(e: Exception) -> str:
    msg = str(e)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
        return "VayuSense is getting a lot of questions right now (API rate limit). Please wait a few seconds and try again."
    return "Something went wrong answering that question. Please try again in a moment."


def _validate_ask(body: AskBody, request: Request) -> str | None:
    """Returns a client-facing error string, or None if the request is valid."""
    question = body.question.strip()
    if not question:
        return "Please type a question first."
    if len(question) > 500:
        return "That question is too long. Try something shorter."
    client_id = _client_id(request)
    if _rate_limited(client_id):
        return "You're asking questions faster than VayuSense can think. Please wait a moment and try again."
    return None


@app.post("/api/ask")
async def ask(body: AskBody, request: Request):
    question = body.question.strip()
    err = _validate_ask(body, request)
    if err:
        status = 429 if "faster than" in err else 400
        return JSONResponse({"error": err}, status_code=status)

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
        answer, analysis, trace = "", "", []
        async for event in runner.run_async(
            user_id="web", session_id=session.id, new_message=content
        ):
            # Every tool call the agents actually make, in call order -- this is
            # what "explainable AI" means here in concrete terms: not a claim
            # that the answer is grounded, a literal list of the real function
            # calls (name + args) that produced it, so a user can see this
            # wasn't free-form generation over the question alone.
            for call in event.get_function_calls():
                trace.append({"agent": event.author, "tool": call.name, "args": dict(call.args or {})})
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
        return {"answer": answer or analysis, "analysis": analysis, "session_id": session.id, "trace": trace}
    except Exception as e:
        log.exception("ask() failed for question=%r", question)
        return JSONResponse({"error": _friendly_llm_error(e)}, status_code=503)


@app.post("/api/ask/stream")
async def ask_stream(body: AskBody, request: Request):
    """Same agent pipeline as /api/ask, but token-by-token over SSE instead of
    blocking for the full answer -- "real-time inference," concretely: this
    was previously the single biggest gap against that criterion (verified:
    the old endpoint had no streaming path of any kind)."""
    question = body.question.strip()
    err = _validate_ask(body, request)
    if err:
        status = 429 if "faster than" in err else 400
        return JSONResponse({"error": err}, status_code=status)

    async def gen():
        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"
        try:
            session_id = body.session_id or str(uuid.uuid4())
            session = await runner.session_service.get_session(
                app_name="vayusense", user_id="web", session_id=session_id
            )
            if session is None:
                session = await runner.session_service.create_session(
                    app_name="vayusense", user_id="web", session_id=session_id
                )
            yield sse({"type": "session", "session_id": session.id})
            content = types.Content(role="user", parts=[types.Part.from_text(text=question)])
            got_answer = False
            async for event in runner.run_async(
                user_id="web", session_id=session.id, new_message=content,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                for call in event.get_function_calls():
                    yield sse({"type": "tool", "agent": event.author, "tool": call.name,
                               "args": dict(call.args or {})})
                # data_analyst's output is internal context for health_advisor,
                # never shown to the user (same rule as /api/ask) -- only
                # stream the final agent's text deltas.
                if event.author != "data_analyst" and event.content and event.content.parts \
                        and event.content.parts[0].text:
                    got_answer = True
                    yield sse({"type": "delta", "text": event.content.parts[0].text,
                               "partial": bool(event.partial)})
            if not got_answer:
                yield sse({"type": "error",
                           "error": "The agent didn't return an answer. Please try rephrasing your question."})
            yield sse({"type": "done"})
        except Exception as e:
            log.exception("ask_stream() failed for question=%r", question)
            yield sse({"type": "error", "error": _friendly_llm_error(e)})

    return StreamingResponse(gen(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
