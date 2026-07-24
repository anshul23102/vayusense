"""Expand VayuSense's dataset with 16 more Indian cities, one per state not
yet covered by the original 20 (Goa excluded: verified zero OpenAQ stations
anywhere in the state, via both a point search and a whole-state bbox query
-- no real data exists there to ingest, so it's honestly left out rather
than faked).

Runs the identical clean -> aggregate -> rolling trend -> anomaly pipeline
used in vayusense_gpu_benchmark.ipynb / expand_cities.py (pandas path), for
these NEW cities only, then merges the result into the existing processed
parquet files. The GPU benchmark artifacts (benchmark.png /
benchmark_results.json) are left untouched: they are the fixed, one-time
proof of the 37.5x cuDF speedup and are not regenerated here.
"""
import concurrent.futures as cf
import gzip
import io
import os
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
OPENAQ_API_KEY = os.environ["OPENAQ_API_KEY"]
HEADERS = {"X-API-Key": OPENAQ_API_KEY}

# Verified against the live OpenAQ API before committing to this list: every
# city here has at least one real pm25-capable station within 25km. Station
# counts at verification time noted alongside each (Faridabad's NCR-adjacent
# monitoring density genuinely dwarfs the rest -- not a typo).
NEW_CITY_QUERIES = {
    "Guwahati":  {"coordinates": "26.1445,91.7362", "radius": 25000},   # Assam, 8 stations
    "Raipur":    {"coordinates": "21.2514,81.6296", "radius": 25000},   # Chhattisgarh, 5
    "Faridabad": {"coordinates": "28.4089,77.3178", "radius": 25000},   # Haryana, 49
    "Baddi":     {"coordinates": "30.9578,76.7914", "radius": 25000},   # Himachal Pradesh, 4
    "Dhanbad":   {"coordinates": "23.7957,86.4304", "radius": 25000},   # Jharkhand, 2
    "Kochi":     {"coordinates": "9.9312,76.2673",  "radius": 25000},   # Kerala, 3
    "Imphal":    {"coordinates": "24.8170,93.9368", "radius": 25000},   # Manipur, 4
    "Shillong":  {"coordinates": "25.5788,91.8933", "radius": 25000},   # Meghalaya, 2
    "Aizawl":    {"coordinates": "23.7271,92.7176", "radius": 25000},   # Mizoram, 1
    "Kohima":    {"coordinates": "25.6751,94.1086", "radius": 25000},   # Nagaland, 1
    "Bhubaneswar": {"coordinates": "20.2961,85.8245", "radius": 25000}, # Odisha, 3
    "Ludhiana":  {"coordinates": "30.9010,75.8573", "radius": 25000},   # Punjab, 1
    "Gangtok":   {"coordinates": "27.3389,88.6065", "radius": 25000},   # Sikkim, 2
    "Agartala":  {"coordinates": "23.8315,91.2868", "radius": 25000},   # Tripura, 3
    "Dehradun":  {"coordinates": "30.3165,78.0322", "radius": 25000},   # Uttarakhand, 1
    "Itanagar":  {"coordinates": "27.0844,93.6053", "radius": 25000},   # Arunachal Pradesh, 1
}
YEARS = [2024, 2025, 2026]
MAX_LOCATIONS_PER_CITY = 10
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
    daily = daily.sort_values(["city", "parameter", "date"])
    daily["roll7"] = (
        daily.groupby(["city", "parameter"])["mean"]
        .rolling(7, min_periods=1).mean().reset_index(drop=True)
    )
    stats = daily.groupby(["city", "parameter"])["mean"].agg(["mean", "std"]).reset_index()
    stats.columns = ["city", "parameter", "mu", "sigma"]
    daily = daily.merge(stats, on=["city", "parameter"])
    daily["zscore"] = (daily["mean"] - daily["mu"]) / daily["sigma"]
    daily["anomaly"] = daily["zscore"].abs() > 2.0
    pm = d[d["parameter"] == "pm25"]
    league = (
        pm.groupby(["city", "location"], as_index=False)["value"]
        .mean().sort_values("value", ascending=False)
    )
    return hourly, daily, league


def main():
    print("=== 1) Discovering stations ===", flush=True)
    locations = {}
    empty_cities = []
    for city, q in NEW_CITY_QUERIES.items():
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
        if n == 0:
            empty_cities.append(city)
        print(f"  {city}: {n} stations", flush=True)
    if empty_cities:
        print(f"WARNING: no stations found for {empty_cities} -- will be absent from output, not faked", flush=True)
    print(f"Total new stations: {len(locations)}", flush=True)

    print("\n=== 2) Listing archive files ===", flush=True)
    all_keys = []
    per_city_keys = {}
    for lid, (city, _) in locations.items():
        city_keys = []
        for y in YEARS:
            city_keys += list_keys(f"records/csv.gz/locationid={lid}/year={y}/")
        per_city_keys[city] = per_city_keys.get(city, 0) + len(city_keys)
        all_keys += city_keys
    print(f"{len(all_keys)} daily archive files to download", flush=True)
    for city, n in sorted(per_city_keys.items()):
        flag = " <- NO ARCHIVE FILES" if n == 0 else ""
        print(f"  {city}: {n} files{flag}", flush=True)

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
    print(f"NEW RAW ROWS: {len(raw):,}", flush=True)
    print("Cities actually present in raw data:", sorted(raw["city"].dropna().unique()), flush=True)

    print("\n=== 4) Running pipeline ===", flush=True)
    hourly_new, daily_new, league_new = run_pipeline(raw)
    print(f"New daily rows: {len(daily_new)}, hourly rows: {len(hourly_new)}, league rows: {len(league_new)}", flush=True)

    print("\n=== 5) Merging with existing processed data ===", flush=True)
    daily_old = pd.read_parquet("data/processed/daily_city.parquet")
    hourly_old = pd.read_parquet("data/processed/hourly_recent.parquet")
    league_old = pd.read_parquet("data/processed/station_league.parquet")

    daily_merged = pd.concat([daily_old, daily_new], ignore_index=True)
    hourly_merged = pd.concat([hourly_old, hourly_new], ignore_index=True)
    league_merged = pd.concat([league_old, league_new], ignore_index=True).sort_values(
        "value", ascending=False
    )

    daily_merged.to_parquet("data/processed/daily_city.parquet", index=False)
    hourly_merged.to_parquet("data/processed/hourly_recent.parquet", index=False)
    league_merged.to_parquet("data/processed/station_league.parquet", index=False)

    print(f"\nFINAL: {daily_merged['city'].nunique()} cities, {len(daily_merged)} daily rows", flush=True)
    print("Cities:", sorted(daily_merged["city"].unique()), flush=True)


if __name__ == "__main__":
    main()
