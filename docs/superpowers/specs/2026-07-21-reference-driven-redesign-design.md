# Reference-Driven Redesign (Phases A-D) — Design

**Date:** 2026-07-21
**Project:** VayuSense — post-Phase-6 polish pass, referencing hack2skill.com/event/apac-genaiacademy
**Status:** Approved by user (phase order and Onest font substitute confirmed via AskUserQuestion)

## Reference site findings (inspected directly, not guessed)

`hack2skill.com`'s APAC Gen AI Academy page, checked via computed styles:
- Font: `Google_Sans_Medium` / `Google_Sans` — Google's proprietary internal
  typeface, self-hosted by Google properties. Not freely licensable for
  third-party redistribution, so not something VayuSense can embed directly.
- Hierarchy is single-family, weight/size-driven: H2 ("Overview") 30px/700,
  H3 ("Cohort 1") 20px/700, body paragraphs 14px/400 in a muted
  `rgb(74,74,74)` secondary tone against white.
- Pill-shaped buttons/tags (`border-radius: 9999px`), 16px-radius cards,
  generous section whitespace, colored card outlines using Google's own
  brand colors (`#EA4335` red seen directly, implied blue/yellow/green
  siblings).

## Decision (confirmed with user)

Keep VayuSense's dark "Night Watch" palette exactly as-is — it already has
WCAG-verified contrast values and named color rules built up over multiple
phases this session, and re-theming light would discard that work and
would mean visually adopting another product's actual brand colors.
Borrow only the **hierarchy discipline, spacing, and font feel**.

## Phase A: Typography overhaul

- Replace the current two-family pairing (Space Grotesk for
  headlines/numbers, IBM Plex Sans for body — DESIGN.md's "Two Voices
  Rule") with a **single family, Onest** (free on Google Fonts, built as an
  open alternative to Google Sans with the same rounded-geometric
  proportions), with hierarchy driven by weight and size instead of a
  family switch — matching the reference's actual approach.
- Recalibrate the size/weight ramp to mirror the reference's more
  confident jumps (bigger headline-to-body size delta, heavier weight on
  section titles) rather than VayuSense's current closer-together steps.
- Update DESIGN.md's Typography section: retire "The Two Voices Rule",
  document the new single-family, weight-driven hierarchy as the
  replacement named rule.
- Applies to all three templates: `landing.html`, `summary.html` (the
  Phase 6G generic dashboard), `index.html` (the full city page).

## Phase B: Spacing / layout pass

- Live-inspect each page (landing, summary dashboard, a city page) in the
  browser for the "awkward empty space" / "clustered" complaints — this
  requires visual inspection first; the design here is "audit and fix
  findings," not a predetermined list of changes.
- Apply the reference's generous, deliberate whitespace rhythm between
  sections and within card grids.

## Phase C: Branding fix

- Merge the two-tone "Vayu" / "Sense" logotype into a single word
  "VayuSense", increase its font size/visual weight in the nav, across all
  three templates. Logo mark (the gradient dot/square) stays.

## Phase D: Backend/frontend data-authenticity audit

- Grep the full codebase (templates + Python) for any mock/placeholder/
  hardcoded sample data that could render instead of a real API response.
- For every rendered number/stat across all three templates, confirm it
  traces to a real `/api/*` call (no static arrays standing in for live
  data). Report findings; fix any found instance of fake data.
- This is a verification task, not expected to change much — the app's
  architecture has been live-data-first all session — but it's an explicit
  ask and gets a dedicated pass rather than an assumption.

## Testing

- Phase A: visual browser verification across all three templates + existing
  pytest suite (no backend changes expected).
- Phase B: visual browser verification only (pure CSS/layout).
- Phase C: visual browser verification + grep confirming no remaining
  "Vayu</span>Sense" or "Vayu<span>Sense" two-tone split markup anywhere.
- Phase D: a documented audit (grep + endpoint trace), fixes verified by
  pytest + browser network-tab confirmation of real fetches.
- Deploy cadence unchanged: local verify → Cloud Build → Cloud Run → live
  verify → commit → push, once per phase.
