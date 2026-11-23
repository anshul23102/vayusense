"""Refresh the processed archive from a laptop, with no cloud bucket.

benchmark/refresh_incremental.py does the same job as a nightly Cloud Run Job but
reads and writes a GCS bucket. This is the same logic for the case where there is no
bucket: it fetches only archive days newer than each city's last archived date, runs
the same pandas pipeline as the other ingestion scripts, and merges. Because every
fetched day is strictly newer than what a city already has, no existing row is
overwritten, so a plain append is exact (unlike full_repull.py, which adds stations
to days that already exist and so needs the weighted merge).

Usage (positional arguments, so there are no flags to remember):

    python -m benchmark.refresh_local Chennai /tmp/refresh_test     one city, throwaway folder
    python -m benchmark.refresh_local all                           every city, into data/processed

The second argument is the output folder. If it is omitted the real data/processed
files are replaced, after the originals are copied to a dated backup folder.
"""
from __future__ import annotations

import concurrent.futures as cf
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from benchmark.archive_config import select_stations
from benchmark.extend_2026 import (CITY_QUERIES, HEADERS, PARAMS, fetch_csv, list_keys,
                                   recompute_trend, run_pipeline)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
FILES = ["daily_city.parquet", "hourly_recent.parquet", "station_league.parquet"]
KEY_DATE_RE = re.compile(r"-(\d{8})\.csv\.gz$")


def discover(cities: list[str]) -> dict[int, tuple[str, str]]:
    """Top stations per city (same rule as the nightly job and full_repull). One call
    per city, paced and retried so the 60 requests a minute limit is never hit."""
    out = {}
    for city in cities:
        q = CITY_QUERIES[city]
        for attempt in range(5):
            r = requests.get("https://api.openaq.org/v3/locations",
                             params={"coordinates": q["coordinates"], "radius": q["radius"], "limit": 100},
                             headers=HEADERS, timeout=30)
            if r.status_code == 429:
                time.sleep(15 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        else:
            raise RuntimeError(f"repeated 429s discovering {city}")
        picked = select_stations(r.json()["results"])
        for loc in picked:
            out[loc["id"]] = (city, loc["name"])
        print(f"  {city}: {len(picked)} stations", flush=True)
        time.sleep(1.2)
    return out


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DATA_DIR
    cities = list(CITY_QUERIES) if which == "all" else [c.strip() for c in which.split(",")]
    unknown = [c for c in cities if c not in CITY_QUERIES]
    if unknown:
        raise SystemExit(f"unknown city: {unknown}")

    daily_old = pd.read_parquet(DATA_DIR / "daily_city.parquet")
    daily_old["date"] = pd.to_datetime(daily_old["date"])
    last = daily_old.groupby("city")["date"].max().dt.date.to_dict()
    print("Last archived date per city:", {c: str(last[c]) for c in cities}, flush=True)

    print("\n=== 1) Discovering stations ===", flush=True)
    stations = discover(cities)
    lid_city = {lid: c for lid, (c, _n) in stations.items()}
    print(f"Total stations: {len(stations)}", flush=True)

    print("\n=== 2) Listing archive files newer than each city's last date ===", flush=True)
    today = datetime.now(timezone.utc).date()

    def newer_keys(lid: int) -> list[str]:
        city = lid_city[lid]
        keys = []
        for y in range(last[city].year, today.year + 1):
            keys += list_keys(f"records/csv.gz/locationid={lid}/year={y}/")
        fresh = []
        for k in keys:
            m = KEY_DATE_RE.search(k)
            if m and datetime.strptime(m.group(1), "%Y%m%d").date() > last[city]:
                fresh.append(k)
        return fresh

    all_keys = []
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for ks in ex.map(newer_keys, list(stations)):
            all_keys += ks
    print(f"{len(all_keys)} new archive files to download", flush=True)
    if not all_keys:
        print("Nothing newer than the existing data: nothing to do.")
        return

    print("\n=== 3) Downloading ===", flush=True)
    frames, t0 = [], time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        for i, df in enumerate(ex.map(fetch_csv, all_keys)):
            if df is not None:
                frames.append(df)
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(all_keys)} ({time.perf_counter() - t0:.0f}s)", flush=True)
    if not frames:
        print("Every download failed or was empty: nothing to do.")
        return
    raw = pd.concat(frames, ignore_index=True)
    raw = raw[raw["parameter"].isin(PARAMS)]
    raw["city"] = raw["location_id"].map(lid_city)
    print(f"NEW RAW ROWS: {len(raw):,}", flush=True)

    print("\n=== 4) Pipeline and merge ===", flush=True)
    hourly_new, daily_new, league_new = run_pipeline(raw)
    # Safety: keep only days strictly after each city's last date, so nothing existing is touched.
    daily_new = daily_new[daily_new["date"].dt.date > daily_new["city"].map(last)]
    print(f"New daily rows: {len(daily_new)} | hourly rows: {len(hourly_new)}", flush=True)

    keep = ["city", "parameter", "date", "mean", "max", "count"]
    daily = recompute_trend(pd.concat([daily_old[keep], daily_new[keep]], ignore_index=True)
                            .drop_duplicates(subset=["city", "parameter", "date"], keep="last"))
    hourly_old = pd.read_parquet(DATA_DIR / "hourly_recent.parquet")
    hourly = pd.concat([hourly_old, hourly_new], ignore_index=True).drop_duplicates(
        subset=["city", "parameter", "hour"], keep="last")
    league_old = pd.read_parquet(DATA_DIR / "station_league.parquet")
    league = (pd.concat([league_old, league_new], ignore_index=True)
              .groupby(["city", "location"], as_index=False)["value"].mean()
              .sort_values("value", ascending=False))

    out_dir.mkdir(parents=True, exist_ok=True)
    if out_dir.resolve() == DATA_DIR.resolve():
        backup = DATA_DIR.parent / f"processed_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copytree(DATA_DIR, backup)
        print(f"Backed up the originals to {backup}", flush=True)
    daily.to_parquet(out_dir / "daily_city.parquet", index=False)
    hourly.to_parquet(out_dir / "hourly_recent.parquet", index=False)
    league.to_parquet(out_dir / "station_league.parquet", index=False)

    after = daily.groupby("city")["date"].max().dt.date
    print(f"\nWrote {out_dir}")
    for c in cities:
        print(f"  {c}: {last[c]} -> {after[c]}")
    print(f"FINAL: {daily['city'].nunique()} cities, {len(daily)} daily rows (was {len(daily_old)}), "
          f"{int(daily['count'].sum()):,} readings (was {int(daily_old['count'].sum()):,})")


if __name__ == "__main__":
    main()
