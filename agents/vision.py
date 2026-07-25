"""Multimodal sky-photo assessment -- a qualitative visibility/haze read from
a user-submitted photo, presented as a complementary signal alongside the
sensor-based AQI, never a replacement for it. Directly addresses "Multimodal
AI for text, image, video, and audio understanding" from the challenge brief;
the rest of the app is text/data only.

Uses the same Gemini model as the ADK agents (gemini-2.5-flash) but calls it
directly via google.genai rather than through ADK, since this is a one-shot
image+text call, not a conversational agent turn with tools."""
from __future__ import annotations

from functools import lru_cache

MODEL = "gemini-2.5-flash"
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@lru_cache(maxsize=1)
def _client():
    # Same lesson as agents/rag.py's real production bug: cache one client
    # instance for the process lifetime instead of constructing a fresh one
    # per call, or its transport gets torn down between calls.
    from google import genai
    return genai.Client()


def assess_sky_photo(image_bytes: bytes, mime_type: str, city: str, aqi: int, category: str) -> str:
    """Ask Gemini's vision capability for a short, honest, qualitative read
    on a sky/visibility photo, in the context of the city's real measured
    AQI -- explicitly framed as a non-scientific complement to the sensor
    data, not a substitute for it."""
    from google.genai import types
    prompt = (
        f"This photo of the sky/outdoor visibility was submitted by a resident of "
        f"{city}, India. The city's current EPA-method AQI, computed from real archived "
        f"sensor data, is {aqi} ({category}).\n\n"
        "In 2-3 short sentences: describe what the photo shows about visibility or haze, "
        "and note whether that looks broadly consistent with the AQI reading or "
        "noticeably different (hazier or clearer than the number would suggest). Be "
        "explicit that this is a qualitative visual impression, not a measurement -- "
        "lighting, time of day, and camera settings all affect how hazy a photo looks, "
        "so it can't override the sensor-based number."
    )
    response = _client().models.generate_content(
        model=MODEL,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt],
    )
    return response.text
