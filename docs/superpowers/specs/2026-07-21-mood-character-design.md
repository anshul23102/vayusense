# Phase 6F: Mood Character + Smoke Animation — Design

**Date:** 2026-07-21
**Project:** VayuSense renovation, Phase 6F of 7 (round 2)
**Status:** Approved by user (hand-built flat-design SVG, 3 mood states, confirmed via AskUserQuestion earlier this session — no AI image-generation tool is available in this environment)

## Purpose

Bring the mood-character illustration from the original bundled ask into
the hero/overview section — an illustration whose expression/pose changes
with the current AQI severity. (The other animation request, cigarette
smoke rising from the "cigarette-equivalent exposure" stat, turns out to
already be shipped: `.smokeWrap`/`.puff`/`@keyframes puffRise` at
`app/templates/index.html:177-183`, wired into `impCig` at line 714,
already reduced-motion-safe at line 199. Nothing to do there — this phase
is scoped down to the mood character only.)

## 1. Placement

- **Mood character**: inside the existing `.s6` block that holds the AQI
  ring (`#overview` → first `.s6`, around `app/templates/index.html:276`),
  to the right of `.scoreWrap`, so the character sits beside the ring it's
  reacting to. No new card wrapper — per DESIGN.md's "Boxes are for
  objects, not sections" rule this is a supporting illustration inside an
  existing object area, not its own section.
- **Smoke**: rises from a small cigarette glyph inside the existing
  `impCig` impact-stat card (second `.s6`, `#impCig`'s container), reusing
  that card rather than adding a new one.

## 2. Mood states

Three hand-built flat-design SVG states, swapped by `<use>`-ing a
different `<symbol>` based on `CURRENT_CATEGORY_KEY` (already computed by
every render path per Phase 6C/6D):

- **Happy** (`good`, `moderate`): upright posture, open smiling mouth,
  relaxed raised arms.
- **Neutral/uneasy** (`poor`, `unhealthy`): flat mouth, one hand near
  chest, slightly hunched.
- **Coughing/distressed** (`severe`, `hazardous`): hunched forward, hand
  over mouth, furrowed brow, small motion-line accents.

All three share the same ~80x100 viewBox, silhouette proportions, and
stroke weight so swapping states never shifts layout. Fill uses the
current AQI category color (`var(--...)` per the AQI Ramp) for the
character's accent (e.g. a scarf/shirt patch), body/skin in neutral Ink
tones — the character itself must never imply a race or specific person,
kept abstract/rounded per a mascot register consistent with the rest of
the icon system (`ic-*` symbols already in the file).

## 3. Smoke animation

Already shipped (see Purpose above) — no work needed this phase.

## 4. Behavior

- Both the mood character and smoke are static SVG markup already present
  in the DOM; only the mood character's active `<use href>` symbol
  changes on category change (driven from the same `refresh()` /
  `renderHealthPanel()` category-resolution path already in place — no new
  fetch).
- No backend changes, no new API surface.

## 5. Testing

- Browser verification: switching city/category (e.g. a clean city vs. a
  hazardous one) swaps the mood character's pose/expression; smoke wisps
  animate continuously and respect `prefers-reduced-motion`; no console
  errors; no layout shift between mood states.
- No new pytest surface (pure template/CSS/JS change).
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify →
  commit → push.

## Success criteria

- The hero section has a working, severity-reactive mood character and a
  smoke-rising accent on the cigarette-equivalence stat, both respecting
  DESIGN.md's existing color, motion, and "boxes are for objects" rules.
