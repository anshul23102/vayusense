from app.main import _daily_overall, calendar_api

VALID = {"good", "moderate", "poor", "unhealthy", "severe", "hazardous"}


def test_daily_overall_shape():
    days = _daily_overall("Delhi")
    assert len(days) >= 300          # Delhi archive: 2025-02-19 onward
    assert days == sorted(days, key=lambda d: d["date"])
    assert all(isinstance(d["aqi"], int) and d["aqi"] > 0 for d in days[:50])
    assert all(d["key"] in VALID for d in days[:50])


def test_calendar_year_filter():
    out = calendar_api(city="Delhi", year=2025)
    assert out["year"] == 2025
    assert len(out["days"]) >= 300
    assert all(d["date"].startswith("2025-") for d in out["days"])
    assert 2025 in out["years_available"]
    assert out["basis"] == "EPA-method daily AQI from the archive"


def test_calendar_multi_year_city():
    # Every city's archive now spans 2024, 2025, and into 2026
    out = calendar_api(city="Chennai", year=2024)
    assert {2024, 2025, 2026}.issubset(set(out["years_available"]))
    assert len(out["days"]) >= 250
    assert all(d["date"].startswith("2024-") for d in out["days"])


def test_calendar_unknown_city():
    out = calendar_api(city="Atlantis", year=2025)
    assert "error" in out
