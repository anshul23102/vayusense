"""Instant, rule-based health guidance per condition and AQI category.

Deterministic and LLM-free by design: keeps the product's "facts before advice"
principle intact for a feature that would otherwise tempt a per-click agent call.
Category keys match agents/aqi.py's CATEGORIES exactly."""
from __future__ import annotations

CONDITIONS = ["general", "children", "elderly", "asthma", "heart", "outdoor_workers"]

CONDITION_LABELS = {
    "general": "General Population",
    "children": "Children",
    "elderly": "Elderly",
    "asthma": "Asthma / Respiratory",
    "heart": "Heart / Cardiovascular",
    "outdoor_workers": "Outdoor Workers & Athletes",
}

GUIDANCE = {
    "general": {
        "good": "Air quality poses little or no risk. Enjoy normal outdoor activities.",
        "moderate": "Air quality is acceptable for most people. Unusually sensitive individuals should consider reducing prolonged outdoor exertion.",
        "poor": "Reduce prolonged or heavy outdoor exertion, especially if you notice coughing or throat irritation.",
        "unhealthy": "Limit prolonged outdoor exertion. Consider moving strenuous activities indoors or to a later time.",
        "severe": "Avoid prolonged outdoor exertion. Keep windows closed and run an air purifier indoors if available.",
        "hazardous": "Avoid all outdoor physical activity. Remain indoors with air filtration running whenever possible.",
    },
    "children": {
        "good": "No restrictions. Outdoor play is safe.",
        "moderate": "Outdoor play remains fine, but watch for coughing or unusual tiredness during extended activity.",
        "poor": "Shorten outdoor playtime and swap vigorous games for lighter activity, particularly for children with an asthma history.",
        "unhealthy": "Move recess and sports practice indoors where possible. Children's developing lungs are more sensitive to sustained exposure.",
        "severe": "Keep children indoors. Schools should suspend outdoor activities and physical education.",
        "hazardous": "Keep children indoors at all times with windows closed. Seek medical advice if a child shows breathing difficulty.",
    },
    "elderly": {
        "good": "No precautions needed.",
        "moderate": "Generally safe, but elderly individuals with existing heart or lung conditions should monitor how they feel during outdoor activity.",
        "poor": "Reduce time spent outdoors, especially during the day's peak pollution hours.",
        "unhealthy": "Limit outdoor exposure and avoid unnecessary errands outside. Rest indoors if experiencing fatigue or breathlessness.",
        "severe": "Stay indoors as much as possible. Keep any prescribed inhalers or heart medication readily accessible.",
        "hazardous": "Remain indoors continuously. Contact a doctor promptly if chest tightness, dizziness, or breathing difficulty occurs.",
    },
    "asthma": {
        "good": "Air quality is unlikely to trigger symptoms.",
        "moderate": "Keep rescue medication on hand; most people with well-controlled asthma will be unaffected.",
        "poor": "Carry a reliever inhaler and reduce outdoor exertion. Pollution at this level can trigger symptoms in sensitive airways.",
        "unhealthy": "Avoid outdoor exertion entirely. Pre-treat with prescribed medication before any necessary outdoor exposure.",
        "severe": "Stay indoors with air filtration running. This level of pollution can provoke asthma attacks even at rest.",
        "hazardous": "Remain indoors and keep emergency medication within reach. Seek urgent care immediately if breathing worsens.",
    },
    "heart": {
        "good": "No added cardiovascular risk from air quality today.",
        "moderate": "Low added risk; people with heart disease can continue normal routines.",
        "poor": "Reduce strenuous outdoor activity. Fine particulate matter at this level has been linked to added strain on the cardiovascular system.",
        "unhealthy": "Avoid outdoor exertion. Sustained exposure at this level is associated with increased risk of cardiac events in vulnerable individuals.",
        "severe": "Stay indoors and avoid physical exertion of any kind. Monitor for chest pain, palpitations, or unusual shortness of breath.",
        "hazardous": "Remain indoors and minimize all exertion. Seek emergency care immediately for any chest pain or cardiac symptoms.",
    },
    "outdoor_workers": {
        "good": "Full outdoor training and work schedules are safe.",
        "moderate": "Normal outdoor work and training can continue; stay alert to any respiratory discomfort during intense exertion.",
        "poor": "Schedule the most strenuous outdoor work or training for early morning when pollution is typically lower, and take more frequent breaks.",
        "unhealthy": "Reduce training intensity and duration. Employers should provide more frequent indoor rest breaks for outdoor workers.",
        "severe": "Postpone outdoor training and non-essential outdoor work. Use N95-class masks if outdoor work cannot be avoided.",
        "hazardous": "Suspend outdoor training and non-essential outdoor labor entirely. Essential outdoor work should be minimized and use respiratory protection.",
    },
}


def get_guidance(condition: str, category_key: str) -> str:
    return GUIDANCE[condition][category_key]


def citation() -> str:
    return ("Guidance keyed to WHO Air Quality Guidelines and US EPA AQI category "
            "thresholds for sensitive groups.")
