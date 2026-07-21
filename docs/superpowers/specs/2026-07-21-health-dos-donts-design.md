# Phase 6C: Health Advisory Do's/Don'ts Redesign — Design

**Date:** 2026-07-21
**Project:** VayuSense renovation, Phase 6C of 6 (round 2)
**Status:** Approved by user

## Purpose

Restructure the existing 36-cell rule-based health guidance (currently one prose
paragraph per condition × AQI category) into the reference screenshots' Do's/
Don'ts format: a short summary line, a green-check "Do" list, and a red-cross
"Don't" list, with the condition's icon shown large next to the content. Same
underlying rule-based, zero-LLM-call architecture — this is a data-shape and
layout change, not a new system.

## 1. Data restructuring (`agents/health_guidance.py`)

`GUIDANCE[condition][category]` changes from a plain string to:

```python
{"summary": "...", "dos": ["...", "..."], "donts": ["...", "..."]}
```

All 36 cells (6 conditions × 6 categories) get a summary (derived from the
existing paragraph) plus 2-3 concrete "Do" actions and 2 "Don't" actions,
scaled to severity exactly as today (Good = minimal/no restrictions, Hazardous =
strict). `get_guidance()` returns the dict; `citation()` unchanged.

## 2. API

`/api/health_guidance`'s `guidance` field shape changes to match — each
condition→category value is now the `{summary, dos, donts}` object instead of a
string. No new endpoint.

## 3. Frontend layout (`app/templates/index.html`)

The `#healthPanel` redesign: the active condition's icon renders large (48px,
tinted by the current AQI category color) beside the summary line; below it, two
columns — "Do" (green check ✓ prefix) and "Don't" (rose cross ✕ prefix) — each
listing that cell's items. Tabs, citation line, and the rule-based/instant nature
are unchanged.

## 4. Testing

- `tests/test_health_guidance.py` updated: every cell has a non-empty `summary`,
  ≥2 `dos`, ≥2 `donts`; no two cells for the same condition share an identical
  summary (same duplication guard as before, adapted to the new shape).
- `tests/test_health_guidance_api.py` updated: asserts the new nested shape.
- Browser verification: switching tabs/cities updates the large icon, summary,
  and both lists correctly with zero network calls (same instant, rule-based
  behavior as before); no console errors.
- Deploy cadence: local verify → Cloud Build → Cloud Run → live verify → push.

## Out of scope

The 6 conditions and 6 categories themselves are unchanged. No LLM call is
introduced anywhere — this stays strictly rule-based per the original Phase 4
decision.

## Success criteria

- All 36 cells present a summary + Do's + Don'ts, not a single paragraph.
- Large tinted icon accompanies the active condition.
- Still zero-latency, zero-LLM-call; existing tests updated and passing;
  deployed and verified live.
