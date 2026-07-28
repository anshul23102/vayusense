# Live Data Pulse — design spec

## Concept

The site's core claim is "this is real, live data," but nothing visibly
marks the moment data actually arrives -- numbers just appear or swap
silently. This adds a brief, one-shot pulse (an expanding, fading glow
ring, the standard "something just updated" affordance) on the AQI hero
ring and the surrounding stat cards every time a fetch actually resolves
with new data: on first page load and on every city switch.

Applies to `index.html` (city page: `#scoreRing` + `.kpi` pollutant
cards) and `summary.html` (dashboard: `#scoreRing` + `.impactStat`
cards). Not `landing.html` -- it has no live per-visit data refresh to
mark (the hero stats there are static archive totals, already
one-time-counted-up).

## Mechanics

```css
@keyframes dataPulse{
  0%{box-shadow:0 0 0 0 var(--pulseColor,rgba(157,193,255,.5))}
  70%{box-shadow:0 0 0 16px rgba(157,193,255,0)}
  100%{box-shadow:0 0 0 0 rgba(157,193,255,0)}
}
.pulseOnce{animation:dataPulse .8s cubic-bezier(.2,.8,.2,1)}
```

`--pulseColor` is set inline from the current severity's RGB (reusing
`ATMOSPHERE_RGB`, already computed by `setAtmosphere()` immediately
before this runs -- no new color logic) so the pulse always matches
today's actual air quality color, not a fixed accent.

```js
function pulseData(){
  if(reduceMotion)return;
  const [r,g,b]=ATMOSPHERE_RGB;
  const ring=$('scoreRing');
  if(ring){
    ring.style.setProperty('--pulseColor',`rgba(${r},${g},${b},.55)`);
    ring.classList.remove('pulseOnce'); void ring.offsetWidth; ring.classList.add('pulseOnce');
  }
  document.querySelectorAll('.kpi, .impactStat').forEach((el,i)=>{
    el.style.setProperty('--pulseColor',`rgba(${r},${g},${b},.35)`);
    el.classList.remove('pulseOnce'); void el.offsetWidth;
    setTimeout(()=>el.classList.add('pulseOnce'), Math.min(i,6)*25);
  });
}
```

`classList.remove` + `void el.offsetWidth` + `classList.add` is the
standard restart-a-CSS-animation trick (needed because a second
`add('pulseOnce')` while the class is already present is a no-op) --
matters here since `pulseData()` fires on every city switch, not just
once. The small per-card stagger (25ms, capped at index 6) gives the KPI
strip a slight cascade rather than every card flashing in perfect
unison, similar in spirit to the existing `cardIn` stagger pattern
already used elsewhere in this file.

Called once, at the end of the AQI hero block in `refresh()`
(`index.html`) / `loadOverview()` (`summary.html`), right after
`setAtmosphere(a.aqi)` -- so `ATMOSPHERE_RGB` is guaranteed fresh for
this exact reading before the pulse reads it.

## Reduced motion

`pulseData()` returns immediately under `reduceMotion` (matching every
other continuous/one-shot motion feature this session) -- no pulse at
all, not a static flash substitute, since the numbers themselves already
update instantly and don't need an additional non-motion cue.

## Explicitly out of scope

- `landing.html` -- no live per-visit refresh cycle to mark.
- Any change to how often or when data actually refreshes -- purely a
  visual marker on refreshes that already happen.
- The existing `.livePulse` small dot (marks "this reading is
  live-sourced, not archive") -- unrelated, unrenamed, stays as-is.

## Testing

- Verify against real production: switching cities on the city page
  triggers a visible pulse on the ring and KPI cards in the current
  severity color; loading the dashboard triggers the same on
  `#scoreRing` and the two impact stats.
- Confirm no pulse at all under `prefers-reduced-motion: reduce`.
- Confirm re-triggering (switching city A -> B -> A quickly) restarts
  the animation each time rather than silently no-op'ing.
- No new Python code; existing 112-test suite must still pass unchanged.
