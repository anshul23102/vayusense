from app.main import alerts_api


def test_alerts_api_shape():
    out = alerts_api()
    assert "alerts" in out and "count" in out and "generated_at" in out
    assert out["count"] == len(out["alerts"])


def test_alerts_api_city_filter():
    all_alerts = alerts_api()
    some_city = all_alerts["alerts"][0]["city"]
    filtered = alerts_api(city=some_city)
    assert filtered["count"] >= 1
    assert all(a["city"] == some_city for a in filtered["alerts"])


def test_alerts_api_city_filter_case_insensitive():
    all_alerts = alerts_api()
    some_city = all_alerts["alerts"][0]["city"]
    filtered = alerts_api(city=some_city.upper())
    assert filtered["count"] >= 1


def test_alerts_api_unknown_city_returns_empty_not_error():
    out = alerts_api(city="Not A Real City")
    assert out["count"] == 0
    assert out["alerts"] == []
