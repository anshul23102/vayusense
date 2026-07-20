# Phase 5C: Scroll-Motion Polish — Design

**Date:** 2026-07-20
**Project:** VayuSense renovation, Phase 5C (final phase)
**Status:** Approved by user

## Purpose

Every dashboard section already fades in as a whole block via the existing
`.reveal`/`IntersectionObserver` pattern, and smooth-scroll/reduced-motion handling
is already correct. The one remaining gap: repeating card grids that are rendered
via `innerHTML` (pollutant cards, city ranking rows, forecast-bench cards) pop in
all at once with no stagger, unlike the landing page's showcase tiles. This phase
closes that gap with one small, reusable, CSS-only entrance animation — no new
animation engine, no choreography, consistent with DESIGN.md's restrained-motion
principle.

## 1. Shared keyframe

One new CSS rule in `app/templates/index.html`:

```css
@keyframes cardIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.cardIn{animation:cardIn .35s cubic-bezier(.2,.8,.2,1) both}
```

Applied via an inline `style="animation-delay:{i*40}ms"` (or a small set of
`.cardIn.d0`..`.d9` delay classes, whichever is simpler to generate in the
existing template-string render code) on each item at render time, in:
- `renderShowcase`'s pollutant cards (`app/templates/index.html`'s pollutant grid
  render, inside `refresh()`)
- the city ranking table rows (`citiesTable` render, inside `refresh()`)
- the forecast-bench cards (`benchGrid` render, inside `refresh()`)

No change to the landing page — its showcase tiles already have staggered reveal
via the `d1`/`d2`/`d3` classes from Phase 5A.

## 2. Reduced motion

Add to the existing `@media (prefers-reduced-motion: reduce)` block in
`index.html`:

```css
.cardIn{animation:none !important;opacity:1 !important;transform:none !important}
```

so reduced-motion users see all cards immediately, fully rendered, no animation
frame ever applied — consistent with every other motion treatment already shipped.

## 3. Testing

- Browser verification: switching city causes the pollutant cards, ranking rows,
  and bench cards to visibly stagger in (short delay between each), not pop in
  simultaneously; reduced-motion emulation shows all cards immediately with no
  animation; no console errors; no layout shift (animation is opacity+translateY
  only, doesn't affect flow).
- No backend changes, no new pytest surface.
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Out of scope

No new animation system, no scroll-triggered parallax beyond what already exists,
no changes to landing.html (already has its own staggered reveal), no changes to
calendar cells or monthly chart bars (Plotly-rendered, out of scope for hand-written
CSS stagger).

## Success criteria

- Pollutant cards, ranking rows, and forecast-bench cards stagger in on render.
- Reduced motion disables it completely.
- No regressions; deployed and verified live.
