"""Request-time OpenAQ v3 'latest' fetcher with a per-city TTL cache.

Returns latest concentrations for a city or None (no key, no stations, HTTP
failure, or nothing fresher than MAX_AGE_HOURS). Callers fall back to the
archive; the app must never error because OpenAQ is unavailable."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.openaq.org/v3"
TTL_SECONDS = 2700          # 45 min
MAX_AGE_HOURS = 24
_cache: dict[str, tuple[float, dict | None]] = {}


def _now() -> float:
    return time.time()


def _api_key() -> str:
    return os.getenv("OPENAQ_API_KEY", "")


@lru_cache(maxsize=1)
def _locations_raw() -> dict:
    return json.loads((ROOT / "ingest" / "live_locations.json").read_text())


def _locations() -> dict:
    return _locations_raw()


def _get_json(url: str) -> dict:
    with httpx.Client(timeout=6, headers={"X-API-Key": _api_key()}) as cli:
        r = cli.get(url)
        r.raise_for_status()
        return r.json()


def _fetch(city: str) -> dict | None:
    locs = _locations().get(city, [])
    if not locs or not _api_key():
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    per_param: dict[str, list[float]] = {}
    units: dict[str, str] = {}
    newest: datetime | None = None
    stations = 0
    for loc in locs[:5]:
        try:
            data = _get_json(f"{API}/locations/{loc['location_id']}/latest")
        except Exception:
            continue
        hit = False
        for row in data.get("results", []):
            meta = loc["sensors"].get(str(row.get("sensorsId")))
            if not meta:
                continue
            ts_raw = (row.get("datetime") or {}).get("utc")
            val = row.get("value")
            if ts_raw is None or val is None or val < 0:
                continue
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            if ts < cutoff:
                continue
            per_param.setdefault(meta["parameter"], []).append(float(val))
            units[meta["parameter"]] = meta["unit"]
            newest = ts if newest is None or ts > newest else newest
            hit = True
        stations += 1 if hit else 0
    if not per_param:
        return None
    return {
        "concs": {p: {"value": sum(v) / len(v), "unit": units[p]}
                  for p, v in per_param.items()},
        "last_updated": newest.isoformat(),
        "stations": stations,
    }


def get_live_city(city: str) -> dict | None:
    hit = _cache.get(city)
    if hit and _now() - hit[0] < TTL_SECONDS:
        return hit[1]
    try:
        result = _fetch(city)
    except Exception:
        result = None
    _cache[city] = (_now(), result)   # cache None too: no hammering on failure
    return result


def peek_live_city(city: str) -> dict | None:
    """Cached value only — never triggers a fetch (used for cheap rankings)."""
    hit = _cache.get(city)
    if hit and _now() - hit[0] < TTL_SECONDS:
        return hit[1]
    return None
