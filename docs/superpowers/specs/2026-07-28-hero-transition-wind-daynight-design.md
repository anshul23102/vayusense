# Smooth City Switch + Wind-Driven Particles + Day/Night Density — design spec

Three additive immersive passes, bundled since they touch the same
particle/hero systems already built this session.

## A. Smooth city-switch transition

**Scope: `index.html` only.** Neither `summary.html` (its hero city is
auto-selected as "worst nationally," not user-picked) nor `landing.html`
(no per-city hero) has a user-driven city switch to smooth.

### Mechanics

`refresh()` already toggles `#scoreLive`'s `.loading` class (opacity
dip) around the AQI-hero fetch, and already fires `pulseData()` the
moment fresh data lands. This extends that same window to the whole
hero (`.scoreWrap`: ring + live region + mood character), but only when
the city actually changed -- not on every pollutant-dropdown switch,
which re-fetches the same city's data and doesn't need a "new place"
transition.

```js
let LAST_TRANSITIONED_CITY=null;
```

At the top of `refresh()`, before the fetch:
```js
const cityChanging = !reduceMotion && CITY!==LAST_TRANSITIONED_CITY;
if(cityChanging) $('overview').querySelector('.scoreWrap').classList.add('heroFade');
```//placeholder illustrating intent; actual insertion point is right
next to the existing `$('scoreLive').classList.add('loading')` line.

Right after the existing `$('scoreLive').classList.remove('loading')`
line (where `pulseData()` is also called):
```js
$('overview').querySelector('.scoreWrap').classList.remove('heroFade');
LAST_TRANSITIONED_CITY=CITY;
```

```css
.scoreWrap{transition:opacity .35s cubic-bezier(.2,.8,.2,1),transform .35s cubic-bezier(.2,.8,.2,1)}
.scoreWrap.heroFade{opacity:.4;transform:scale(.985)}
```

Guarded by `!reduceMotion` at the call site (not just via a reduced-
motion CSS override) so the class is never added at all under reduced
motion -- consistent with this session's "suppress entirely" convention
for continuous/transitional motion, rather than leaving a class that a
CSS override then has to neutralize.

## B. Wind-driven particle drift

**Scope: `index.html` and `summary.html`.** Both already fetch and
display real wind speed via `renderWeather()`; `landing.html` has no
per-city weather context to draw a wind vector from, so its particles
stay severity-driven only (no change there).

### Backend: expose wind direction

`app/weather.py`'s `_fetch()` only requests
`temperature_2m,relative_humidity_2m,wind_speed_10m,uv_index` from
Open-Meteo. Adding `wind_direction_10m` and returning it as `wind_deg`
is additive -- existing consumers (the weather strip, existing tests
that mock `_fetch`'s return dict) are unaffected since they simply won't
reference a key they don't expect.

```python
"current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,uv_index",
...
"wind_deg": cur.get("wind_direction_10m"),
```

### Frontend: drift vector

`renderWeather()` already fetches `/api/weather?city=...` per page (with
one real bug fixed along the way -- see below). It now also stores the
result on two module-level vars read by the haze tick loop, the same
pattern `ATMOSPHERE_RGB`/`ATMOSPHERE_SEVERITY` already use:

```js
let WIND_DEG=null, WIND_KMH=0;
// inside renderWeather(), after a successful fetch:
WIND_DEG=w.wind_deg; WIND_KMH=w.wind_kmh||0;
```

In the haze tick loop, each frame:
```js
if(WIND_DEG!=null){
  const bearing=(WIND_DEG+180)%360*Math.PI/180; // wind_deg is FROM; particles drift TOWARD the opposite bearing
  const force=Math.min(WIND_KMH,40)/40*.03;
  const wdx=Math.sin(bearing)*force, wdy=-Math.cos(bearing)*force;
  for(const p of parts){ p.vx+=wdx; p.vy+=wdy; /* existing cursor/severity forces unchanged */ }
}
```

Capped at 40 km/h so a rare high-wind reading doesn't send particles
flying off-screen every frame -- still reads as "windier" beyond the cap,
just not unbounded. This is a gentle constant bias blended with the
existing cursor-attraction and severity-settling forces already in the
loop, not a replacement for them.

### Bug fixed along the way: dashboard weather always showed Delhi's

`summary.html`'s `renderWeather()` still hardcoded
`/api/weather?city=Delhi`, left over from before this session's earlier
"dynamic worst-city hero" pass -- so the weather strip would show
Delhi's wind/temp/humidity next to a *different* city's AQI hero once
that fix shipped. `renderWeather()` now takes the resolved city as a
parameter, called as `renderWeather(worstCity)` from `loadOverview()`
alongside the already-correct `renderMoodChar()` call on the same line.

## C. Day/night ambient particle density

**Scope: all three files** (`index.html`, `summary.html`,
`landing.html`) -- the haze particle system is the "starfield" visual in
every screenshot referenced this session; there's no separate static
star layer to modify.

### Mechanics

A single `nightFactor()` helper (duplicated per file, matching this
codebase's established no-shared-module convention for templates):

```js
function nightFactor(){
  const now=new Date();
  const istMin=(now.getUTCHours()*60+now.getUTCMinutes()+330)%1440; // UTC -> IST (+5:30)
  const h=istMin/60;
  if(h>=22||h<5) return 1.15;               // night: denser, slightly boosted
  if(h>=9&&h<17) return .55;                // day: sparser
  const rampStart = h<9 ? 5 : 17, rampEnd = h<9 ? 9 : 22;
  const t=(h-rampStart)/(rampEnd-rampStart);
  const from = h<9 ? 1.15 : .55, to = h<9 ? .55 : 1.15;
  return from+(to-from)*Math.max(0,Math.min(1,t));
}
```

Recomputed every 5 minutes via `setInterval` into a module var
`NIGHT_FACTOR` (cheap: one `Date` + arithmetic, no DOM work), rather
than once at load -- a demo session or a tab left open across a
dawn/dusk boundary should still drift, not freeze at whatever value was
true when the page first loaded.

Applied as a multiplier on each particle's alpha at draw time:
```js
ctx.fillStyle=`rgba(${cr},${cg},${cb},${p.o*NIGHT_FACTOR})`;
```

No new particles are added or removed (avoids the complexity of
resizing the pool mid-session) -- day vs. night reads as
dimmer-vs-brighter/denser-feeling, not a literal count change, which is
sufficient for the ambient effect this is going for.

## Reduced motion

- A: guarded at the call site (see above) -- no class ever added.
- B: the wind force loop lives inside the same `if(!reduceMotion){...}`
  block that already wraps the entire haze particle system in all three
  files -- already fully skipped, no new guard needed.
- C: same -- `nightFactor()`/`NIGHT_FACTOR` only matter inside the haze
  draw loop, which doesn't run at all under reduced motion.

## Testing

- A: switching cities via search/dropdown visibly dips and restores the
  whole hero once; switching only the pollutant parameter does not
  trigger it.
- B: verify against real production data for a high-wind city, confirm
  particle drift direction visually matches the reported wind direction
  (not just faster/slower); confirm the dashboard's weather strip now
  shows the *worst* city's weather, not always Delhi's.
- C: verify `nightFactor()`'s returned value at a few IST hours
  (2am, 7am, 12pm, 8pm) matches the intended curve via direct function
  call in the browser console -- not practical to visually verify actual
  night vs. day rendering in one sitting.
- No existing test breaks: `wind_deg` is a new, optional key; existing
  `tests/test_weather.py` mocks don't reference it and aren't affected.
- Full 112-test suite must still pass unchanged.
