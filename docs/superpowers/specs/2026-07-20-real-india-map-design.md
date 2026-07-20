# Phase 5D: Real India Map + 3D Tilt — Design

**Date:** 2026-07-20
**Project:** VayuSense renovation, Phase 5D (map fix, inserted before 5C)
**Status:** Approved by user

## Purpose

Replace the hand-drawn, unrecognizable India outline shipped in Phase 5A with an
accurate silhouette generated from real public geographic boundary data, projected
into the same SVG viewBox the map already uses. Add a genuine 3D tilt interaction
(mouse-driven perspective rotation, hover-lift on city dots, grab cursor on drag)
by extending the codebase's own existing `.tilt` pattern — no new external library,
no WebGL, keeping risk low with the deadline close.

## 1. Real boundary data

- Source: India's national border polygon from the public `world.geo.json`
  country-boundary dataset (`IND.geo.json`), a single 136-point ring covering the
  mainland — factual geographic boundary data, the same category of data every
  mapping library ships, not creative content.
- One-time offline projection (`ml/` or a throwaway script, not part of the served
  app): equirectangular projection of the ring's (lon, lat) points into the
  existing `viewBox="0 0 300 340"`, preserving true aspect ratio (scaled to fit
  with 12px padding on all sides, centered — not stretched to fill).
- The 10 city dot coordinates are regenerated from the **same real (lon, lat)**
  values already used in `ingest/discover_live_locations.py`'s `CITY_QUERIES`,
  run through the identical projection function — so city dots land in genuinely
  correct relative positions on the real outline instead of hand-guessed spots.
- Output: one SVG path string (replaces the current hand-drawn `<path d="...">`
  in `landing.html`) and one `CITY_COORDS` JS object (replaces the current
  hand-guessed one) — both computed together so they share the exact same
  projection and can never drift apart.

## 2. 3D tilt (reusing the existing pattern, not a new library)

- The `.mapWrap` container gets the same treatment already proven on
  `landing.html`'s `.tilt` feature cards: on `mousemove` over the map, compute
  cursor position relative to the element's bounding box and apply
  `perspective(900px) rotateY(±deg) rotateX(∓deg)`; on `mouseleave`, clear the
  transform for a spring-back to flat.
- Slightly larger rotation range than the feature cards (the map is a bigger,
  more central element) — tune by feel, capped low enough to stay legible (dots
  and labels must not visually swim).
- `mousedown`/`mouseup` toggle a `grabbing` class that swaps the cursor to
  `grabbing` and increases the tilt sensitivity slightly while held, giving a
  tactile "you can grab this" feel without implementing free-rotation drag
  physics.

## 3. Hover depth on city dots

- On a dot's `:hover`/`:focus`, it scales up (already partially present:
  `.mapDot:hover circle{r:8}`) and gains a soft `filter: drop-shadow(...)` that
  reads as lifting toward the viewer, plus its label brightens from `--dim` to
  `--txt`. Pure CSS, no JS change needed beyond what Phase 5A already added.

## 4. Reduced motion

- The tilt `mousemove`/`mousedown` listeners are gated behind the existing
  `reduceMotion` const (already used to skip `.tilt` cards' listeners entirely) —
  under reduced motion, the map stays flat and fully clickable, exactly like the
  rest of the page's motion.

## 5. Testing

- Browser verification: the rendered outline is visibly recognizable as India
  (spot-check silhouette shape — northern land mass, western coastline bulge,
  southern peninsula tapering to a point, not a generic blob); all 10 dots sit in
  correct relative geography (Delhi north, Chennai/Bengaluru south, Mumbai/
  Ahmedabad west coast, Kolkata/Patna east); moving the mouse over the map tilts
  it smoothly and it springs back flat on mouse-leave; hovering a dot lifts it
  with a shadow; mousedown shows a grab cursor; reduced-motion disables tilt
  entirely while dots stay clickable; no console errors.
- No backend changes, no new pytest surface (frontend-only, same as 5A).
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Out of scope

Full WebGL/Three.js globe (explicitly declined in favor of this lower-risk
approach). Free-rotation drag. Any change to search, showcase tiles, or the
`/city/<slug>` pages from Phases 5A/5B.

## Success criteria

- The map is unmistakably India, not an abstract shape.
- All 10 city dots are placed via the same real coordinates already used
  elsewhere in the codebase (`ingest/discover_live_locations.py`), not
  hand-guessed pixel positions.
- Tilt, hover-lift, and grab-cursor all work and all respect reduced-motion.
- Deployed and verified live.
