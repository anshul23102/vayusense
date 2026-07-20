# Phase 5A: Landing Page Redesign — Design

**Date:** 2026-07-20
**Project:** VayuSense renovation, Phase 5A of 5 (aqi.in-inspired)
**Status:** Approved by user

## Purpose

The landing page (`app/templates/landing.html`) still pitches the pre-renovation
MVP: a generic score, human-impact stats, and a GPU-benchmark story. It says
nothing about the Forecast Bench, the Air Quality Calendar, the 10-city ranking
table, or the health-guidance panel shipped in Phases 1-4. This phase rewrites the
landing page's content to actually showcase what exists, adds a city search bar
and a simple India map picker (both honestly scoped to the 10 cities we track),
extends the existing reveal-animation pattern to the landmark/health icons, and
closes with a short audit confirming the hackathon's original evaluation criteria
are still concretely met underneath all the polish.

## 1. Content refresh (`app/templates/landing.html`)

Add/rewrite feature blocks (each pulling one real, live number via a small fetch
on page load — never a hardcoded stat that could drift from reality):

- **Forecast Bench** block: "Four models compete on real data" — fetches
  `/api/forecast_bench?city=Delhi&parameter=pm25` on load and shows the winning
  method's name and its backtest MAE live in the copy.
- **Air Quality Calendar** block: a static preview (a few sample colored day-cells
  reusing the AQI Ramp, non-interactive — the real calendar lives on the
  dashboard/city pages) with copy pointing at what it is.
- **City ranking** block: fetches `/api/aqi?city=Delhi` and shows the current
  #1-ranked city and its AQI live, with the landmark icon for that city.
- **Health guidance** block: shows 2-3 of the 6 condition icons with a one-line
  teaser ("Guidance for asthma, heart conditions, children, and more — instant,
  zero-latency, WHO/EPA-grounded").
- Existing GPU-benchmark and human-impact sections stay (still accurate, still
  differentiated) but move later in scroll order, after the above.

## 2. City search bar

- A single `<input>` in the nav or hero, backed by a client-side autocomplete
  over the city list fetched once from `/api/cities` on page load (the same
  endpoint the dashboard already uses) — never a hardcoded copy, so the list can
  never drift from the real dataset.
- Typing filters a dropdown of matches; no free-text "search any location"
  promise anywhere in the copy — the placeholder explicitly says "Search one of
  10 tracked Indian cities."
- Selecting a result navigates to `/dashboard?city=<name>` (5B's dedicated
  `/city/<slug>` pages will become the target once shipped; this phase wires the
  interaction against the URL scheme that exists today so it's never a dead
  click).

## 3. India map picker

- One hand-authored SVG outline of India (simplified, low-detail path — a
  recognizable silhouette, not survey-accurate), `viewBox` sized to place 10
  dots by approximate relative position (Delhi north, Kolkata east, Chennai
  south-east, Mumbai west, etc. — relative placement only, not precise
  lat/long projection).
- Each dot fetches its city's AQI band color from the same `/api/aqi` ranking
  data already used elsewhere (one fetch, shared across search/map/ranking
  blocks — no duplicate network calls).
- Click a dot → same navigation as search. Hover shows a tooltip with city name
  + current AQI. Keyboard-focusable (`<button>` per dot, not bare `<circle>`
  click handlers) for accessibility.

## 4. Icon animation pass

- Reuse the existing `.reveal` + `IntersectionObserver` pattern (already in both
  templates) — apply it to the landmark icon in the ranking block and the
  health-condition icons in the health teaser, so they fade/scale in on scroll
  like the rest of the page's elements already do. No new animation system;
  this phase is application, not invention.
- Add one new shared micro-interaction: icon badges get a hover
  scale(1.05)+lift, matching the existing `.card:hover`/`.objCard:hover` language
  from Phase 2/3 — consistent, not novel.
- Everything gated by the existing `reduceMotion` check in both templates.

## 5. Hackathon-alignment audit

A short reviewed checklist (in the spec's Success Criteria, not new code)
cross-referencing `PRODUCT.md`'s stated positioning and the four evaluation
criteria (Solution Architecture & Technical Execution; Innovation Quality &
Functional Depth; Real-world Impact & Applicability; UX/Presentation/Technical
Feasibility) against what has actually shipped through Phase 4, to confirm nothing
core was lost while iterating on polish.

## 6. Testing

- Browser verification: typing in the search filters correctly and only ever
  shows the 10 real tracked cities; selecting a result or clicking a map dot
  navigates correctly; map dot colors match live `/api/aqi` ranking data; all
  landing-page live-fetched numbers match their source endpoints exactly (no
  rounding/formatting drift); reveal/hover animations respect reduced-motion;
  no console errors.
- No new pytest surface — this phase is frontend content/interaction only, no
  new backend endpoints (everything consumed already exists: `/api/cities`,
  `/api/aqi`, `/api/forecast_bench`).
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Out of scope (later phases)

Dedicated `/city/<slug>` pages are Phase 5B. Scroll-triggered motion polish
across the whole app is Phase 5C (the original "Phase 5"). No dashboard changes
in this phase — landing.html only.

## Success criteria

- Landing page visibly showcases the Forecast Bench, Calendar, City Ranking, and
  Health Guidance features with real, live numbers.
- Search and map picker are both honestly scoped to exactly the 10 tracked
  cities — never imply broader coverage.
- Landmark/health icons animate in via the existing reveal pattern; hover
  micro-interaction matches the established card-hover language.
- Hackathon-alignment audit completed and confirms no regression against
  `PRODUCT.md`'s stated criteria.
- Deployed and verified live; no console errors; reduced-motion respected.
