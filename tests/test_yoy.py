import json

from agents.tools import get_year_over_year
from app.main import yoy, yoy_ranking


def test_get_year_over_year_shape():
    out = json.loads(get_year_over_year("Delhi", 7))
    assert "error" not in out
    assert out["city"] == "Delhi"
    assert out["window_days"] == 7
    assert out["current_period"]["avg_aqi"] > 0
    assert out["same_period_last_year"]["avg_aqi"] > 0
    assert out["verdict"] in {"worse", "better", "about the same"}
    expect = round(
        (out["current_period"]["avg_aqi"] - out["same_period_last_year"]["avg_aqi"])
        / out["same_period_last_year"]["avg_aqi"] * 100, 1
    )
    assert out["pct_change"] == expect


def test_get_year_over_year_unknown_city():
    out = json.loads(get_year_over_year("Atlantis", 7))
    assert "error" in out


def test_window_days_clamped():
    out = json.loads(get_year_over_year("Delhi", 999))
    assert out["window_days"] == 30


def test_yoy_api():
    out = yoy(city="Mumbai", window=7)
    assert out["city"] == "Mumbai"
    assert "pct_change" in out


def test_yoy_ranking_api():
    out = yoy_ranking(window=7)
    assert out["cities_compared"] >= 15
    assert len(out["most_improved"]) <= 5
    assert len(out["most_worsened"]) <= 5
    # most improved should be the most negative pct_change (best case)
    if out["most_improved"] and out["most_worsened"]:
        assert out["most_improved"][0]["pct_change"] <= out["most_worsened"][-1]["pct_change"]
