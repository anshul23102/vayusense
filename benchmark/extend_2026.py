"""Extend VayuSense's dataset through 2026 (up to today) for all 20 cities.

The archive/daily parquet stopped at 2025-12-31. This runs the identical
clean -> aggregate -> rolling trend -> anomaly pipeline used in
vayusense_gpu_benchmark.ipynb / expand_cities.py (pandas path), pulling only
the NEW year=2026 archive files for the same 20 cities, then merges the
result into the existing processed parquet files and recomputes the rolling
7-day mean + z-score/anomaly columns over the FULL (old + new) timeline per
city/parameter so the stats stay consistent across the year boundary.
"""
import concurrent.futures as cf
import gzip
import io
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests

OPENAQ_API_KEY = open("/tmp/openaq_key.txt").read().strip()
HEADERS = {"X-API-Key": OPENAQ_API_KEY}

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
}
YEARS = [2026]
MAX_LOCATIONS_PER_CITY = 12
PARAMS = {"pm25", "pm10", "no2", "o3", "so2", "co"}

S3 = "https://openaq-data-archive.s3.amazonaws.com"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


def _get_with_retry(url, params=None, timeout=30, attempts=4):
    last_exc = None
    for i in range(attempts):
        try:
            return requests.get(url, params=params, timeout=timeout)
        except requests.exceptions.RequestException as e:
            last_exc = e
            time.sleep(0.5 * (2 ** i))
    raise last_exc


def list_keys(prefix):
    keys, token = [], None
    while True:
        params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        r = _get_with_retry(S3, params=params, timeout=30)
        root = ET.fromstring(r.text)
        keys += [c.find("s3:Key", NS).text for c in root.findall("s3:Contents", NS)]
        token_el = root.find("s3:NextContinuationToken", NS)
        if token_el is None:
            break
        token = token_el.text
    return keys


def fetch_csv(key):
    try:
        r = _get_with_retry(f"{S3}/{key}", timeout=60)
        if r.status_code != 200:
            return None
        return pd.read_csv(io.BytesIO(gzip.decompress(r.content)))
    except Exception:
        return None


def run_pipeline(df):
    """Identical logic to the notebook's run_pipeline, pandas-only."""
    d = df.copy()
    d = d[(d["value"] >= 0) & (d["value"] < 2000)]
    d["ts"] = pd.to_datetime(d["datetime"], errors="coerce", utc=True)
    d = d.dropna(subset=["ts"])
    d["hour"] = d["ts"].dt.floor("h")
    d["date"] = d["ts"].dt.floor("D")
    hourly = d.groupby(["city", "parameter", "hour"], as_index=False)["value"].mean()
    daily = d.groupby(["city", "parameter", "date"], as_index=False)["value"].agg(
        ["mean", "max", "count"]
    ).reset_index()
    daily["date"] = daily["date"].dt.tz_localize(None)
    pm = d[d["parameter"] == "pm25"]
    league = (
        pm.groupby(["city", "location"], as_index=False)["value"]
        .mean().sort_values("value", ascending=False)
    )
    return hourly, daily, league


def recompute_trend(daily):
    """Rolling 7-day mean + z-score/anomaly, over the FULL city/parameter
    timeline (not just the new rows) so stats stay consistent across the
    2025/2026 boundary."""
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


def main():
    import os
    cache_path = "/tmp/vayusense_2026_raw.parquet"
    if os.path.exists(cache_path):
        print(f"=== Using cached raw download at {cache_path} ===", flush=True)
        raw = pd.read_parquet(cache_path)
        print(f"NEW RAW ROWS (2026, cached): {len(raw):,}", flush=True)
        return _finish(raw)

    print("=== 1) Discovering stations ===", flush=True)
    locations = {}
    for city, q in CITY_QUERIES.items():
        r = requests.get(
            "https://api.openaq.org/v3/locations",
            params={"coordinates": q["coordinates"], "radius": q["radius"], "limit": 100},
            headers=HEADERS, timeout=30,
        )
        r.raise_for_status()
        results = r.json()["results"]
        results.sort(key=lambda x: len(x.get("sensors", [])), reverse=True)
        n = 0
        for loc in results[:MAX_LOCATIONS_PER_CITY]:
            locations[loc["id"]] = (city, loc["name"])
            n += 1
        print(f"  {city}: {n} stations", flush=True)
    print(f"Total stations: {len(locations)}", flush=True)

    print("\n=== 2) Listing 2026 archive files ===", flush=True)
    all_keys = []
    for lid in locations:
        for y in YEARS:
            all_keys += list_keys(f"records/csv.gz/locationid={lid}/year={y}/")
    print(f"{len(all_keys)} daily archive files to download", flush=True)

    print("\n=== 3) Downloading ===", flush=True)
    frames = []
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        for i, df in enumerate(ex.map(fetch_csv, all_keys)):
            if df is not None:
                frames.append(df)
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(all_keys)} ({time.perf_counter()-t0:.0f}s)", flush=True)

    raw = pd.concat(frames, ignore_index=True)
    raw = raw[raw["parameter"].isin(PARAMS)]
    city_map = {lid: c for lid, (c, _) in locations.items()}
    raw["city"] = raw["location_id"].map(city_map)
    print(f"NEW RAW ROWS (2026): {len(raw):,}", flush=True)
    raw.to_parquet(cache_path, index=False)
    return _finish(raw)


def _finish(raw):
    print("\n=== 4) Running pipeline ===", flush=True)
    hourly_new, daily_new, league_new = run_pipeline(raw)
    print(f"New daily rows: {len(daily_new)}, hourly rows: {len(hourly_new)}, league rows: {len(league_new)}", flush=True)
    print("Cities covered in 2026 pull:", sorted(daily_new["city"].dropna().unique()), flush=True)

    print("\n=== 5) Merging with existing processed data ===", flush=True)
    daily_old = pd.read_parquet("data/processed/daily_city.parquet")
    hourly_old = pd.read_parquet("data/processed/hourly_recent.parquet")
    league_old = pd.read_parquet("data/processed/station_league.parquet")

    keep_cols = ["city", "parameter", "date", "mean", "max", "count"]
    daily_merged = pd.concat(
        [daily_old[keep_cols], daily_new[keep_cols]], ignore_index=True
    ).drop_duplicates(subset=["city", "parameter", "date"], keep="last")
    daily_merged = recompute_trend(daily_merged)

    hourly_merged = pd.concat([hourly_old, hourly_new], ignore_index=True).drop_duplicates(
        subset=["city", "parameter", "hour"], keep="last"
    )
    league_merged = pd.concat([league_old, league_new], ignore_index=True).sort_values(
        "value", ascending=False
    )

    daily_merged.to_parquet("data/processed/daily_city.parquet", index=False)
    hourly_merged.to_parquet("data/processed/hourly_recent.parquet", index=False)
    league_merged.to_parquet("data/processed/station_league.parquet", index=False)

    print(f"\nFINAL: {daily_merged['city'].nunique()} cities, {len(daily_merged)} daily rows", flush=True)
    print("Date range:", daily_merged["date"].min(), "to", daily_merged["date"].max(), flush=True)
    print("Per-city max date:", flush=True)
    print(daily_merged.groupby("city")["date"].max(), flush=True)


if __name__ == "__main__":
    main()
