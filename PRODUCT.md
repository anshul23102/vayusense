# Product

## Register

product

## Platform

web

## Users

Two audiences carry equal weight this round. The first is real end users in Indian and APAC cities: parents deciding whether outdoor sports practice is safe this week, school administrators, clinic staff bracing for respiratory admissions, and city or ward officials drafting public advisories. Their context is a rushed moment, often on a phone, needing a straight answer rather than a chart to interpret. The second audience is hackathon judges evaluating the Top 101 refinement submission: they arrive cold, spend a few minutes with the live app, and need the value and the engineering depth (GPU acceleration, grounded multi agent reasoning) to be legible almost immediately.

## Product Purpose

VayuSense turns millions of raw air quality sensor readings into one decision ready answer. It is not another AQI dashboard; it is a decision intelligence layer that converts pollutant data into a plain language safety verdict, a human impact estimate (cigarette equivalent exposure, life expectancy impact), and a grounded, tool using AI recommendation. Success looks like a user closing the app knowing exactly what to do today, and a judge understanding within two minutes why the underlying engineering (NVIDIA RAPIDS acceleration, a Google ADK multi agent pipeline) is not a cosmetic add-on but the thing that makes the decision timely.

## Positioning

VayuSense is the only air quality tool that proves its own speed and translates pollution into human stakes: a reproducible 37.5x GPU benchmark stands behind every "fresh" data claim, and cigarette equivalent exposure and life expectancy impact stand behind every "this matters" claim. Nothing else in the category shows its receipts on both counts.

## Brand Personality

Clinical, trustworthy, calm. This is closer to a medical instrument than a consumer app: authority comes from precision and restraint, not urgency theatrics. Severity is communicated through clear data and honest numbers, never through aggressive color, blinking states, or alarmist copy. Calm does not mean soft: a hazardous reading should still land hard, but through the weight of the number itself, not through visual noise.

## Anti-references

Explicitly not a generic SaaS dashboard. No hero metric card cliche (big number, small label, gradient accent), no gradient text, no side stripe borders on cards, no cookie cutter admin template layout, no identical card grids repeated for every section. If a screenshot of this could be mistaken for a generic analytics SaaS product with the labels swapped, it has failed.

## Design Principles

Facts before advice, in the interface as much as in the agent architecture: every screen should let a person see the underlying numbers before it hands them an interpretation, mirroring the Data Analyst then Health Advisor pipeline.

Show the receipts. The GPU benchmark and the grounded agent responses are the project's actual proof points; the design should keep evidence (methodology notes, real timings, real citations to WHO guidelines) visible rather than hiding it behind a polished but unverifiable claim.

One straight answer over a wall of charts. The product's own pitch is "a straight answer, not a spreadsheet." Resist the pull toward becoming a conventional BI dashboard with charts for their own sake.

Clinical calm over alarmist noise. Severity is conveyed through honest data and typographic weight, not through red flashing UI or aggressive motion.

Serve both audiences without pandering to either. Every surface must read as genuinely useful in a rushed daily moment and be immediately legible and impressive to a judge seeing it cold for the first time.

## Accessibility & Inclusion

Target beyond baseline WCAG AA toward AAA where feasible: verified color contrast (including the hazardous/safe status colors, which must not rely on hue alone), full keyboard navigation, and screen reader tested markup for the dashboard's data (safety score, human impact figures, trend chart, chat). Every animation needs a `prefers-reduced-motion` alternative. Given the subject matter (health guidance for children, the elderly, and people with respiratory conditions), accessibility here is not a checkbox but part of the product's credibility.
