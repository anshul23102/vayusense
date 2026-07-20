# AQI Engine + Live Core Implementation Plan (Renovation Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Real US EPA AQI everywhere (engine + API + agents), an honest live-data hero (OpenAQ v3 request-time fetch with archive fallback), and the aqi.in-style hero renovation (AQI ring, category chip, graded scale bar with pointer, LIVE/Archive badge, rank chip).

**Architecture:** A pure-function AQI module (`agents/aqi.py`) is shared by the app and agents. A TTL-cached live fetcher (`app/live.py`) reads committed station metadata (`ingest/live_locations.json`, produced by a one-time discovery script) and returns latest concentrations or None; `/api/aqi` composes live-or-archive AQI plus a 10-city ranking. The dashboard hero consumes `/api/aqi` and retires the invented 0–100 score.

**Tech Stack:** Python 3.11, FastAPI, httpx, pandas (existing), OpenAQ v3 API, vanilla JS/CSS frontend, pytest.

## Global Constraints

- Working directory `/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense`; venv at `.venv/bin/python`.
- Archive units: pm25/pm10/no2/o3/so2 in µg/m³, **co in mg/m³** (`ARCHIVE_UNITS` in `agents/aqi.py` is the single source of truth).
- AQI bands/labels: Good 0–50, Moderate 51–100, Poor 101–150, Unhealthy 151–200, Severe 201–300, Hazardous 301–500 (clamp at 500).
- New ramp colors (DESIGN.md "The AQI Ramp"): Good `#4fe3ac`, Moderate `#ffce80`, Poor `#ffab73` (Ember, new), Unhealthy `#ff8aa3`, Severe `#ef7ac8` (Magenta Signal, new), Hazardous `#b04a63` (Oxblood, new). New tokens allowed ONLY in AQI-severity visualizations; always paired with the band label.
- Basis labeling is mandatory: archive AQI = "EPA-method AQI from daily averages"; live AQI = "latest measurements" + timestamp.
- `OPENAQ_API_KEY`: never print/echo the value anywhere (chat, logs, git). Local source file `/tmp/openaq_key.txt`; if missing, STOP and ask the user to paste it into an opened file (established pattern).
- Live HTTP budget: ≤5 locations/city, 6 s client timeout, 45-min TTL cache (None results cached too); measurements older than 24 h don't count as live.
- Commits end with the Co-Authored-By Claude trailer; push after each task. Deploy cadence: local verify → Cloud Build (`/tmp/cloudbuild.yaml`, `-f deploy/Dockerfile`) → `gcloud run deploy vayusense --region=us-central1` → live verify → push.

---

### Task 1: EPA AQI engine

**Files:**
- Create: `agents/aqi.py`
- Test: `tests/test_aqi.py`

**Interfaces:**
- Produces: `to_epa_unit(parameter, value, unit) -> float | None` (target units: pm→µg/m³, o3/so2/no2→ppb, co→ppm; accepted unit strings: `"ugm3"`, `"mgm3"`, `"ppb"`, `"ppm"`, plus the µ/m³ glyph variants); `pollutant_aqi(parameter, value, unit="ugm3") -> int | None`; `overall_aqi(concs: dict[str, float], units: dict[str, str]) -> tuple[int, str, dict[str, int]]` (AQI, dominant parameter, per-pollutant sub-AQIs); `category(aqi: int) -> dict` (`{key, label, color}`); constant `ARCHIVE_UNITS: dict[str, str]`.

- [ ] **Step 1: Write the failing test**

`tests/test_aqi.py`:
```python
import pytest

from agents.aqi import ARCHIVE_UNITS, category, overall_aqi, pollutant_aqi, to_epa_unit


# Published EPA anchor points (2024 PM2.5 table)
@pytest.mark.parametrize("param,value,unit,expected", [
    ("pm25", 9.0, "ugm3", 50),
    ("pm25", 35.4, "ugm3", 100),
    ("pm25", 55.4, "ugm3", 150),
    ("pm25", 125.4, "ugm3", 200),
    ("pm25", 225.4, "ugm3", 300),
    ("pm10", 54, "ugm3", 50),
    ("pm10", 154, "ugm3", 100),
    ("co", 4.4, "ppm", 50),
    ("co", 9.4, "ppm", 100),
    ("so2", 35, "ppb", 50),
    ("no2", 53, "ppb", 50),
    ("o3", 70, "ppb", 100),
])
def test_epa_anchor_points(param, value, unit, expected):
    assert pollutant_aqi(param, value, unit) == expected


def test_clamps_at_500_above_table():
    assert pollutant_aqi("pm25", 999.0, "ugm3") == 500


def test_unknown_or_negative_returns_none():
    assert pollutant_aqi("xyz", 10, "ugm3") is None
    assert pollutant_aqi("pm25", -1, "ugm3") is None


def test_unit_conversion_no2_ugm3():
    # 100 ug/m3 NO2 -> 53.15 ppb -> truncated 53 ppb -> AQI 50 (top of Good)
    assert pollutant_aqi("no2", 100.0, "ugm3") == 50


def test_unit_conversion_co_mgm3():
    # 5.0 mg/m3 CO -> ~4.36 ppm -> AQI in Good band (<=50)
    v = to_epa_unit("co", 5.0, "mgm3")
    assert 4.3 < v < 4.45
    assert pollutant_aqi("co", 5.0, "mgm3") <= 50


def test_overall_picks_dominant():
    aqi, dominant, subs = overall_aqi(
        {"pm25": 55.4, "no2": 20.0}, {"pm25": "ugm3", "no2": "ugm3"}
    )
    assert aqi == 150 and dominant == "pm25"
    assert subs["pm25"] == 150 and subs["no2"] < 50


def test_category_bands():
    assert category(50)["key"] == "good"
    assert category(51)["key"] == "moderate"
    assert category(150)["label"] == "Poor"
    assert category(300)["key"] == "severe"
    assert category(301)["key"] == "hazardous"
    assert category(301)["color"] == "#b04a63"


def test_archive_units_cover_all_params():
    assert set(ARCHIVE_UNITS) == {"pm25", "pm10", "no2", "o3", "so2", "co"}
    assert ARCHIVE_UNITS["co"] == "mgm3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_aqi.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.aqi'`

- [ ] **Step 3: Implement `agents/aqi.py`**

```python
"""US EPA AQI computation (pure functions, no I/O).

Breakpoints: EPA tables, PM2.5 per the May-2024 update. Archive-derived AQI is
computed from daily means, not EPA's 1h/8h windows — callers must label it
"EPA-method AQI from daily averages"."""
from __future__ import annotations

import math

# (concentration_low, concentration_high) per band, in EPA units:
# pm25/pm10 ug/m3, o3/so2/no2 ppb, co ppm.
BREAKPOINTS: dict[str, list[tuple[float, float]]] = {
    "pm25": [(0.0, 9.0), (9.1, 35.4), (35.5, 55.4), (55.5, 125.4), (125.5, 225.4), (225.5, 325.4)],
    "pm10": [(0, 54), (55, 154), (155, 254), (255, 354), (355, 424), (425, 604)],
    "o3":   [(0, 54), (55, 70), (71, 85), (86, 105), (106, 200), (201, 604)],
    "co":   [(0.0, 4.4), (4.5, 9.4), (9.5, 12.4), (12.5, 15.4), (15.5, 30.4), (30.5, 50.4)],
    "so2":  [(0, 35), (36, 75), (76, 185), (186, 304), (305, 604), (605, 1004)],
    "no2":  [(0, 53), (54, 100), (101, 360), (361, 649), (650, 1249), (1250, 2049)],
}
AQI_BANDS = [(0, 50), (51, 100), (101, 150), (151, 200), (201, 300), (301, 500)]
CATEGORIES = [
    {"key": "good", "label": "Good", "color": "#4fe3ac"},
    {"key": "moderate", "label": "Moderate", "color": "#ffce80"},
    {"key": "poor", "label": "Poor", "color": "#ffab73"},
    {"key": "unhealthy", "label": "Unhealthy", "color": "#ff8aa3"},
    {"key": "severe", "label": "Severe", "color": "#ef7ac8"},
    {"key": "hazardous", "label": "Hazardous", "color": "#b04a63"},
]
_MW = {"no2": 46.006, "so2": 64.066, "o3": 48.0, "co": 28.01}
# EPA truncation: decimals kept per parameter (in EPA units)
_TRUNC = {"pm25": 1, "pm10": 0, "o3": 0, "so2": 0, "no2": 0, "co": 1}
# How the processed archive stores each parameter
ARCHIVE_UNITS = {"pm25": "ugm3", "pm10": "ugm3", "no2": "ugm3",
                 "o3": "ugm3", "so2": "ugm3", "co": "mgm3"}

_UNIT_ALIASES = {"µg/m³": "ugm3", "ug/m3": "ugm3", "mg/m³": "mgm3", "mg/m3": "mgm3",
                 "ppb": "ppb", "ppm": "ppm", "ugm3": "ugm3", "mgm3": "mgm3"}


def to_epa_unit(parameter: str, value: float, unit: str = "ugm3") -> float | None:
    """Convert a concentration to the EPA unit for its parameter (25 C, 1 atm)."""
    unit = _UNIT_ALIASES.get(unit)
    if unit is None or parameter not in BREAKPOINTS:
        return None
    if parameter in ("pm25", "pm10"):
        return float(value)  # ug/m3 across all our sources
    if unit == "ppb":
        ppb = float(value)
    elif unit == "ppm":
        ppb = float(value) * 1000.0
    elif unit == "ugm3":
        ppb = float(value) * 24.45 / _MW[parameter]
    else:  # mgm3
        ppb = float(value) * 1000.0 * 24.45 / _MW[parameter]
    return ppb / 1000.0 if parameter == "co" else ppb


def _truncate(parameter: str, value: float) -> float:
    q = 10 ** _TRUNC[parameter]
    return math.floor(value * q) / q


def pollutant_aqi(parameter: str, value: float, unit: str = "ugm3") -> int | None:
    if value is None or value < 0:
        return None
    conc = to_epa_unit(parameter, value, unit)
    if conc is None:
        return None
    conc = _truncate(parameter, conc)
    table = BREAKPOINTS[parameter]
    for (c_lo, c_hi), (i_lo, i_hi) in zip(table, AQI_BANDS):
        if c_lo <= conc <= c_hi:
            return round((i_hi - i_lo) / (c_hi - c_lo) * (conc - c_lo) + i_lo)
    return 500  # above the top breakpoint


def overall_aqi(concs: dict[str, float], units: dict[str, str]) -> tuple[int, str, dict[str, int]]:
    subs: dict[str, int] = {}
    for p, v in concs.items():
        a = pollutant_aqi(p, v, units.get(p, "ugm3"))
        if a is not None:
            subs[p] = a
    if not subs:
        raise ValueError("no computable pollutants")
    dominant = max(subs, key=subs.get)
    return subs[dominant], dominant, subs


def category(aqi: int) -> dict:
    for (lo, hi), cat in zip(AQI_BANDS, CATEGORIES):
        if lo <= aqi <= hi:
            return dict(cat)
    return dict(CATEGORIES[-1])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_aqi.py -v`
Expected: all pass (12 parametrized + 7 others)

- [ ] **Step 5: Commit and push**

```bash
git add agents/aqi.py tests/test_aqi.py
git commit -m "feat: US EPA AQI engine (2024 PM2.5 table, unit conversions, categories)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: Live-station discovery (one-time, needs OpenAQ key)

**Files:**
- Create: `ingest/discover_live_locations.py`
- Produce: `ingest/live_locations.json`

**Interfaces:**
- Produces: `ingest/live_locations.json` schema consumed by Task 3:
  `{city: [{"location_id": int, "sensors": {"<sensor_id>": {"parameter": "pm25", "unit": "µg/m³"}}}, ...]}` (≤5 locations/city).

- [ ] **Step 1: Key checkpoint**

Run: `test -f /tmp/openaq_key.txt && echo present || echo MISSING`
If MISSING: STOP — open a fresh file for the user to paste the OpenAQ key into (do not accept it via chat), then continue.

- [ ] **Step 2: Implement `ingest/discover_live_locations.py`**

```python
"""One-time discovery: map each VayuSense city to up to 5 active OpenAQ v3
locations, recording sensor->parameter/unit so the live fetcher can decode
/latest responses without extra API calls. Writes ingest/live_locations.json."""
from __future__ import annotations

import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
KEY = open("/tmp/openaq_key.txt").read().strip()
HEADERS = {"X-API-Key": KEY}
API = "https://api.openaq.org/v3"
PARAMS = {"pm25", "pm10", "no2", "o3", "so2", "co"}
CITY_QUERIES = {
    "Delhi":     {"coordinates": "28.6139,77.2090", "radius": 25000},
    "Mumbai":    {"coordinates": "19.0760,72.8777", "radius": 25000},
    "Kolkata":   {"coordinates": "22.5726,88.3639", "radius": 25000},
    "Chennai":   {"coordinates": "13.0827,80.2707", "radius": 25000},
    "Bengaluru": {"coordinates": "12.9716,77.5946", "radius": 25000},
    "Hyderabad": {"coordinates": "17.3850,78.4867", "radius": 25000},
    "Pune":      {"coordinates": "18.5204,73.8567", "radius": 25000},
    "Ahmedabad": {"coordinates": "23.0225,72.5714", "radius": 25000},
    "Lucknow":   {"coordinates": "26.8467,80.9462", "radius": 25000},
    "Patna":     {"coordinates": "25.5941,85.1376", "radius": 25000},
}


def main() -> None:
    out: dict[str, list[dict]] = {}
    for city, q in CITY_QUERIES.items():
        r = requests.get(f"{API}/locations",
                         params={**q, "limit": 100}, headers=HEADERS, timeout=30)
        r.raise_for_status()
        locs = []
        for loc in r.json().get("results", []):
            sensors = {}
            for s in loc.get("sensors", []):
                pname = (s.get("parameter") or {}).get("name")
                punits = (s.get("parameter") or {}).get("units", "")
                if pname in PARAMS:
                    sensors[str(s["id"])] = {"parameter": pname, "unit": punits}
            if sensors:
                locs.append({"location_id": loc["id"], "sensors": sensors})
            if len(locs) >= 5:
                break
        out[city] = locs
        print(f"{city}: {len(locs)} locations, "
              f"{sum(len(l['sensors']) for l in locs)} sensors")
    (ROOT / "ingest" / "live_locations.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it**

Run: `.venv/bin/python ingest/discover_live_locations.py`
Expected: one line per city with ≥1 location for most cities. If a city has 0, that's acceptable (live will fall back to archive there) — note it.

- [ ] **Step 4: Sanity-check and commit**

Run: `.venv/bin/python -c "import json; d=json.load(open('ingest/live_locations.json')); print({k: len(v) for k,v in d.items()})"`

```bash
git add ingest/discover_live_locations.py ingest/live_locations.json
git commit -m "feat: OpenAQ live-station discovery for the 10 tracked cities

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 3: Live fetcher with TTL cache

**Files:**
- Create: `app/live.py`
- Test: `tests/test_live.py`
- Modify: `requirements.txt` (add `httpx` line if absent)

**Interfaces:**
- Consumes: `ingest/live_locations.json` (Task 2 schema).
- Produces: `get_live_city(city: str) -> dict | None` — `{"concs": {param: {"value": float, "unit": str}}, "last_updated": iso_str, "stations": int}`; `peek_live_city(city) -> dict | None` (cache-only, never fetches); module constants `TTL_SECONDS = 2700`, `MAX_AGE_HOURS = 24`; `_cache` dict and `_now()` seam for tests.

- [ ] **Step 1: Write the failing test**

`tests/test_live.py`:
```python
import json
from datetime import datetime, timedelta, timezone

import app.live as live


def _payload(param="pm25", value=52.0, unit="µg/m³", hours_ago=1, sensor_id="901"):
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {"results": [{"sensorsId": int(sensor_id), "value": value,
                         "datetime": {"utc": ts}}]}


def _fake_locations():
    return {"Testville": [{"location_id": 7,
                           "sensors": {"901": {"parameter": "pm25", "unit": "µg/m³"}}}]}


def test_fetch_aggregates_and_caches(monkeypatch):
    live._cache.clear()
    monkeypatch.setattr(live, "_locations", _fake_locations)
    monkeypatch.setattr(live, "_api_key", lambda: "k")
    calls = {"n": 0}

    def fake_get(url):
        calls["n"] += 1
        return _payload()
    monkeypatch.setattr(live, "_get_json", fake_get)

    out = live.get_live_city("Testville")
    assert out["concs"]["pm25"]["value"] == 52.0
    assert out["concs"]["pm25"]["unit"] == "µg/m³"
    assert out["stations"] == 1
    live.get_live_city("Testville")           # second call
    assert calls["n"] == 1                     # served from cache


def test_stale_measurements_mean_no_live(monkeypatch):
    live._cache.clear()
    monkeypatch.setattr(live, "_locations", _fake_locations)
    monkeypatch.setattr(live, "_api_key", lambda: "k")
    monkeypatch.setattr(live, "_get_json", lambda url: _payload(hours_ago=48))
    assert live.get_live_city("Testville") is None


def test_http_failure_returns_none_and_is_cached(monkeypatch):
    live._cache.clear()
    monkeypatch.setattr(live, "_locations", _fake_locations)
    monkeypatch.setattr(live, "_api_key", lambda: "k")
    calls = {"n": 0}

    def boom(url):
        calls["n"] += 1
        raise RuntimeError("down")
    monkeypatch.setattr(live, "_get_json", boom)
    assert live.get_live_city("Testville") is None
    assert live.get_live_city("Testville") is None
    assert calls["n"] == 1                     # failure cached, no hammering


def test_no_key_returns_none(monkeypatch):
    live._cache.clear()
    monkeypatch.setattr(live, "_api_key", lambda: "")
    assert live.get_live_city("Testville") is None


def test_peek_never_fetches(monkeypatch):
    live._cache.clear()
    monkeypatch.setattr(live, "_get_json",
                        lambda url: (_ for _ in ()).throw(AssertionError("fetched")))
    assert live.peek_live_city("Testville") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_live.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.live'`

- [ ] **Step 3: Implement `app/live.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_live.py -v`
Expected: 5 passed

- [ ] **Step 5: Ensure httpx ships in the app image**

Run: `grep -i "^httpx" requirements.txt || echo "httpx" >> requirements.txt; tail -3 requirements.txt`

- [ ] **Step 6: Commit and push**

```bash
git add app/live.py tests/test_live.py requirements.txt
git commit -m "feat: TTL-cached OpenAQ live fetcher with honest staleness rules

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 4: `/api/aqi` + snapshot AQI + analyst instruction

**Files:**
- Modify: `app/main.py` (new endpoint after `/api/forecast_bench`)
- Modify: `agents/tools.py` (snapshot gains AQI fields)
- Modify: `agents/agent.py` (one instruction line)
- Test: `tests/test_aqi_api.py`

**Interfaces:**
- Consumes: `overall_aqi`, `category`, `ARCHIVE_UNITS` (Task 1); `get_live_city`, `peek_live_city` (Task 3); `data_tools._daily()`.
- Produces: `GET /api/aqi?city=` → `{city, aqi, category:{key,label,color}, dominant, sub_aqi, source: "live"|"archive", last_updated, basis, rank, of, ranking:[{city,aqi,category}]}`; `get_city_snapshot` JSON gains top-level `"aqi"`, `"aqi_category"`, `"aqi_dominant"`, `"aqi_basis"`.

- [ ] **Step 1: Write the failing test**

`tests/test_aqi_api.py`:
```python
import json

import agents.tools as tools
from app.main import _city_aqi


def test_city_aqi_archive_fallback(monkeypatch):
    import app.live as live
    monkeypatch.setattr(live, "get_live_city", lambda c: None)
    out = _city_aqi("Delhi", allow_fetch=True)
    assert out["source"] == "archive"
    assert out["basis"] == "EPA-method AQI from daily averages"
    assert isinstance(out["aqi"], int) and out["aqi"] > 0
    assert out["category"]["key"] in {"good", "moderate", "poor", "unhealthy", "severe", "hazardous"}
    assert out["dominant"] in out["sub_aqi"]


def test_city_aqi_live_path(monkeypatch):
    import app.live as live
    monkeypatch.setattr(live, "get_live_city",
                        lambda c: {"concs": {"pm25": {"value": 52.0, "unit": "µg/m³"}},
                                   "last_updated": "2026-07-20T04:00:00+00:00",
                                   "stations": 3})
    out = _city_aqi("Delhi", allow_fetch=True)
    assert out["source"] == "live"
    assert out["aqi"] == 142  # EPA 2024 table: pm25 52.0 ug/m3 -> 141.6 -> 142
    assert out["last_updated"] == "2026-07-20T04:00:00+00:00"


def test_snapshot_includes_aqi():
    out = json.loads(tools.get_city_snapshot("Delhi"))
    assert isinstance(out["aqi"], int)
    assert out["aqi_category"] in {"Good", "Moderate", "Poor", "Unhealthy", "Severe", "Hazardous"}
    assert out["aqi_dominant"] in out["pollutants"]
    assert out["aqi_basis"] == "EPA-method AQI from daily averages"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_aqi_api.py -v`
Expected: FAIL with `ImportError: cannot import name '_city_aqi'`

- [ ] **Step 3: Implement in `app/main.py`**

Add imports near the top (after `from agents import tools as data_tools`):
```python
from agents.aqi import ARCHIVE_UNITS, category as aqi_category, overall_aqi
from app import live
```

Add after the `/api/forecast_bench` route:
```python
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
            "source": source, "last_updated": last_updated, "basis": basis}


@app.get("/api/aqi")
def city_aqi(city: str = "Delhi"):
    main_out = _city_aqi(city, allow_fetch=True)
    if main_out is None:
        return JSONResponse({"error": f"no data for city '{city}'"}, status_code=404)
    ranking = []
    for c in json.loads(data_tools.list_cities()):
        r = main_out if c.lower() == city.lower() else _city_aqi(c, allow_fetch=False)
        if r:
            ranking.append({"city": c, "aqi": r["aqi"], "category": r["category"]["label"]})
    ranking.sort(key=lambda x: -x["aqi"])
    main_out["ranking"] = ranking
    main_out["of"] = len(ranking)
    main_out["rank"] = next((i + 1 for i, r in enumerate(ranking)
                             if r["city"].lower() == city.lower()), None)
    return main_out
```

- [ ] **Step 4: Add AQI to `get_city_snapshot` in `agents/tools.py`**

Import at top (after the WHO_24H constant): `from .aqi import ARCHIVE_UNITS, category as _aqi_category, overall_aqi as _overall_aqi`

In `get_city_snapshot`, just before `return json.dumps(out)`:
```python
    concs = {p: v["daily_mean"] for p, v in out["pollutants"].items()}
    try:
        aqi_val, dominant, _subs = _overall_aqi(concs, ARCHIVE_UNITS)
        out["aqi"] = aqi_val
        out["aqi_category"] = _aqi_category(aqi_val)["label"]
        out["aqi_dominant"] = dominant
        out["aqi_basis"] = "EPA-method AQI from daily averages"
    except ValueError:
        pass
```

- [ ] **Step 5: Analyst instruction line in `agents/agent.py`** — in the bullet list, extend the `get_city_snapshot` bullet:

Replace:
```
- get_city_snapshot(city) for the latest levels, trends vs WHO guidelines, anomalies
```
with:
```
- get_city_snapshot(city) for the latest levels, trends vs WHO guidelines, anomalies,
  and the EPA-method AQI with its category. Report AQI alongside WHO multiples, and
  note it is computed from daily averages — never present it as an instantaneous
  reading
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_aqi_api.py tests/ -v 2>&1 | tail -3`
Expected: full suite passes (existing tests unaffected).

- [ ] **Step 7: HTTP smoke test**

Run: `curl -s "http://localhost:8090/api/aqi?city=Delhi" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['aqi'], d['category']['label'], d['source'], d['rank'], 'of', d['of'])"`
Expected: an AQI number, a category, source live or archive (depends on key presence locally), and a rank ≤ 10.

- [ ] **Step 8: Commit and push**

```bash
git add app/main.py agents/tools.py agents/agent.py tests/test_aqi_api.py
git commit -m "feat: /api/aqi with live-or-archive source, ranking, and snapshot AQI

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 5: Hero renovation + DESIGN.md ramp

**Files:**
- Modify: `app/templates/index.html` (hero card, scale bar CSS, JS)
- Modify: `DESIGN.md` (AQI Ramp named rule + tokens)

**Interfaces:**
- Consumes: `/api/aqi` (Task 4 response shape).

- [ ] **Step 1: DESIGN.md — add to the Tertiary color section** (after the Amber Caution line):

```markdown
- **Ember** (#ffab73): AQI ramp only — the "Poor" band.
- **Magenta Signal** (#ef7ac8): AQI ramp only — the "Severe" band.
- **Oxblood** (#b04a63): AQI ramp only — the "Hazardous" band.
```

And add to Named Rules (after The Status-Plus-Label Rule):
```markdown
**The AQI Ramp.** The only sanctioned 6-step severity scale: Good=Signal OK,
Moderate=Amber Caution, Poor=Ember, Unhealthy=Alert Rose, Severe=Magenta Signal,
Hazardous=Oxblood. Ember, Magenta Signal, and Oxblood may appear ONLY inside
AQI-severity visualizations (scale bar, calendar, rankings, charts), always with the
band label present. Ultraviolet and Photon Green are not part of the ramp.
```

- [ ] **Step 2: Hero markup** — in `index.html`, replace the Air-safety-score card content (the `.eyebrow` line and `.scoreWrap` div inside the first `s6` card) with:

```html
      <div class="eyebrow">Air quality index <span class="tag" id="scoreCity">Delhi</span><span class="tag" id="aqiSource">…</span></div>
      <div class="scoreWrap">
        <div class="ring">
          <svg width="150" height="150" viewBox="0 0 150 150">
            <circle cx="75" cy="75" r="65" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="12"/>
            <circle id="ringArc" cx="75" cy="75" r="65" fill="none" stroke="#ffce80" stroke-width="12"
                    stroke-linecap="round" stroke-dasharray="408" stroke-dashoffset="408" style="transition:stroke-dashoffset 1.4s cubic-bezier(.2,.8,.2,1),stroke .4s"/>
          </svg>
          <div class="val"><b id="aqiVal">–</b><small>AQI (US EPA)</small></div>
        </div>
        <div class="liveRegion" id="scoreLive" aria-live="polite">
          <div class="verdict" id="verdict" style="color:var(--amber);border-color:var(--amber)">…</div>
          <p class="scoreTxt" id="scoreTxt">Crunching the latest readings…</p>
          <p class="scoreTxt" id="aqiMeta" style="font-size:11.5px;opacity:.8;margin-top:6px"></p>
        </div>
      </div>
      <div class="aqiScale" aria-hidden="true">
        <div class="aqiBar">
          <span style="flex:50" class="sGood"></span><span style="flex:50" class="sMod"></span><span style="flex:50" class="sPoor"></span><span style="flex:50" class="sUnh"></span><span style="flex:100" class="sSev"></span><span style="flex:199" class="sHaz"></span>
          <div class="aqiPointer" id="aqiPointer"></div>
        </div>
        <div class="aqiLabels"><span>Good</span><span>Moderate 51</span><span>Poor 101</span><span>Unhealthy 151</span><span>Severe 201</span><span>Hazardous 301+</span></div>
      </div>
```

- [ ] **Step 3: Hero CSS** — add to the `<style>` block (near the `.scoreTxt` rules):

```css
  .aqiScale{margin-top:18px}
  .aqiBar{position:relative;display:flex;height:8px;border-radius:99px;overflow:visible}
  .aqiBar span{height:100%}
  .aqiBar span:first-child{border-radius:99px 0 0 99px}
  .aqiBar span:last-child{border-radius:0 99px 99px 0}
  .sGood{background:#4fe3ac}.sMod{background:#ffce80}.sPoor{background:#ffab73}
  .sUnh{background:#ff8aa3}.sSev{background:#ef7ac8}.sHaz{background:#b04a63}
  .aqiPointer{position:absolute;top:-6px;left:0;width:0;height:0;transform:translateX(-5px);
    border-left:5px solid transparent;border-right:5px solid transparent;
    border-top:7px solid var(--txt);transition:left .8s cubic-bezier(.2,.8,.2,1)}
  .aqiLabels{display:flex;justify-content:space-between;color:var(--dim);font-size:10px;margin-top:6px;letter-spacing:.3px}
  .livePulse{display:inline-block;width:7px;height:7px;border-radius:50%;background:#4fe3ac;margin-right:5px;animation:pulse 1.6s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
```
And inside the existing `@media (prefers-reduced-motion: reduce)` block add:
```css
    .livePulse{animation:none}
    .aqiPointer{transition:none}
```

- [ ] **Step 4: Hero JS** — delete the `scoreFrom()` function entirely, and in `refresh()` replace the block that consumed it (from `const {score,worst,worstName}=scoreFrom(s.pollutants);` through the `$('scoreTxt').textContent=...` line) with a fetch of `/api/aqi`:

```javascript
    $('scoreCity').textContent=CITY;
    try{
      const a=await (await fetch(`/api/aqi?city=${CITY}`)).json();
      if(myToken!==refreshToken)return;
      if(a.aqi!==undefined){
        $('aqiVal').textContent=a.aqi;
        $('ringArc').style.strokeDashoffset=408-(408*Math.min(a.aqi,500)/500);
        $('ringArc').style.stroke=a.category.color;
        const v=$('verdict');
        v.innerHTML='<span class="vdot"></span>'+a.category.label;
        v.style.color=a.category.color;v.style.borderColor=a.category.color;
        $('scoreTxt').textContent=`Driven by ${a.dominant.toUpperCase()} — rank #${a.rank} of ${a.of} tracked cities right now.`;
        $('aqiMeta').textContent=`${a.basis} · updated ${a.last_updated}`;
        $('aqiSource').innerHTML=a.source==='live'?'<span class="livePulse"></span>LIVE':'ARCHIVE';
        $('aqiPointer').style.left=(Math.min(a.aqi,500)/500*100)+'%';
      }
    }catch(e){}
```
(The surrounding snapshot handling — KPI strip, impact, etc. — stays untouched; only the score-specific lines go.)

- [ ] **Step 5: Browser verify** — reload `http://localhost:8090/dashboard`; confirm: AQI number + category chip colored by band; scale pointer sits at the right position; badge reads LIVE (if local key present) or ARCHIVE with the daily-averages basis line; city switch moves everything; no console errors; reduced-motion kills the pulse.

- [ ] **Step 6: Commit and push**

```bash
git add app/templates/index.html DESIGN.md
git commit -m "feat: hero shows real EPA AQI with graded scale, live badge, and rank

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 6: Key to Cloud Run, deploy, live verify, README

**Files:**
- Modify: `README.md` (hero/AQI description, API table row, tech stack)
- Deploy: env var + Cloud Build + Cloud Run

- [ ] **Step 1: Set the OpenAQ key on Cloud Run without printing it**

```bash
printf 'OPENAQ_API_KEY: "%s"\n' "$(cat /tmp/openaq_key.txt)" > /tmp/openaq_env.yaml
gcloud run services update vayusense --region=us-central1 --env-vars-file=/tmp/openaq_env.yaml 2>&1 | tail -2
rm /tmp/openaq_env.yaml
```
Expected: new revision listed. (`--env-vars-file` merges with existing env vars; verify Vertex vars survived: `gcloud run services describe vayusense --region=us-central1 --format="value(spec.template.spec.containers[0].env)" | grep -c GOOGLE` → ≥2.)

- [ ] **Step 2: README updates**
  - "What it does" dashboard paragraph: replace "Air Safety Score out of 100" with "a real US EPA AQI (2024 PM2.5 table) with category band, graded scale, and a LIVE badge when powered by request-time OpenAQ data (archive-stamped fallback otherwise)".
  - API table: add `| /api/aqi?city= | GET | EPA-method AQI (live OpenAQ when fresh, archive fallback), category, per-pollutant sub-AQIs, 10-city ranking |`.
  - Tech stack Application layer: add "httpx for the request-time OpenAQ live layer (TTL-cached, graceful archive fallback)".

- [ ] **Step 3: Full test suite**

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -2`
Expected: all pass.

- [ ] **Step 4: Build + deploy**

Write `/tmp/cloudbuild.yaml` (docker build `-f deploy/Dockerfile`, image `gcr.io/gen-lang-client-0133314577/vayusense`), then:
`gcloud builds submit --config=/tmp/cloudbuild.yaml .` and
`gcloud run deploy vayusense --image=gcr.io/gen-lang-client-0133314577/vayusense --region=us-central1 --platform=managed`

- [ ] **Step 5: Live verify**

Run: `curl -s "https://vayusense-663068003180.us-central1.run.app/api/aqi?city=Delhi" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['aqi'], d['category']['label'], d['source'], d['basis'], d['rank'])"`
Expected: `source` is `live` (key present + fresh data) — if `archive`, check env var wiring before accepting. Also load the dashboard URL in the browser and confirm the hero.

- [ ] **Step 6: Commit and push**

```bash
git add README.md
git commit -m "docs: real EPA AQI hero + live OpenAQ layer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```
