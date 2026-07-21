"""Instant, rule-based health guidance per condition and AQI category.

Deterministic and LLM-free by design: keeps the product's "facts before advice"
principle intact for a feature that would otherwise tempt a per-click agent call.
Category keys match agents/aqi.py's CATEGORIES exactly. Each cell is a summary
line plus concrete Do's and Don'ts, scaled to severity."""
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
        "good": {
            "summary": "Air quality poses little or no risk today.",
            "dos": ["Enjoy normal outdoor activities", "Ventilate your home by opening windows"],
            "donts": ["Don't assume tomorrow will be the same — check back daily", "Don't skip ventilating indoor spaces"],
        },
        "moderate": {
            "summary": "Acceptable for most people; unusually sensitive individuals should ease off.",
            "dos": ["Continue normal outdoor plans", "Watch for coughing or throat irritation if sensitive"],
            "donts": ["Don't push through symptoms if you notice irritation", "Don't ignore repeated headaches during outdoor time"],
        },
        "poor": {
            "summary": "Reduce prolonged or heavy outdoor exertion.",
            "dos": ["Take breaks during outdoor exercise", "Keep windows closed during peak traffic hours"],
            "donts": ["Don't do intense outdoor workouts", "Don't leave windows open all day"],
        },
        "unhealthy": {
            "summary": "Limit prolonged outdoor exertion; move strenuous activity indoors.",
            "dos": ["Move exercise indoors", "Wear a well-fitted N95 mask if you must go out"],
            "donts": ["Don't jog or cycle outdoors", "Don't prop doors/windows open for long periods"],
        },
        "severe": {
            "summary": "Avoid prolonged outdoor exertion; run an air purifier indoors.",
            "dos": ["Run an air purifier indoors", "Keep all windows and doors closed"],
            "donts": ["Don't exercise outdoors at all", "Don't ventilate with outside air right now"],
        },
        "hazardous": {
            "summary": "Avoid all outdoor physical activity; stay indoors with filtration running.",
            "dos": ["Stay indoors with air filtration running", "Wear an N95 mask for any unavoidable outdoor trip"],
            "donts": ["Don't go outside unless absolutely necessary", "Don't exercise, even indoors, near open windows"],
        },
    },
    "children": {
        "good": {
            "summary": "No restrictions — outdoor play is safe.",
            "dos": ["Let kids play outside freely", "Use this window for outdoor sports practice"],
            "donts": ["Don't cancel outdoor plans out of caution today"],
        },
        "moderate": {
            "summary": "Outdoor play remains fine; watch for coughing or fatigue.",
            "dos": ["Continue normal outdoor play", "Watch for unusual coughing or tiredness"],
            "donts": ["Don't ignore a child complaining of a scratchy throat", "Don't extend play time if symptoms appear"],
        },
        "poor": {
            "summary": "Shorten outdoor playtime; favor lighter activity.",
            "dos": ["Shorten recess/outdoor playtime", "Swap vigorous games for lighter activity"],
            "donts": ["Don't schedule long outdoor sports practice", "Don't let children with asthma history overexert outdoors"],
        },
        "unhealthy": {
            "summary": "Move recess and sports practice indoors where possible.",
            "dos": ["Move recess and PE indoors", "Offer indoor alternatives for active play"],
            "donts": ["Don't hold outdoor sports practice", "Don't assume kids will self-report discomfort — check in"],
        },
        "severe": {
            "summary": "Keep children indoors; schools should suspend outdoor activities.",
            "dos": ["Keep children indoors", "Suspend outdoor PE and recess entirely"],
            "donts": ["Don't allow outdoor activity even briefly", "Don't send children to school without checking advisories"],
        },
        "hazardous": {
            "summary": "Keep children indoors at all times with windows closed.",
            "dos": ["Keep children indoors with windows closed", "Seek medical advice if a child shows breathing difficulty"],
            "donts": ["Don't let children outside for any reason", "Don't wait to seek care if a child struggles to breathe"],
        },
    },
    "elderly": {
        "good": {
            "summary": "No precautions needed.",
            "dos": ["Go about daily routines and errands as normal"],
            "donts": ["Don't feel the need to limit outdoor time today"],
        },
        "moderate": {
            "summary": "Generally safe; those with heart/lung conditions should monitor how they feel.",
            "dos": ["Continue normal activity", "Monitor how you feel during outdoor time if you have a condition"],
            "donts": ["Don't ignore unusual breathlessness during activity"],
        },
        "poor": {
            "summary": "Reduce time outdoors, especially during peak pollution hours.",
            "dos": ["Run errands earlier in the day", "Rest indoors during peak afternoon pollution"],
            "donts": ["Don't spend long stretches outdoors midday", "Don't skip rest breaks during outdoor tasks"],
        },
        "unhealthy": {
            "summary": "Limit outdoor exposure; rest indoors if fatigued.",
            "dos": ["Postpone non-essential errands", "Rest indoors if experiencing fatigue or breathlessness"],
            "donts": ["Don't make unnecessary trips outside", "Don't push through fatigue or dizziness"],
        },
        "severe": {
            "summary": "Stay indoors as much as possible; keep medication accessible.",
            "dos": ["Stay indoors as much as possible", "Keep prescribed inhalers/heart medication within reach"],
            "donts": ["Don't go outdoors without a clear reason", "Don't let medication run low during this period"],
        },
        "hazardous": {
            "summary": "Remain indoors continuously; contact a doctor for any symptoms.",
            "dos": ["Remain indoors continuously", "Contact a doctor promptly for chest tightness, dizziness, or breathing difficulty"],
            "donts": ["Don't leave home for any non-emergency reason", "Don't delay calling a doctor if symptoms appear"],
        },
    },
    "asthma": {
        "good": {
            "summary": "Air quality is unlikely to trigger symptoms.",
            "dos": ["Carry on with normal outdoor activity"],
            "donts": ["Don't skip carrying your regular medication as a habit"],
        },
        "moderate": {
            "summary": "Keep rescue medication on hand; most well-controlled asthma is unaffected.",
            "dos": ["Keep rescue inhaler on hand as usual", "Proceed with planned outdoor activity"],
            "donts": ["Don't leave rescue medication at home"],
        },
        "poor": {
            "summary": "Carry a reliever inhaler and reduce outdoor exertion.",
            "dos": ["Carry a reliever inhaler at all times", "Reduce outdoor exertion"],
            "donts": ["Don't do strenuous outdoor exercise", "Don't go out without your inhaler"],
        },
        "unhealthy": {
            "summary": "Avoid outdoor exertion; pre-treat before necessary exposure.",
            "dos": ["Pre-treat with prescribed medication before going out", "Limit outdoor time to essential trips only"],
            "donts": ["Don't exert yourself outdoors", "Don't go out without pre-treating if advised by your doctor"],
        },
        "severe": {
            "summary": "Stay indoors with air filtration — this can provoke attacks even at rest.",
            "dos": ["Stay indoors with air filtration running", "Keep emergency medication within reach at all times"],
            "donts": ["Don't go outdoors even briefly", "Don't assume rest alone prevents a flare-up at this level"],
        },
        "hazardous": {
            "summary": "Remain indoors; seek urgent care if breathing worsens.",
            "dos": ["Remain indoors with emergency medication within reach", "Seek urgent care immediately if breathing worsens"],
            "donts": ["Don't wait out worsening symptoms at home", "Don't go outside for any reason"],
        },
    },
    "heart": {
        "good": {
            "summary": "No added cardiovascular risk from air quality today.",
            "dos": ["Continue normal activity levels"],
            "donts": ["Don't alter your routine — no added risk today"],
        },
        "moderate": {
            "summary": "Low added risk; normal routines can continue.",
            "dos": ["Continue normal routines", "Stay attentive to how you feel during exertion"],
            "donts": ["Don't ignore new or unusual chest discomfort"],
        },
        "poor": {
            "summary": "Reduce strenuous outdoor activity — added strain on the cardiovascular system.",
            "dos": ["Reduce strenuous outdoor activity", "Choose lighter activity over intense exercise"],
            "donts": ["Don't do intense outdoor cardio", "Don't ignore palpitations during exertion"],
        },
        "unhealthy": {
            "summary": "Avoid outdoor exertion — linked to increased risk of cardiac events.",
            "dos": ["Avoid outdoor exertion entirely", "Move any necessary activity indoors"],
            "donts": ["Don't exercise outdoors", "Don't dismiss unusual shortness of breath"],
        },
        "severe": {
            "summary": "Avoid physical exertion of any kind; monitor for chest pain.",
            "dos": ["Avoid physical exertion of any kind", "Monitor for chest pain, palpitations, or shortness of breath"],
            "donts": ["Don't exert yourself indoors or outdoors", "Don't delay care if symptoms appear"],
        },
        "hazardous": {
            "summary": "Minimize all exertion; seek emergency care for any cardiac symptoms.",
            "dos": ["Minimize all exertion", "Seek emergency care immediately for any chest pain or cardiac symptoms"],
            "donts": ["Don't leave home unless for emergency care", "Don't wait out chest pain or palpitations"],
        },
    },
    "outdoor_workers": {
        "good": {
            "summary": "Full outdoor training and work schedules are safe.",
            "dos": ["Proceed with normal outdoor work/training schedules"],
            "donts": ["Don't add unnecessary precautions today"],
        },
        "moderate": {
            "summary": "Normal outdoor work can continue; stay alert during intense exertion.",
            "dos": ["Continue normal outdoor work", "Stay alert to respiratory discomfort during intense exertion"],
            "donts": ["Don't ignore repeated coughing during heavy exertion"],
        },
        "poor": {
            "summary": "Schedule the most strenuous work for early morning; take more breaks.",
            "dos": ["Schedule strenuous work for early morning", "Take more frequent breaks"],
            "donts": ["Don't schedule peak-intensity work in the afternoon", "Don't skip scheduled breaks"],
        },
        "unhealthy": {
            "summary": "Reduce training intensity and duration; more indoor rest breaks.",
            "dos": ["Reduce training/work intensity and duration", "Provide more frequent indoor rest breaks"],
            "donts": ["Don't sustain high-intensity outdoor work", "Don't skip indoor recovery time"],
        },
        "severe": {
            "summary": "Postpone outdoor training and non-essential work; use N95 masks if unavoidable.",
            "dos": ["Postpone outdoor training and non-essential outdoor work", "Use N95-class masks if outdoor work can't be avoided"],
            "donts": ["Don't conduct non-essential outdoor work", "Don't go without respiratory protection outdoors"],
        },
        "hazardous": {
            "summary": "Suspend outdoor training/labor; minimize essential work with protection.",
            "dos": ["Suspend outdoor training and non-essential labor entirely", "Use respiratory protection for essential outdoor work"],
            "donts": ["Don't conduct outdoor training at all", "Don't perform essential outdoor work without protection"],
        },
    },
}


def get_guidance(condition: str, category_key: str) -> dict:
    return GUIDANCE[condition][category_key]


def citation() -> str:
    return ("Guidance keyed to WHO Air Quality Guidelines and US EPA AQI category "
            "thresholds for sensitive groups.")
