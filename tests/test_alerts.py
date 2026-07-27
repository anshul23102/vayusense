from agents.alerts import (
    ANOMALY_ZSCORE_MIN,
    CATEGORY_BREACH,
    WHO_BREACH_MULTIPLE,
    get_active_alerts,
    get_active_alerts_tool,
)

VALID_TYPES = {"category_breach", "who_breach", "anomaly"}


def test_shape_and_types():
    alerts = get_active_alerts()
    assert isinstance(alerts, list)
    for a in alerts:
        assert a["type"] in VALID_TYPES
        assert a["city"] and a["city_slug"] == a["city"].lower()
        assert isinstance(a["message"], str) and len(a["message"]) > 10


def test_category_breach_only_uses_breach_categories():
    alerts = [a for a in get_active_alerts() if a["type"] == "category_breach"]
    for a in alerts:
        assert a["severity"] in CATEGORY_BREACH
        assert isinstance(a["aqi"], int)


def test_who_breach_meets_threshold():
    alerts = [a for a in get_active_alerts() if a["type"] == "who_breach"]
    for a in alerts:
        assert a["times_who"] >= WHO_BREACH_MULTIPLE


def test_anomaly_meets_threshold_and_is_positive_direction():
    alerts = [a for a in get_active_alerts() if a["type"] == "anomaly"]
    for a in alerts:
        assert a["zscore"] >= ANOMALY_ZSCORE_MIN  # positive-only by construction


def test_sort_order_worst_first():
    alerts = get_active_alerts()
    type_rank = {"category_breach": 0, "who_breach": 1, "anomaly": 2}
    ranks = [type_rank[a["type"]] for a in alerts]
    assert ranks == sorted(ranks)


def test_real_data_has_at_least_one_alert():
    # Not a tautology about the implementation -- a live check that the
    # archive genuinely contains alert-worthy conditions right now, so this
    # test would actually fail if the feature silently stopped finding them.
    alerts = get_active_alerts()
    assert len(alerts) > 0


def test_tool_wrapper_returns_valid_json_matching_function():
    import json
    direct = get_active_alerts()
    wrapped = json.loads(get_active_alerts_tool())
    assert wrapped["count"] == len(direct)
    assert len(wrapped["alerts"]) == len(direct)
