# Phase 3: City Landmarks + Ranking Table + Landing De-boxing — Design

**Date:** 2026-07-20
**Project:** VayuSense renovation, Phase 3 of 5 (aqi.in-inspired)
**Status:** Approved by user

## Purpose

Give the 10-city ranking (already computed honestly by `/api/aqi`'s `ranking` field)
a real home: a full open-section table with per-city monoline landmark icons,
category chips, and dominant pollutant — replacing the buried rank-only chip in the
hero. Extend Phase 2's typography/shape system to the landing page so both pages
read as one product.

## 1. City landmark icons

Ten hand-drawn monoline SVG symbols added to the existing icon sprite in
`index.html` (`<svg style="position:absolute" aria-hidden="true">` block, alongside
`ic-lungs`/`ic-bolt`/`ic-chip`). Single `stroke="currentColor"`, `fill="none"`,
`stroke-width` matching the existing icons (~1.8-2), viewBox `0 0 24 24`, simple
enough to read at 28-36px:

- `ic-delhi` — India Gate (arch silhouette)
- `ic-mumbai` — Gateway of India (arch + dome)
- `ic-kolkata` — Victoria Memorial (dome + wings)
- `ic-chennai` — Dravidian gopuram/temple tower (tiered pyramid)
- `ic-bengaluru` — Vidhana Soudha (domed legislature silhouette)
- `ic-hyderabad` — Charminar (four minarets)
- `ic-pune` — Shaniwar Wada gate (fortified gateway)
- `ic-ahmedabad` — mosque silhouette (dome + minaret)
- `ic-lucknow` — Bara Imambara arch (large central arch)
- `ic-patna` — Golghar (beehive-shaped granary dome)

A JS map `CITY_ICON = {Delhi:'ic-delhi', Mumbai:'ic-mumbai', ...}` with a
`ic-generic` fallback (simple skyline mark) for any city not in the map, so the
table never breaks if a city is added later without an icon.

## 2. India Cities ranking section

New open section `#cities` (after `#overview`, before `#pollutants`, matching
reading order: "where do I stand" before "why"): a header row (City · AQI ·
Category · Dominant) and one row per tracked city, sorted worst AQI first (already
the API's order). Each row: landmark icon in a small `.objCard`-style badge (28px,
tinted by that city's category color at low opacity), city name, AQI number (Space
Grotesk, tabular), category chip (reusing the verdict-chip pattern), dominant
pollutant tag. The current `CITY` row is highlighted (Ice Solid left border). Rows
are hairline-separated (`border-top:1px solid var(--line)` per row), not boxed —
only the icon badge is an object. Clicking a row sets `CITY`, calls `refresh()` +
`renderCalendar()` + `renderTrends()`, and scrolls to `#overview`.

Basis line under the header: "Ranked on the latest archive day, same basis for
every city" (reuses the existing `ranking_basis` field from `/api/aqi`).

The hero's existing rank chip text simplifies to reference this section (e.g. "See
full ranking ↓" anchor) instead of repeating the sentence inline — avoids duplicated
copy now that the full table exists.

## 3. Backend: enrich the ranking payload

`/api/aqi`'s `ranking` list gains `dominant` (from `overall_aqi`'s existing return)
and `source` (`"live"` if `live.peek_live_city(c)` has a cached hit, else
`"archive"` — cache-only, never triggers a new fetch, so building the ranking never
costs extra OpenAQ calls beyond what the hero already warmed). No new endpoint;
`_city_aqi`'s existing per-city AQI computation is reused inside the ranking loop
(replacing the current inline `overall_aqi` call) so dominant/units aren't
recomputed with different logic in two places.

## 4. Landing page de-boxing

Apply Phase 2's Named Rule ("Boxes are for objects, not sections") to
`landing.html`: convert its feature-card grid section(s) into an open `.section`
with `.objCard` items for individual features/stats, matching the dashboard's
established radius (14px), flat fill, and no-gradient-border treatment. Typography
already matches from Phase 2 (Space Grotesk/IBM Plex Sans) — this task is shape-only.
Scope: the feature/stat cards specifically; hero layout and CTA button styling are
unchanged (out of scope — no user complaint there).

## 5. Testing

- `tests/test_ranking_enrichment.py`: `/api/aqi` ranking rows include `dominant` (a
  valid parameter key) and `source` (`"live"`/`"archive"`); ranking stays sorted
  descending by AQI; row count matches tracked city count; peeking the ranking
  never triggers a live HTTP fetch (monkeypatch `live.get_live_city` to raise if
  called, `live.peek_live_city` mocked to return cached-or-None).
- Browser verification: all 10 landmark icons render (no broken `<use>` refs),
  ranking table sorted correctly, clicking a row switches city and scrolls,
  current-city row highlighted, landing page shows open sections + object cards
  with no lingering gradient-border cards.
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Out of scope (later phases)

Cigarette/health-condition tabs and any further motion polish are Phase 4.
Landing hero restructuring beyond the feature-card de-boxing is not part of this
phase.

## Success criteria

- All 10 cities have a distinct, recognizable monoline landmark icon (or fallback).
- The ranking table is the definitive place to see all 10 cities compared, on one
  consistent, labeled basis.
- Landing page's feature/stat cards follow the same shape rule as the dashboard.
- All tests green; deployed and verified live.
