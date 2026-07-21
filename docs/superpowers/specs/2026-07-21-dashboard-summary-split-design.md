# Phase 6G: Generic Dashboard → Summary-Only Split — Design

**Date:** 2026-07-21
**Project:** VayuSense renovation, Phase 6G of 7 (round 2) — final sub-phase
**Status:** Approved by user (last item of the original bundled Phase 6 ask)

## Current state

`/dashboard` and `/city/{slug}` both render the exact same full-depth
`index.html` (`app/main.py:45-57`) — the only difference is which city is
pre-selected. So visiting the generic dashboard shows the same pollutant
cards, health guidance, solutions panel, calendar, trend/forecast/benchmark,
and chat as a specific city's page, just defaulted to Delhi. There is no
actual "summary" view today.

## Change

- **New template** `app/templates/summary.html`: a standalone, lighter page
  reusing the existing visual language (fonts, colors, aurora/grain/haze
  background, nav, reveal/cardIn motion, mood character) but showing only:
  nav (logo + city search), hero headline, the AQI ring + verdict + mood
  character + human-impact stat (`#overview`, trimmed — no KPI strip, since
  per-pollutant WHO comparisons are city-page depth), and the full "India's
  cities, ranked" table. No pollutant cards, health guidance, solutions,
  calendar, trend/forecast chart, benchmark comparison, or chat.
- `/dashboard` now serves `summary.html`. `/city/{slug}` is unchanged —
  still serves the full `index.html`, which remains the one place with full
  depth.
- Clicking any city (search result or ranking row) on the summary page does
  a real navigation to `/city/<slug>` (there's no in-page city-switch
  machinery on this lighter page — that's the whole point of the split).
- Default anchor city for the summary page's ring/impact stat stays Delhi,
  matching the existing default.

## Testing

- Browser verification: `/dashboard` shows only nav/hero/ring/impact/
  ranking, no pollutant/health/solutions/calendar/trend/chat sections;
  clicking a ranking row or search result navigates to `/city/<slug>` with
  full depth; `/city/<slug>` unaffected (still full page); no console
  errors.
- New pytest: `/dashboard` route returns the summary template (distinct
  from `/city/{slug}`'s), `/city/{slug}` behavior unchanged.
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify →
  commit → push.
