"""Request-time current-weather fetcher (Open-Meteo, free, no API key) with a
per-city TTL cache. Returns None on any failure; callers must never error
because the weather API is unavailable -- weather is a supporting context
signal, not the app's core data."""
from __future__ import annotations

import time

import httpx

API = "https://api.open-meteo.com/v1/forecast"
TTL_SECONDS = 1800          # 30 min
_cache: dict[str, tuple[float, dict | None]] = {}

# Same city-center coordinates already used for OpenAQ station discovery
# (ingest/discover_live_locations.py, benchmark/expand_cities.py).
CITY_COORDS = {
    "Delhi": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777),
    "Kolkata": (22.5726, 88.3639),
    "Chennai": (13.0827, 80.2707),
    "Bengaluru": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Pune": (18.5204, 73.8567),
    "Ahmedabad": (23.0225, 72.5714),
    "Lucknow": (26.8467, 80.9462),
    "Patna": (25.5941, 85.1376),
}


def _now() -> float:
    return time.time()


def _fetch(city: str) -> dict | None:
    coords = CITY_COORDS.get(city)
    if not coords:
        return None
    lat, lon = coords
    try:
        with httpx.Client(timeout=6) as cli:
            r = cli.get(API, params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,uv_index",
                "timezone": "auto",
            })
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    cur = data.get("current")
    if not cur:
        return None
    return {
        "temp_c": cur.get("temperature_2m"),
        "humidity_pct": cur.get("relative_humidity_2m"),
        "wind_kmh": cur.get("wind_speed_10m"),
        "uv_index": cur.get("uv_index"),
        "observed_at": cur.get("time"),
    }


def get_weather(city: str) -> dict | None:
    hit = _cache.get(city)
    if hit and _now() - hit[0] < TTL_SECONDS:
        return hit[1]
    try:
        result = _fetch(city)
    except Exception:
        result = None
    _cache[city] = (_now(), result)
    return result
