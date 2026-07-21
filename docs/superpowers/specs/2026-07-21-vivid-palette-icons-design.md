# Phase 6A: Vivid Color Refresh + Larger Icons — Design

**Date:** 2026-07-21
**Project:** VayuSense renovation, Phase 6A of 6 (aqi.in-inspired, round 2)
**Status:** Approved by user

## Purpose

User feedback: the current palette feels "too cool/corporate," referencing
aqi.in's more vivid, saturated color coding. This phase raises saturation/
brightness across the existing token set (same tokens, same meanings, more
vivid values) and scales up icon sizing wherever icons act as visual anchors,
without abandoning the dark "instrument panel" identity that differentiates
VayuSense from a generic dashboard.

## 1. Color value updates (DESIGN.md + both templates)

Update `colors:` values in DESIGN.md frontmatter and the corresponding CSS
custom properties in `index.html`/`landing.html` — same token names, same
semantic meaning, more saturated/brighter hex values:

- `signal-ok` (Good): `#4fe3ac` → `#3dfc9e` (brighter, more saturated green)
- `amber-caution` (Moderate): `#ffce80` → `#ffc247` (richer amber, less pastel)
- Ember (Poor): `#ffab73` → `#ff9640`
- `alert-rose` (Unhealthy): `#ff8aa3` → `#ff5c85`
- Magenta Signal (Severe): `#ef7ac8` → `#ef4fc0`
- Oxblood (Hazardous): `#b04a63` → `#c93a5a` (more vivid, still reads "danger"
  without becoming pure red — keeps the restrained-but-clear register)
- `ice-solid` (primary accent): `#9dc1ff` → `#7fb0ff` (more saturated blue)
- `ultraviolet`: `#b9a8fb` → `#a688fb`
- `photon-green`: `#9adb3f` → `#8ef22a`

Every value has been contrast-checked against `night-bg` (#0e1424) using the
WCAG relative-luminance formula: all nine colors clear 3.0:1 (the AA floor for
UI components/graphical objects), ranging from Oxblood's 3.70:1 up to Photon
Green's 13.01:1. No further checking needed at implementation time — these
exact hex values are final.

## 2. Icon sizing

- Pollutant cards (`.objCard` icon slots), city ranking-row icon badges, and
  health-condition tab icons scale up: existing `width/height` values
  increase ~30-35% (e.g. a currently-18px icon becomes ~24px, a 32px badge
  becomes ~42px), with surrounding padding adjusted so layouts don't break.
- Icons that are purely decorative accents (nav logo mark, footer) are
  unchanged — this is about icons that carry information (pollutant type,
  city, health condition), not chrome.

## 3. Testing

- Browser verification: computed colors on key elements (AQI ring, category
  chips, calendar cells, ranking rows) match the new hex values; icon sizes
  visibly larger at the specified anchors; contrast spot-checked against
  night-bg; no layout breakage from the size increase; no console errors.
- No backend changes, no new pytest surface.
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Out of scope

Calendar layout (6B), health advisory restructuring (6C), solutions panel
(6D), dashboard search (6E), character illustration (6F), and the generic/
detail page split (6G) are separate phases with their own specs.

## Success criteria

- All AQI-ramp and primary-accent colors read more vivid/saturated while
  keeping their existing meanings and WCAG-AA contrast against night-bg.
- Informational icons are visibly larger across pollutant cards, city rows,
  and health tabs.
- Deployed and verified live; no regressions.
