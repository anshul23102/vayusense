"""Retrieval-augmented grounding for Ask VayuSense: a small, hand-curated
corpus of real WHO and CPCB (India) air-quality guideline text, retrieved by
embedding similarity so the health_advisor agent can cite an actual source
passage instead of only reasoning from the app's own AQI number.

This is deliberately separate from agents/health_guidance.py's rule-based
per-condition Do's/Don'ts panel, which stays LLM-free by design (see that
module's docstring) -- Ask VayuSense already accepts LLM latency/cost per
question, so adding retrieval there is additive, not a regression of that
panel's "instant, zero-cost" guarantee.

Every passage below was pulled from a live fetch of the cited page at build
time (WHO's ambient air quality fact sheet, and CPCB NAAQS reference pages),
not recalled from training data -- health/regulatory figures are exactly the
kind of thing that's easy to misquote from memory.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

EMBED_MODEL = "gemini-embedding-001"

CORPUS = [
    {
        "id": "who_pm25_annual",
        "source": "WHO Global Air Quality Guidelines, 2021",
        "text": "WHO's 2021 annual guideline value for PM2.5 is 5 micrograms per cubic metre "
                "(µg/m3) -- half the previous 2005 guideline of 10 µg/m3.",
    },
    {
        "id": "who_pm10_annual",
        "source": "WHO Global Air Quality Guidelines, 2021",
        "text": "WHO's 2021 annual guideline value for PM10 is 15 µg/m3, a 25% reduction "
                "from the 2005 guideline of 20 µg/m3.",
    },
    {
        "id": "who_no2_annual",
        "source": "WHO Global Air Quality Guidelines, 2021",
        "text": "WHO's 2021 annual guideline value for nitrogen dioxide (NO2) is 10 µg/m3, "
                "four times lower than the previous 2005 guideline of 40 µg/m3.",
    },
    {
        "id": "who_o3",
        "source": "WHO Global Air Quality Guidelines, 2021",
        "text": "WHO's ozone (O3) guideline is 100 µg/m3 for an 8-hour mean, with a "
                "60 µg/m3 peak-season mean.",
    },
    {
        "id": "who_24h",
        "source": "WHO Global Air Quality Guidelines, 2021 (24-hour values)",
        "text": "WHO's 2021 24-hour guideline values: PM2.5 15 µg/m3, PM10 45 µg/m3, "
                "NO2 25 µg/m3, SO2 40 µg/m3, O3 100 µg/m3 (8-hour).",
    },
    {
        "id": "who_burden",
        "source": "WHO, ambient (outdoor) air quality and health fact sheet",
        "text": "Ambient (outdoor) air pollution is estimated to have caused 4.2 million "
                "premature deaths worldwide in 2019, with 89% of those deaths occurring "
                "in low- and middle-income countries.",
    },
    {
        "id": "who_coverage",
        "source": "WHO, ambient (outdoor) air quality and health fact sheet",
        "text": "In 2019, 99% of the world's population was living in places where WHO "
                "air quality guideline levels were not met.",
    },
    {
        "id": "who_causes",
        "source": "WHO, ambient (outdoor) air quality and health fact sheet",
        "text": "Of outdoor air pollution related premature deaths, 68% were due to "
                "ischaemic heart disease and stroke, 14% due to chronic obstructive "
                "pulmonary disease, 14% due to acute lower respiratory infections, and "
                "4% due to lung cancers.",
    },
    {
        "id": "cpcb_pm25",
        "source": "CPCB National Ambient Air Quality Standards (NAAQS), 2009",
        "text": "India's National Ambient Air Quality Standards set PM2.5 at 40 µg/m3 "
                "annual and 60 µg/m3 24-hour -- 8x and 4x looser than WHO's 2021 "
                "guideline, respectively.",
    },
    {
        "id": "cpcb_pm10",
        "source": "CPCB National Ambient Air Quality Standards (NAAQS), 2009",
        "text": "India's NAAQS for PM10: 60 µg/m3 annual, 100 µg/m3 24-hour.",
    },
    {
        "id": "cpcb_no2",
        "source": "CPCB National Ambient Air Quality Standards (NAAQS), 2009",
        "text": "India's NAAQS for nitrogen dioxide (NO2): 40 µg/m3 annual (industrial/"
                "residential zones), 80 µg/m3 24-hour.",
    },
    {
        "id": "cpcb_so2",
        "source": "CPCB National Ambient Air Quality Standards (NAAQS), 2009",
        "text": "India's NAAQS for sulphur dioxide (SO2): 50 µg/m3 annual (industrial/"
                "residential zones), 80 µg/m3 24-hour.",
    },
    {
        "id": "cpcb_co",
        "source": "CPCB National Ambient Air Quality Standards (NAAQS), 2009",
        "text": "India's NAAQS for carbon monoxide (CO): 2 mg/m3 over an 8-hour mean, "
                "4 mg/m3 over a 1-hour mean.",
    },
    {
        "id": "cpcb_o3",
        "source": "CPCB National Ambient Air Quality Standards (NAAQS), 2009",
        "text": "India's NAAQS for ozone (O3): 100 µg/m3 over an 8-hour mean, 180 µg/m3 "
                "over a 1-hour mean.",
    },
    {
        "id": "who_vs_cpcb",
        "source": "Comparison: WHO 2021 guideline vs CPCB NAAQS 2009",
        "text": "A city can be legally compliant with India's air quality standards "
                "(CPCB NAAQS) while still being multiple times above WHO's 2021 "
                "health-based guideline -- the two are not measuring the same bar.",
    },
]


def _client():
    from google import genai
    return genai.Client()


def _embed(texts: list[str], task_type: str) -> np.ndarray:
    from google.genai import types
    result = _client().models.embed_content(
        model=EMBED_MODEL, contents=texts,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return np.array([e.values for e in result.embeddings], dtype=float)


@lru_cache(maxsize=1)
def _corpus_embeddings() -> np.ndarray:
    """Embedded once per process (not at import time -- only on first real
    query), then cached for the process lifetime. A handful of short
    passages; re-embedding per request would be wasteful and slower."""
    return _embed([c["text"] for c in CORPUS], task_type="RETRIEVAL_DOCUMENT")


def retrieve_guidelines(query: str, top_k: int = 3) -> str:
    """Retrieve the most relevant real WHO/CPCB air-quality guideline passages
    for a query, via embedding similarity (not keyword matching).

    Args:
        query: What the user is asking about, e.g. "is Delhi's AQI safe by
            international standards" or "why does India allow higher PM2.5
            than WHO recommends".
        top_k: How many passages to return (default 3).
    """
    corpus_vecs = _corpus_embeddings()
    query_vec = _embed([query], task_type="RETRIEVAL_QUERY")[0]
    norms = np.linalg.norm(corpus_vecs, axis=1) * np.linalg.norm(query_vec)
    sims = (corpus_vecs @ query_vec) / np.where(norms == 0, 1, norms)
    top_idx = np.argsort(-sims)[:top_k]
    lines = [f'- "{CORPUS[i]["text"]}" (source: {CORPUS[i]["source"]})' for i in top_idx]
    return "\n".join(lines)
