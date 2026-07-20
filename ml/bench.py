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
