"""Automated public advisory generator -- workflow automation for the real
task a school administrator, clinic, or city ward office does by hand today:
cross-referencing the AQI, condition-specific guidance, forecast outlook, and
human-impact stakes across several separate panels, then writing a plain-
language notice. One call synthesizes all of that into ready-to-publish text.

Deliberately rule-based, not an LLM call -- same "facts before advice"
discipline as health_guidance.py. This also makes true batch automation
viable: generate_advisory_batch() below can produce every tracked city's
advisory in one pass, instantly and at zero marginal cost, which a per-
question LLM chatbot architecture could not do at this speed or price.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .aqi import category as aqi_category
from .health_guidance import CONDITION_LABELS, GUIDANCE
from .tools import get_city_snapshot, get_forecast, get_human_impact, list_cities

# Conditions worth calling out by name once the air is bad enough that
# "general population" guidance alone understates the real risk for them.
SENSITIVE_CONDITIONS = ["children", "elderly", "asthma", "heart"]
ELEVATED_RISK_CATEGORIES = {"poor", "unhealthy", "severe", "hazardous"}


def _forecast_outlook(city: str, parameter: str) -> str | None:
    """A one-line, hedged forecast sentence, or None if there isn't enough
    history to project (get_forecast already guards this itself)."""
    try:
        fc = json.loads(get_forecast(city, parameter, days=3))
    except Exception:
        return None
    if "error" in fc or not fc.get("forecast"):
        return None
    values = [row["value"] for row in fc["forecast"]]
    first, last = values[0], values[-1]
    if last > first * 1.08:
        direction = "likely to worsen"
    elif last < first * 0.92:
        direction = "likely to improve"
    else:
        direction = "expected to hold roughly steady"
    mae = fc.get("backtest_mae")
    basis = (f"historical error ±{mae} on held-out data" if mae is not None
             else "based on recent trend only, no held-out backtest available")
    return (f"Over the next {len(values)} days, {parameter.upper()} is {direction} "
            f"(projected by {fc['method_label']}; {basis}).")


def generate_advisory(city: str) -> dict:
    """Build one city's advisory. Returns {"error": ...} if the city isn't
    covered or lacks enough data -- callers (the API route, the batch
    function below) should skip/report those rather than fail outright."""
    snap = json.loads(get_city_snapshot(city))
    if "error" in snap:
        return snap
    cat = aqi_category(snap["aqi"])
    cat_key = cat["key"]
    dominant = snap["aqi_dominant"]

    impact = json.loads(get_human_impact(city))
    cigs = impact.get("cigarettes_per_day_equivalent") if "error" not in impact else None

    outlook = _forecast_outlook(city, dominant)

    general = GUIDANCE["general"][cat_key]
    lines = [
        f"{city.upper()} AIR QUALITY ADVISORY, "
        f"{datetime.now(timezone.utc).strftime('%B %d, %Y')}",
        "",
        f"Current status: {cat['label']} (AQI {snap['aqi']}), driven by {dominant.upper()}."
        + (f" Today's exposure carries a health burden comparable to smoking "
           f"{cigs} cigarettes." if cigs is not None else ""),
    ]
    if outlook:
        lines += ["", f"Outlook: {outlook}"]
    lines += ["", f"General public: {general['summary']}"]
    lines += [f"  • {d}" for d in general["dos"]]
    lines += [f"  ✗ {d}" for d in general["donts"]]

    if cat_key in ELEVATED_RISK_CATEGORIES:
        lines += ["", "Sensitive groups needing additional precautions:"]
        for cond in SENSITIVE_CONDITIONS:
            g = GUIDANCE[cond][cat_key]
            lines.append(f"  {CONDITION_LABELS[cond]}: {g['summary']}")

    lines += [
        "",
        "Issued by VayuSense, automated air-quality decision intelligence.",
        "Basis: EPA-method AQI from real archived sensor data (OpenAQ). "
        "Guidance keyed to WHO Air Quality Guidelines and US EPA sensitive-group thresholds.",
    ]

    return {
        "city": city,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aqi": snap["aqi"],
        "category": cat["label"],
        "category_key": cat_key,
        "dominant_pollutant": dominant,
        "cigarette_equivalent": cigs,
        "outlook": outlook,
        "text": "\n".join(lines),
    }


def generate_advisory_batch() -> list[dict]:
    """Every tracked city's advisory, generated in one pass. The concrete
    "workflow automation" claim, at scale: this runs deterministically over
    all cities in well under a second, not city-by-city LLM calls."""
    cities = json.loads(list_cities())
    out = []
    for city in cities:
        result = generate_advisory(city)
        if "error" not in result:
            out.append(result)
    return out
