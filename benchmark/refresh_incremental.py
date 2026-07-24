"""Nightly incremental archive refresh, run as a Cloud Run Job (see
deploy/nightly-refresh.md for the gcloud setup) on a Cloud Scheduler cron.

Unlike benchmark/extend_2026.py (which pulled a full year's worth of new
data once, by hand), this script is designed to run unattended every night:
it downloads the CURRENT processed parquet from GCS (the single source of
truth for the running app), finds each city's last archived date, and only
fetches the archive days newer than that -- usually zero to a handful of
files per city, since OpenAQ's archive itself lags real time by several
days. If nothing is new anywhere, it exits cleanly without touching GCS.

Reuses the exact discovery/download/pipeline logic from extend_2026.py so
the two scripts can never quietly drift into different processing rules.
"""
from __future__ import annotations

import concurrent.futures as cf
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmark.extend_2026 import (  # noqa: E402
    CITY_QUERIES, HEADERS, fetch_csv, list_keys, recompute_trend, run_pipeline,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
KEY_DATE_RE = re.compile(r"-(\d{8})\.csv\.gz$")


def _bucket_name() -> str:
    name = os.environ.get("VAYUSENSE_DATA_BUCKET", "").strip()
    if not name:
        raise SystemExit("VAYUSENSE_DATA_BUCKET is not set; refusing to run without a data bucket.")
    return name


def _download_current_parquet(bucket) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for fname in ["daily_city.parquet", "hourly_recent.parquet", "station_league.parquet"]:
        blob = bucket.blob(f"processed/{fname}")
        if blob.exists():
            blob.download_to_filename(str(DATA_DIR / fname))
            print(f"downloaded current {fname} from GCS", flush=True)
        else:
            print(f"no existing {fname} in GCS bucket yet", flush=True)


def _upload_parquet(bucket, fname: str) -> None:
    blob = bucket.blob(f"processed/{fname}")
    blob.upload_from_filename(str(DATA_DIR / fname))
    print(f"uploaded {fname} to GCS", flush=True)


def main() -> None:
    from google.cloud import storage

    bucket_name = _bucket_name()
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    print(f"=== Syncing current processed data from gs://{bucket_name}/processed/ ===", flush=True)
    _download_current_parquet(bucket)

    daily_path = DATA_DIR / "daily_city.parquet"
    if not daily_path.exists():
        raise SystemExit("no daily_city.parquet available (neither in GCS nor baked into the image)")

    daily_old = pd.read_parquet(daily_path)
    daily_old["date"] = pd.to_datetime(daily_old["date"])
    last_date_by_city = daily_old.groupby("city")["date"].max().dt.date.to_dict()

    today = datetime.now(timezone.utc).date()
    cities_needing_refresh = {
        city: last_date_by_city.get(city)
        for city in CITY_QUERIES
        if last_date_by_city.get(city) is None or last_date_by_city[city] < today - timedelta(days=1)
    }
    if not cities_needing_refresh:
        print("Every city is already up to date (within 1 day) -- nothing to do.", flush=True)
        return
    print(f"Cities needing refresh: {cities_needing_refresh}", flush=True)

    print("\n=== 1) Discovering stations for cities needing refresh ===", flush=True)
    import requests
    locations = {}
    for city in cities_needing_refresh:
        q = CITY_QUERIES[city]
        r = requests.get(
            "https://api.openaq.org/v3/locations",
            params={"coordinates": q["coordinates"], "radius": q["radius"], "limit": 100},
            headers=HEADERS, timeout=30,
        )
        r.raise_for_status()
        results = r.json()["results"]
        results.sort(key=lambda x: len(x.get("sensors", [])), reverse=True)
        for loc in results[:12]:
            locations[loc["id"]] = (city, loc["name"])
    print(f"Total stations: {len(locations)}", flush=True)

    print("\n=== 2) Listing archive files for the years that might have new days ===", flush=True)
    years_needed = sorted({last_date_by_city.get(c, today).year for c in cities_needing_refresh} | {today.year})
    all_keys = []
    for lid, (city, _name) in locations.items():
        for y in years_needed:
            all_keys += list_keys(f"records/csv.gz/locationid={lid}/year={y}/")

    # Only download files strictly newer than that city's last known date --
    # this is what keeps a nightly run cheap (usually a handful of files).
    def _is_new(key: str, city: str) -> bool:
        m = KEY_DATE_RE.search(key)
        if not m:
            return False
        file_date = datetime.strptime(m.group(1), "%Y%m%d").date()
        last = last_date_by_city.get(city)
        return last is None or file_date > last

    lid_city = {lid: c for lid, (c, _n) in locations.items()}
    new_keys = [k for k in all_keys if _is_new(k, lid_city.get(int(k.split("locationid=")[1].split("/")[0]), ""))]
    print(f"{len(new_keys)} new archive files to download (of {len(all_keys)} listed)", flush=True)
    if not new_keys:
        print("No new files past each city's last date -- nothing to do.", flush=True)
        return

    print("\n=== 3) Downloading ===", flush=True)
    frames = []
    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        for df in ex.map(fetch_csv, new_keys):
            if df is not None:
                frames.append(df)
    if not frames:
        print("All downloads failed or returned no data -- nothing to do.", flush=True)
        return

    raw = pd.concat(frames, ignore_index=True)
    raw = raw[raw["parameter"].isin({"pm25", "pm10", "no2", "o3", "so2", "co"})]
    raw["city"] = raw["location_id"].map(lid_city)
    print(f"NEW RAW ROWS: {len(raw):,}", flush=True)

    print("\n=== 4) Running pipeline ===", flush=True)
    hourly_new, daily_new, league_new = run_pipeline(raw)
    print(f"New daily rows: {len(daily_new)}", flush=True)

    print("\n=== 5) Merging ===", flush=True)
    hourly_old = pd.read_parquet(DATA_DIR / "hourly_recent.parquet")
    league_old = pd.read_parquet(DATA_DIR / "station_league.parquet")

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

    daily_merged.to_parquet(DATA_DIR / "daily_city.parquet", index=False)
    hourly_merged.to_parquet(DATA_DIR / "hourly_recent.parquet", index=False)
    league_merged.to_parquet(DATA_DIR / "station_league.parquet", index=False)

    print("\n=== 6) Uploading refreshed parquet to GCS ===", flush=True)
    _upload_parquet(bucket, "daily_city.parquet")
    _upload_parquet(bucket, "hourly_recent.parquet")
    _upload_parquet(bucket, "station_league.parquet")

    print(f"\nFINAL: {daily_merged['city'].nunique()} cities, {len(daily_merged)} daily rows", flush=True)
    print("Per-city max date:", flush=True)
    print(daily_merged.groupby("city")["date"].max(), flush=True)


if __name__ == "__main__":
    main()
