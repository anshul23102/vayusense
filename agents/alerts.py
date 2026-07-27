"""Early Warning System -- surfaces three kinds of "needs attention right
now" signal across every tracked city, closing the two problem-statement
requirements no other feature in the app addresses: "generate ... alerts"
and "identify patterns, trends, and anomalies".

Deliberately built on statistics the pipeline already computes and already
trusts elsewhere: category() and times_who_limit are exactly what
get_city_snapshot() already returns per pollutant; the rolling z-score is
the same column the ingestion pipeline uses to silently drop sensor-fault
city-days (see benchmark/extend_2026.py's run_pipeline docstring). This
module adds no new statistics, only a new lens on ones already tested.
"""
from __future__ import annotations

import json

from .aqi import CATEGORIES, pollutant_label
from .tools import _daily, get_city_snapshot, list_cities

CATEGORY_BREACH = {"poor", "unhealthy", "severe", "hazardous"}
WHO_BREACH_MULTIPLE = 2.0
# The pipeline's own "anomaly" boolean is cut at |zscore| > 2.0 for a
# different purpose (dropping sensor faults from the merged archive) and
# includes negative-direction days. Alerts use a separate, lower,
# positive-only cutoff: a spike worth telling someone about, not a
# statistically-flagged data-quality day.
ANOMALY_ZSCORE_MIN = 1.5

_CATEGORY_RANK = {c["key"]: i for i, c in enumerate(CATEGORIES)}


def _category_alert(city: str, snap: dict) -> dict | None:
    cat_label = snap.get("aqi_category")
    if not cat_label:
        return None
    cat_key = cat_label.lower()
    if cat_key not in CATEGORY_BREACH:
        return None
    return {
        "city": city,
        "city_slug": city.lower(),
        "type": "category_breach",
        "severity": cat_key,
        "aqi": snap["aqi"],
        "pollutant": snap["aqi_dominant"],
        "message": f"{city}'s AQI is {cat_label} ({snap['aqi']}), driven by "
                   f"{pollutant_label(snap['aqi_dominant'])}.",
    }


def _who_breach_alerts(city: str, snap: dict) -> list[dict]:
    out = []
    for param, p in snap.get("pollutants", {}).items():
        times = p.get("times_who_limit")
        if times is not None and times >= WHO_BREACH_MULTIPLE:
            label = pollutant_label(param)
            out.append({
                "city": city,
                "city_slug": city.lower(),
                "type": "who_breach",
                "pollutant": param,
                "times_who": times,
                "message": f"{city}'s {label} is {times}x the WHO 24-hour guideline.",
            })
    return out


def _isnan(v) -> bool:
    # Avoids importing pandas/numpy just for a null check; NaN is the only
    # float value unequal to itself.
    return v != v


def _anomaly_alerts(city: str) -> list[dict]:
    df = _daily()
    d = df[df["city"] == city]
    if d.empty:
        return []
    out = []
    for param, grp in d.groupby("parameter"):
        grp = grp.sort_values("date")
        last = grp.iloc[-1]
        z = last.get("zscore")
        if z is None or _isnan(z):
            continue
        if z >= ANOMALY_ZSCORE_MIN:
            label = pollutant_label(param)
            out.append({
                "city": city,
                "city_slug": city.lower(),
                "type": "anomaly",
                "pollutant": param,
                "zscore": round(float(z), 1),
                "message": f"{city}'s {label} spiked to {round(float(z), 1)} standard "
                           f"deviations above its rolling baseline.",
            })
    return out


def get_active_alerts() -> list[dict]:
    """Every current alert across all tracked cities, worst-first.

    Sort key: category breaches (ranked hazardous > severe > unhealthy >
    poor) come first for a given city, then WHO breaches by descending
    multiple, then anomalies by descending z-score. Across cities, category
    breaches as a group sort before WHO breaches as a group, which sort
    before anomalies as a group, so the most actionable signal always leads.
    """
    cities = json.loads(list_cities())
    alerts: list[dict] = []
    for city in cities:
        try:
            snap = json.loads(get_city_snapshot(city))
        except Exception:
            continue
        if "error" in snap:
            continue
        cat_alert = _category_alert(city, snap)
        if cat_alert:
            alerts.append(cat_alert)
        alerts.extend(_who_breach_alerts(city, snap))
        alerts.extend(_anomaly_alerts(city))

    def sort_key(a: dict):
        type_rank = {"category_breach": 0, "who_breach": 1, "anomaly": 2}[a["type"]]
        if a["type"] == "category_breach":
            secondary = -_CATEGORY_RANK.get(a["severity"], 0)
        elif a["type"] == "who_breach":
            secondary = -a["times_who"]
        else:
            secondary = -a["zscore"]
        return (type_rank, secondary)

    alerts.sort(key=sort_key)
    return alerts


def get_active_alerts_tool() -> str:
    """Get every current air-quality alert across all tracked cities: AQI
    category breaches, WHO 24-hour guideline exceedances, and statistically
    detected pollutant spikes, worst-first. Use this when asked about
    active alerts, warnings, or "what needs attention right now" across
    cities, rather than for a single city's routine status (use
    get_city_snapshot for that)."""
    alerts = get_active_alerts()
    return json.dumps({"count": len(alerts), "alerts": alerts})
