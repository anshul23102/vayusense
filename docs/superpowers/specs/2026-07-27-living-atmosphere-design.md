# Living Atmosphere — design spec

## Concept

The ambient background on every page (`#aurora`, `canvas#haze`) already exists,
already shares one `RAMP` palette across `landing.html`, `index.html`, and
`summary.html`, and already reacts to the mouse. It has never reacted to the
one thing the app is actually about: the air quality itself.

This pass makes the atmosphere a felt translation of the real AQI being
shown, using the same color language already used in the AQI ring, the
category badges, and the pollutant panel — not a new palette, a new use of
the existing one. Good air reads calm and cool; hazardous air reads warm and
restless. The landing page, which has no single city in context, instead
reflects the worst currently active alert nationwide (from `/api/alerts`,
shipped in the previous pass) — so a first-time visitor feels "here's what's
actually happening in India's air right now" before clicking anything.

Everything is gated behind the `reduceMotion` check that already exists in
all three files. No new dependency, no new DOM subtree, no new palette.

## Shared mechanism: `severityColor(aqi)`

A single JS function, duplicated into each of the three templates (matching
this codebase's existing convention — `RAMP`, `esc()`, `bandOf()`-style
helpers are already duplicated per-file rather than shared via a module,
since these are plain server-rendered templates with no bundler):

```js
const SEVERITY_STOPS = [
  [0,   [61,252,158]],  // good      #3dfc9e
  [50,  [61,252,158]],
  [100, [255,194,71]],  // moderate  #ffc247
  [150, [255,150,64]],  // poor      #ff9640
  [200, [255,92,133]],  // unhealthy #ff5c85
  [300, [239,79,192]],  // severe    #ef4fc0
  [400, [201,58,90]],   // hazardous #c93a5a (clamped past 400)
];
function severityColor(aqi){
  const a = Math.max(0, Math.min(400, aqi));
  for (let i = 0; i < SEVERITY_STOPS.length - 1; i++) {
    const [lo, c0] = SEVERITY_STOPS[i], [hi, c1] = SEVERITY_STOPS[i+1];
    if (a <= hi) {
      const t = hi === lo ? 0 : (a - lo) / (hi - lo);
      return c0.map((v,k) => Math.round(v + (c1[k]-v) * t));
    }
  }
  return SEVERITY_STOPS[SEVERITY_STOPS.length-1][1];
}
```

This walks the *same six anchor colors, in the same order*, as the AQI ramp
bar already visible on every page — so the atmosphere's color at any given
AQI always agrees with what the category badge next to it is already saying.
A naive two-stop lerp (green straight to oxblood) was considered and
rejected: it produces a muddy desaturated grey-green at moderate AQI values,
which would read as a bug, not a feeling.

## Per-page mechanics

### City page (`index.html`) and dashboard (`summary.html`)

Both already compute the loaded city's AQI (`aqi` value used for the ring/
verdict). On every successful data load:

1. Compute `severityColor(aqi)` → `rgb(r,g,b)`.
2. A new fixed, full-viewport `#atmosphere` div (z-index 0, alongside
   `#aurora`, `pointer-events:none`) gets its `background` set to a soft
   radial gradient using that color, while its `opacity` is `0`.
3. Force a reflow, then transition `opacity` to its resting value (`.16`),
   over `900ms ease`.
4. On a *subsequent* city change, fade opacity back to `0` first, swap the
   gradient color while invisible, then fade back in. This avoids relying on
   CSS interpolating between two different `background-image` values, which
   is not natively animatable — the opacity-only crossfade is what actually
   produces the smooth transition, not a color tween.
5. Haze canvas: each particle's fill color lerps from the existing neutral
   `rgba(196,212,245,o)` toward the severity color, weighted by
   `severity = min(1, aqi/300)`. Particle speed (`vx`,`vy` scale) increases
   mildly with `severity` (up to ~1.4×) so worse air also reads as *more
   agitated*, not just differently colored. Particle count is unchanged (80)
   — resizing the array mid-flight adds complexity for a marginal effect.

### Landing page (`landing.html`)

No single city in context. On load, fetch `/api/alerts` (already public,
already fast — 0.29s for all 36 cities per the previous pass's
measurement). Take the worst `category_breach` alert's AQI if one exists;
otherwise fall back to a calm baseline (`aqi = 40`, solidly Good) rather
than implying a false alarm when the country's air is genuinely fine.
Same `#atmosphere` + haze-tint mechanism as above, applied once on load
(no city-switching case to handle here).

## Accessibility & failure modes

- Entirely skipped when `reduceMotion` is true (existing check, already
  wraps the haze particle loop in all three files) — the `#atmosphere` div
  still gets its color set for a static tint, but no fade transition and no
  particle speed change.
- `/api/alerts` fetch failure on the landing page silently falls back to the
  calm baseline — the atmosphere is decoration, never a loading state a user
  waits on.
- The `#atmosphere` div sits behind all content (`z-index:0`, same layer as
  `#aurora`) and its resting opacity (`.16`) is chosen low enough that no
  text contrast on the page is affected — this will be verified with the
  same contrast-sweep method used earlier in this session, not assumed.

## Testing

- Visual check at all six severity bands (Good through Hazardous) on the
  city page, using real cities already at those levels where the archive
  has them, or a temporary manual override for bands not currently present
  in the live data.
- Contrast sweep (reused JS method from the earlier design-audit pass) run
  again after this change, to confirm the new `#atmosphere` layer hasn't
  dropped any text below WCAG thresholds.
- `reduceMotion` path checked explicitly (no crash, no particle loop, still
  gets a static tint).
- Landing page checked both with and against a mocked empty `/api/alerts`
  response, to confirm the calm-baseline fallback actually triggers rather
  than leaving the atmosphere uncolored.
- No new Python code, so no new pytest coverage; existing 112-test suite
  must still pass unchanged (this is a pure frontend change).

## Explicitly out of scope for this pass

- Sound design.
- Resizing the haze particle count dynamically.
- Any change to `#aurora`'s existing mouse-follow behavior — `#atmosphere`
  is an additive layer, not a replacement.
- The "supporting polish" (stagger timing, easing consistency) mentioned in
  the brainstorm is folded into implementation as small touch-ups where
  encountered, not tracked as separate deliverables.
