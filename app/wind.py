"""Real wind-vector grid over India, sampled from Open-Meteo (free, no API
key), reshaped into the same U/V-component GRIB-like JSON format that
leaflet-velocity (github.com/weacast/leaflet-velocity, MIT license) expects --
the same shape wind-js-server produces from real GFS GRIB2 data. TTL-cached
and never raises: callers get None on failure, same discipline as live.py and
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
_cache: dict[str, tuple[float, dict | None]] = {}

# India's bounding box, roughly (matches the country's actual extent with a
# small margin so coastal/border cities aren't right at the grid's edge).
LO1, LA1 = 66.0, 38.0     # NW corner (lon, lat)
LO2, LA2 = 98.0, 6.0      # SE corner (lon, lat)
NX, NY = 22, 17           # grid resolution: 374 points, ~1.5 deg spacing
                          # (kept under Open-Meteo's ~414-triggering URL length limit)


def _now() -> float:
    return time.time()


def _grid_points() -> tuple[list[float], list[float]]:
    dx = (LO2 - LO1) / (NX - 1)
    dy = (LA1 - LA2) / (NY - 1)
    lats, lons = [], []
    for j in range(NY):
        lat = LA1 - j * dy
        for i in range(NX):
            lon = LO1 + i * dx
            lats.append(round(lat, 3))
            lons.append(round(lon, 3))
    return lats, lons


def _fetch_grid() -> dict | None:
    lats, lons = _grid_points()
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
    if not isinstance(results, list) or len(results) != NX * NY:
        log.warning("wind grid response shape mismatch: expected %d points, got %s",
                     NX * NY, len(results) if isinstance(results, list) else type(results))
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
        "lo1": LO1, "la1": LA1, "lo2": LO2, "la2": LA2,
        "nx": NX, "ny": NY,
        "dx": (LO2 - LO1) / (NX - 1), "dy": (LA1 - LA2) / (NY - 1),
        "refTime": ref_time, "forecastTime": 0,
        "numberPoints": NX * NY,
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


def get_wind_grid() -> dict | None:
    hit = _cache.get("india")
    if hit and _now() - hit[0] < TTL_SECONDS:
        return hit[1]
    try:
        result = _fetch_grid()
    except Exception as e:
        log.warning("get_wind_grid failed: %s", e)
        result = None
    _cache["india"] = (_now(), result)
    return result
