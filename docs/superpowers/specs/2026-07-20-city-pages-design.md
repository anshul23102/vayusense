# Phase 5B: Dedicated City Pages — Design

**Date:** 2026-07-20
**Project:** VayuSense renovation, Phase 5B of 5
**Status:** Approved by user (approach chosen during Phase 5 decomposition)

## Purpose

Give each tracked city a real, distinct, shareable URL (`/city/delhi`, `/city/mumbai`,
...) instead of only `/dashboard?city=X`, satisfying "clicking a city should take you
to a dedicated page" — while reusing the existing, working single-page dashboard
entirely (same template, same JS, same sections) to keep risk low with the deadline
close. In-dashboard city switches (ranking table row, search, pollutant cards) also
start updating the browser URL via `history.pushState`, so the back button and
bookmarking work consistently everywhere, not just on first load.

## 1. Backend route

- New `GET /city/{slug}` in `app/main.py`. Case-insensitively matches `slug` against
  `data_tools.list_cities()`'s real city names (all single-word today: Delhi,
  Mumbai, Kolkata, Chennai, Bengaluru, Hyderabad, Pune, Ahmedabad, Lucknow, Patna).
  - Match found: read `index.html`'s text (same as `/dashboard`) and replace the
    single occurrence of `let CITY='Delhi';` with `let CITY='<RealCityName>';`,
    return as `HTMLResponse`.
  - No match: `JSONResponse({"error": f"unknown city '{slug}'"}, status_code=404)`.
- `/dashboard` and `/dashboard?city=X` continue to work unchanged (no removal of the
  existing route) — `/city/<slug>` is an additional, not replacement, entry point.

## 2. Frontend: URL sync on in-page navigation

- In `index.html`, wherever a city switch already happens in-place today
  (`selectCity()` used by the ranking table, and the search/pollutant-card click
  handlers that set `CITY` directly), add one line calling
  `history.pushState({}, '', '/city/' + city.toLowerCase())` after the switch, so
  the address bar reflects the current city without a page reload.
- `document.title` updates to `` `VayuSense — ${CITY} Air Quality` `` on every city
  switch (cheap, real nicety for tab-switching/bookmarking).
- Handle the browser back/forward buttons: a `popstate` listener re-reads the city
  from `location.pathname` and calls the existing in-place switch logic (no reload),
  so back/forward feels instant rather than triggering a full page fetch.

## 3. Frontend: landing page links to real city pages

- `app/templates/landing.html`'s `goToCity(name)` (added in Phase 5A) changes from
  `location.href = '/dashboard?city=' + name` to
  `location.href = '/city/' + name.toLowerCase()` — search results and map dots now
  land on the dedicated page.

## 4. Testing

- `tests/test_city_pages.py`: `/city/delhi` returns 200 and its HTML contains
  `let CITY='Delhi';`; `/city/DELHI` (case-insensitive) also resolves to Delhi;
  `/city/mumbai` contains `let CITY='Mumbai';`; `/city/atlantis` returns 404 with an
  error body; `/dashboard` (no slug) still returns 200 unchanged.
- Browser verification: navigating to `/city/chennai` loads the dashboard pre-set to
  Chennai (hero, ranking highlight, chart all show Chennai on first paint, no flash
  of Delhi-then-Chennai); clicking a different city in the ranking table updates the
  URL to `/city/<that city>` without a full page reload; browser back button returns
  to the previous city without a network fetch delay; landing page search/map now
  land on `/city/<slug>` URLs.
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Out of scope

Phase 5C (scroll-motion polish) remains the final phase after this one. No SEO
sitemap/meta-tag work beyond the `document.title` update. No change to the
`/dashboard?city=` query-param path — it stays as a working alternate entry point.

## Success criteria

- All 10 cities have a working `/city/<slug>` URL that pre-loads correctly.
- Unknown slugs 404 cleanly.
- In-dashboard navigation keeps the URL in sync without reintroducing full-page
  reloads for city switches.
- All existing tests still pass; new tests for the route pass; deployed and
  verified live.
