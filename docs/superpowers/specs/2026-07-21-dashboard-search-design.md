# Phase 6E: Dashboard Search Bar — Design

**Date:** 2026-07-21
**Project:** VayuSense renovation, Phase 6E of 6 (round 2)
**Status:** Approved by user

## Purpose

The landing page already has a city search (Phase 5A). The dashboard itself
(`index.html`) only has a plain `<select>` dropdown for city choice. Add the
same autocomplete search experience to the dashboard nav, honestly scoped to
the 10 tracked cities exactly like the landing page's — but selecting a result
does an in-page city switch (`selectCity()`, no reload) since the user is
already on the dashboard, rather than a full navigation.

## 1. Markup

A `.searchWrap`/`.searchInput`/`.searchDrop` group (same CSS classes/behavior
as `landing.html`'s, copied into `index.html`'s stylesheet) placed in the nav's
`.right` group, before the city `<select>` — the select stays as a fallback/
explicit picker, the search is the fast path.

## 2. Behavior

- Autocomplete list sourced from the already-loaded city list (`loadCities()`
  already populates `citySel`'s options — the search reuses that same array,
  no new fetch).
- Typing filters; arrow keys + Enter navigate the list, matching the landing
  page's exact interaction (same `filterSearch`/`searchKeydown` logic,
  adapted to call `selectCity(name)` instead of `goToCity(name)`).
- Selecting a result calls `selectCity(name)`, which already updates `CITY`,
  the `<select>`, the URL (`syncCityUrl`), and re-renders every section — no
  new re-render logic needed, this phase only wires the input to that
  existing function.

## 3. Testing

- Browser verification: typing filters to only real tracked cities; selecting
  a result switches the dashboard in place (no page reload, URL updates to
  `/city/<slug>`); keyboard navigation (arrow keys + Enter) works; dropdown
  closes on outside click; no console errors.
- No backend changes, no new pytest surface.
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Success criteria

- Dashboard has a working, honestly-scoped city search identical in feel to
  the landing page's, wired to the existing in-page city-switch path.
