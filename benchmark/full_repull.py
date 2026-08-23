"""Full archive re-pull: grow station coverage per city from the previous
MAX_LOCATIONS_PER_CITY=12 cap (extend_2026.py) up to 30, for the SAME date
window the production archive already covers (2023-12-31 through today).

This is deliberately NOT the same operation as extend_2026.py /
refresh_incremental.py, which only ever append genuinely new dates for the
same station set. Here we're adding new STATIONS whose historical readings
overlap dates that already have an aggregated row in daily_city.parquet, so
a plain "concat + drop_duplicates(keep=last)" would silently throw away the
old stations' contribution to those dates instead of combining it. Instead,
for any (city, parameter, date) that already exists, this recomputes a
count-weighted mean (sum(mean*count) / sum(count) is algebraically exact,
not an approximation) so the old and new stations' readings are properly
combined rather than one replacing the other.

Only stations that are NOT already represented in station_league.parquet
(matched by name) are pulled, so previously-counted stations are never
double counted.
"""
from __future__ import annotations

import concurrent.futures as cf
import time
from pathlib import Path

import pandas as pd
import requests

from benchmark.extend_2026 import (
    HEADERS, PARAMS, fetch_csv, list_keys, run_pipeline,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
MAX_LOCATIONS_PER_CITY = 30
YEARS = [2023, 2024, 2025, 2026]

CITY_QUERIES = {
    "Delhi":         {"coordinates": "28.6139,77.2090", "radius": 25000},
    "Mumbai":        {"coordinates": "19.0760,72.8777", "radius": 25000},
    "Kolkata":       {"coordinates": "22.5726,88.3639", "radius": 25000},
    "Chennai":       {"coordinates": "13.0827,80.2707", "radius": 25000},
    "Bengaluru":     {"coordinates": "12.9716,77.5946", "radius": 25000},
    "Hyderabad":     {"coordinates": "17.3850,78.4867", "radius": 25000},
    "Pune":          {"coordinates": "18.5204,73.8567", "radius": 25000},
    "Ahmedabad":     {"coordinates": "23.0225,72.5714", "radius": 25000},
    "Lucknow":       {"coordinates": "26.8467,80.9462", "radius": 25000},
    "Patna":         {"coordinates": "25.5941,85.1376", "radius": 25000},
    "Jaipur":        {"coordinates": "26.9124,75.7873", "radius": 25000},
    "Surat":         {"coordinates": "21.1702,72.8311", "radius": 25000},
    "Kanpur":        {"coordinates": "26.4499,80.3319", "radius": 25000},
    "Nagpur":        {"coordinates": "21.1458,79.0882", "radius": 25000},
    "Indore":        {"coordinates": "22.7196,75.8577", "radius": 25000},
    "Bhopal":        {"coordinates": "23.2599,77.4126", "radius": 25000},
    "Visakhapatnam": {"coordinates": "17.6868,83.2185", "radius": 25000},
    "Vadodara":      {"coordinates": "22.3072,73.1812", "radius": 25000},
    "Coimbatore":    {"coordinates": "11.0168,76.9558", "radius": 25000},
    "Nashik":        {"coordinates": "19.9975,73.7898", "radius": 25000},
    "Guwahati":      {"coordinates": "26.1445,91.7362", "radius": 25000},
    "Raipur":        {"coordinates": "21.2514,81.6296", "radius": 25000},
    "Faridabad":     {"coordinates": "28.4089,77.3178", "radius": 25000},
    "Baddi":         {"coordinates": "30.9578,76.7914", "radius": 25000},
    "Dhanbad":       {"coordinates": "23.7957,86.4304", "radius": 25000},
    "Kochi":         {"coordinates": "9.9312,76.2673",  "radius": 25000},
    "Imphal":        {"coordinates": "24.8170,93.9368", "radius": 25000},
    "Shillong":      {"coordinates": "25.5788,91.8933", "radius": 25000},
    "Aizawl":        {"coordinates": "23.7271,92.7176", "radius": 25000},
    "Kohima":        {"coordinates": "25.6751,94.1086", "radius": 25000},
    "Bhubaneswar":   {"coordinates": "20.2961,85.8245", "radius": 25000},
    "Ludhiana":      {"coordinates": "30.9010,75.8573", "radius": 25000},
    "Gangtok":       {"coordinates": "27.3389,88.6065", "radius": 25000},
    "Agartala":      {"coordinates": "23.8315,91.2868", "radius": 25000},
    "Dehradun":      {"coordinates": "30.3165,78.0322", "radius": 25000},
    "Itanagar":      {"coordinates": "27.0844,93.6053", "radius": 25000},
}


def discover_new_stations(known_names: dict[str, set[str]]) -> dict[int, tuple[str, str]]:
    """One /v3/locations call per city (36 total, well under the 60/min,
    2000/hour rate limit), sorted by sensor count, keeping the top
    MAX_LOCATIONS_PER_CITY -- then dropping any whose name already appears
    in station_league.parquet for that city, so already-counted stations
    are never re-pulled or double counted.

    station_league.parquet's "location" values come from the raw archive
    CSV's own location column, which is "{api name}-{sensor id}" (verified:
    the /v3/locations API returns "Anand Vihar, New Delhi - DPCC" for
    location id 235, but the archive CSV rows for that station carry
    "Anand Vihar, New Delhi - DPCC-3379575"). An exact match against
    loc["name"] would therefore never match anything already known --
    matching must check whether a known league entry STARTS WITH the API
    name instead."""
    locations = {}
    for i, (city, q) in enumerate(CITY_QUERIES.items()):
        for attempt in range(5):
            r = requests.get(
                "https://api.openaq.org/v3/locations",
                params={"coordinates": q["coordinates"], "radius": q["radius"], "limit": 100},
                headers=HEADERS, timeout=30,
            )
            if r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  429 on {city}, backing off {wait}s", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            break
        else:
            raise RuntimeError(f"Repeated 429s discovering {city}, giving up")
        results = r.json()["results"]
        results.sort(key=lambda x: len(x.get("sensors", [])), reverse=True)
        existing = known_names.get(city, set())
        added = 0
        for loc in results[:MAX_LOCATIONS_PER_CITY]:
            if any(known.startswith(loc["name"]) for known in existing):
                continue
            locations[loc["id"]] = (city, loc["name"])
            added += 1
        print(f"  {city}: {len(results)} candidates, {added} new stations to pull", flush=True)
        time.sleep(1.2)  # 36 cities well under 60/min even with prior calls this minute
    return locations


def weighted_merge_daily(daily_old: pd.DataFrame, daily_new: pd.DataFrame) -> pd.DataFrame:
    """Combine old + new station coverage for the same (city, parameter,
    date). sum(mean*count)/sum(count) across groups equals the true mean of
    all underlying readings -- exact, not an approximation -- so rows that
    exist in both are properly combined instead of one silently replacing
    the other."""
    keep_cols = ["city", "parameter", "date", "mean", "max", "count"]
    both = pd.concat([daily_old[keep_cols], daily_new[keep_cols]], ignore_index=True)
    both["weighted_sum"] = both["mean"] * both["count"]
    merged = both.groupby(["city", "parameter", "date"], as_index=False).agg(
        weighted_sum=("weighted_sum", "sum"),
        count=("count", "sum"),
        max=("max", "max"),
    )
    merged["mean"] = merged["weighted_sum"] / merged["count"]
    return merged.drop(columns="weighted_sum")


def recompute_trend(daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily.sort_values(["city", "parameter", "date"]).reset_index(drop=True)
    daily["roll7"] = (
        daily.groupby(["city", "parameter"])["mean"]
        .rolling(7, min_periods=1).mean().reset_index(drop=True)
    )
    stats = daily.groupby(["city", "parameter"])["mean"].agg(["mean", "std"]).reset_index()
    stats.columns = ["city", "parameter", "mu", "sigma"]
    daily = daily.drop(columns=[c for c in ("mu", "sigma", "zscore", "anomaly") if c in daily.columns])
    daily = daily.merge(stats, on=["city", "parameter"])
    daily["zscore"] = (daily["mean"] - daily["mu"]) / daily["sigma"]
    daily["anomaly"] = daily["zscore"].abs() > 2.0
    return daily


def main() -> None:
    league_old = pd.read_parquet(DATA_DIR / "station_league.parquet")
    known_names = league_old.groupby("city")["location"].apply(set).to_dict()

    print("=== 1) Discovering new stations (beyond the existing 185) ===", flush=True)
    locations = discover_new_stations(known_names)
    print(f"Total NEW stations to pull: {len(locations)}", flush=True)
    if not locations:
        print("No new stations found beyond what's already in the archive -- nothing to do.", flush=True)
        return

    print("\n=== 2) Listing archive files for 2023-2026 ===", flush=True)
    all_keys = []
    for lid in locations:
        for y in YEARS:
            all_keys += list_keys(f"records/csv.gz/locationid={lid}/year={y}/")
    print(f"{len(all_keys)} archive files to download", flush=True)

    print("\n=== 3) Downloading ===", flush=True)
    frames = []
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        for i, df in enumerate(ex.map(fetch_csv, all_keys)):
            if df is not None:
                frames.append(df)
            if (i + 1) % 1000 == 0:
                print(f"  {i + 1}/{len(all_keys)} ({time.perf_counter()-t0:.0f}s)", flush=True)

    if not frames:
        print("No data returned for any new station -- nothing to do.", flush=True)
        return
    raw = pd.concat(frames, ignore_index=True)
    raw = raw[raw["parameter"].isin(PARAMS)]
    lid_city = {lid: c for lid, (c, _n) in locations.items()}
    raw["city"] = raw["location_id"].map(lid_city)
    print(f"NEW RAW ROWS: {len(raw):,}", flush=True)
    raw.to_parquet("/tmp/vayusense_full_repull_raw.parquet", index=False)

    print("\n=== 4) Running pipeline on new stations ===", flush=True)
    hourly_new, daily_new, league_new = run_pipeline(raw)
    print(f"New station daily rows: {len(daily_new)}, hourly rows: {len(hourly_new)}, "
          f"league rows: {len(league_new)}", flush=True)

    print("\n=== 5) Weighted merge into existing archive ===", flush=True)
    daily_old = pd.read_parquet(DATA_DIR / "daily_city.parquet")
    daily_old["date"] = pd.to_datetime(daily_old["date"])
    hourly_old = pd.read_parquet(DATA_DIR / "hourly_recent.parquet")

    daily_merged = weighted_merge_daily(daily_old, daily_new)
    daily_merged = recompute_trend(daily_merged)

    hourly_merged = pd.concat([hourly_old, hourly_new], ignore_index=True).drop_duplicates(
        subset=["city", "parameter", "hour"], keep="last"
    )
    league_merged = (
        pd.concat([league_old, league_new], ignore_index=True)
        .groupby(["city", "location"], as_index=False)["value"].mean()
        .sort_values("value", ascending=False)
    )

    daily_merged.to_parquet(DATA_DIR / "daily_city.parquet", index=False)
    hourly_merged.to_parquet(DATA_DIR / "hourly_recent.parquet", index=False)
    league_merged.to_parquet(DATA_DIR / "station_league.parquet", index=False)

    print(f"\nFINAL: {daily_merged['city'].nunique()} cities, {len(daily_merged)} daily rows, "
          f"{league_merged.shape[0]} stations, count sum {daily_merged['count'].sum():,}", flush=True)
    print("Date range:", daily_merged["date"].min(), "to", daily_merged["date"].max(), flush=True)


if __name__ == "__main__":
    main()
