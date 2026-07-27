# Breathing Motion — design spec

## Concept

Living Atmosphere (previous pass) made the background color/motion a felt
translation of real AQI severity. This pass adds a second, complementary
physical metaphor to the app's own chrome: the header logo mark and the
AQI ring breathe, continuously, at a rate and depth tied to the same
severity value Living Atmosphere already computes.

Worse air does not mean a bigger, more dramatic pulse — it means a
**faster but shallower** one. This is deliberate: it mirrors actual labored
breathing (quick, shallow breaths under distress) rather than an arbitrary
"more severity = more animation" mapping, and it stays visually restrained
at exactly the moment restraint matters (a large pulsing logo at Hazardous
would read as alarmist, not honest).

## Mechanics

One CSS `@keyframes breathe` (a pure `transform:scale()` animation — cheap,
GPU-composited, no layout thrash), applied to two existing elements per
page:

- `.logo .dot` (the header logo image — present identically in all three
  templates, scoped by the existing `.logo .dot` selector)
- `#scoreRing` (the AQI ring wrapper — present in `index.html` and
  `summary.html`; the landing page has no AQI ring, so only its logo
  breathes there)

```css
@keyframes breathe {
  0%, 100% { transform: scale(1); }
  50%      { transform: scale(var(--breathAmp, 1.04)); }
}
.logo .dot, #scoreRing { animation: breathe var(--breathDur, 3500ms) ease-in-out infinite; }
```

`--breathDur` and `--breathAmp` are set via inline style on each target
element, computed in the same place `setAtmosphere()` already runs (so no
new fetch, no new data — it reuses the severity value already in hand):

```js
function setBreathing(severity){
  const dur = Math.round(5000 - severity * 3000);   // 5000ms (Good) -> 2000ms (Hazardous)
  const amp = (1.06 - severity * 0.04).toFixed(3);   // 1.06 (Good) -> 1.02 (Hazardous)
  document.querySelectorAll('.logo .dot, #scoreRing').forEach(el => {
    el.style.setProperty('--breathDur', dur + 'ms');
    el.style.setProperty('--breathAmp', amp);
  });
}
```

Called immediately after `setAtmosphere(aqi)` in `index.html` and
`summary.html`, and after `setAtmosphere(worstAqi)` inside
`initAtmosphereFromAlerts()` in `landing.html` — same call sites, same
severity value, no duplicated computation.

## Reduced motion

Fully suppressed, not merely shortened: `@media (prefers-reduced-motion:
reduce) { .logo .dot, #scoreRing { animation: none } }` in all three
files' existing reduced-motion blocks. A continuous infinite pulse is
exactly the category of motion that setting exists to prevent — unlike
the one-shot fade-ins elsewhere in the app, which stay (just instant).

## Testing

- Visual check at Good and Hazardous severity (screenshot-based, per the
  Living Atmosphere pass's finding that `getComputedStyle` reporting was
  unreliable through the browser tool in this environment — screenshots
  are the trusted verification method here).
- Confirm the ring's existing arc-fill and count-up animations on page
  load are undisturbed by the new continuous breathing transform (they
  animate different properties — `stroke-dashoffset` and text content —
  so no property conflict is expected, but worth a visual pass to
  confirm nothing looks like it's fighting itself).
- `reduceMotion` path: confirm `animation: none` actually suppresses the
  keyframe (no pulse, static scale).
- No new Python code; existing 112-test suite must still pass unchanged.

## Explicitly out of scope

- Any change to the ring's existing arc-fill or number count-up animations.
- Breathing on any element other than the logo mark and the AQI ring.
- Sound.
