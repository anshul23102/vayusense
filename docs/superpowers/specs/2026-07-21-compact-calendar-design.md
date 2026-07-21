# Phase 6B: Compact Calendar Redesign — Design

**Date:** 2026-07-21
**Project:** VayuSense renovation, Phase 6B of 6 (round 2)
**Status:** Approved by user

## Purpose

The current Air Quality Calendar renders all 12 months of the selected year in a
responsive grid simultaneously, consuming a large amount of vertical space. The
reference screenshots show a much tighter paged view: two months visible at a
time with prev/next navigation. This phase rebuilds the calendar's rendering
around that paged layout while keeping the exact same underlying data
(`/api/calendar`, unchanged) and the same per-day color/value cells already built.

## 1. Paged 2-month view

- `renderCalendar()` keeps fetching the full year's data from `/api/calendar` as
  today, but only renders **2 months at a time** into `#calGrid` instead of all
  12 (or fewer, if a year has less real data — same "empty cell" handling as
  today for a month with zero days).
- New state: `CAL_PAGE_START` (0-11, the first of the two months on screen).
  Defaults to the pair ending at the **most recent month with real data** for
  the selected city/year (so the calendar opens on the most relevant months, not
  always January), clamped so the page never runs past month index 11.
- Prev/next arrow buttons (◀ ▶) step `CAL_PAGE_START` by 2, disabled/dimmed at
  the boundaries (page start ≤ 0 disables prev; page start + 2 ≥ 12 disables
  next). Clicking re-renders only the grid, not a full data refetch.
- Switching year or city resets `CAL_PAGE_START` to the new default (most
  recent populated pair) rather than preserving the old page index.

## 2. Layout

- Two `.calMonth` blocks side by side (existing month-grid cell rendering
  unchanged — day-of-week header, color-filled day cells with AQI numbers)
  inside a flex/grid row, with the prev/next arrows and a page indicator
  ("June – July 2025" style label, matching the reference) above them.
- Legend row (band colors + ranges) stays below, unchanged.
- Year toggle chips stay above, unchanged.

## 3. Testing

- Browser verification: only 2 months render at once; the shown pair defaults to
  the most recent real data; clicking next/prev moves by exactly 2 months and
  updates the visible label; arrows disable correctly at year boundaries;
  switching city or year resets to the new default pair; no console errors; no
  new network calls on prev/next (data already fetched, just re-rendered).
- No backend changes, no new pytest surface — `/api/calendar` is unchanged.
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Out of scope

`/api/calendar` itself, the year toggle mechanism, the legend, and per-day cell
rendering are all unchanged — this phase only changes how many months are
visible at once and adds paging controls.

## Success criteria

- Calendar's vertical footprint drops dramatically (2 months visible instead of
  up to 12).
- Paging is smooth, correctly bounded, and defaults to the most relevant months.
- Deployed and verified live; no regressions.
