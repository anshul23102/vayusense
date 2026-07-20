"""Data-access tools exposed to the VayuSense ADK agents.

All tools read the processed parquet produced by the GPU pipeline
(benchmark notebook) in data/processed/.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

# WHO 2021 24-hour guideline values (µg/m³ unless noted)
WHO_24H = {"pm25": 15.0, "pm10": 45.0, "no2": 25.0, "so2": 40.0, "o3": 100.0}


@lru_cache(maxsize=1)
def _daily() -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / "daily_city.parquet")
    df["date"] = pd.to_datetime(df["date"])
    return df


@lru_cache(maxsize=1)
def _league() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "station_league.parquet")


@lru_cache(maxsize=1)
def _forecasts() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "forecasts.parquet")


@lru_cache(maxsize=1)
def _bench() -> dict:
    path = Path(__file__).resolve().parent.parent / "benchmark" / "forecast_bench.json"
    return json.loads(path.read_text())


def list_cities() -> str:
    """List the cities available in the VayuSense dataset."""
    return json.dumps(sorted(_daily()["city"].dropna().unique().tolist()))


def get_city_snapshot(city: str) -> str:
    """Get the latest air-quality snapshot for a city: most recent daily mean per
    pollutant, the 7-day rolling trend, WHO guideline comparison, and anomaly flags.

    Args:
        city: City name, e.g. "Delhi".
    """
    df = _daily()
    d = df[df["city"].str.lower() == city.lower()]
    if d.empty:
        return json.dumps({"error": f"no data for city '{city}'", "available": json.loads(list_cities())})
    out = {"city": city, "pollutants": {}}
    for param, grp in d.groupby("parameter"):
        grp = grp.sort_values("date")
        last = grp.iloc[-1]
        prev7 = grp["roll7"].iloc[-8] if len(grp) >= 8 else None
        who = WHO_24H.get(param)
        out["pollutants"][param] = {
            "latest_date": str(last["date"].date()),
            "daily_mean": round(float(last["mean"]), 1),
            "rolling_7d": round(float(last["roll7"]), 1),
            "trend": ("rising" if prev7 is not None and last["roll7"] > prev7 * 1.05
                      else "falling" if prev7 is not None and last["roll7"] < prev7 * 0.95
                      else "stable"),
            "who_24h_guideline": who,
            "times_who_limit": round(float(last["mean"]) / who, 1) if who else None,
            "is_anomaly_day": bool(last["anomaly"]),
        }
    return json.dumps(out)


def get_trend(city: str, parameter: str, days: int = 30) -> str:
    """Get recent daily values + 7-day rolling average for one pollutant in a city.

    Args:
        city: City name, e.g. "Delhi".
        parameter: Pollutant code: pm25, pm10, no2, o3, so2, co.
        days: Number of trailing days to return (default 30).
    """
    df = _daily()
    d = df[(df["city"].str.lower() == city.lower()) & (df["parameter"] == parameter)].sort_values("date").tail(days)
    if d.empty:
        return json.dumps({"error": f"no {parameter} data for {city}"})
    series = [
        {"date": str(row["date"].date()), "mean": round(float(row["mean"]), 1),
         "roll7": round(float(row["roll7"]), 1)}
        for _, row in d.iterrows()
    ]
    return json.dumps({"city": city, "parameter": parameter, "series": series})


def _damped_fallback(city: str, parameter: str, days: int, d: pd.DataFrame) -> str:
    """In-process damped-trend projection: the zero-dependency fallback used when
    the precomputed Forecast Bench artifacts are unavailable for this series."""
    roll7 = d["roll7"].to_numpy()
    last_date = d["date"].iloc[-1]
    last_value = float(roll7[-1])

    # Weekly trend: average daily change over the last 7 days (smoother than day-over-day noise).
    slope = float(roll7[-1] - roll7[-8]) / 7.0

    # Recent daily noise around the rolling average, for an honest uncertainty band.
    recent = d.tail(21)
    residual_std = float((recent["mean"] - recent["roll7"]).std()) if len(recent) >= 7 else last_value * 0.15
    residual_std = max(residual_std, last_value * 0.05)

    # Historical bounds for this city+parameter, so the projection can't run away.
    hist_max = float(d["mean"].max())
    hist_min = float(d["mean"].min())
    clamp_hi = hist_max * 1.1
    clamp_lo = max(0.0, hist_min * 0.5)

    phi = 0.85  # damping factor: each further day trusts the trend less
    forecast = []
    cumulative_phi = 0.0
    for t in range(1, days + 1):
        cumulative_phi += phi ** t
        projected = last_value + slope * cumulative_phi
        projected = min(max(projected, clamp_lo), clamp_hi)
        band = residual_std * (1 + 0.25 * t)  # widen the band a little further out
        forecast.append({
            "date": str((last_date + pd.Timedelta(days=t)).date()),
            "value": round(projected, 1),
            "low": round(max(0.0, projected - band), 1),
            "high": round(projected + band, 1),
        })

    return json.dumps({
        "city": city,
        "parameter": parameter,
        "last_date": str(last_date.date()),
        "last_value": round(last_value, 1),
        "trend_per_day": round(slope, 2),
        "method": "damped_trend",
        "method_label": "Damped trend",
        "backtest_mae": None,
        "methods_compared": 1,
        "fallback": True,
        "forecast": forecast,
        "methodology": (
            "Damped-trend statistical projection (Holt's damped trend, phi=0.85) applied to "
            "the 7-day rolling average, clamped to the city's historical range. This is a "
            "short-term illustrative projection based on recent trend only, not a "
            "meteorological forecast, and grows less reliable beyond 3-5 days."
        ),
    })


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


def get_worst_stations(city: str, top_n: int = 5) -> str:
    """Get the stations with the highest average PM2.5 in a city (pollution hotspots).

    Args:
        city: City name.
        top_n: How many stations to return.
    """
    lg = _league()
    d = lg[lg["city"].str.lower() == city.lower()].head(top_n)
    if d.empty:
        return json.dumps({"error": f"no station data for {city}"})
    return json.dumps([{"station": r.location, "avg_pm25": round(float(r.value), 1)} for r in d.itertuples()])


def get_human_impact(city: str) -> str:
    """Translate a city's annual average PM2.5 into two plain-human-stakes metrics that
    go beyond a raw AQI number: (1) the equivalent daily cigarette exposure (Berkeley
    Earth methodology: sustained 22 ug/m3 of PM2.5 for 24h ~= smoking 1 cigarette), and
    (2) an illustrative life-expectancy impact using an AQLI-style coefficient (~0.98
    years of life expectancy lost per 10 ug/m3 of PM2.5 sustained above the WHO annual
    guideline of 5 ug/m3, based on published air-quality epidemiology). This is an
    ESTIMATE for decision-support/awareness, not a medical or actuarial diagnosis.

    Args:
        city: City name, e.g. "Delhi".
    """
    df = _daily()
    d = df[(df["city"].str.lower() == city.lower()) & (df["parameter"] == "pm25")]
    if d.empty:
        return json.dumps({"error": f"no PM2.5 data for {city}"})
    annual_avg = float(d["mean"].mean())
    who_annual = 5.0  # WHO 2021 annual PM2.5 guideline (ug/m3)
    cigarettes_per_day = round(annual_avg / 22.0, 1)
    excess = max(0.0, annual_avg - who_annual)
    years_lost = round((excess / 10.0) * 0.98, 2)
    return json.dumps({
        "city": city,
        "annual_avg_pm25": round(annual_avg, 1),
        "who_annual_guideline": who_annual,
        "cigarettes_per_day_equivalent": cigarettes_per_day,
        "cigarettes_per_year_equivalent": round(cigarettes_per_day * 365, 0),
        "estimated_life_expectancy_years_lost": years_lost,
        "methodology": (
            "Cigarette-equivalence: Berkeley Earth (22 ug/m3 sustained PM2.5 ~ 1 cigarette/day). "
            "Life-expectancy impact: AQLI-style coefficient (~0.98 years per 10 ug/m3 of PM2.5 "
            "sustained above the WHO annual guideline of 5 ug/m3). Illustrative estimate, not a "
            "medical or actuarial diagnosis."
        ),
    })
