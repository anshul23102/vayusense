"""Single source of truth for how many stations per city the archive tracks.

full_repull.py grew the archive from 12 to 30 stations per city. The nightly
refresh_incremental.py had its own hardcoded 12, so new days would have been
built from far fewer stations than the history they are appended to. Both
scripts now take the cap and the selection rule from here so they cannot drift
apart again.
"""
from __future__ import annotations

MAX_LOCATIONS_PER_CITY = 30


def select_stations(results: list[dict]) -> list[dict]:
    """Top MAX_LOCATIONS_PER_CITY OpenAQ locations, most sensors first."""
    ranked = sorted(results, key=lambda x: len(x.get("sensors", [])), reverse=True)
    return ranked[:MAX_LOCATIONS_PER_CITY]
