# Phase 2: Typography/Shape Overhaul + The City Record — Design

**Date:** 2026-07-20
**Project:** VayuSense renovation, Phase 2 of 5 (aqi.in-inspired)
**Status:** Approved by user

## Purpose

Kill the generic look (Inter + uniform glass boxes) and add the analytical depth of a
real city record: per-pollutant sub-AQI cards, a full Air Quality Calendar, and
monthly/annual trend analysis. Inspired by aqi.in's information richness and severity-
color fluency — rendered in VayuSense's own clinical night-glass identity, not their
consumer-app cuteness.

## 1. Typography system

- **Space Grotesk** (weights 500/600/700): all display — h1/h2, the hero AQI number,
  every stat numeral (KPI values, impact numbers, bench MAEs, calendar cells' numbers
  use it at small size). `font-variant-numeric: tabular-nums` on stat numbers.
- **IBM Plex Sans** (400/500/600): body, labels, buttons, chat, captions.
- Inter is removed from both templates (link + all font-family declarations).
- Both loaded from Google Fonts with `display=swap`.
- DESIGN.md §3 Typography rewritten accordingly; frontmatter tokens updated.
- `.impeccable/config.json`: drop the old Inter ignore-value if present; add none.

## 2. Shape language: "Boxes are for objects, not sections"

New DESIGN.md Named Rule with exactly that name. Concretely:

- **Open sections:** trend chart, Air Quality Calendar, monthly/annual trends, and
  the forecast-bench scoreboard sit directly on the night background as `.section`
  blocks: `border-top: 1px solid var(--line)`, generous vertical padding, no card
  wrapper, no blur. The hero (AQI number + scale) also goes open — the number IS the
  design.
- **Object cards only:** pollutant cards, city tiles (Phase 3), forecast-method
  chips, impact stats. Restyle: radius 14px (was 22px), flatter fill
  `rgba(255,255,255,.035)`, no gradient-border pseudo-element, and a 3px left
  severity edge-bar (`border-left: 3px solid <band color>`) where the object has a
  severity.
- The chat panel keeps a soft container (conversation needs containment) at the new
  flatter style. Aurora/haze/grain backgrounds stay — they're distinctive, not generic.
- KPI strip and Human-impact stats become open rows with hairline separators, not
  boxes-in-a-box.

## 3. Major Pollutants section (new)

Six object cards (pm25, pm10, no2, o3, so2, co): concentration + unit (Space
Grotesk), per-pollutant **sub-AQI** with band label (from `/api/aqi` `sub_aqi`),
severity edge-bar in the band color, WHO multiple + trend arrow (from
`/api/snapshot`). Clicking a card selects that pollutant (drives the existing
`paramSel`) and scrolls to the trend section. Data basis label shown once for the
section (live sub-AQIs when hero is live, archive otherwise — same source as hero).

## 4. Air Quality Calendar (new, the showpiece)

- **Backend:** `GET /api/calendar?city=&year=` → for each archive day in that year:
  overall EPA-method AQI across pollutants (daily-average basis, labeled).
  Response: `{city, year, years_available, basis, days: [{date: "YYYY-MM-DD",
  aqi: int, key: "poor"}]}`. lru-cached per (city, year). 404-style JSON error for
  unknown city/year.
- **Frontend:** 12 month-grids (Sun-first columns, weekday header), each day a cell
  tinted with its band color (ramp at ~85% strength, readable numeral inside in
  Space Grotesk small), missing days hollow. Year toggle chips (2024 / 2025,
  driven by `years_available`). A compact ramp legend below (band label + range).
  Fully archive-framed ("EPA-method daily AQI from the archive").

## 5. Monthly & annual trends (new)

- **Backend:** `GET /api/monthly?city=` → `{city, basis, months: [{month: "2024-01",
  avg_aqi: int, key: band}], most_polluted: {month, avg_aqi}, least_polluted: {...},
  annual: [{year, avg_aqi}], annual_change_pct: float}` (change = last year vs
  first year). lru-cached per city.
- **Frontend:** Plotly bar chart of monthly averages, each bar colored by its band
  (ramp), hover shows month + AQI + band; two callout stat blocks (most/least
  polluted month); an annual line: "2024 avg 172 → 2025 avg 158 · 8% improvement"
  with the direction stated in words.

## 6. Section subnav

Slim sticky chip-row under the main nav: Overview · Pollutants · Calendar · Trends ·
Forecast bench · Ask — anchor links to section ids, active state on scroll not
required (keep it simple: hover/focus states only).

## 7. Scope guards

- Landing page: typography swap only (de-boxing it is Phase 3).
- No new agent tools this phase (agents already speak AQI); calendar/monthly are
  dashboard analytics.
- Forecast bench, chat, human-impact content unchanged (restyled only).

## 8. Testing

- `tests/test_calendar_api.py`: Delhi 2025 has ≥300 day entries, every `aqi` int>0,
  every `key` in the 6 bands, unknown city → error JSON, `years_available` correct.
- `tests/test_monthly_api.py`: months sorted, avg mathematically consistent with
  calendar days for a spot month, most/least correct extremes, annual change matches
  annual averages.
- Browser verification: computed font-family actually reports Space Grotesk / IBM
  Plex Sans (not vibes); calendar renders 12 grids with colored cells; pollutant
  card click switches trend; no console errors; reduced-motion unaffected.
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Success criteria

- Inter appears nowhere; Space Grotesk/IBM Plex Sans render on both pages.
- Sections are open (hairline-separated); only objects have cards; severity
  edge-bars use the AQI Ramp.
- Calendar + monthly trends live with honest archive basis labels.
- All tests green; deployed and verified live.
