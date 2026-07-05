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
