from app.main import _daily_overall, monthly_api


def test_monthly_shape_and_math():
    out = monthly_api(city="Delhi")
    months = out["months"]
    assert months == sorted(months, key=lambda m: m["month"])
    assert len(months) >= 10                      # Delhi: Feb-Dec 2025
    # spot-check one month's average against the daily data
    days = _daily_overall("Delhi")
    m0 = months[0]["month"]
    vals = [d["aqi"] for d in days if d["date"].startswith(m0)]
    assert months[0]["avg_aqi"] == round(sum(vals) / len(vals))
    # extremes are true extremes
    avgs = {m["month"]: m["avg_aqi"] for m in months}
    assert out["most_polluted"]["avg_aqi"] == max(avgs.values())
    assert out["least_polluted"]["avg_aqi"] == min(avgs.values())


def test_annual_change_multi_year_city():
    # Every city now spans 2024, 2025, and into 2026, so annual change is computable
    out = monthly_api(city="Chennai")
    a = out["annual"]
    assert len(a) >= 2
    expect = round((a[-1]["avg_aqi"] - a[0]["avg_aqi"]) / a[0]["avg_aqi"] * 100, 1)
    assert out["annual_change_pct"] == expect


def test_delhi_also_spans_multiple_years():
    out = monthly_api(city="Delhi")
    assert len(out["annual"]) >= 2


def test_monthly_unknown_city():
    assert "error" in monthly_api(city="Atlantis")
