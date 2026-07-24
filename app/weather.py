"""Request-time current-weather fetcher (Open-Meteo, free, no API key) with a
per-city TTL cache. Returns None on any failure; callers must never error
because the weather API is unavailable -- weather is a supporting context
signal, not the app's core data."""
from __future__ import annotations

import logging
import time

import httpx

log = logging.getLogger("vayusense.weather")
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
    "Jaipur": (26.9124, 75.7873),
    "Surat": (21.1702, 72.8311),
    "Kanpur": (26.4499, 80.3319),
    "Nagpur": (21.1458, 79.0882),
    "Indore": (22.7196, 75.8577),
    "Bhopal": (23.2599, 77.4126),
    "Visakhapatnam": (17.6868, 83.2185),
    "Vadodara": (22.3072, 73.1812),
    "Coimbatore": (11.0168, 76.9558),
    "Nashik": (19.9975, 73.7898),
    # Added to give every state real coverage (Goa excluded: verified zero
    # OpenAQ stations anywhere in the state before deciding not to fake it).
    "Guwahati": (26.1445, 91.7362),
    "Raipur": (21.2514, 81.6296),
    "Faridabad": (28.4089, 77.3178),
    "Baddi": (30.9578, 76.7914),
    "Dhanbad": (23.7957, 86.4304),
    "Kochi": (9.9312, 76.2673),
    "Imphal": (24.8170, 93.9368),
    "Shillong": (25.5788, 91.8933),
    "Aizawl": (23.7271, 92.7176),
    "Kohima": (25.6751, 94.1086),
    "Bhubaneswar": (20.2961, 85.8245),
    "Ludhiana": (30.9010, 75.8573),
    "Gangtok": (27.3389, 88.6065),
    "Agartala": (23.8315, 91.2868),
    "Dehradun": (30.3165, 78.0322),
    "Itanagar": (27.0844, 93.6053),
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
    except Exception as e:
        log.warning("weather fetch failed for %s: %s", city, e)
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
    except Exception as e:
        log.warning("get_weather(%s) failed: %s", city, e)
        result = None
    _cache[city] = (_now(), result)
    return result
