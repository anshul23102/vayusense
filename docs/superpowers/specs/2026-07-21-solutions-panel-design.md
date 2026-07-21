# Phase 6D: Solutions Panel — Design

**Date:** 2026-07-21
**Project:** VayuSense renovation, Phase 6D of 6 (round 2)
**Status:** Approved by user

## Purpose

Add the reference screenshots' "Solutions" panel: concrete protective actions
(Air Purifier, N95 Mask, Stay Indoor, Car Filter) each labeled with a status
that escalates with the current AQI severity. Same rule-based, zero-LLM
architecture as the health guidance panel (Phase 4/6C) — this is a new,
independent 4×6 data table, not an extension of the health guidance module
(different dimension: solution type × AQI category, not condition × category).

## 1. Data module (`agents/solutions.py`)

- `SOLUTIONS = ["air_purifier", "car_filter", "n95_mask", "stay_indoor"]` with
  `SOLUTION_LABELS`.
- `STATUS_TABLE[solution][category_key] -> {"status": str, "tip": str}` — 24
  cells (4 solutions × 6 categories). `status` is one of `"Not needed"`,
  `"Optional"`, `"Recommended"`, `"Advised"`, `"Must"`, escalating with
  severity; each solution has its own escalation curve (e.g. a mask matters
  sooner for outdoor exposure than a car cabin filter). `tip` is one short,
  concrete line.
- `get_solutions(category_key) -> list[dict]` returns all 4 solutions'
  `{type, label, status, tip}` for that category — mirrors
  `get_guidance()`'s shape discipline, pure function, no I/O.
- `citation()` — same style as health_guidance's, WHO/EPA-aligned framing.

## 2. API

New `GET /api/solutions?category=<key>` → `{category, solutions: [...], citation}`.
No dependency on live/archive AQI fetching itself — the frontend already knows
the current category from `/api/aqi` and just passes it through.

## 3. Frontend

New section `#solutions` on the dashboard (after `#health`, reusing the same
open-section pattern): 4 object-card tiles, each with a new monoline icon
(air purifier, car filter, N95 mask, house/stay-indoor), the solution name, a
status chip colored by urgency (reusing existing status-color language: green
for Not needed/Optional, amber for Recommended/Advised, rose for Must), and
the one-line tip. Re-renders whenever the AQI category changes (city switch),
same as the health panel — one fetch per category change, no per-click cost.

## 4. Testing

- `tests/test_solutions.py`: all 24 cells present, well-formed (`status` is a
  non-empty string from the allowed set, `tip` non-empty); `get_solutions`
  returns exactly 4 entries in a stable order; unknown category raises
  `KeyError`.
- `tests/test_solutions_api.py`: `/api/solutions?category=hazardous` returns 4
  solutions with a citation; unknown category returns an error response.
- Browser verification: 4 solution cards render with correct icons/status/tip
  for the current city's AQI category; status chip colors escalate correctly
  across cities of different severity; switching city updates the panel; no
  console errors.
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Out of scope

No purchase links/affiliate content (the reference site's "Get an Air
Purifier" CTAs are commercial upsells, not something VayuSense does). No
change to the health guidance module — this is a separate, independent panel.

## Success criteria

- 4 solutions × 6 categories, all real and distinct, escalating sensibly.
- Panel updates live with AQI category; zero LLM calls; deployed and verified.
