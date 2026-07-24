"""Real-time global AQI station markers from OpenAQ v3, for whatever
bounding box the map is currently showing.

Verified directly against the live API before building this: GET
/v3/locations?bbox=... genuinely filters by bounding box, but GET
/v3/parameters/{id}/latest ignores bbox entirely and always returns
unfiltered global results -- so there is no single bulk call that returns
"latest PM2.5 in this region." Each candidate station's latest reading is
fetched individually instead, bounded by a small concurrency pool so a
pan/zoom can't fan out into dozens of simultaneous requests.

TTL-cached per (rounded) bbox and never raises: callers get None on failure,
same discipline as live.py and wind.py. Every point returned is a real
station with a real timestamp -- nothing here is synthesized."""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import httpx

from agents import aqi as aqi_calc
from app.weather import CITY_COORDS

log = logging.getLogger("vayusense.aqi_stations")
API = "https://api.openaq.org/v3"
TTL_SECONDS = 900          # 15 min
MAX_AGE_HOURS = 24
# OpenAQ's real limit is 60 requests/min per key (verified against the live
# API), shared across this whole app -- app/live.py's per-city LIVE badges
# use the same key. One bbox query costs 1 (locations) + up to MAX_STATIONS
# (latest) calls, so this has to stay well under 60 or a single pan/zoom can
# burn the whole minute's budget and start 429ing normal usage.
MAX_STATIONS = 20
CONCURRENCY = 5
CACHE_PRECISION = 1        # degrees -- bbox rounded to this before cache-keying
_cache: dict[tuple, tuple[float, list[dict] | None]] = {}

# VayuSense's own supported cities -> their /city/<slug> page, so a marker
# that happens to land near one of these links to a real detail page; every
# other station gets an honest "no detail page for this" popup instead.
# Matched by coordinates, not by name: OpenAQ's "locality" field is often a
# verbose station label ("Mundka, Delhi - DPCC") rather than a clean city
# name, so a string match against it silently misses real matches.
SUPPORTED_CITY_RADIUS_DEG = 0.4   # roughly metro-area scale
_SUPPORTED_CITY_COORDS = [(name.lower(), lat, lon) for name, (lat, lon) in CITY_COORDS.items()]


def _nearest_supported_city(lat: float, lon: float) -> str | None:
    for slug, clat, clon in _SUPPORTED_CITY_COORDS:
        if (lat - clat) ** 2 + (lon - clon) ** 2 <= SUPPORTED_CITY_RADIUS_DEG ** 2:
            return slug
    return None


def _api_key() -> str:
    return os.getenv("OPENAQ_API_KEY", "")


def _now() -> float:
    return time.time()


def _get_json(url: str, params: dict | None = None) -> dict:
    with httpx.Client(timeout=8, headers={"X-API-Key": _api_key()}) as cli:
        r = cli.get(url, params=params)
        r.raise_for_status()
        return r.json()


def _fetch_locations(bbox: tuple[float, float, float, float]) -> list[dict]:
    lo1, la1, lo2, la2 = bbox
    data = _get_json(f"{API}/locations", params={
        "bbox": f"{lo1},{la1},{lo2},{la2}",
        "parameters_id": 2,   # pm25 -- the pollutant the rest of the app treats as primary
        "limit": 200,
    })
    return data.get("results") or []


def _pm25_sensor_id(loc: dict) -> int | None:
    for s in loc.get("sensors") or []:
        if (s.get("parameter") or {}).get("name") == "pm25":
            return s.get("id")
    return None


def _nearest_first(locations: list[dict], center: tuple[float, float]) -> list[dict]:
    clat, clon = center

    def dist2(loc: dict) -> float:
        c = loc.get("coordinates") or {}
        return (c.get("latitude", 0.0) - clat) ** 2 + (c.get("longitude", 0.0) - clon) ** 2

    return sorted(locations, key=dist2)


def _fetch_latest_pm25(location_id: int, sensor_id: int) -> dict | None:
    try:
        data = _get_json(f"{API}/locations/{location_id}/latest")
    except Exception:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    for r in data.get("results") or []:
        if r.get("sensorsId") != sensor_id:
            continue
        ts = (r.get("datetime") or {}).get("utc")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt < cutoff:
            return None
        return {"value": r.get("value"), "updated_at": ts}
    return None


def _build_station(loc: dict, reading: dict) -> dict | None:
    value = reading.get("value")
    if value is None or value < 0:
        return None
    aqi = aqi_calc.pollutant_aqi("pm25", value, "ugm3")
    if aqi is None:
        return None
    cat = aqi_calc.category(aqi)
    city = loc.get("locality") or loc.get("name") or "Unknown"
    country = (loc.get("country") or {}).get("name") or ""
    coords = loc.get("coordinates") or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    if lat is None or lon is None:
        return None
    slug = _nearest_supported_city(lat, lon)
    return {
        "name": loc.get("name") or city,
        "city": city,
        "country": country,
        "lat": lat,
        "lon": lon,
        "aqi": aqi,
        "category": cat["label"],
        "category_key": cat["key"],
        "color": cat["color"],
        "pollutant": "pm25",
        "value": value,
        "updated_at": reading.get("updated_at"),
        "is_supported_city": slug is not None,
        "supported_city_slug": slug,
    }


def _fetch_stations(bbox: tuple[float, float, float, float]) -> list[dict]:
    locations = _fetch_locations(bbox)
    sensor_by_id = {loc["id"]: sid for loc in locations
                    if (sid := _pm25_sensor_id(loc)) is not None}
    candidates = [loc for loc in locations if loc["id"] in sensor_by_id]
    if not candidates:
        return []
    lo1, la1, lo2, la2 = bbox
    center = ((la1 + la2) / 2, (lo1 + lo2) / 2)
    candidates = _nearest_first(candidates, center)[:MAX_STATIONS]

    stations: list[dict] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = {
            ex.submit(_fetch_latest_pm25, loc["id"], sensor_by_id[loc["id"]]): loc
            for loc in candidates
        }
        for fut in as_completed(futures):
            loc = futures[fut]
            try:
                reading = fut.result()
            except Exception:
                reading = None
            if reading is None:
                continue
            station = _build_station(loc, reading)
            if station:
                stations.append(station)
    return stations


def get_stations(bbox: tuple[float, float, float, float]) -> list[dict] | None:
    """bbox is (lo1, la1, lo2, la2) = (west, south, east, north), degrees."""
    if not _api_key():
        return None
    key = tuple(round(v / CACHE_PRECISION) * CACHE_PRECISION for v in bbox)
    hit = _cache.get(key)
    if hit and _now() - hit[0] < TTL_SECONDS:
        return hit[1]
    try:
        result = _fetch_stations(bbox)
    except Exception as e:
        log.warning("get_stations failed: %s", e)
        result = None
    _cache[key] = (_now(), result)
    return result
