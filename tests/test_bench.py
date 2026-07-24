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


def test_bq_mae_is_merged_but_stale_forecast_rows_are_not():
    # bq["series"]' MAE is a historical backtest score -- still valid to
    # reuse regardless of when it was computed, so arima_plus can still win
    # the comparison. bq["forecasts"] rows are dated relative to whenever
    # ml/bq_arima.py last actually ran BigQuery training, though, and there's
    # no cheap way to "refresh" them the way local methods get recomputed
    # fresh on every run -- so they must NOT be merged into the served
    # output, or a stale prediction would be presented as a live one.
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
    assert (forecasts["method"] == "arima_plus").sum() == 0
