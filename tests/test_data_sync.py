import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import io

import pandas as pd

from app import data_sync

# pandas lazily imports its Arrow extension types on the first parquet call.
# patch.dict("sys.modules") unloads anything first imported inside it, and the
# reimport then raises "pandas.period already defined". Warm it up here.
pd.DataFrame({"a": [1]}).to_parquet(io.BytesIO())
pd.read_parquet(io.BytesIO(pd.DataFrame({"a": [1]}).to_parquet()))


def _write_valid(path: Path, fname: str, rows: int = 10) -> None:
    cols = sorted(data_sync.REQUIRED_COLUMNS[fname])
    pd.DataFrame({c: list(range(rows)) for c in cols}).to_parquet(path, index=False)


def _fake_storage(payloads: dict):
    """Fake GCS client. payloads maps fname -> callable(path) that writes the
    downloaded file, or None for a blob that does not exist."""
    def _blob(name):
        fname = name.split("/")[-1]
        blob = MagicMock()
        writer = payloads.get(fname)
        blob.exists.return_value = writer is not None
        if writer is not None:
            blob.download_to_filename.side_effect = lambda p, w=writer, f=fname: w(Path(p), f)
        return blob

    bucket = MagicMock()
    bucket.blob.side_effect = _blob
    client = MagicMock()
    client.bucket.return_value = bucket
    module = MagicMock()
    module.Client.return_value = client
    return module


def _run_sync(monkeypatch, tmp_path, payloads):
    monkeypatch.setenv("VAYUSENSE_DATA_BUCKET", "fake-bucket")
    monkeypatch.setattr(data_sync, "DATA_DIR", tmp_path)
    data_sync._last_sync = 0.0
    with patch.dict("sys.modules", {"google.cloud.storage": _fake_storage(payloads)}), \
         patch("app.main.invalidate_all_caches") as fake_invalidate:
        changed = data_sync.maybe_refresh(force=True)
    return changed, fake_invalidate


def _all_valid(rows=10):
    return {f: (lambda p, fname, r=rows: _write_valid(p, fname, r)) for f in data_sync.FILES}


def test_maybe_refresh_noop_without_bucket(monkeypatch):
    monkeypatch.delenv("VAYUSENSE_DATA_BUCKET", raising=False)
    assert data_sync.maybe_refresh(force=True) is False


def test_maybe_refresh_respects_ttl(monkeypatch):
    monkeypatch.setenv("VAYUSENSE_DATA_BUCKET", "fake-bucket")
    data_sync._last_sync = time.time()
    assert data_sync.maybe_refresh(force=False) is False


def test_maybe_refresh_downloads_and_invalidates(monkeypatch, tmp_path):
    changed, fake_invalidate = _run_sync(monkeypatch, tmp_path, _all_valid())
    assert changed is True
    for fname in data_sync.FILES:
        assert len(pd.read_parquet(tmp_path / fname)) == 10
    fake_invalidate.assert_called_once()
    assert not (tmp_path / ".sync_staging").exists()


def test_maybe_refresh_survives_gcs_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("VAYUSENSE_DATA_BUCKET", "fake-bucket")
    monkeypatch.setattr(data_sync, "DATA_DIR", tmp_path)
    data_sync._last_sync = 0.0
    module = MagicMock()
    module.Client.side_effect = RuntimeError("network down")
    with patch.dict("sys.modules", {"google.cloud.storage": module}):
        assert data_sync.maybe_refresh(force=True) is False


def test_corrupt_download_is_rejected_and_nothing_is_swapped(monkeypatch, tmp_path):
    for f in data_sync.FILES:
        _write_valid(tmp_path / f, f, rows=10)
    payloads = _all_valid(rows=20)
    payloads["forecasts.parquet"] = lambda p, f: p.write_bytes(b"not a parquet file")
    changed, fake_invalidate = _run_sync(monkeypatch, tmp_path, payloads)
    assert changed is False
    fake_invalidate.assert_not_called()
    # Every file, including the ones that downloaded fine, is still the old copy.
    for f in data_sync.FILES:
        assert len(pd.read_parquet(tmp_path / f)) == 10


def test_truncated_parquet_is_rejected(monkeypatch, tmp_path):
    for f in data_sync.FILES:
        _write_valid(tmp_path / f, f, rows=10)

    def _truncated(p, f):
        _write_valid(p, f, rows=20)
        p.write_bytes(p.read_bytes()[: p.stat().st_size // 2])

    payloads = _all_valid(rows=20)
    payloads["daily_city.parquet"] = _truncated
    changed, _ = _run_sync(monkeypatch, tmp_path, payloads)
    assert changed is False
    assert len(pd.read_parquet(tmp_path / "daily_city.parquet")) == 10


def test_wrong_schema_is_rejected(monkeypatch, tmp_path):
    payloads = _all_valid()
    payloads["station_league.parquet"] = lambda p, f: pd.DataFrame({"city": [1]}).to_parquet(p)
    changed, _ = _run_sync(monkeypatch, tmp_path, payloads)
    assert changed is False
    assert not (tmp_path / "station_league.parquet").exists()


def test_empty_file_is_rejected(monkeypatch, tmp_path):
    payloads = _all_valid()
    payloads["hourly_recent.parquet"] = lambda p, f: _write_valid(p, f, rows=0)
    changed, _ = _run_sync(monkeypatch, tmp_path, payloads)
    assert changed is False


def test_download_far_smaller_than_current_is_rejected(monkeypatch, tmp_path):
    for f in data_sync.FILES:
        _write_valid(tmp_path / f, f, rows=100)
    payloads = _all_valid(rows=100)
    payloads["daily_city.parquet"] = lambda p, f: _write_valid(p, f, rows=10)
    changed, _ = _run_sync(monkeypatch, tmp_path, payloads)
    assert changed is False
    assert len(pd.read_parquet(tmp_path / "daily_city.parquet")) == 100


def test_missing_blob_is_skipped_but_others_still_sync(monkeypatch, tmp_path):
    payloads = _all_valid()
    payloads["forecasts.parquet"] = None
    changed, _ = _run_sync(monkeypatch, tmp_path, payloads)
    assert changed is True
    assert not (tmp_path / "forecasts.parquet").exists()
    assert (tmp_path / "daily_city.parquet").exists()


def test_failed_swap_rolls_back_every_file(monkeypatch, tmp_path):
    for f in data_sync.FILES:
        _write_valid(tmp_path / f, f, rows=10)
    real_replace = Path.replace
    calls = {"n": 0}

    def _flaky_replace(self, target):
        # Fail on the third file moved into place; backup restores also use
        # replace, so only count moves whose source is in the staging dir.
        if self.parent.name == ".sync_staging" and not self.name.endswith(".bak"):
            calls["n"] += 1
            if calls["n"] == 3:
                raise OSError("disk full")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", _flaky_replace)
    changed, fake_invalidate = _run_sync(monkeypatch, tmp_path, _all_valid(rows=20))
    assert changed is False
    fake_invalidate.assert_not_called()
    monkeypatch.undo()
    for f in data_sync.FILES:
        assert len(pd.read_parquet(tmp_path / f)) == 10
