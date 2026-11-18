"""Keeps the processed archive parquet fresh without a code redeploy.

benchmark/refresh_incremental.py runs nightly as a Cloud Run Job, pulls only
the new archive days since each city's last recorded date, and uploads the
updated parquet files to a GCS bucket. This module is the read side: a
TTL-gated check (see app/main.py's sync_processed_data middleware) syncs
fresh copies into data/processed/ and invalidates the in-memory caches in
agents/tools.py + app/main.py so the running web app picks them up -- no
restart required.

This is deliberately request-triggered rather than a free-running background
thread: Cloud Run only allocates CPU during request handling by default, so
a thread trying to run on its own timer between requests can stall
indefinitely. Piggybacking the (cheap, TTL-gated) check on actual traffic
guarantees it executes.

Same discipline as app/live.py and app/weather.py: this must never raise or
block the app. Any failure (no bucket configured, network error, missing
blob) just leaves whatever data is already on disk in place."""
from __future__ import annotations

import logging
import shutil
import threading
import time
from pathlib import Path

log = logging.getLogger("vayusense.data_sync")

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
FILES = ["daily_city.parquet", "station_league.parquet", "forecasts.parquet", "hourly_recent.parquet"]
TTL_SECONDS = 3 * 3600  # re-check every 3 hours; cheap even as a no-op

REQUIRED_COLUMNS = {
    "daily_city.parquet": {"city", "parameter", "date", "count", "max", "mean",
                           "roll7", "mu", "sigma", "zscore", "anomaly"},
    "station_league.parquet": {"city", "location", "value"},
    "forecasts.parquet": {"city", "parameter", "method", "date", "value", "low", "high"},
    "hourly_recent.parquet": {"city", "parameter", "hour", "value"},
}
# The archive only ever grows, so a download far smaller than what is already
# serving is a truncated or wrong upload, not a legitimate update.
MIN_ROW_FRACTION = 0.5

_last_sync = 0.0
_lock = threading.Lock()


def _validate(path: Path, fname: str, current: Path) -> None:
    """Raise if a staged parquet is unreadable, has the wrong schema, is empty,
    or is suspiciously smaller than the copy currently being served."""
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)  # raises on a truncated or corrupt footer
    missing = REQUIRED_COLUMNS[fname] - set(pf.schema_arrow.names)
    if missing:
        raise ValueError(f"{fname}: missing columns {sorted(missing)}")
    rows = pf.metadata.num_rows
    if rows == 0:
        raise ValueError(f"{fname}: file has no rows")
    # Read the last row group too: truncation damages the tail of the data
    # even in cases where the footer metadata still parses.
    pf.read_row_group(pf.num_row_groups - 1, columns=[sorted(REQUIRED_COLUMNS[fname])[0]])
    if current.exists():
        try:
            previous = pq.ParquetFile(current).metadata.num_rows
        except Exception:
            previous = 0
        if previous and rows < previous * MIN_ROW_FRACTION:
            raise ValueError(f"{fname}: {rows} rows is under {MIN_ROW_FRACTION:.0%} of the {previous} being served")


def _swap_in(fnames: list[str], staging: Path) -> bool:
    """Move validated staged files over the live ones, restoring the originals
    if any single move fails so the set is never left half-updated."""
    done, backups = [], {}
    try:
        for fname in fnames:
            dest = DATA_DIR / fname
            if dest.exists():
                backup = staging / (fname + ".bak")
                shutil.copy2(dest, backup)
                backups[fname] = backup
            (staging / fname).replace(dest)
            done.append(fname)
    except Exception:
        for fname in done:
            if fname in backups:
                backups[fname].replace(DATA_DIR / fname)
            else:
                (DATA_DIR / fname).unlink(missing_ok=True)
        raise
    return bool(done)


def _bucket_name() -> str:
    import os
    return os.environ.get("VAYUSENSE_DATA_BUCKET", "").strip()


def maybe_refresh(force: bool = False) -> bool:
    """Sync data/processed/*.parquet from GCS if the TTL has elapsed (or
    force=True). Returns True if anything actually changed on disk."""
    global _last_sync
    bucket_name = _bucket_name()
    if not bucket_name:
        return False
    now = time.time()
    if not force and now - _last_sync < TTL_SECONDS:
        return False
    if not _lock.acquire(blocking=False):
        return False  # a sync is already in progress
    try:
        _last_sync = now
        try:
            from google.cloud import storage
        except ImportError:
            log.warning("google-cloud-storage not installed; skipping GCS sync")
            return False
        staging = DATA_DIR / ".sync_staging"
        try:
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir(parents=True, exist_ok=True)
            # Stage and validate EVERYTHING first; only touch live files once
            # the whole set is known good, so a bad or partial download can
            # never leave the app on a mix of fresh and stale files.
            staged = []
            for fname in FILES:
                blob = bucket.blob(f"processed/{fname}")
                if not blob.exists():
                    continue
                tmp = staging / fname
                blob.download_to_filename(str(tmp))
                _validate(tmp, fname, DATA_DIR / fname)
                staged.append(fname)
            changed = _swap_in(staged, staging)
            if changed:
                from app import main as _main  # local import: avoid import cycle at module load
                _main.invalidate_all_caches()
                log.info("synced fresh processed data from gs://%s/processed/", bucket_name)
            return changed
        except Exception as e:
            log.warning("GCS data sync failed, keeping existing local data: %s", e)
            return False
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    finally:
        _lock.release()
