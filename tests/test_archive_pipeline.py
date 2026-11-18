"""First tests for the archive ingestion layer (benchmark/)."""
import inspect

import pandas as pd

from benchmark import archive_config, full_repull, refresh_incremental
from benchmark.full_repull import weighted_merge_daily


def _loc(i, sensors):
    return {"id": i, "name": f"s{i}", "sensors": [{}] * sensors}


def test_select_stations_caps_and_prefers_most_sensors():
    results = [_loc(i, i % 7) for i in range(100)]
    picked = archive_config.select_stations(results)
    assert len(picked) == archive_config.MAX_LOCATIONS_PER_CITY
    counts = [len(p["sensors"]) for p in picked]
    assert counts == sorted(counts, reverse=True)
    assert min(counts) >= max(len(r["sensors"]) for r in results if r not in picked)


def test_select_stations_handles_fewer_than_cap_and_missing_sensors():
    assert len(archive_config.select_stations([_loc(1, 3), {"id": 2, "name": "x"}])) == 2


def test_nightly_job_and_full_repull_share_one_station_rule():
    assert "select_stations(" in inspect.getsource(refresh_incremental._discover_locations)
    assert "select_stations(" in inspect.getsource(full_repull.discover_new_stations)
    assert "[:12]" not in inspect.getsource(refresh_incremental)


def _daily(rows):
    return pd.DataFrame(rows, columns=["city", "parameter", "date", "mean", "max", "count"])


def test_weighted_merge_combines_overlapping_dates_exactly():
    d = pd.Timestamp("2026-01-01")
    old = _daily([["Delhi", "pm25", d, 100.0, 150.0, 10]])
    new = _daily([["Delhi", "pm25", d, 40.0, 90.0, 30]])
    out = weighted_merge_daily(old, new)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["count"] == 40
    assert row["max"] == 150.0
    assert abs(row["mean"] - (100 * 10 + 40 * 30) / 40) < 1e-9


def test_weighted_merge_keeps_non_overlapping_rows_from_both_sides():
    a, b = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02")
    old = _daily([["Delhi", "pm25", a, 10.0, 12.0, 5]])
    new = _daily([["Delhi", "pm25", b, 20.0, 25.0, 7], ["Mumbai", "pm25", a, 30.0, 31.0, 2]])
    out = weighted_merge_daily(old, new)
    assert len(out) == 3
    assert set(out["city"]) == {"Delhi", "Mumbai"}
