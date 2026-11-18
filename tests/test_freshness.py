import json

import pandas as pd

from ml import freshness


def _build(tmp_path, archive_latest, model_cutoff, forecast_end):
    proc = tmp_path / "data" / "processed"
    weights = tmp_path / "ml" / "model_weights"
    proc.mkdir(parents=True)
    weights.mkdir(parents=True)
    pd.DataFrame({"date": pd.to_datetime([archive_latest])}).to_parquet(proc / "daily_city.parquet")
    pd.DataFrame({"date": pd.to_datetime([forecast_end])}).to_parquet(proc / "forecasts.parquet")
    (weights / "transformer_forecaster.meta.json").write_text(json.dumps({"cutoff": model_cutoff}))
    return tmp_path


def test_fresh_model_and_forecasts_pass(tmp_path):
    root = _build(tmp_path, "2026-08-19", "2026-07-05", "2026-08-26")
    r = freshness.check(root)
    assert r["model_lag_days"] == 0
    assert not r["model_stale"] and not r["forecast_stale"]


def test_model_trained_on_an_older_archive_is_flagged(tmp_path):
    # Mirrors the real situation before the retrain: cutoff 2026-06-06 against
    # an archive that has since advanced to 2026-08-19.
    root = _build(tmp_path, "2026-08-19", "2026-06-06", "2026-08-26")
    r = freshness.check(root)
    assert r["model_lag_days"] == 29
    assert r["model_stale"]
    # A retrain that is only a few days behind is tolerated.
    root2 = _build(tmp_path / "b", "2026-08-19", "2026-06-30", "2026-08-26")
    assert not freshness.check(root2)["model_stale"]


def test_forecast_cache_that_stops_short_of_the_archive_is_flagged(tmp_path):
    root = _build(tmp_path, "2026-08-19", "2026-07-05", "2026-08-20")
    assert freshness.check(root)["forecast_stale"]
