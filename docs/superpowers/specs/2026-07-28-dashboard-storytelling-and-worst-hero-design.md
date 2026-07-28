# Dashboard Scroll Storytelling + Dynamic "Worst Right Now" Hero — design spec

## Concept

Two fixes to `summary.html`, both scoped to the dashboard only:

1. **Scroll storytelling**, extending the chapter-rail + header-parallax +
   scroll-linked-atmosphere treatment already built for the city page
   (`index.html`, see `2026-07-28-scroll-storytelling-design.md`) to the
   dashboard's own five long-scroll sections, so both pages share the
   same continuous feel instead of only the city page having it.
2. **Dynamic hero city**, replacing the dashboard's currently hardcoded
   `const CITY='Delhi'` (in `loadOverview()`) with the actual worst-AQI
   city nationally, computed live rather than fixed -- the dashboard's
   entire premise is "a quick read across all 36 tracked cities," so its
   featured hero snapshot should reflect the country's real worst point,
   not always Delhi regardless of what the data says.

## Mechanics

### Dynamic worst-city hero

`/api/aqi?city=<any>` already computes AQI for all 36 tracked cities on
every call (see `main.py:city_aqi()`) and returns them pre-sorted
worst-first as `ranking`, regardless of which city was queried -- only
the hero-specific fields (`rank`, `of`, `dominant`, etc.) differ by which
city was passed. So `loadOverview()` changes from a single fetch to:

```js
async function loadOverview(){
  const probe = await (await fetch('/api/aqi?city=Delhi')).json();
  const worstCity = probe.ranking?.[0]?.city || 'Delhi';
  const a = worstCity === 'Delhi' ? probe : await (await fetch(`/api/aqi?city=${worstCity}`)).json();
  // ...rest of the function unchanged, using `a` instead of a fresh fetch
}
```

The first call is not wasted -- it's the same full 36-city sweep either
way, and its `ranking` array is exactly what determines which city is
"worst," so this costs at most one extra round-trip (skipped entirely
when Delhi happens to already be the worst city) rather than a duplicate
full computation, since per-city results are cached server-side.

The hero's eyebrow gets a small explicit badge so it reads as
intentional, not a leftover default:

```html
<div class="eyebrow">Air quality index
  <span class="tag" id="scoreCity">Delhi</span>
  <span class="tag worstBadge" id="worstBadge">Worst right now</span>
  <span class="tag" id="aqiSource">…</span>
  <span class="tag" id="aqiRank" style="display:none"></span>
</div>
```

`worstBadge` is always shown (the hero is *always* the worst city by
construction now, not conditionally) -- a small accent-colored pill,
visually distinct from the neutral `aqiSource`/`aqiRank` tags, using the
existing `--bad` custom property already used elsewhere in this file for
"this needs attention" framing.

### Scroll storytelling

Same mechanism as `index.html`, adapted to the dashboard's five sections
(it has no Health/Trends/Ask sections, so the chapter list is shorter):

```js
const CHAPTERS=[
  {id:'overview',label:'Overview'},
  {id:'alerts',label:'Alerts'},
  {id:'cities',label:'Compare'},
  {id:'yoyRanking',label:'Year/Year'},
  {id:'windmap',label:'Live map'},
];
```

Everything else -- the `#storyRail` markup and CSS, the rAF-throttled
scroll listener, `applyScrollAtmosphere()`, the header-parallax transform,
the `reduceMotion` guard, the `<900px` CSS hide -- is copied verbatim
from `index.html`'s implementation, not re-derived, since it's already
tested and correct there. This file already has its own copies of
`setAtmosphere`/`ATMOSPHERE_RGB`/`RAMP`/`reduceMotion` (established
per-template convention in this codebase, confirmed by the existing
Living Atmosphere / Breathing / Vignette code already duplicated across
`index.html`, `summary.html`, and `landing.html`), so the rail code slots
into the same pattern rather than introducing a new one.

One placement difference from `index.html`: `updateStory()` there reads
`CURRENT_CATEGORY_KEY`, which in `summary.html` is set inside
`loadOverview()` (async, after the worst-city fetch resolves) rather than
at a fixed `let` declaration site. The rail setup code is placed after
`CURRENT_CATEGORY_KEY`'s `let` declaration (so no temporal-dead-zone
error, matching the bug found and fixed in `index.html` this session),
but its first `updateStory()` call will read the *initial* placeholder
value until `loadOverview()` resolves and updates it -- acceptable, since
the rail's color just follows whatever `CURRENT_CATEGORY_KEY` is at each
scroll tick, same as `index.html`, and the placeholder is a real
(non-crashing) category key already present in this file.

## Explicitly out of scope

- `landing.html` -- no long-scroll section structure, not a target for
  either change.
- `index.html` -- already has scroll storytelling; not touched further.
- Any change to the live wind/AQI map itself (`windmap` section) --
  that's an existing, separate, already-immersive feature; this pass
  only adds it as a rail chapter, doesn't modify its internals.
- Any change to how `/api/aqi` computes or caches per-city results --
  the dynamic-hero fix is purely a client-side choice of which city to
  request second, not a backend change.

## Testing

- Verify against real production: dashboard hero shows whichever city is
  genuinely worst that day (cross-check against the ranking table's #1
  row, which must match), confirm the badge reads "Worst right now",
  confirm rank/of fields are internally consistent (e.g. rank should be
  1 for the worst city).
- Verify the chapter rail advances through Overview → Alerts → Compare →
  Year/Year → Live map in scroll order, confirm clicking a dot jumps
  correctly, confirm it's hidden under reduced motion and under 900px,
  same checks already used for `index.html`.
- No new Python code; existing 112-test suite must still pass unchanged.
