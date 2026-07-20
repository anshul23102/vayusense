# The Forecast Bench — Design

**Date:** 2026-07-20
**Project:** VayuSense (Gen AI Academy APAC Cohort 2, Prototype Refinement Phase, deadline 2026-07-26)
**Status:** Approved by user

## Purpose

Replace VayuSense's single statistical forecast with a competitive, honestly-evaluated
forecasting system: four forecasting methods are backtested on identical held-out
windows of real data, the app publicly displays the scoreboard, and each forecast is
served by whichever method actually won for that city and pollutant — with its
measured historical error cited everywhere the projection appears.

Why this wins: hackathon projects add ML models; almost none add baselines,
rolling-origin backtests, and per-series model selection. This is visible ML
engineering maturity, it extends the product's "show the receipts" principle to the
models themselves, and it puts BigQuery + Vertex AI + ADK (the cohort's stated core
stack) into one architecture.

## The four forecasters

1. **Naive persistence** — forecast(t+k) = last observed daily mean. The honest
   baseline; if a method can't beat it, the scoreboard says so.
2. **Damped trend** — the existing Holt's damped-trend method (phi=0.85) on the 7-day
   rolling average, clamped to historical range (already in `agents/tools.py`).
3. **Gradient boosting** — scikit-learn `HistGradientBoostingRegressor` trained on
   engineered features per series: lags (1, 2, 3, 7, 14 days), rolling means (7, 14),
   day-of-week, day-of-year seasonality (sin/cos). Multi-step forecasts via recursive
   prediction. Trained per city×pollutant series on that series' history.
4. **BigQuery ML ARIMA_PLUS** — one `CREATE MODEL ... OPTIONS(model_type='ARIMA_PLUS',
   time_series_id_col=...)` statement training all city×pollutant series together in
   SQL. Forecasts fetched with `ML.FORECAST`, including its native prediction
   intervals.

## Evaluation: rolling-origin backtest

- For each city×pollutant series with sufficient history: hold out the final 8
  windows of 3 days each (rolling origin). For each fold, every method trains/fits
  only on data strictly before the window, forecasts into it, and is scored MAE
  against the actual observed daily means.
- All methods are scored on **identical folds**. No method sees test data.
- BigQuery ARIMA_PLUS backtesting: score ARIMA_PLUS on a single holdout (the last
  24 days, matching the union of the 8 local folds), trained once on data before the
  holdout. The scoreboard labels this explicitly ("single 24-day holdout") so it is
  never presented as fold-identical to the local methods. Rationale: bounded cost,
  bounded complexity, still honest.
- Outputs (committed artifacts, same pattern as the GPU benchmark):
  - `benchmark/forecast_bench.json` — per-series and overall MAE per method,
    fold definitions, winner per series, train timestamps.
  - `data/processed/forecasts.parquet` — each method's final 7-day forecast
    (value, low, high) per city×parameter, produced after training on full history.

## Offline pipeline

- New directory `ml/`:
  - `ml/features.py` — feature engineering for the GBT model (pure functions,
    unit-testable).
  - `ml/bench.py` — runs the full backtest + final forecasts for local methods
    (naive, damped, GBT); merges in BQ results if present; writes both artifacts.
  - `ml/bq_arima.py` — loads `daily_city.parquet` into BigQuery, trains ARIMA_PLUS,
    pulls `ML.FORECAST` + holdout scores, writes intermediate JSON for `bench.py`.
    Runs only offline, never at request time.
- Dataset is static (ends 2025-12-31), so one offline run is honest and reproducible.
- New dev-only dependency: `scikit-learn`, listed in a separate
  `ml/requirements-ml.txt`. It is NOT added to the app's `requirements.txt`; the app
  image ships precomputed artifacts only and stays slim.

## Runtime changes

- `agents/tools.py` `get_forecast(city, parameter, days)`:
  - Reads `forecasts.parquet` + `forecast_bench.json` (lru-cached like `_daily()`).
  - Serves the **winning method's** forecast rows for that series, sliced to `days`.
  - Response gains: `method` (e.g. "arima_plus"), `method_label` (human name),
    `backtest_mae`, `methods_compared` (count), and keeps the existing honest
    `methodology` caveat text, updated to describe the bench.
  - If artifacts are missing/corrupt → falls back to the existing in-process damped
    trend, labeled `"method": "damped_trend", "fallback": true`. The live demo can
    never break because of the bench.
- New endpoint `GET /api/forecast_bench?city=&parameter=` in `app/main.py` — returns
  the scoreboard rows for that series (method, MAE, winner flag) plus fold metadata.
- No runtime BigQuery calls. No new failure modes at request time.

## UI changes (`app/templates/index.html`)

- New "Forecast Bench" card beside/below the trend chart: the four methods ranked by
  backtest MAE for the selected city/pollutant, winner visually highlighted, one
  caption explaining the evaluation ("scored on N held-out windows of real data").
- The projection hover/caption now names the winning method and its MAE.
- Styling follows DESIGN.md: existing hues only, measured-vs-projected rule extended
  — the scoreboard is measured fact (solid treatment); no new colors introduced.

## Agent changes (`agents/agent.py`)

- `data_analyst_agent` instruction: when relaying a forecast, cite the method name
  and its backtest MAE (e.g. "projected by ARIMA_PLUS; historical error ±11 µg/m³ on
  held-out data"). Keep existing hedging requirements.
- `health_advisor_agent`: unchanged hedging rules; may reference the cited error.

## Cost constraints (user-facing honesty)

- BigQuery free tier: 10 GB storage, 1 TB query/month. Our table is <10 MB.
- ARIMA_PLUS training bills as bytes processed; expected total for all runs is
  effectively ₹0–₹20 against the ~₹28,000 GCP trial credit.
- Report actual billed amounts to the user after the first training run. All BQ work
  is one-time/offline — never per-visitor.

## Testing

- Unit tests (pytest, new `tests/` dir): fold-splitter produces correct,
  non-overlapping windows; MAE scoring; feature engineering shapes; winner-selection
  logic; `get_forecast` fallback path when artifacts are absent.
- HTTP tests: `/api/forecast` new fields; `/api/forecast_bench` shape.
- Playwright: scoreboard card renders, winner highlighted, chart hover names method.
- Rollout cadence (established): local verify → Cloud Run build+deploy → live verify
  → commit+push.

## Out of scope (this spec)

- The C-lite "advisory brief" page — only if time remains after this ships; separate
  spec if pursued.
- Any change to ingestion, city expansion, or the GPU benchmark story.
- Meteorological/physics-based forecasting; policy counterfactuals.

## Success criteria

- Scoreboard shows real, reproducible MAE numbers for 4 methods on identical folds.
- Every served forecast names its method and measured error, in API, UI, and agent.
- Live demo remains stable with artifacts absent (fallback verified).
- BigQuery + Vertex AI + ADK all genuinely used in the shipped architecture.
