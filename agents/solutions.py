"""Instant, rule-based protective-action recommendations per AQI category.

Deterministic and LLM-free, same discipline as agents/health_guidance.py, but
keyed on solution type x AQI category rather than condition x category — a
different, independent dimension. Category keys match agents/aqi.py's
CATEGORIES exactly."""
from __future__ import annotations

SOLUTIONS = ["air_purifier", "car_filter", "n95_mask", "stay_indoor"]

SOLUTION_LABELS = {
    "air_purifier": "Air Purifier",
    "car_filter": "Car Cabin Filter",
    "n95_mask": "N95 Mask",
    "stay_indoor": "Stay Indoor",
}

STATUS_TABLE = {
    "air_purifier": {
        "good": {"status": "Not needed", "tip": "No need to run it today."},
        "moderate": {"status": "Optional", "tip": "Run it if anyone in the home is sensitive."},
        "poor": {"status": "Recommended", "tip": "Turn it on for bedrooms and living spaces."},
        "unhealthy": {"status": "Recommended", "tip": "Keep it running continuously indoors."},
        "severe": {"status": "Must", "tip": "Run on high in all closed rooms."},
        "hazardous": {"status": "Must", "tip": "Run continuously in every sealed room."},
    },
    "car_filter": {
        "good": {"status": "Not needed", "tip": "Standard cabin filter is fine."},
        "moderate": {"status": "Not needed", "tip": "No action needed yet."},
        "poor": {"status": "Optional", "tip": "Check your cabin air filter isn't clogged."},
        "unhealthy": {"status": "Recommended", "tip": "Use recirculate mode while driving."},
        "severe": {"status": "Must", "tip": "Recirculate mode; consider a HEPA cabin filter."},
        "hazardous": {"status": "Must", "tip": "Keep windows shut and recirculate mode on at all times."},
    },
    "n95_mask": {
        "good": {"status": "Not needed", "tip": "Not required."},
        "moderate": {"status": "Not needed", "tip": "Not required for most people."},
        "poor": {"status": "Optional", "tip": "Carry one for extended outdoor time."},
        "unhealthy": {"status": "Recommended", "tip": "Wear one for any outdoor activity."},
        "severe": {"status": "Must", "tip": "Wear a well-fitted N95 for all outdoor exposure."},
        "hazardous": {"status": "Must", "tip": "Wear a well-fitted N95 outdoors — no exceptions."},
    },
    "stay_indoor": {
        "good": {"status": "Not needed", "tip": "No restrictions — enjoy the outdoors."},
        "moderate": {"status": "Optional", "tip": "Fine to be outside; sensitive groups take care."},
        "poor": {"status": "Recommended", "tip": "Limit long outdoor stretches."},
        "unhealthy": {"status": "Advised", "tip": "Stay indoors during peak hours."},
        "severe": {"status": "Must", "tip": "Stay indoors as much as possible."},
        "hazardous": {"status": "Must", "tip": "Stay indoors; avoid going outside entirely."},
    },
}


def get_solutions(category_key: str) -> list[dict]:
    return [
        {"type": s, "label": SOLUTION_LABELS[s], **STATUS_TABLE[s][category_key]}
        for s in SOLUTIONS
    ]


def citation() -> str:
    return ("Protective-action guidance aligned with WHO and US EPA AQI category "
            "thresholds; escalates with measured or projected severity.")
