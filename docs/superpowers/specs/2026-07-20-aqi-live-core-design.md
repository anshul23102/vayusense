# Phase 1: AQI Engine + Live Core — Design

**Date:** 2026-07-20
**Project:** VayuSense renovation, Phase 1 of 5 (aqi.in-inspired)
**Status:** Approved by user

## Purpose

Replace VayuSense's invented "Air Safety Score (0–100)" with a real, standards-based
US EPA AQI, add an honest live-data layer for the hero (OpenAQ v3 at request time,
archive fallback), and renovate the dashboard hero in the aqi.in style: big AQI
number, category chip, graded scale bar with pointer, LIVE/Archive badge with
last-updated stamp, and a rank-among-tracked-cities chip. This phase is the
foundation: every later phase (calendar, rankings, charts, health layer) keys off
computed AQI and its severity ramp.

## 1. AQI engine — `agents/aqi.py`

Pure functions, no I/O, shared by app and agents.

- **Breakpoints:** US EPA tables (PM2.5 uses the May-2024 updated table):
  - PM2.5 24h µg/m³: (0.0–9.0, 9.1–35.4, 35.5–55.4, 55.5–125.4, 125.5–225.4, 225.5–325.4)
  - PM10 24h µg/m³: (0–54, 55–154, 155–254, 255–354, 355–424, 425–604)
  - O3 8h ppb: (0–54, 55–70, 71–85, 86–105, 106–200) then capped band to 300+
  - CO 8h ppm: (0–4.4, 4.5–9.4, 9.5–12.4, 12.5–15.4, 15.5–30.4, 30.5–50.4)
  - SO2 1h ppb: (0–35, 36–75, 76–185, 186–304, 305–604, 605–1004)
  - NO2 1h ppb: (0–53, 54–100, 101–360, 361–649, 650–1249, 1250–2049)
  - AQI bands: (0–50, 51–100, 101–150, 151–200, 201–300, 301–500). Concentrations
    above the top breakpoint clamp to AQI 500.
- **Unit conversion:** archive stores µg/m³ for all parameters. Gases convert at
  25 °C / 1 atm: ppb = µg/m³ × 24.45 / MW, with MW NO2 46.006, SO2 64.066,
  O3 48.00, CO 28.01 (CO further to ppm). The live layer receives per-measurement
  units from OpenAQ and converts only when needed. Implementation must verify
  archive units before trusting the conversion (spot-check magnitudes).
- **API:**
  - `pollutant_aqi(parameter: str, value: float, unit: str = "ugm3") -> int | None`
    (None for unknown parameter/negative value)
  - `overall_aqi(concs: dict[str, float]) -> tuple[int, str]` — (AQI, dominant parameter)
  - `category(aqi: int) -> dict` — `{key, label, color}` with the six bands:
    Good, Moderate, Poor, Unhealthy, Severe, Hazardous
- **Honesty rule:** archive-derived AQI is computed from daily means, not EPA's
  1h/8h windows. Every surface that shows archive AQI labels it
  "EPA-method AQI from daily averages". Live AQI uses latest instantaneous
  measurements and is labeled with its measurement timestamp.

## 2. Live layer — `app/live.py` + `ingest/discover_live_locations.py`

- **One-time discovery script** (`ingest/discover_live_locations.py`): reuses the
  OpenAQ v3 discovery approach from `benchmark/expand_cities.py` to map each of the
  10 cities to up to 5 active monitoring location IDs; writes committed
  `ingest/live_locations.json` (`{city: [location_id, ...]}`). Run offline; rerun
  only if stations change.
- **Request-time fetcher** (`app/live.py`):
  - `get_live_city(city) -> dict | None` — fetches `GET /v3/locations/{id}/latest`
    for that city's location IDs (OpenAQ v3, `X-API-Key` from `OPENAQ_API_KEY` env),
    aggregates latest values per parameter (mean across stations, most recent
    timestamp), converts units, returns
    `{concs: {param: ugm3}, last_updated: iso, stations: n}`.
  - In-process TTL cache per city (45 min) so a busy dashboard costs ~13 OpenAQ
    calls/hour total, well inside free limits. Total HTTP budget per refresh ≤ 6 s;
    any failure (timeout, quota, no fresh data) → return None.
  - Uses `httpx` (add to `requirements.txt` if not already a transitive dep).
- **Fallback:** callers treat None as "use archive latest day"; the API response's
  `source` field says `"live"` or `"archive"` and the UI badge follows it. The app
  never errors because OpenAQ is down.
- **Key handling:** `OPENAQ_API_KEY` set on Cloud Run via `--env-vars-file` from the
  existing local key file; never echoed to chat, logs, or git.

## 3. API + agent changes

- New `GET /api/aqi?city=` (app/main.py) →
  ```json
  {"city": ..., "aqi": 138, "category": {"key":"poor","label":"Poor","color":"#ffab73"},
   "dominant": "pm25", "sub_aqi": {"pm25": 138, "pm10": 88, ...},
   "source": "live|archive", "last_updated": "...", "basis": "latest measurements|daily averages",
   "rank": 3, "of": 10,
   "ranking": [{"city":"Delhi","aqi":138,"category":"Poor"}, ...]}
  ```
  Ranking computes AQI for all 10 cities (live where cached/available, archive
  otherwise) and sorts descending; it powers the rank chip now and Phase 3's table later.
- `get_city_snapshot` (agents/tools.py) gains `"aqi"`, `"aqi_category"`,
  `"aqi_dominant"` (archive-based, with the daily-averages caveat in the JSON), and
  the analyst instruction gains one line: report AQI + category alongside WHO
  multiples, and never present daily-average AQI as an instantaneous reading.
- The invented 0–100 Air Safety Score is retired everywhere (UI, `scoreFrom()` JS).

## 4. Hero renovation — `app/templates/index.html`

- Ring now displays AQI (0–500 scale → stroke-dashoffset = 408 − 408×min(aqi,500)/500),
  stroke color = category color.
- Beside it: category chip (existing verdict-chip component, now category-driven),
  dominant line ("Driven by PM2.5 — 52 µg/m³"), PM2.5/PM10 sub-readings.
- **Graded scale bar**: six fixed segments (widths proportional to band spans over
  0–500) using the AQI ramp colors, with a pointer triangle positioned at
  min(aqi,500)/500 of the bar width; band labels underneath (Good 0 · Moderate 51 ·
  Poor 101 · Unhealthy 151 · Severe 201 · Hazardous 301+).
- **LIVE badge**: pulsing dot + "LIVE" when `source=="live"` (pulse disabled under
  `prefers-reduced-motion`); "ARCHIVE" tag otherwise. Next to it the last-updated
  stamp and basis text.
- **Rank chip**: "#3 most polluted of 10 tracked cities".
- Existing card layout/grid/tokens unchanged; this replaces the score card's content.

## 5. Design system — DESIGN.md

New Named Rule, **The AQI Ramp**: the only sanctioned 6-step severity scale.
- Good = Signal OK `#4fe3ac` (existing token)
- Moderate = Amber Caution `#ffce80` (existing token)
- Poor = **Ember** `#ffab73` (new)
- Unhealthy = Alert Rose `#ff8aa3` (existing token)
- Severe = **Magenta Signal** `#ef7ac8` (new)
- Hazardous = **Oxblood** `#b04a63` (new)
The three new tokens may appear ONLY inside AQI-severity visualizations (scale bar,
and later calendar/rankings/charts). Status-Plus-Label rule applies: band colors
always ship with the band label. Ultraviolet and Photon Green keep their exclusive
meanings and are NOT part of the ramp.

## 6. Testing

- `tests/test_aqi.py`: published-example checks (e.g. PM2.5 35.4 → 100, 9.0 → 50,
  55.3 → ~150 boundary math), band edges (50/51, 300/301), clamp at 500, unit
  conversions (NO2 100 µg/m³ ≈ 53 ppb → AQI ~100 boundary region), unknown
  parameter → None, overall_aqi dominant selection.
- `tests/test_live.py`: fetcher aggregates mocked OpenAQ payloads; TTL cache hit
  avoids second HTTP call; failure → None; `/api/aqi` falls back to archive with
  `source:"archive"` when live returns None (monkeypatched).
- Browser verify: hero shows AQI + scale pointer + badge; city switch updates rank;
  reduced-motion disables pulse. Then deploy → live verify → push.

## Out of scope (later phases)

Calendar, monthly/annual trends, pollutant detail cards (Phase 2); city landmark
grid + full ranking table UI (Phase 3); cigarette animation + condition tabs
(Phase 4); count-up/motion polish (Phase 5); archive top-up ingest
(`ingest/refresh_recent.py`, Phase 2).

## Success criteria

- Hero shows a real EPA-method AQI with honest basis labeling, live when OpenAQ
  answers, archive-stamped when it doesn't.
- All AQI unit tests pass, including EPA boundary examples.
- No regression in existing tests; forecast bench untouched.
- The 0–100 score no longer appears anywhere.
