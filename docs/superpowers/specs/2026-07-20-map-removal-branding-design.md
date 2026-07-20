# Phase 5E: Remove Map, Add City Chip Grid, Strengthen Branding — Design

**Date:** 2026-07-20
**Project:** VayuSense renovation, Phase 5E
**Status:** Approved by user

## Purpose

Remove the India map entirely (user judged it not worth the risk/effort even after
the real-geography fix) and replace it with a non-map way to browse the same 10
cities. Separately, give the "VayuSense" brand more visual presence — it currently
reads as a small nav-corner wordmark — without turning the page loud.

## 1. Remove the map

Delete from `app/templates/landing.html`:
- The `#map` `<section>` (kicker, h2 "Ten cities. One tap away.", lead paragraph,
  `.mapWrap`/`#indiaMap` SVG and its path/dots group).
- `CITY_COORDS`, `renderMap()`, and the `.mapWrap` mousemove/mouseleave/mousedown/
  mouseup tilt listener block.
- CSS: `.mapWrap`, `.mapWrap.grabbing`, `.mapDot` rules, and the
  `prefers-reduced-motion` override line for `.mapWrap`.
- The `loadLandingData()` call to `renderMap()`.

## 2. Replace with a city chip grid

New section (same position in scroll order, right after `#showcase`): a kicker
("Pick a city"), heading, and a responsive grid of 10 chips — one per tracked
city — each built from data already in `LANDING_DATA.ranking` (no new fetch):
landmark icon (`cityIcon()`), city name, live/archive AQI number (Space Grotesk,
tabular), and a category-colored dot + label (`bandOf()`). Clicking a chip calls
the existing `goToCity(name)` → `/city/<slug>`. Chips are `.showTile`-style flat
objects (matches Phase 5A's established card language exactly — no new visual
system), in a `repeat(auto-fill,minmax(150px,1fr))` grid so 10 chips wrap cleanly
at any width. Reveal-in animation reuses the existing `.reveal`/`io` pattern.

## 3. Strengthen branding

- Nav wordmark: increase `.logo` font-size from 18px to 21px, weight from 650 to
  700, and give `.logo .dot` a slightly stronger glow (`box-shadow` intensity up)
  so the mark reads with more confidence at a glance — still a nav-corner
  lockup, just no longer whispering.
- Hero: add one line repeating the full product name in the hero itself, not just
  the nav — e.g. a small kicker-style label above the `<h1>` reading
  "VAYUSENSE" (uppercase, tracked, in the existing `.kicker` treatment already
  used elsewhere) so a visitor's first eyeful includes the name, not only "Know
  when the air is safe." This is additive (one new element), not a restructuring
  of the existing hero headline/subhead/CTA.
- No color, font, or shape-system changes — brand strengthening stays inside
  DESIGN.md's existing tokens (Space Grotesk for the name treatments, existing
  Ice/Ultraviolet palette), per the "Two Voices"/"boxes are for objects" rules
  already established.

## 4. Testing

- Browser verification: `#map`/`indiaMap`/`mapDots`/`CITY_COORDS`/`renderMap` no
  longer exist anywhere in the served HTML/JS; the new city chip grid renders 10
  chips with correct live AQI/category/icon per city and each navigates to the
  right `/city/<slug>` on click; nav wordmark and hero kicker render at the new
  sizes; no console errors; reduced-motion still behaves correctly (no leftover
  map-related media-query rules referencing removed selectors).
- No backend changes, no new pytest surface (frontend-only, consistent with 5A/5D).
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Out of scope

Any other landing-page section (search bar, showcase tiles, footer) beyond what's
listed above. No further map/geography experiments this renovation.

## Success criteria

- Map, its data, its JS, and its CSS are fully removed — zero dead code left behind.
- All 10 cities are still one click away from the landing page, via chips instead
  of a map.
- The VayuSense name has a clear, deliberate presence in both the nav and the
  hero, without adding new colors/fonts/shapes outside DESIGN.md.
- Deployed and verified live; no console errors.
