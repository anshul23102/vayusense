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


def _ddl(sql: str) -> None:
    """CREATE/DDL statements return status text, not JSON — run and discard."""
    _bq("query", "--quiet", "--use_legacy_sql=false", sql)


def _query(sql: str) -> list[dict]:
    out = _bq("query", "--quiet", "--use_legacy_sql=false", "--format=json",
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
    _ddl(f"CREATE OR REPLACE TABLE {t}.daily_train` AS "
         f"SELECT * FROM {t}.daily_city` WHERE date <= TIMESTAMP('{cutoff}')")
    _ddl(f"CREATE OR REPLACE MODEL {t}.arima_train` OPTIONS({ARIMA_OPTS}) AS "
         f"SELECT city, parameter, date, mean FROM {t}.daily_train`")
    holdout = _query(f"""
        SELECT f.city, f.parameter, AVG(ABS(f.forecast_value - a.mean)) AS mae
        FROM ML.FORECAST(MODEL {t}.arima_train`,
                         STRUCT({HOLDOUT_DAYS} AS horizon, 0.8 AS confidence_level)) f
        JOIN {t}.daily_city` a
          ON a.city = f.city AND a.parameter = f.parameter
         AND a.date = f.forecast_timestamp
        GROUP BY 1, 2""")
    _ddl(f"CREATE OR REPLACE MODEL {t}.arima_full` OPTIONS({ARIMA_OPTS}) AS "
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
