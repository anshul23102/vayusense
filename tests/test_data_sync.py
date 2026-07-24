import time
from unittest.mock import MagicMock, patch

from app import data_sync


def test_maybe_refresh_noop_without_bucket(monkeypatch):
    monkeypatch.delenv("VAYUSENSE_DATA_BUCKET", raising=False)
    assert data_sync.maybe_refresh(force=True) is False


def test_maybe_refresh_respects_ttl(monkeypatch):
    monkeypatch.setenv("VAYUSENSE_DATA_BUCKET", "fake-bucket")
    data_sync._last_sync = time.time()
    assert data_sync.maybe_refresh(force=False) is False


def test_maybe_refresh_downloads_and_invalidates(monkeypatch, tmp_path):
    monkeypatch.setenv("VAYUSENSE_DATA_BUCKET", "fake-bucket")
    monkeypatch.setattr(data_sync, "DATA_DIR", tmp_path)
    data_sync._last_sync = 0.0

    def _fake_download(path):
        from pathlib import Path
        Path(path).write_bytes(b"fake parquet bytes")

    fake_blob = MagicMock()
    fake_blob.exists.return_value = True
    fake_blob.download_to_filename.side_effect = _fake_download
    fake_bucket = MagicMock()
    fake_bucket.blob.return_value = fake_blob
    fake_client = MagicMock()
    fake_client.bucket.return_value = fake_bucket

    fake_storage_module = MagicMock()
    fake_storage_module.Client.return_value = fake_client

    with patch.dict("sys.modules", {"google.cloud.storage": fake_storage_module}), \
         patch("app.main.invalidate_all_caches") as fake_invalidate:
        changed = data_sync.maybe_refresh(force=True)

    assert changed is True
    assert fake_blob.download_to_filename.call_count == len(data_sync.FILES)
    fake_invalidate.assert_called_once()


def test_maybe_refresh_survives_gcs_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("VAYUSENSE_DATA_BUCKET", "fake-bucket")
    monkeypatch.setattr(data_sync, "DATA_DIR", tmp_path)
    data_sync._last_sync = 0.0

    fake_storage_module = MagicMock()
    fake_storage_module.Client.side_effect = RuntimeError("network down")

    with patch.dict("sys.modules", {"google.cloud.storage": fake_storage_module}):
        changed = data_sync.maybe_refresh(force=True)

    assert changed is False
