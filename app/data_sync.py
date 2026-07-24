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
import threading
import time
from pathlib import Path

log = logging.getLogger("vayusense.data_sync")

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
FILES = ["daily_city.parquet", "station_league.parquet", "forecasts.parquet", "hourly_recent.parquet"]
TTL_SECONDS = 3 * 3600  # re-check every 3 hours; cheap even as a no-op

_last_sync = 0.0
_lock = threading.Lock()


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
        try:
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            changed = False
            for fname in FILES:
                blob = bucket.blob(f"processed/{fname}")
                if not blob.exists():
                    continue
                dest = DATA_DIR / fname
                tmp = dest.with_suffix(dest.suffix + ".tmp")
                blob.download_to_filename(str(tmp))
                tmp.replace(dest)
                changed = True
            if changed:
                from app import main as _main  # local import: avoid import cycle at module load
                _main.invalidate_all_caches()
                log.info("synced fresh processed data from gs://%s/processed/", bucket_name)
            return changed
        except Exception as e:
            log.warning("GCS data sync failed, keeping existing local data: %s", e)
            return False
    finally:
        _lock.release()
