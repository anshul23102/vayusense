# Smog Vignette — design spec

## Concept

The two previous passes (Living Atmosphere, Breathing Motion) both reuse
the same severity value to drive color and pulse. This pass adds a third,
genuinely different sensory dimension: visibility itself. Real smog does
not just tint the air, it shortens how far you can see. At high severity
the screen's edges darken and close in; at Good it is effectively absent.

Paired with a small tweak to the existing haze particles so they drift
downward at high severity, on top of their existing motion -- like real
particulate matter settling, not just changing color and speed as the
previous pass already made them do.

This is deliberately the most literal of the three metaphors, and
deliberately the one that gets the most scrutiny before shipping, because
it is the one most likely to interact with legibility at the edges, where
the nav and search bar live.

## Mechanics

### Vignette

A new `#vignette` element per page: `position:fixed;inset:0`, a radial
gradient (transparent center, warm smog-grey edges), `pointer-events:none`,
sitting in the same layer tier as the existing `.grain` overlay (z-index 1,
above the aurora/atmosphere/haze background layer but below actual content
in effective stacking, since `.grain` already coexists there without
touching legibility).

```js
function severityVignetteColor(severity){
  const neutral=[20,26,45];  // near-invisible over the page's own --bg
  const smog=[70,58,48];     // desaturated warm brownish-grey
  return neutral.map((v,i)=>Math.round(v+(smog[i]-v)*severity));
}
function setVignette(severity){
  const el=$('vignette'); if(!el)return;
  const [r,g,b]=severityVignetteColor(severity);
  const alpha=(severity*0.5).toFixed(2); // 0 at Good -> 0.5 at the outer edge at Hazardous
  const grad=`radial-gradient(circle at 50% 38%, transparent 42%, rgba(${r},${g},${b},${alpha}) 100%)`;
  if(reduceMotion){ el.style.background=grad; return; }
  el.style.opacity='0';
  requestAnimationFrame(()=>{ el.style.background=grad;
    requestAnimationFrame(()=>{ el.style.opacity='1'; }); });
}
```

Same opacity-crossfade technique as `#atmosphere` (fade out, swap the
gradient while invisible, fade back in) -- `background-image` is not
natively animatable, so this is what actually produces a smooth
transition, not a CSS transition on the gradient itself. Called from the
same site as `setBreathing()`, inside `setAtmosphere()`.

The 42% transparent-center radius is chosen so the primary content column
on a typical viewport sits inside the untouched hole; the darkening only
reaches into the outer border. This is a starting number, not a promise --
it gets checked visually and adjusted if the contrast sweep (below) finds
a problem near the edges.

### Particle settling

One line added to the existing haze `tick()` loop (already modified twice
this session, for color and speed):

```js
p.vy += ATMOSPHERE_SEVERITY * 0.008;
```

A gentle constant downward bias, scaled by severity, added on top of the
existing velocity. Lives entirely inside the `if(!reduceMotion){...}` block
the haze loop already runs in, so it needs no separate reduced-motion
gate -- it simply does not run when motion is off, which is the agreed
behavior (cut the particle motion, keep the vignette).

## Reduced motion

- **Vignette stays**, but static: color/opacity are set directly with no
  crossfade animation. This is a deliberate exception to this session's
  usual "suppress entirely under reduceMotion" rule for continuous
  animations -- the vignette is not motion, it is a static tint level,
  confirmed with the user before implementation.
- **Particle settling is cut**, because it lives inside the haze loop that
  is already skipped entirely under `reduceMotion`.

## Testing

- Contrast sweep (same method as the previous two passes) run at
  worst-case Hazardous severity, specifically checking text near the
  screen edges (nav links, search input) where the vignette reaches
  furthest -- not just the page center, which the previous sweeps
  happened to be sufficient for since neither prior effect touched the
  edges specifically.
- Visual check at Good and Hazardous via screenshot (not
  `getComputedStyle` on opacity, per this session's established finding
  that property is unreliable through this browser tool).
- Confirm the 42% transparent-center radius via direct measurement against
  where the nav bar and primary content actually sit, adjusting if needed.
- No new Python code; existing 112-test suite must still pass unchanged.

## Explicitly out of scope

- Sound (raised again by the user's "keep going," re-declined for the same
  demo-safety reason as the previous two passes).
- Any change to the vignette's transparent-center radius being
  responsive/different per breakpoint -- one radius, checked at the
  desktop and mobile widths already used for verification this session,
  adjusted only if a real problem is found, not preemptively.
