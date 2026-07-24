"""Real wind-vector grid, sampled from Open-Meteo (free, no API key) for
whatever bounding box the map is currently showing, reshaped into the same
U/V-component GRIB-like JSON format that leaflet-velocity
(github.com/weacast/leaflet-velocity, MIT license) expects -- the same shape
wind-js-server produces from real GFS GRIB2 data. TTL-cached per bbox and
never raises: callers get None on failure, same discipline as live.py and
weather.py."""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timezone

import httpx

log = logging.getLogger("vayusense.wind")
API = "https://api.open-meteo.com/v1/forecast"
TTL_SECONDS = 1800          # 30 min -- wind fields don't need to be per-minute fresh
_cache: dict[tuple, tuple[float, dict | None]] = {}

# India's bounding box, roughly -- used as the default when the frontend
# hasn't sent one yet (first paint, before the map reports its own bounds).
DEFAULT_BBOX = (66.0, 6.0, 98.0, 38.0)   # lo1, la1, lo2, la2

# Total sample points kept under this regardless of bbox size/shape, since
# that's what actually drives the request URL length (Open-Meteo starts
# rejecting requests around ~414 chars worth of comma-joined coordinates,
# not the geographic extent itself).
MAX_POINTS = 374
MIN_DIM = 4          # never collapse an axis below this even at extreme aspect ratios
CACHE_PRECISION = 1  # degrees -- bbox rounded to this before cache-keying, so
                      # small pans/zooms reuse the same cached grid


def _now() -> float:
    return time.time()


def _normalize_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    lo1, la1, lo2, la2 = bbox
    lo1 = max(-180.0, min(180.0, lo1))
    lo2 = max(-180.0, min(180.0, lo2))
    la1 = max(-85.0, min(85.0, la1))
    la2 = max(-85.0, min(85.0, la2))
    if lo2 <= lo1:
        lo2 = lo1 + 1.0
    if la2 <= la1:
        la2 = la1 + 1.0
    return lo1, la1, lo2, la2


def _grid_dims(width: float, height: float) -> tuple[int, int]:
    """Pick nx/ny proportional to the bbox's aspect ratio, total points <= MAX_POINTS."""
    ratio = width / height if height else 1.0
    ny = max(MIN_DIM, round(math.sqrt(MAX_POINTS / max(ratio, 0.01))))
    nx = max(MIN_DIM, MAX_POINTS // ny)
    return nx, ny


def _grid_points(bbox: tuple[float, float, float, float]) -> tuple[list[float], list[float], int, int]:
    lo1, la1, lo2, la2 = bbox
    nx, ny = _grid_dims(lo2 - lo1, la2 - la1)
    dx = (lo2 - lo1) / (nx - 1)
    dy = (la2 - la1) / (ny - 1)
    lats, lons = [], []
    for j in range(ny):
        lat = la2 - j * dy   # top (la2) to bottom (la1), matches header lo1/la1 convention below
        for i in range(nx):
            lon = lo1 + i * dx
            lats.append(round(lat, 3))
            lons.append(round(lon, 3))
    return lats, lons, nx, ny


def _fetch_grid(bbox: tuple[float, float, float, float]) -> dict | None:
    lo1, la1, lo2, la2 = bbox
    lats, lons, nx, ny = _grid_points(bbox)
    lat_str = ",".join(str(v) for v in lats)
    lon_str = ",".join(str(v) for v in lons)
    try:
        with httpx.Client(timeout=20) as cli:
            r = cli.get(API, params={
                "latitude": lat_str, "longitude": lon_str,
                "current": "wind_speed_10m,wind_direction_10m",
                "wind_speed_unit": "ms",
            })
            r.raise_for_status()
            results = r.json()
    except Exception as e:
        log.warning("wind grid fetch failed: %s", e)
        return None
    if not isinstance(results, list) or len(results) != nx * ny:
        log.warning("wind grid response shape mismatch: expected %d points, got %s",
                     nx * ny, len(results) if isinstance(results, list) else type(results))
        return None

    u_data, v_data = [], []
    for point in results:
        cur = (point or {}).get("current") or {}
        speed = cur.get("wind_speed_10m")
        direction = cur.get("wind_direction_10m")
        if speed is None or direction is None:
            u_data.append(0.0)
            v_data.append(0.0)
            continue
        rad = math.radians(direction)
        # Meteorological convention: direction is where wind comes FROM.
        u_data.append(round(-speed * math.sin(rad), 2))
        v_data.append(round(-speed * math.cos(rad), 2))

    ref_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    header_common = {
        "lo1": lo1, "la1": la2, "lo2": lo2, "la2": la1,
        "nx": nx, "ny": ny,
        "dx": (lo2 - lo1) / (nx - 1), "dy": (la2 - la1) / (ny - 1),
        "refTime": ref_time, "forecastTime": 0,
        "numberPoints": nx * ny,
        # GRIB2 "Momentum" category (2); parameterNumber 2/3 is how
        # leaflet-velocity's createBuilder() actually distinguishes U from V
        # (it switches on these two numeric fields, NOT on the name string).
        "parameterCategory": 2,
    }
    return [
        {"header": {**header_common, "parameterNumber": 2,
                    "parameterNumberName": "U-component_of_wind",
                    "parameterUnit": "m.s-1"}, "data": u_data},
        {"header": {**header_common, "parameterNumber": 3,
                    "parameterNumberName": "V-component_of_wind",
                    "parameterUnit": "m.s-1"}, "data": v_data},
    ]


def get_wind_grid(bbox: tuple[float, float, float, float] | None = None) -> dict | None:
    bbox = _normalize_bbox(bbox or DEFAULT_BBOX)
    key = tuple(round(v / CACHE_PRECISION) * CACHE_PRECISION for v in bbox)
    hit = _cache.get(key)
    if hit and _now() - hit[0] < TTL_SECONDS:
        return hit[1]
    try:
        result = _fetch_grid(bbox)
    except Exception as e:
        log.warning("get_wind_grid failed: %s", e)
        result = None
    _cache[key] = (_now(), result)
    return result
