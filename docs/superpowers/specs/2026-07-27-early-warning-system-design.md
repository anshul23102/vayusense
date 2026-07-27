# Early Warning System — Design

## Why

The hackathon's own problem statement lists five required capabilities. VayuSense
already answers three of them (ingest/analyze multi-source data, natural-language
interaction, decision-support). Two are not yet addressed by any feature:

- "Generate insights, recommendations, forecasts, **or alerts**"
- "Identify patterns, trends, **and anomalies**"

The data pipeline already computes a rolling z-score and anomaly flag per
city/pollutant/day (`data/processed/daily_city.parquet`, columns `zscore`,
`anomaly`), and `agents/tools.py`'s `get_city_snapshot()` already computes
`times_who_limit` per pollutant. Both of these are currently used only
internally (anomaly flags exist to filter sensor faults; WHO multiples are
shown per-pollutant on the city page). Neither is surfaced as a first-class
"here is what needs attention right now" feature. This design does that:
turns already-correct, already-tested statistics into a new page section
that closes the two rubric gaps.

## Scope

In scope: one new backend module, one new endpoint, one new agent tool
registration, two frontend sections (dashboard + per-city), tests.

Out of scope (explicitly deferred): push notifications of any kind
(email/SMS/browser push), user-configurable thresholds, alert history/logging
over time, and any change to the advisory generator's own logic — this
feature only calls the advisory generator's existing endpoint, it does not
modify `agents/advisory.py`.

## Backend

### `agents/alerts.py` (new file, mirrors `agents/advisory.py`'s style)

```
CATEGORY_BREACH = {"poor", "unhealthy", "severe", "hazardous"}
WHO_BREACH_MULTIPLE = 2.0
ANOMALY_ZSCORE_MIN = 1.5   # only positive-direction spikes count as alerts
```

One function, `get_active_alerts() -> list[dict]`, computing across all 36
cities in a single pass (same batch-over-cities pattern as
`generate_advisory_batch()`):

For each city, using the latest date per city/parameter already available
via the existing `_daily()` frame in `agents/tools.py`:

1. **Category breach** — if the city's current overall AQI category (via
   `agents/aqi.py`'s existing `category()`) is in `CATEGORY_BREACH`, emit:
   ```json
   {"city": "Delhi", "type": "category_breach", "severity": "severe",
    "aqi": 243, "dominant": "pm25",
    "message": "Delhi's AQI is Severe (243), driven by PM2.5."}
   ```
2. **WHO breach** — for each pollutant where `times_who_limit >= 2.0`, emit:
   ```json
   {"city": "Kanpur", "type": "who_breach", "pollutant": "no2",
    "times_who": 2.4,
    "message": "Kanpur's NO2 is 2.4x the WHO 24-hour guideline."}
   ```
3. **Anomaly spike** — for each pollutant where `anomaly == True` and
   `zscore >= ANOMALY_ZSCORE_MIN` (positive only — a negative z-score is an
   unusually clean day, not a warning), emit:
   ```json
   {"city": "Delhi", "type": "anomaly", "pollutant": "so2", "zscore": 2.1,
    "message": "Delhi's SO2 spiked to 2.1 standard deviations above its
    90-day baseline."}
   ```

A city can produce zero, one, or multiple alerts across the three types.
Results are sorted worst-first: category breaches ordered by severity rank
(hazardous > severe > unhealthy > poor), then WHO breaches by descending
multiple, then anomalies by descending z-score, with category breaches
listed before the other two types for a given city.

Each alert dict also carries `"city_slug"` (lowercased city name) so the
frontend can link directly into that city's advisory generation without an
extra lookup.

### `GET /api/alerts` (new route in `app/main.py`)

Returns `{"alerts": [...], "generated_at": "<ISO timestamp>", "count": N}`.
Accepts an optional `?city=<name>` query parameter; when present, filters
the same list to that one city (case-insensitive match on `"city"`), rather
than duplicating the computation. Unknown city with the filter applied
returns `{"alerts": [], "generated_at": ..., "count": 0}`, not an error —
"no alerts for this city" and "city not found" both correctly render as an
empty/all-clear state on the frontend.

### Agent tool registration (`agents/agent.py`)

Add a thin wrapper (matching the existing `-> str` JSON-returning convention
of every other tool in `agents/tools.py`) and register it on
`data_analyst_agent`'s `tools=[...]` list, alongside the seven tools already
there. This lets "Ask VayuSense" answer questions like "any active alerts
right now?" using the same pipeline, at near-zero additional design cost.

## Frontend

### Dashboard — `app/templates/summary.html`

New section, "Active Alerts", styled consistently with the existing
dashboard sections (same `.card`/`.kicker`/`.eyebrow` conventions already in
the file). Fetches `/api/alerts` on load. Renders each alert as a row:
city name, a colored type badge (reusing the existing `RAMP` category
colors for category breaches; a distinct but harmonious color for WHO
breaches and anomalies), the message text, and a **"Generate advisory"**
button. That button calls the *existing* `/api/advisory?city=<city>`
endpoint directly — this feature adds no new advisory logic, it only adds a
convenient entry point into the one that already exists — and renders the
result using the same display pattern already built for the per-city
Advisory section (copy/download buttons included).

Empty state: "No active alerts right now. Every tracked city is within
normal bounds." Given 36 cities and real-world variance, this state will be
rare in practice but must render correctly and not look broken when it
occurs (e.g., during a genuinely clean data day).

A nav link, "Alerts", is added to `summary.html`'s existing tab bar.

### City page — `app/templates/index.html`

A smaller "Alerts for this city" widget placed near the existing "Right Now"
hero section. Fetches `/api/alerts?city=<CITY>` (reusing the page's existing
`CITY` JS variable, same pattern as every other per-city fetch already on
this page). Shows 0+ rows for just this city, same "Generate advisory"
button wiring, reusing the advisory-rendering code that already exists on
this page for its own Advisory section rather than duplicating it.

Empty state for a single city: "No active alerts for {city} right now."

A nav link, "Alerts", is added to `index.html`'s existing `.navLinks` bar,
in the same position (after "Advisory") as on the dashboard, for
consistency between the two pages' navigation order.

## Error handling

- `agents/alerts.py` follows the existing codebase convention: no
  try/except inside `get_active_alerts()` itself (data reads either succeed
  or the process has a real bug worth surfacing); the FastAPI route wraps
  it the same way `/api/advisory` already does.
- If `_daily()` has no rows for a city (shouldn't happen given the archive
  covers all 36 tracked cities, but matches the defensive pattern already
  used in `get_city_snapshot()`), that city is silently skipped rather than
  raising — one city's data gap must not break the alert feed for the other
  35.
- Frontend: a failed `/api/alerts` fetch shows the same "Something went
  wrong, try again" pattern already used elsewhere in `index.html`, not a
  silent blank section.

## Testing

- `tests/test_alerts.py` (unit, mirrors `tests/test_solutions.py`): shape of
  `get_active_alerts()`'s return value; category-breach cities are
  correctly identified against known fixture data; WHO-breach threshold
  boundary (exactly 2.0x) is inclusive; anomaly filtering excludes negative
  z-scores; sort order (severity-first) is correct.
- `tests/test_alerts_api.py` (API, mirrors `tests/test_solutions_api.py`):
  `/api/alerts` returns the expected shape; `/api/alerts?city=Delhi` filters
  correctly; an unknown city returns an empty list, not a 404 or 500.
- Full existing suite (101 tests as of this session) must continue to pass
  unmodified — this feature adds tests, it does not touch existing ones.

## Verification before calling this done

- Local server run: confirm `/api/alerts` returns real, current data (not
  an empty list) given the live archive, and that at least one alert of
  each of the three types can be found in the actual data to visually
  verify each badge/message renders correctly.
- Confirm the "Generate advisory" button on an alert row produces the same
  output as manually visiting the existing Advisory section for that city.
- Full pytest run, then deploy and verify against the live Cloud Run URL,
  matching the verification discipline used for every other change this
  session.
