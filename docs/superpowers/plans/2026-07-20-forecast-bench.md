# Forecast Bench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four forecasting methods (naive persistence, damped trend, gradient boosting, BigQuery ML ARIMA_PLUS) compete on held-out real data; the app serves each city×pollutant's winning method and publicly shows the scoreboard with measured error.

**Architecture:** All training/backtesting runs offline in a new `ml/` package, writing two committed artifacts (`benchmark/forecast_bench.json`, `data/processed/forecasts.parquet`). The FastAPI app and ADK agents only read artifacts; the existing in-process damped-trend forecast remains as fallback so the live demo cannot break. BigQuery work goes through the `bq` CLI (same auth as gcloud), never at request time.

**Tech Stack:** Python 3.11, pandas/pyarrow (already present), scikit-learn (dev-only), BigQuery ML ARIMA_PLUS via `bq` CLI, FastAPI, Plotly frontend, pytest.

## Global Constraints

- Working directory: `/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense` (paths below relative to it).
- GCP project: `gen-lang-client-0133314577`. BigQuery dataset name: `vayusense`.
- `scikit-learn` and `pytest` go in `ml/requirements-ml.txt` ONLY — never in `requirements.txt` (app image stays slim; app reads precomputed artifacts).
- Dataset is static (ends 2025-12-31); offline one-time training is the design, not a shortcut.
- Backtest scheme: 8 rolling-origin folds × 3-day horizon for local methods; ARIMA_PLUS scored on a single 24-day holdout and labeled as such everywhere.
- Series with < 120 daily rows are skipped by the bench; `get_forecast` falls back to in-process damped trend for them.
- UI uses existing DESIGN.md tokens only — no new colors. Winner highlight uses Ice Solid border; scoreboard is measured fact (solid treatment).
- Every commit message ends with the Co-Authored-By Claude trailer. Push after each task (blanket authorization established this session).
- Deploy cadence for the final task: local verify → Cloud Build (`/tmp/cloudbuild.yaml` pattern, Dockerfile at `deploy/Dockerfile`) → `gcloud run deploy vayusense --region=us-central1` → live verify → push.

---

### Task 1: ML package scaffolding + feature engineering

**Files:**
- Create: `ml/__init__.py` (empty)
- Create: `ml/requirements-ml.txt`
- Create: `ml/features.py`
- Test: `tests/test_features.py`

**Interfaces:**
- Produces: `make_training_frame(dates: pd.Series, values: np.ndarray) -> pd.DataFrame` (columns: `date`, `y`, all of `FEATURES`; NaN rows dropped); `next_day_features(dates: pd.Series, values: np.ndarray) -> tuple[pd.DataFrame, pd.Timestamp]` (1-row frame with `FEATURES` columns, plus the next day's date); constant `FEATURES: list[str]`.

- [ ] **Step 1: Create scaffolding and install dev deps**

`ml/requirements-ml.txt`:
```
scikit-learn>=1.4
pytest>=8
```

Run: `touch ml/__init__.py tests/__init__.py && pip3 install -r ml/requirements-ml.txt`
Expected: installs succeed (pandas/pyarrow already present).

- [ ] **Step 2: Write the failing test**

`tests/test_features.py`:
```python
import numpy as np
import pandas as pd

from ml.features import FEATURES, make_training_frame, next_day_features


def _series(n=60):
    dates = pd.Series(pd.date_range("2025-01-01", periods=n, freq="D"))
    values = np.linspace(50, 80, n) + np.sin(np.arange(n)) * 3
    return dates, values


def test_training_frame_has_features_and_no_nans():
    dates, values = _series()
    frame = make_training_frame(dates, values)
    assert set(FEATURES) <= set(frame.columns)
    assert not frame[FEATURES + ["y"]].isna().any().any()
    # longest lag is 14, so at most 14 rows are dropped
    assert len(frame) == 60 - 14


def test_lag_values_are_correct():
    dates, values = _series()
    frame = make_training_frame(dates, values)
    # for any row, lag1 must equal the previous day's y
    row = frame.iloc[5]
    prev = frame.iloc[4]
    assert row["lag1"] == prev["y"]


def test_next_day_features_shape_and_date():
    dates, values = _series()
    X, d = next_day_features(dates, values)
    assert list(X.columns) == FEATURES
    assert len(X) == 1
    assert d == dates.iloc[-1] + pd.Timedelta(days=1)
    assert float(X["lag1"].iloc[0]) == values[-1]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_features.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.features'`

- [ ] **Step 4: Implement `ml/features.py`**

```python
"""Feature engineering for the gradient-boosted forecaster."""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = [1, 2, 3, 7, 14]
ROLLS = [7, 14]
FEATURES = (
    [f"lag{l}" for l in LAGS]
    + [f"rmean{w}" for w in ROLLS]
    + ["dow_sin", "dow_cos", "doy_sin", "doy_cos"]
)


def _seasonal(dates: pd.Series) -> pd.DataFrame:
    dow = dates.dt.dayofweek
    doy = dates.dt.dayofyear
    return pd.DataFrame({
        "dow_sin": np.sin(2 * np.pi * dow / 7),
        "dow_cos": np.cos(2 * np.pi * dow / 7),
        "doy_sin": np.sin(2 * np.pi * doy / 365.25),
        "doy_cos": np.cos(2 * np.pi * doy / 365.25),
    })


def make_training_frame(dates: pd.Series, values: np.ndarray) -> pd.DataFrame:
    """One row per day with lag/rolling/seasonal features and target y."""
    dates = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    df = pd.DataFrame({"date": dates, "y": np.asarray(values, dtype=float)})
    for l in LAGS:
        df[f"lag{l}"] = df["y"].shift(l)
    for w in ROLLS:
        # shift(1) so the window only sees strictly-past values
        df[f"rmean{w}"] = df["y"].shift(1).rolling(w).mean()
    df = pd.concat([df, _seasonal(dates)], axis=1)
    return df.dropna().reset_index(drop=True)


def next_day_features(dates: pd.Series, values: np.ndarray) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Feature row for the day after the last observed date."""
    dates = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    values = np.asarray(values, dtype=float)
    d = dates.iloc[-1] + pd.Timedelta(days=1)
    row = {f"lag{l}": values[-l] for l in LAGS}
    for w in ROLLS:
        row[f"rmean{w}"] = float(np.mean(values[-w:]))
    seas = _seasonal(pd.Series([d]))
    for c in seas.columns:
        row[c] = float(seas[c].iloc[0])
    return pd.DataFrame([row])[FEATURES], d
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_features.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit and push**

```bash
git add ml/ tests/ && git commit -m "feat(ml): feature engineering for GBT forecaster

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: The three local forecasters

**Files:**
- Create: `ml/forecasters.py`
- Test: `tests/test_forecasters.py`

**Interfaces:**
- Consumes: `ml.features.make_training_frame`, `next_day_features`, `FEATURES`.
- Produces: `naive_forecast(train: pd.DataFrame, horizon: int) -> np.ndarray`, `damped_trend_forecast(train, horizon) -> np.ndarray`, `gbt_forecast(train, horizon) -> np.ndarray` — each takes a DataFrame with columns `date`, `mean`, `roll7` sorted ascending by date and returns `horizon` non-negative floats. Dict `LOCAL_FORECASTERS = {"naive": ..., "damped_trend": ..., "gbt": ...}`.

- [ ] **Step 1: Write the failing test**

`tests/test_forecasters.py`:
```python
import numpy as np
import pandas as pd

from ml.forecasters import LOCAL_FORECASTERS, damped_trend_forecast, gbt_forecast, naive_forecast


def _train(n=150, slope=0.5):
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    mean = 60 + slope * np.arange(n) + np.random.default_rng(0).normal(0, 2, n)
    df = pd.DataFrame({"date": dates, "mean": mean})
    df["roll7"] = df["mean"].rolling(7, min_periods=1).mean()
    return df


def test_naive_repeats_last_value():
    train = _train()
    out = naive_forecast(train, 3)
    assert out.shape == (3,)
    assert np.allclose(out, train["mean"].iloc[-1])


def test_damped_follows_trend_direction_and_clamps():
    train = _train(slope=0.5)
    out = damped_trend_forecast(train, 5)
    assert out.shape == (5,)
    # rising series: forecast should not fall below the last rolling value minus noise
    assert out[0] >= train["roll7"].iloc[-1] - 1
    # clamped: never exceeds 1.1x historical max
    assert out.max() <= train["mean"].max() * 1.1 + 1e-9


def test_gbt_is_deterministic_and_finite():
    train = _train()
    a = gbt_forecast(train, 4)
    b = gbt_forecast(train, 4)
    assert a.shape == (4,)
    assert np.allclose(a, b)
    assert np.all(np.isfinite(a)) and np.all(a >= 0)


def test_registry_names():
    assert set(LOCAL_FORECASTERS) == {"naive", "damped_trend", "gbt"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_forecasters.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.forecasters'`

- [ ] **Step 3: Implement `ml/forecasters.py`**

```python
"""The three locally-trained forecasters. Common signature:
forecast(train, horizon) -> np.ndarray of `horizon` values, where train is a
DataFrame with columns date/mean/roll7 sorted ascending by date."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .features import FEATURES, make_training_frame, next_day_features


def naive_forecast(train: pd.DataFrame, horizon: int) -> np.ndarray:
    return np.repeat(float(train["mean"].iloc[-1]), horizon)


def damped_trend_forecast(train: pd.DataFrame, horizon: int, phi: float = 0.85) -> np.ndarray:
    """Same math as the in-app fallback in agents/tools.py."""
    roll7 = train["roll7"].to_numpy(dtype=float)
    last = float(roll7[-1])
    slope = float(roll7[-1] - roll7[-8]) / 7.0
    hi = float(train["mean"].max()) * 1.1
    lo = max(0.0, float(train["mean"].min()) * 0.5)
    out, cum = [], 0.0
    for t in range(1, horizon + 1):
        cum += phi ** t
        out.append(min(max(last + slope * cum, lo), hi))
    return np.array(out)


def gbt_forecast(train: pd.DataFrame, horizon: int, random_state: int = 0) -> np.ndarray:
    """Gradient boosting on lag/rolling/seasonal features; recursive multi-step."""
    frame = make_training_frame(train["date"], train["mean"].to_numpy(dtype=float))
    model = HistGradientBoostingRegressor(max_iter=200, random_state=random_state)
    model.fit(frame[FEATURES], frame["y"])
    dates = pd.to_datetime(train["date"]).reset_index(drop=True)
    values = train["mean"].to_numpy(dtype=float).copy()
    preds = []
    for _ in range(horizon):
        X, d = next_day_features(dates, values)
        p = max(0.0, float(model.predict(X)[0]))
        preds.append(p)
        values = np.append(values, p)
        dates = pd.concat([dates, pd.Series([d])], ignore_index=True)
    return np.array(preds)


LOCAL_FORECASTERS = {
    "naive": naive_forecast,
    "damped_trend": damped_trend_forecast,
    "gbt": gbt_forecast,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_forecasters.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit and push**

```bash
git add ml/forecasters.py tests/test_forecasters.py && git commit -m "feat(ml): naive, damped-trend, and gradient-boosted forecasters

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 3: Rolling-origin backtest

**Files:**
- Create: `ml/backtest.py`
- Test: `tests/test_backtest.py`

**Interfaces:**
- Consumes: forecaster signature from Task 2.
- Produces: constants `MIN_HISTORY = 120`, `N_FOLDS = 8`, `HORIZON = 3`; `make_folds(n_rows: int, n_folds=N_FOLDS, horizon=HORIZON) -> list[tuple[int, int]]` (positional `[start, end)` test windows, oldest first, train = rows `[:start]`); `mae(pred, actual) -> float`; `backtest_series(series: pd.DataFrame, forecasters: dict) -> dict[str, float]` (mean MAE per method over identical folds).

- [ ] **Step 1: Write the failing test**

`tests/test_backtest.py`:
```python
import numpy as np
import pandas as pd

from ml.backtest import HORIZON, MIN_HISTORY, N_FOLDS, backtest_series, mae, make_folds


def test_folds_are_contiguous_nonoverlapping_and_cover_the_tail():
    folds = make_folds(200)
    assert len(folds) == N_FOLDS
    # oldest first, each window exactly HORIZON long, back-to-back, ending at n
    for i, (s, e) in enumerate(folds):
        assert e - s == HORIZON
        if i > 0:
            assert s == folds[i - 1][1]
    assert folds[-1][1] == 200
    assert folds[0][0] == 200 - N_FOLDS * HORIZON


def test_mae_exact():
    assert mae([1, 2, 3], [2, 2, 5]) == 1.0


def test_backtest_scores_every_method_on_identical_folds():
    n = MIN_HISTORY + 40
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    vals = 50 + 0.2 * np.arange(n)
    series = pd.DataFrame({"date": dates, "mean": vals})
    series["roll7"] = series["mean"].rolling(7, min_periods=1).mean()

    perfect = lambda train, h: np.array(
        [50 + 0.2 * (len(train) + t) for t in range(h)]
    )
    awful = lambda train, h: np.zeros(h)
    scores = backtest_series(series, {"perfect": perfect, "awful": awful})
    assert scores["perfect"] < 0.01
    assert scores["awful"] > 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_backtest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.backtest'`

- [ ] **Step 3: Implement `ml/backtest.py`**

```python
"""Rolling-origin backtest: identical held-out folds for every method."""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_HISTORY = 120   # series shorter than this are skipped by the bench
N_FOLDS = 8
HORIZON = 3         # days per fold


def make_folds(n_rows: int, n_folds: int = N_FOLDS, horizon: int = HORIZON) -> list[tuple[int, int]]:
    """Positional [start, end) test windows over the final n_folds*horizon rows,
    oldest fold first. Train set for a fold is rows [:start]."""
    folds = []
    for k in range(n_folds, 0, -1):
        end = n_rows - (k - 1) * horizon
        folds.append((end - horizon, end))
    return folds


def mae(pred, actual) -> float:
    return float(np.mean(np.abs(np.asarray(pred, dtype=float) - np.asarray(actual, dtype=float))))


def backtest_series(series: pd.DataFrame, forecasters: dict) -> dict[str, float]:
    """Mean MAE per forecaster over identical rolling-origin folds.
    `series`: columns date/mean/roll7, one city+parameter, any order."""
    series = series.sort_values("date").reset_index(drop=True)
    scores: dict[str, list[float]] = {name: [] for name in forecasters}
    for start, end in make_folds(len(series)):
        train = series.iloc[:start]
        actual = series.iloc[start:end]["mean"].to_numpy(dtype=float)
        for name, fn in forecasters.items():
            scores[name].append(mae(fn(train, end - start), actual))
    return {name: float(np.mean(v)) for name, v in scores.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_backtest.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit and push**

```bash
git add ml/backtest.py tests/test_backtest.py && git commit -m "feat(ml): rolling-origin backtest with identical folds per method

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 4: Bench runner + first real artifacts (local methods)

**Files:**
- Create: `ml/bench.py`
- Test: `tests/test_bench.py`
- Produce: `benchmark/forecast_bench.json`, `data/processed/forecasts.parquet`

**Interfaces:**
- Consumes: `LOCAL_FORECASTERS`, `backtest_series`, `MIN_HISTORY`, `N_FOLDS`, `HORIZON`.
- Produces: `run_bench(daily: pd.DataFrame, bq: dict | None) -> tuple[dict, pd.DataFrame]` and CLI `python3 -m ml.bench`. Artifact schemas:
  - `forecast_bench.json`: `{generated_at, fold_scheme: {n_folds, horizon_days, min_history_days, note}, methods: {key: label}, series: [{city, parameter, winner, mae: {method: float}}]}`
  - `forecasts.parquet` columns: `city, parameter, method, date (str YYYY-MM-DD), value, low, high` — 7 rows per method per series.
  - `bq` merge format (Task 5 produces it): `{"series": [{city, parameter, mae}], "forecasts": [rows in parquet schema with method="arima_plus"]}`.

- [ ] **Step 1: Write the failing test**

`tests/test_bench.py`:
```python
import numpy as np
import pandas as pd

from ml.bench import FINAL_HORIZON, run_bench


def _daily(n=160):
    rng = np.random.default_rng(1)
    rows = []
    for city, base in [("Testville", 80), ("Tinytown", 40)]:
        dates = pd.date_range("2025-06-01", periods=n, freq="D")
        vals = base + rng.normal(0, 5, n)
        df = pd.DataFrame({"city": city, "parameter": "pm25", "date": dates, "mean": vals})
        df["roll7"] = df["mean"].rolling(7, min_periods=1).mean()
        rows.append(df)
    # a too-short series that must be skipped
    short = rows[0].head(30).copy()
    short["city"] = "Shortville"
    return pd.concat(rows + [short], ignore_index=True)


def test_run_bench_scores_series_and_writes_winner():
    bench, forecasts = run_bench(_daily(), bq=None)
    cities = {s["city"] for s in bench["series"]}
    assert cities == {"Testville", "Tinytown"}          # Shortville skipped
    s = bench["series"][0]
    assert set(s["mae"]) == {"naive", "damped_trend", "gbt"}
    assert s["winner"] == min(s["mae"], key=s["mae"].get)
    # 3 methods x 7 days x 2 series
    assert len(forecasts) == 3 * FINAL_HORIZON * 2
    assert (forecasts["low"] <= forecasts["value"]).all()
    assert (forecasts["value"] <= forecasts["high"]).all()


def test_bq_results_are_merged():
    bq = {
        "series": [{"city": "Testville", "parameter": "pm25", "mae": 0.01}],
        "forecasts": [
            {"city": "Testville", "parameter": "pm25", "method": "arima_plus",
             "date": "2025-11-08", "value": 80.0, "low": 70.0, "high": 90.0}
        ],
    }
    bench, forecasts = run_bench(_daily(), bq=bq)
    tv = next(s for s in bench["series"] if s["city"] == "Testville")
    assert tv["mae"]["arima_plus"] == 0.01
    assert tv["winner"] == "arima_plus"                  # 0.01 beats everything
    assert (forecasts["method"] == "arima_plus").sum() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_bench.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.bench'`

- [ ] **Step 3: Implement `ml/bench.py`**

```python
"""Run the Forecast Bench: backtest local methods, merge BigQuery ARIMA_PLUS
results if ml/bq_results.json exists, pick winners, write artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import HORIZON, MIN_HISTORY, N_FOLDS, backtest_series
from .forecasters import LOCAL_FORECASTERS

ROOT = Path(__file__).resolve().parent.parent
FINAL_HORIZON = 7
METHOD_LABELS = {
    "naive": "Naive persistence",
    "damped_trend": "Damped trend",
    "gbt": "Gradient boosting",
    "arima_plus": "BigQuery ML ARIMA_PLUS",
}


def _final_forecast_rows(series: pd.DataFrame, city: str, parameter: str) -> list[dict]:
    last_date = pd.to_datetime(series["date"]).iloc[-1]
    recent = series.tail(21)
    last_roll = float(series["roll7"].iloc[-1])
    residual_std = float((recent["mean"] - recent["roll7"]).std())
    if not np.isfinite(residual_std):
        residual_std = 0.0
    residual_std = max(residual_std, last_roll * 0.05)
    rows = []
    for name, fn in LOCAL_FORECASTERS.items():
        for t, v in enumerate(fn(series, FINAL_HORIZON), start=1):
            band = residual_std * (1 + 0.25 * t)
            rows.append({
                "city": city, "parameter": parameter, "method": name,
                "date": str((last_date + pd.Timedelta(days=t)).date()),
                "value": round(float(v), 1),
                "low": round(max(0.0, float(v) - band), 1),
                "high": round(float(v) + band, 1),
            })
    return rows


def run_bench(daily: pd.DataFrame, bq: dict | None) -> tuple[dict, pd.DataFrame]:
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    series_out, forecast_rows = [], []
    for (city, parameter), grp in daily.groupby(["city", "parameter"]):
        grp = grp.sort_values("date").reset_index(drop=True)
        if len(grp) < MIN_HISTORY:
            continue
        scores = backtest_series(grp, LOCAL_FORECASTERS)
        if bq:
            match = next((s for s in bq["series"]
                          if s["city"] == city and s["parameter"] == parameter), None)
            if match:
                scores["arima_plus"] = float(match["mae"])
        series_out.append({
            "city": city, "parameter": parameter,
            "winner": min(scores, key=scores.get),
            "mae": {k: round(v, 2) for k, v in scores.items()},
        })
        forecast_rows += _final_forecast_rows(grp, city, parameter)
    if bq:
        forecast_rows += bq["forecasts"]
    bench = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fold_scheme": {
            "n_folds": N_FOLDS, "horizon_days": HORIZON, "min_history_days": MIN_HISTORY,
            "note": ("identical rolling-origin folds for naive/damped_trend/gbt; "
                     "arima_plus scored on a single 24-day holdout"),
        },
        "methods": METHOD_LABELS,
        "series": series_out,
    }
    return bench, pd.DataFrame(forecast_rows)


def main() -> None:
    daily = pd.read_parquet(ROOT / "data" / "processed" / "daily_city.parquet")
    bq_path = ROOT / "ml" / "bq_results.json"
    bq = json.loads(bq_path.read_text()) if bq_path.exists() else None
    bench, forecasts = run_bench(daily, bq)
    (ROOT / "benchmark" / "forecast_bench.json").write_text(json.dumps(bench, indent=1))
    forecasts.to_parquet(ROOT / "data" / "processed" / "forecasts.parquet", index=False)
    print(f"bench: {len(bench['series'])} series, {len(forecasts)} forecast rows, "
          f"bq={'merged' if bq else 'absent'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_bench.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the bench on the real dataset**

Run: `python3 -m ml.bench`
Expected: a line like `bench: ~40-60 series, ~840-1260 forecast rows, bq=absent` (exact counts depend on how many series clear MIN_HISTORY). Takes a few minutes (GBT trains per fold per series). Sanity-check: `python3 -c "import json;b=json.load(open('benchmark/forecast_bench.json'));print(len(b['series']),b['series'][0])"`

- [ ] **Step 6: Commit and push (code + artifacts)**

```bash
git add ml/bench.py tests/test_bench.py benchmark/forecast_bench.json data/processed/forecasts.parquet
git commit -m "feat(ml): forecast bench runner + first artifacts (local methods)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 5: BigQuery ML ARIMA_PLUS + artifact refresh

**Files:**
- Create: `ml/bq_arima.py`
- Modify: none (bench re-run refreshes both artifacts)

**Interfaces:**
- Consumes: `bq` CLI (ships with gcloud SDK, shares gcloud auth), `data/processed/daily_city.parquet`.
- Produces: `ml/bq_results.json` in the merge format Task 4 consumes: `{"series": [{"city", "parameter", "mae"}], "forecasts": [{city, parameter, method: "arima_plus", date, value, low, high}]}`.

- [ ] **Step 1: Verify bq CLI is available and authed**

Run: `bq --project_id gen-lang-client-0133314577 ls 2>&1 | head -5`
Expected: dataset list or empty (no auth error). If auth error, run `gcloud auth login` first — surface to user before proceeding.

- [ ] **Step 2: Implement `ml/bq_arima.py`**

```python
"""Train BigQuery ML ARIMA_PLUS on the daily series and export holdout scores
plus 7-day forecasts to ml/bq_results.json for ml/bench.py to merge.

Offline, one-time. Uses the `bq` CLI (same auth as gcloud); never runs at
app request time. Scored on a single 24-day holdout, labeled as such."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROJECT = "gen-lang-client-0133314577"
DATASET = "vayusense"
HOLDOUT_DAYS = 24
FINAL_HORIZON = 7
ARIMA_OPTS = ("model_type='ARIMA_PLUS', time_series_timestamp_col='date', "
              "time_series_data_col='mean', time_series_id_col=['city','parameter'], "
              "horizon=31")


def _bq(*args: str) -> str:
    res = subprocess.run(["bq", "--project_id", PROJECT, *args],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"bq {' '.join(args[:2])} failed:\n{res.stderr[:2000]}")
    return res.stdout


def _query(sql: str) -> list[dict]:
    out = _bq("query", "--use_legacy_sql=false", "--format=json",
              "--max_rows=100000", sql)
    return json.loads(out) if out.strip() else []


def main() -> None:
    daily = pd.read_parquet(ROOT / "data" / "processed" / "daily_city.parquet")
    daily = daily[["city", "parameter", "date", "mean"]].copy()
    daily["date"] = pd.to_datetime(daily["date"])
    cutoff = (daily["date"].max() - pd.Timedelta(days=HOLDOUT_DAYS)).date()

    _bq("mk", "--force", "--dataset", f"{PROJECT}:{DATASET}")
    with tempfile.NamedTemporaryFile(suffix=".parquet") as f:
        daily.to_parquet(f.name, index=False)
        _bq("load", "--replace", "--source_format=PARQUET",
            f"{DATASET}.daily_city", f.name)

    t = f"`{PROJECT}.{DATASET}"
    _query(f"CREATE OR REPLACE TABLE {t}.daily_train` AS "
           f"SELECT * FROM {t}.daily_city` WHERE date <= TIMESTAMP('{cutoff}')")
    _query(f"CREATE OR REPLACE MODEL {t}.arima_train` OPTIONS({ARIMA_OPTS}) AS "
           f"SELECT city, parameter, date, mean FROM {t}.daily_train`")
    holdout = _query(f"""
        SELECT f.city, f.parameter, AVG(ABS(f.forecast_value - a.mean)) AS mae
        FROM ML.FORECAST(MODEL {t}.arima_train`,
                         STRUCT({HOLDOUT_DAYS} AS horizon, 0.8 AS confidence_level)) f
        JOIN {t}.daily_city` a
          ON a.city = f.city AND a.parameter = f.parameter
         AND a.date = f.forecast_timestamp
        GROUP BY 1, 2""")
    _query(f"CREATE OR REPLACE MODEL {t}.arima_full` OPTIONS({ARIMA_OPTS}) AS "
           f"SELECT city, parameter, date, mean FROM {t}.daily_city`")
    fc = _query(f"""
        SELECT city, parameter,
               FORMAT_TIMESTAMP('%Y-%m-%d', forecast_timestamp) AS date,
               forecast_value AS value,
               prediction_interval_lower_bound AS low,
               prediction_interval_upper_bound AS high
        FROM ML.FORECAST(MODEL {t}.arima_full`,
                         STRUCT({FINAL_HORIZON} AS horizon, 0.8 AS confidence_level))""")

    out = {
        "series": [{"city": r["city"], "parameter": r["parameter"],
                    "mae": round(float(r["mae"]), 2)} for r in holdout],
        "forecasts": [{"city": r["city"], "parameter": r["parameter"],
                       "method": "arima_plus", "date": r["date"],
                       "value": round(float(r["value"]), 1),
                       "low": round(max(0.0, float(r["low"])), 1),
                       "high": round(float(r["high"]), 1)} for r in fc],
    }
    (ROOT / "ml" / "bq_results.json").write_text(json.dumps(out, indent=1))
    print(f"arima_plus: {len(out['series'])} series scored, "
          f"{len(out['forecasts'])} forecast rows")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it (real BigQuery, offline one-time)**

Run: `python3 -m ml.bq_arima`
Expected: `arima_plus: ~40-60 series scored, ~280-420 forecast rows`. If a series lacks enough history for ARIMA_PLUS, BigQuery drops it — that's fine, the merge is per-series.

- [ ] **Step 4: Report cost to the user**

Run: `bq --project_id gen-lang-client-0133314577 ls -j -n 10 --format=prettyjson | grep -E '"totalBytesProcessed"|"query"' | head -20`
Summarize total bytes processed in the chat (expected: low MBs → effectively ₹0). This is a user-facing honesty requirement from the spec.

- [ ] **Step 5: Re-run the bench to merge, sanity-check winners**

Run: `python3 -m ml.bench`
Expected: `... bq=merged`. Then: `python3 -c "import json;b=json.load(open('benchmark/forecast_bench.json'));import collections;print(collections.Counter(s['winner'] for s in b['series']))"` — a mix of winners (if one method wins literally everything, inspect two series by hand before trusting it).

- [ ] **Step 6: Commit and push (script + bq_results + refreshed artifacts)**

```bash
git add ml/bq_arima.py ml/bq_results.json benchmark/forecast_bench.json data/processed/forecasts.parquet
git commit -m "feat(ml): BigQuery ML ARIMA_PLUS joins the forecast bench

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 6: Serve the winner — `get_forecast` upgrade + `/api/forecast_bench`

**Files:**
- Modify: `agents/tools.py` (refactor `get_forecast`, add `get_forecast_bench`)
- Modify: `app/main.py` (new endpoint)
- Test: `tests/test_forecast_serving.py`

**Interfaces:**
- Consumes: artifacts from Tasks 4-5; existing `_daily()` loader.
- Produces: `get_forecast(city, parameter, days)` JSON gains `method`, `method_label`, `backtest_mae` (float|None), `methods_compared` (int), optional `"fallback": true`; keeps `city, parameter, last_date, last_value, forecast, methodology`. New `get_forecast_bench(city, parameter)` JSON: `{city, parameter, series: {winner, mae}, methods, fold_scheme}` or `{error}`. New route `GET /api/forecast_bench?city=&parameter=`.

- [ ] **Step 1: Write the failing test**

`tests/test_forecast_serving.py`:
```python
import json

import agents.tools as tools


def _clear_caches():
    for fn in (tools._forecasts, tools._bench):
        fn.cache_clear()


def test_get_forecast_serves_winner_with_citation():
    _clear_caches()
    out = json.loads(tools.get_forecast("Delhi", "pm25", 3))
    assert "error" not in out
    assert out["method"] in {"naive", "damped_trend", "gbt", "arima_plus"}
    assert out["method_label"]
    assert out["methods_compared"] >= 3
    assert isinstance(out["backtest_mae"], float)
    assert len(out["forecast"]) == 3
    assert "fallback" not in out


def test_get_forecast_falls_back_when_artifacts_missing(monkeypatch):
    _clear_caches()
    monkeypatch.setattr(tools, "_forecasts", lambda: (_ for _ in ()).throw(FileNotFoundError()))
    out = json.loads(tools.get_forecast("Delhi", "pm25", 3))
    assert out["method"] == "damped_trend"
    assert out["fallback"] is True
    assert len(out["forecast"]) == 3


def test_get_forecast_bench_shape():
    _clear_caches()
    out = json.loads(tools.get_forecast_bench("Delhi", "pm25"))
    assert out["series"]["winner"] in out["series"]["mae"]
    assert set(out["methods"]) >= {"naive", "damped_trend", "gbt"}
    assert out["fold_scheme"]["n_folds"] == 8


def test_get_forecast_bench_unknown_city():
    _clear_caches()
    out = json.loads(tools.get_forecast_bench("Atlantis", "pm25"))
    assert "error" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_forecast_serving.py -v`
Expected: FAIL with `AttributeError: module 'agents.tools' has no attribute '_forecasts'`

- [ ] **Step 3: Implement in `agents/tools.py`**

Add loaders after `_league()`:

```python
@lru_cache(maxsize=1)
def _forecasts() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "forecasts.parquet")


@lru_cache(maxsize=1)
def _bench() -> dict:
    path = Path(__file__).resolve().parent.parent / "benchmark" / "forecast_bench.json"
    return json.loads(path.read_text())
```

Rename the current `get_forecast` body (everything after the guard clauses) into a private helper and rebuild `get_forecast`:

```python
def _damped_fallback(city: str, parameter: str, days: int, d: pd.DataFrame) -> str:
    # ... the existing damped-trend computation, unchanged, but the returned dict
    # additionally includes: "method": "damped_trend",
    # "method_label": "Damped trend", "backtest_mae": None,
    # "methods_compared": 1, "fallback": True
    ...


def get_forecast(city: str, parameter: str, days: int = 3) -> str:
    """Project the next few days of a pollutant's daily mean. Serves whichever of
    four benchmarked methods (naive persistence, damped trend, gradient boosting,
    BigQuery ML ARIMA_PLUS) won the held-out backtest for this city+pollutant,
    and cites that method's measured historical error. A short-term statistical
    projection, NOT a meteorological forecast; accuracy degrades beyond 3-5 days.

    Args:
        city: City name, e.g. "Delhi".
        parameter: Pollutant code: pm25, pm10, no2, o3, so2, co.
        days: How many days ahead to project (default 3, max 7).
    """
    days = max(1, min(int(days), 7))
    df = _daily()
    d = df[(df["city"].str.lower() == city.lower()) & (df["parameter"] == parameter)].sort_values("date")
    if len(d) < 14:
        return json.dumps({"error": f"not enough {parameter} history for {city} to forecast"})
    try:
        bench = _bench()
        entry = next(s for s in bench["series"]
                     if s["city"].lower() == city.lower() and s["parameter"] == parameter)
        winner = entry["winner"]
        fc = _forecasts()
        rows = fc[(fc["city"].str.lower() == city.lower())
                  & (fc["parameter"] == parameter)
                  & (fc["method"] == winner)].sort_values("date").head(days)
        if rows.empty:
            raise LookupError("no forecast rows for winner")
        label = bench["methods"][winner]
        mae_val = entry["mae"][winner]
        return json.dumps({
            "city": city, "parameter": parameter,
            "last_date": str(d["date"].iloc[-1].date()),
            "last_value": round(float(d["roll7"].iloc[-1]), 1),
            "method": winner, "method_label": label,
            "backtest_mae": float(mae_val),
            "methods_compared": len(entry["mae"]),
            "forecast": [
                {"date": r.date, "value": float(r.value), "low": float(r.low), "high": float(r.high)}
                for r in rows.itertuples()
            ],
            "methodology": (
                f"Served by {label}, which beat {len(entry['mae']) - 1} competing methods "
                f"on held-out backtests of real data (MAE {mae_val} ug/m3; "
                f"{bench['fold_scheme']['note']}). A short-term statistical projection, "
                "not a meteorological forecast; reliability drops beyond 3-5 days."
            ),
        })
    except Exception:
        return _damped_fallback(city, parameter, days, d)


def get_forecast_bench(city: str, parameter: str) -> str:
    """Get the forecast-bench scoreboard for one city+pollutant: each method's
    backtest MAE on held-out data and which method currently wins (and is served).

    Args:
        city: City name, e.g. "Delhi".
        parameter: Pollutant code: pm25, pm10, no2, o3, so2, co.
    """
    try:
        bench = _bench()
        entry = next((s for s in bench["series"]
                      if s["city"].lower() == city.lower() and s["parameter"] == parameter), None)
        if entry is None:
            return json.dumps({"error": f"no bench results for {city}/{parameter}"})
        return json.dumps({
            "city": entry["city"], "parameter": parameter,
            "series": {"winner": entry["winner"], "mae": entry["mae"]},
            "methods": bench["methods"], "fold_scheme": bench["fold_scheme"],
        })
    except FileNotFoundError:
        return json.dumps({"error": "bench artifacts not generated yet"})
```

`_damped_fallback` is the existing body verbatim (slope/residual/clamp/loop/return), with the four extra keys added to the returned dict. Add `from pathlib import Path` import only if not present (it is already imported).

- [ ] **Step 4: Add the endpoint in `app/main.py`** (after the `/api/forecast` route)

```python
@app.get("/api/forecast_bench")
def forecast_bench(city: str = "Delhi", parameter: str = "pm25"):
    return json.loads(data_tools.get_forecast_bench(city, parameter))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_forecast_serving.py -v`
Expected: 4 passed

- [ ] **Step 6: HTTP smoke test against the running dev server**

Run: `curl -s "http://localhost:8090/api/forecast?city=Delhi&parameter=pm25&days=3" | python3 -m json.tool | head -20 && curl -s "http://localhost:8090/api/forecast_bench?city=Delhi&parameter=pm25" | python3 -m json.tool`
Expected: forecast response includes `method`, `method_label`, `backtest_mae`; bench response shows 4 methods' MAE. (Restart the uvicorn dev server first if it doesn't auto-reload.)

- [ ] **Step 7: Commit and push**

```bash
git add agents/tools.py app/main.py tests/test_forecast_serving.py
git commit -m "feat: serve per-series winning forecaster with cited backtest error

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 7: Scoreboard UI + agent citations

**Files:**
- Modify: `app/templates/index.html` (bench card + method-named projection)
- Modify: `agents/agent.py` (analyst instruction: cite method + error; add `get_forecast_bench` awareness via updated `get_forecast` description only — no new tool needed)

**Interfaces:**
- Consumes: `/api/forecast_bench` and upgraded `/api/forecast` from Task 6.

- [ ] **Step 1: Add the bench card markup** — in `app/templates/index.html`, directly after the trend-section `</div>` that closes the `s8`/`s4` grid row (after the NVIDIA card's closing tags), insert inside the same `.grid`:

```html
  <div class="s12 reveal">
    <div class="card" id="benchCard" style="display:none">
      <div class="eyebrow">Forecast bench <span class="tag">4 methods · held-out backtest</span><span class="tag">lower MAE is better</span></div>
      <div class="kpiStrip" id="benchGrid"></div>
      <p class="impactNote" id="benchFoldNote"></p>
    </div>
  </div>
```

- [ ] **Step 2: Populate it in `refresh()`** — after the forecast-note block (`else note.style.display='none';`) and still inside `if(t.series){`, add:

```javascript
    try{
      const fb=await (await fetch(`/api/forecast_bench?city=${CITY}&parameter=${p}`)).json();
      if(myToken!==refreshToken)return;
      const bc=$('benchCard');
      if(fb.series){
        bc.style.display='';
        const ranked=Object.entries(fb.series.mae).sort((a,b)=>a[1]-b[1]);
        $('benchGrid').innerHTML=ranked.map(([m,v],i)=>
          `<div class="kpi" style="${i===0?'border-color:rgba(157,193,255,.55)':''}">
            <div class="l">${fb.methods[m]}</div><div class="v">${v}</div>
            <div class="who ${i===0?'ok':''}">${i===0?'serving · ':''}MAE µg/m³</div></div>`).join('');
        $('benchFoldNote').textContent=`Every method scored on the same ${fb.fold_scheme.n_folds} held-out ${fb.fold_scheme.horizon_days}-day windows of real measured data (ARIMA_PLUS: single 24-day holdout). The app serves whichever method wins for this city and pollutant.`;
      }else bc.style.display='none';
    }catch(e){$('benchCard').style.display='none'}
```

- [ ] **Step 3: Name the winning method on the chart** — in the forecast-trace block, change the trace `name:'projected'` to use the method label, and extend the caption. Replace:

```javascript
          {x:fx,y:fy,name:'projected',mode:'lines',line:{color:'#ffce80',width:2,dash:'dot'},hovertemplate:'%{x}<br>%{y:.1f} µg/m³ (projected)<extra></extra>'}
```
with:
```javascript
          {x:fx,y:fy,name:`projected · ${f.method_label||'damped trend'}`,mode:'lines',line:{color:'#ffce80',width:2,dash:'dot'},hovertemplate:'%{x}<br>%{y:.1f} µg/m³ (projected)<extra></extra>'}
```
and where `forecastMethod` is set (`forecastMethod=f.methodology||'';`) it already carries the new methodology text — no further change needed there.

- [ ] **Step 4: Update the analyst instruction** — in `agents/agent.py`, replace the `get_forecast` bullet with:

```
- get_forecast(city, parameter, days) whenever the question is about tomorrow, the
  next few days, or "will it get better/worse" — this serves whichever of four
  benchmarked forecasting methods won the held-out backtest for that city and
  pollutant. Always cite the method name and its backtest error from the response
  (e.g. "projected by BigQuery ML ARIMA_PLUS; historical error ±11 µg/m³ on
  held-out data") and never state a forecast value with the same confidence as a
  measured one.
```

- [ ] **Step 5: Verify in browser** — reload `http://localhost:8090/dashboard`, confirm via the browser tools: bench card visible with 4 ranked methods, winner highlighted and marked "serving", chart legend names the method, no console errors, and switching city/pollutant updates the card (or hides it for series without bench results).

- [ ] **Step 6: Ask the agent a forecast question** — `curl -s -X POST http://localhost:8090/api/ask -H 'Content-Type: application/json' -d '{"question":"Will Delhi air get better or worse over the next 3 days?"}' | python3 -m json.tool` — Expected: answer cites the method name and hedges.

- [ ] **Step 7: Commit and push**

```bash
git add app/templates/index.html agents/agent.py
git commit -m "feat: forecast bench scoreboard UI + agent cites model and error

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 8: Docs, deploy, live verification

**Files:**
- Modify: `README.md` (forecast section rewrite, API table, architecture diagram gains BigQuery, tech stack)
- Deploy: Cloud Build + Cloud Run

- [ ] **Step 1: Update README.md**
  - "Forecast layer" section: rewrite to describe the Forecast Bench (4 methods, identical folds, per-series winner, cited MAE; ARIMA_PLUS single-holdout labeling; artifacts precomputed offline so the app has no BigQuery runtime dependency).
  - API table: add `| /api/forecast_bench?city=&parameter= | GET | Backtest scoreboard: each method's held-out MAE and the winner being served |` and update the `/api/forecast` row to mention the winning method + cited error.
  - Architecture diagram: add a BigQuery ML line under the Google Cloud layer.
  - Technology stack: add "BigQuery ML (ARIMA_PLUS time-series models trained in SQL)" under Google Cloud, and scikit-learn under a new "ML bench (offline)" bullet.

- [ ] **Step 2: Run the full test suite one last time**

Run: `python3 -m pytest tests/ -v`
Expected: all pass.

- [ ] **Step 3: Build and deploy**

Write `/tmp/cloudbuild.yaml` (docker build with `-f deploy/Dockerfile`, image `gcr.io/gen-lang-client-0133314577/vayusense`), then:
`gcloud builds submit --config=/tmp/cloudbuild.yaml .` then
`gcloud run deploy vayusense --image=gcr.io/gen-lang-client-0133314577/vayusense --region=us-central1 --platform=managed`
Expected: new revision serving 100%.

- [ ] **Step 4: Live verification**

Run: `curl -s "https://vayusense-663068003180.us-central1.run.app/api/forecast_bench?city=Delhi&parameter=pm25" | python3 -m json.tool && curl -s "https://vayusense-663068003180.us-central1.run.app/api/forecast?city=Delhi&parameter=pm25&days=3" | python3 -m json.tool | head -15`
Expected: live scoreboard + method-cited forecast identical in shape to local.

- [ ] **Step 5: Commit and push**

```bash
git add README.md && git commit -m "docs: document the Forecast Bench (4 competing models, honest backtests)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```
