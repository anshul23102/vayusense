# Phase 4: Health-Condition Guidance + Motion Polish — Design

**Date:** 2026-07-20
**Project:** VayuSense renovation, Phase 4 of 5 (aqi.in-inspired)
**Status:** Approved by user

## Purpose

Add instant, deterministic per-condition health guidance (aqi.in's condition-tab
idea, done the "facts before advice" way: rule-based, not another LLM call) and a
scoped count-up animation treatment for the dashboard's three headline numbers
(AQI, cigarette-equivalent, life-expectancy impact).

## 1. Health-condition guidance panel

- **Data module** `agents/health_guidance.py` (pure Python, no I/O, no LLM):
  - `CONDITIONS = ["general", "children", "elderly", "asthma", "heart", "outdoor_workers"]`
    with human labels (`"General Population"`, `"Children"`, `"Elderly"`,
    `"Asthma / Respiratory"`, `"Heart / Cardiovascular"`, `"Outdoor Workers & Athletes"`).
  - `GUIDANCE: dict[str, dict[str, str]]` — one entry per condition, one string per
    AQI category key (`good/moderate/poor/unhealthy/severe/hazardous`, matching
    `agents/aqi.py`'s `CATEGORIES` keys exactly). Every cell is a short (1-2
    sentence), source-grounded recommendation. No cell may be empty or a generic
    fallback — 36 cells total (6 conditions × 6 categories), all authored.
  - `get_guidance(condition: str, category_key: str) -> str` — returns the cell, or
    raises `KeyError` for an unknown condition/category (callers validate before
    calling; no silent fallback that could hide an authoring gap).
  - `citation()` constant: `"Guidance keyed to WHO Air Quality Guidelines and US EPA AQI category thresholds for sensitive groups."`
- **API**: none new. The dashboard already fetches `/api/aqi` (category) once per
  refresh; the guidance panel is a pure client-side lookup once condition tabs are
  populated from a small inlined JSON the template embeds at render time (same
  pattern as no new round-trip is needed — see Frontend below).
- **Frontend** (`app/templates/index.html`): new open section `#health` after
  `#pollutants`. Tab row of the 6 condition labels (first tab active by default:
  "General Population"). Below: the guidance text for `(activeCondition,
  currentCategory)`, the citation line, and a small icon per condition reusing the
  existing icon sprite technique (new symbols `ic-child`, `ic-elder`, `ic-asthma`,
  `ic-heart`, `ic-worker`, plus `ic-lungs` already exists and is reused for
  "general"). Switching tabs or switching city/AQI category re-renders instantly
  (no fetch). To avoid a template-to-JS data duplication trap, the guidance table
  is embedded once as a `<script type="application/json" id="healthData">` block
  rendered server-side from `agents/health_guidance.py` (main.py exposes it via a
  tiny `GET /api/health_guidance` JSON endpoint fetched once on page load, cached
  in a JS variable — simpler than templating raw Python dicts into HTML, and keeps
  the single source of truth in the Python module).

## 2. Cigarette-equivalent + headline count-up animation

- One shared JS utility, `countUp(el, target, {duration=900, decimals=0})`,
  respecting the existing `reduceMotion` flag (module-level const already in
  `index.html`): under reduced motion, sets the final value immediately with no
  intermediate frames.
- Applied to three elements on each `refresh()`/impact update: `#aqiVal` (AQI
  ring number), `#impCig` (cigarette-equivalent, decimals=1 to match existing
  formatting), `#impYears` (life-expectancy years, decimals=2). Re-triggering on
  every city switch (animates from the previous value, not from zero, so rapid
  switching doesn't feel like a reset-and-replay).
- **Smoke-puff accent**: a small CSS-only looping animation (2-3 `border-radius`
  blobs with fade/rise `@keyframes`, ~2.4s loop, `opacity` only — no layout shift)
  positioned next to the cigarette stat. Disabled entirely (`display:none` or
  `animation:none`) under `prefers-reduced-motion`, consistent with every other
  motion treatment already in the codebase.

## 3. Scope guards

- No new agent tools, no new LLM calls anywhere in this phase.
- No changes to the forecast bench, calendar, trends, or ranking table beyond
  what's needed for the new section's placement.
- Motion additions are strictly the count-up + smoke-puff; no new choreography,
  parallax, or scroll-triggered effects beyond the existing `.reveal` pattern.

## 4. Testing

- `tests/test_health_guidance.py`: every condition × every category returns a
  non-empty string; `get_guidance` raises `KeyError` for unknown inputs; no two
  cells for the same condition are byte-identical across all 6 categories (catches
  lazy copy-paste that would defeat the purpose of per-severity guidance);
  `citation()` is non-empty.
- `tests/test_health_guidance_api.py`: `GET /api/health_guidance` returns the full
  36-cell table plus condition labels and the citation string.
- Browser verification: tab switching updates guidance instantly with no flash of
  missing content; changing city/category updates the currently-active tab's text;
  count-up animates on load then holds the exact target value (verified via final
  `textContent`, not just visually); reduced-motion disables both the count-up
  animation and the smoke-puff loop (verified via computed style / instant final
  value with no intermediate frame check needed).
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Success criteria

- All 36 guidance cells are distinct, sourced, and instant (no network latency per
  tab click).
- AQI, cigarette, and life-expectancy numbers animate on load/update and land on
  the exact correct value every time.
- Reduced-motion users see no animation anywhere in this phase's additions.
- All tests green; deployed and verified live.
