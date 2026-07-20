# Landing Page Redesign Implementation Plan (Renovation Phase 5A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the landing page to actually showcase the Forecast Bench, Air Quality Calendar, city ranking, and health guidance (each with a real live number), add a city search bar and an India map picker honestly scoped to the 10 tracked cities, and extend the existing reveal/hover animation language to new icons.

**Architecture:** Frontend-only change to `app/templates/landing.html`. One shared JS loader fetches `/api/cities`, `/api/aqi?city=Delhi` (for the ranking + map colors), and `/api/forecast_bench?city=Delhi&parameter=pm25` once on page load; all new blocks (showcase cards, search, map) read from that shared cached data — no duplicate network calls. No backend changes, no new endpoints, no new pytest surface (per spec).

**Tech Stack:** Vanilla JS/CSS (existing patterns in `landing.html`), hand-authored SVG (icon sprite + India outline), existing `/api/cities`, `/api/aqi`, `/api/forecast_bench` endpoints.

## Global Constraints

- Working dir `/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense`; dev server on :8090 auto-reloads.
- No backend changes. This phase touches `app/templates/landing.html` only.
- Search and map must only ever reference the 10 cities returned by `/api/cities` — never imply broader coverage. Placeholder text must say "Search one of 10 tracked Indian cities."
- All live numbers on the landing page must come from a fetch, never be hardcoded — if a fetch fails, the block hides gracefully (matches the dashboard's existing `try{}catch(e){}` pattern), never shows stale/fake data.
- Map dots are `<button>` elements (keyboard-focusable), not bare SVG shapes with only a click handler.
- All new animation reuses the existing `.reveal`/`IntersectionObserver` pattern and the existing `reduceMotion` const already in `landing.html` — no new animation system.
- Navigation target for both search and map: `/dashboard?city=<name>` (the real, working route today).
- Commits end with the Co-Authored-By Claude trailer; push after each task. Deploy cadence: local verify → Cloud Build (`/tmp/cloudbuild.yaml`) → `gcloud run deploy vayusense --region=us-central1` → live verify → push.

---

### Task 1: Icon sprite additions + shared data loader + base CSS

**Files:**
- Modify: `app/templates/landing.html`

**Interfaces:**
- Produces: 10 city-landmark symbols + 6 health-condition symbols in the existing icon sprite (same ids as `index.html`'s sprite: `ic-delhi`, `ic-mumbai`, ..., `ic-generic`, `ic-child`, `ic-elder`, `ic-asthma`, `ic-heart`, `ic-worker`); JS `LANDING_DATA = {cities: [], ranking: [], bench: null}` and `async function loadLandingData()` that populates it once; `CITY_ICON`/`HEALTH_ICON`/`bandOf`/`RAMP` JS objects (same shape as `index.html`'s, duplicated here since the two templates are independent static files).

- [ ] **Step 1: Add the 16 icon symbols** to the existing sprite block in `landing.html` (the one with `ic-bolt`/`ic-signal`/etc.), before its closing `</svg>`:

```html
  <symbol id="ic-delhi" viewBox="0 0 24 24"><path d="M6 20V10a6 6 0 0 1 12 0v10M6 20h12M4 20h16M9 20v-6M15 20v-6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-mumbai" viewBox="0 0 24 24"><path d="M12 3v3M9 6h6l1 3h-8l1-3z M8 9h8v2H8z M6 11h12v9H6z M9 20v-5M15 20v-5M4 20h16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-kolkata" viewBox="0 0 24 24"><path d="M12 3l2.2 3H9.8zM12 6v3M7 9h10M6 9c0 4 2 5 2 9M18 9c0 4-2 5-2 9M8 18h8M4 20h16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-chennai" viewBox="0 0 24 24"><path d="M12 3l1.6 2.4h-3.2zM10 5.4h4l1.2 2.6H8.8zM8.8 8h6.4l1.3 2.8H7.5zM7.5 10.8h9l1.4 3H6.1zM6.1 13.8h11.8V20H6.1zM4 20h16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-bengaluru" viewBox="0 0 24 24"><path d="M12 3c-1.5 1-1.5 3 0 4c1.5-1 1.5-3 0-4zM7 10h10v3H7z M6 13h12v7H6z M9 20v-4M15 20v-4M4 20h16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-hyderabad" viewBox="0 0 24 24"><path d="M6 20V9c0-1 .8-2 2-2s2 1 2 2v11M14 20V9c0-1 .8-2 2-2s2 1 2 2v11M8 6.5a2 2 0 1 1 4 0M16 6.5a2 2 0 1 1 4 0M4 20h16M10 20v-5h4v5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-pune" viewBox="0 0 24 24"><path d="M5 20V8l3-2 3 2v12M5 8h6M8 6V4M13 20v-9h6v9M13 11h6M4 20h16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-ahmedabad" viewBox="0 0 24 24"><path d="M12 4a2.5 2.5 0 0 1 2.5 2.5c0 1-.6 1.8-1.5 2.3V11h-2V8.8c-.9-.5-1.5-1.3-1.5-2.3A2.5 2.5 0 0 1 12 4zM7 11h10v9H7zM7 20h10M4 20h16M9 20v-5M15 20v-5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-lucknow" viewBox="0 0 24 24"><path d="M12 3.5c-2.2 2-3.5 4.3-3.5 7c0 2.5 1.6 4 3.5 4s3.5-1.5 3.5-4c0-2.7-1.3-5-3.5-7zM6 20v-6M18 20v-6M4 20h16M9 20v-3M15 20v-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-patna" viewBox="0 0 24 24"><path d="M12 4c-3 2-5 5-5 8.5a5 5 0 0 0 10 0C17 9 15 6 12 4zM9 20v-6.5M15 20v-6.5M4 20h16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-generic" viewBox="0 0 24 24"><path d="M4 20V11l4-3 4 3v9M12 20v-6l4-3 4 3v6M4 20h16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-child" viewBox="0 0 24 24"><circle cx="12" cy="6" r="2.4" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 8.5v6M8 12h8M9 20l1.5-5.5M15 20l-1.5-5.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-elder" viewBox="0 0 24 24"><circle cx="12" cy="5.5" r="2.2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M9 20l1-6-2-2 1-4h6l1 4-2 2 1 6M10 13h4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-asthma" viewBox="0 0 24 24"><path d="M9 3v5M9 8c-2 0-3.5 1.6-3.5 3.5S7 15 9 15h6c2 0 3.5-1.6 3.5-3.5S17 8 15 8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 15v3a2 2 0 1 1-4 0M15 15v3a2 2 0 1 0 4 0" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></symbol>
  <symbol id="ic-heart" viewBox="0 0 24 24"><path d="M12 20s-7-4.4-9-9c-1.4-3.3 1-6 4-6c2 0 3.6 1.4 5 3.4C13.4 6.4 15 5 17 5c3 0 5.4 2.7 4 6c-2 4.6-9 9-9 9z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M7 12h2l1.5-3 2 5 1.5-3H17" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-worker" viewBox="0 0 24 24"><path d="M4 8l8-4 8 4M6 9v9M18 9v9M6 20h12M9 13h6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
```

- [ ] **Step 2: Add the shared data loader + helpers** in the `<script>` block, right after the `const reduceMotion = ...` line:

```javascript
const RAMP={good:'#4fe3ac',moderate:'#ffce80',poor:'#ffab73',unhealthy:'#ff8aa3',severe:'#ef7ac8',hazardous:'#b04a63'};
const BANDS=[[0,50,'good','Good'],[51,100,'moderate','Moderate'],[101,150,'poor','Poor'],[151,200,'unhealthy','Unhealthy'],[201,300,'severe','Severe'],[301,9999,'hazardous','Hazardous']];
function bandOf(aqi){for(const [lo,hi,k,l] of BANDS)if(aqi>=lo&&aqi<=hi)return{key:k,label:l,color:RAMP[k]};return{key:'hazardous',label:'Hazardous',color:RAMP.hazardous}}
const CITY_ICON={Delhi:'ic-delhi',Mumbai:'ic-mumbai',Kolkata:'ic-kolkata',Chennai:'ic-chennai',
  Bengaluru:'ic-bengaluru',Hyderabad:'ic-hyderabad',Pune:'ic-pune',Ahmedabad:'ic-ahmedabad',
  Lucknow:'ic-lucknow',Patna:'ic-patna'};
function cityIcon(c){return CITY_ICON[c]||'ic-generic'}
const HEALTH_ICON={general:'ic-lungs',children:'ic-child',elderly:'ic-elder',asthma:'ic-asthma',heart:'ic-heart',outdoor_workers:'ic-worker'};

const LANDING_DATA={cities:[],ranking:[],bench:null};
function goToCity(name){ location.href=`/dashboard?city=${encodeURIComponent(name)}`; }
async function loadLandingData(){
  try{
    const [cities, aqi, bench] = await Promise.all([
      fetch('/api/cities').then(r=>r.json()),
      fetch('/api/aqi?city=Delhi').then(r=>r.json()),
      fetch('/api/forecast_bench?city=Delhi&parameter=pm25').then(r=>r.json()),
    ]);
    LANDING_DATA.cities=cities;
    LANDING_DATA.ranking=aqi.ranking||[];
    LANDING_DATA.bench=bench;
    renderShowcase();
    renderSearch();
    renderMap();
  }catch(e){ /* every render* function below no-ops gracefully if its data is missing */ }
}
```

(`ic-lungs` for `general` already exists in `index.html`'s sprite but NOT in `landing.html`'s — add it too, since Task 1 Step 1's list above doesn't include it. Add this one more symbol alongside the others in Step 1: `<symbol id="ic-lungs" viewBox="0 0 24 24"><path d="M12 3v7M12 10c-1 -3 -4 -3 -5 -1c-2 3 -2 9 0 11c2 1.5 4 -0.5 5 -3M12 10c1 -3 4 -3 5 -1c2 3 2 9 0 11c-2 1.5 -4 -0.5 -5 -3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></symbol>`)

- [ ] **Step 3: Base CSS for the new blocks** — add near the existing `.stat`/`.card` rules:

```css
  .showcase{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-top:36px}
  .showTile{position:relative;padding:20px;border-radius:14px;background:rgba(255,255,255,.035);border:1px solid var(--line);
    transition:transform .2s,background .2s}
  .showTile:hover{background:rgba(255,255,255,.06);transform:translateY(-3px)}
  .showTile .ic{width:40px;height:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;
    margin-bottom:14px;background:rgba(157,193,255,.14);border:1px solid var(--line);color:var(--blueSolid);
    transition:transform .2s}
  .showTile:hover .ic{transform:scale(1.08) translateY(-2px)}
  .showTile .ic svg{width:20px;height:20px}
  .showTile h3{font-size:17px;margin-bottom:6px;font-family:'Space Grotesk',sans-serif}
  .showTile p{color:var(--dim);font-size:13.5px;line-height:1.55}
  .searchWrap{position:relative;max-width:420px;margin-top:20px}
  .searchInput{width:100%;background:rgba(255,255,255,.055);color:var(--txt);border:1px solid var(--line);
    border-radius:14px;padding:13px 16px;font-size:14.5px;font-family:inherit;outline:none}
  .searchInput:focus{border-color:rgba(157,193,255,.5)}
  .searchDrop{position:absolute;top:calc(100% + 6px);left:0;right:0;background:#141b31;border:1px solid var(--line);
    border-radius:12px;overflow:hidden;z-index:20;display:none}
  .searchDrop.on{display:block}
  .searchItem{padding:10px 16px;font-size:13.5px;cursor:pointer;color:var(--dim);display:flex;align-items:center;gap:10px}
  .searchItem:hover,.searchItem.hi{background:rgba(157,193,255,.1);color:var(--txt)}
  .searchItem svg{width:15px;height:15px}
  .mapWrap{position:relative;max-width:420px;margin:24px auto 0}
  .mapDot{cursor:pointer;transition:r .15s}
  .mapDot:hover circle{r:8}
  .mapLabel{font-size:8px;fill:var(--dim);font-family:'IBM Plex Sans',sans-serif;pointer-events:none}
```

- [ ] **Step 4: Browser verify** — reload `http://localhost:8090/`, run in console:
```javascript
loadLandingData().then(()=>console.log(JSON.stringify({cities:LANDING_DATA.cities.length, ranking:LANDING_DATA.ranking.length, bench:!!LANDING_DATA.bench})))
```
Expected: `{"cities":10,"ranking":10,"bench":true}` in the console (or via `read_console_messages`). All 17 new icon symbols present: `['ic-delhi','ic-mumbai','ic-kolkata','ic-chennai','ic-bengaluru','ic-hyderabad','ic-pune','ic-ahmedabad','ic-lucknow','ic-patna','ic-generic','ic-child','ic-elder','ic-asthma','ic-heart','ic-worker','ic-lungs'].every(id=>!!document.getElementById(id))` → `true`.

- [ ] **Step 5: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "feat: landing page icon sprite + shared live-data loader

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: Showcase section (Forecast Bench, Calendar preview, Ranking, Health teaser)

**Files:**
- Modify: `app/templates/landing.html`

**Interfaces:**
- Consumes: `LANDING_DATA` (Task 1), `bandOf`, `cityIcon`, `HEALTH_ICON`.
- Produces: `function renderShowcase()`; section `#showcase` in markup, placed right after the hero `</div>` and before `<section id="why">`.

- [ ] **Step 1: Markup** — insert after the hero's closing `</div>` (the one right after `<div class="scroll">SCROLL</div>`):

```html
<section id="showcase">
  <div class="kicker reveal">What's actually inside</div>
  <h2 class="reveal d1">Not a score. A whole instrument panel.</h2>
  <div class="showcase" id="showcaseGrid"></div>
</section>
```

- [ ] **Step 2: `renderShowcase()`** — add to the script:

```javascript
function renderShowcase(){
  const grid=document.getElementById('showcaseGrid');
  if(!grid)return;
  const top=LANDING_DATA.ranking[0];
  const bench=LANDING_DATA.bench;
  const winner=bench&&bench.series?Object.entries(bench.series.mae).sort((a,b)=>a[1]-b[1])[0]:null;
  const tiles=[];
  if(winner){
    tiles.push(`<div class="showTile reveal"><div class="ic"><svg><use href="#ic-chart"/></svg></div>
      <h3>Forecast Bench</h3><p>Four forecasting methods compete on real held-out data. Right now
      <b style="color:var(--txt)">${bench.methods[winner[0]]}</b> is winning for Delhi PM2.5, with a measured
      backtest error of <b style="color:var(--txt)">${winner[1]} µg/m³</b>. No black box: every method is scored
      on identical folds and the loser is shown too.</p></div>`);
  }
  tiles.push(`<div class="showTile reveal d1"><div class="ic"><svg><use href="#ic-signal"/></svg></div>
    <h3>Air Quality Calendar</h3><p>Every archived day, for every tracked city, colored by its EPA-method
    AQI band. Two years of real measured history you can actually scan for patterns, not just a today-snapshot.</p></div>`);
  if(top){
    tiles.push(`<div class="showTile reveal d2"><div class="ic"><svg><use href="#${cityIcon(top.city)}"/></svg></div>
      <h3>${top.city} leads today</h3><p>Ranked #1 of 10 tracked cities right now at
      <b style="color:var(--txt)">${top.aqi} AQI (${top.category})</b>, on the same honest basis for every city.
      See the full ranking on the dashboard.</p></div>`);
  }
  tiles.push(`<div class="showTile reveal d3"><div class="ic"><svg><use href="#ic-heart"/></svg></div>
    <h3>Guidance by condition</h3><p>Instant, rule-based advice for six groups — children, elderly, asthma,
    heart conditions, outdoor workers, and general — keyed to WHO/EPA thresholds. Zero added latency: no
    model call per click.</p></div>`);
  grid.innerHTML=tiles.join('');
  document.querySelectorAll('#showcaseGrid .reveal').forEach(el=>io.observe(el));
}
```

(`io` is the existing `IntersectionObserver` defined later in the script for `.reveal` elements — Task 2 Step 3 moves its declaration earlier so `renderShowcase` can reuse it instead of creating a second observer.)

- [ ] **Step 3: Hoist the `IntersectionObserver`** — find the existing line:
```javascript
const io = new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('on');io.unobserve(e.target)}}),{threshold:.15});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
```
Move this pair of lines to appear immediately after the `RAMP`/`BANDS`/`bandOf` block added in Task 1 Step 2 (before `loadLandingData` is defined), so `io` exists when `renderShowcase` references it. Leave the original `document.querySelectorAll('.reveal').forEach(el=>io.observe(el))` call in place at the bottom too (it still needs to run once for the static reveal elements already in the DOM at parse time) — only the `const io = new IntersectionObserver(...)` declaration itself moves up; do not duplicate the observer instance.

- [ ] **Step 4: Call `loadLandingData()` at the bottom of the script**, alongside the existing tilt-card setup:

```javascript
loadLandingData();
```

- [ ] **Step 5: Browser verify** — reload `http://localhost:8090/`; scroll to "What's actually inside"; confirm 4 tiles render (Forecast Bench naming the real winning method + MAE, Calendar teaser, top-ranked city with its landmark icon, Health teaser), each fading in on scroll; values match `curl -s localhost:8090/api/forecast_bench?city=Delhi&parameter=pm25` and `curl -s localhost:8090/api/aqi?city=Delhi` exactly; no console errors.

- [ ] **Step 6: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "feat: landing page showcase section with live forecast/ranking/health data

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 3: City search bar

**Files:**
- Modify: `app/templates/landing.html`

**Interfaces:**
- Consumes: `LANDING_DATA.cities` (Task 1), `goToCity` (Task 1).
- Produces: `function renderSearch()`; search input in the hero.

- [ ] **Step 1: Markup** — inside `<div class="hero">`, right after the `<div class="heroBtns reveal d4">...</div>` block and before `<div class="statRow ...">`:

```html
  <div class="searchWrap reveal d4">
    <input class="searchInput" id="citySearch" type="text" autocomplete="off"
      placeholder="Search one of 10 tracked Indian cities…"
      oninput="filterSearch(this.value)" onfocus="filterSearch(this.value)"
      onkeydown="searchKeydown(event)">
    <div class="searchDrop" id="searchDrop"></div>
  </div>
```

- [ ] **Step 2: JS** — add near `renderShowcase`:

```javascript
let SEARCH_HI=-1;
function renderSearch(){ /* cities are already loaded into LANDING_DATA; nothing to pre-render until typed */ }
function filterSearch(q){
  const drop=document.getElementById('searchDrop');
  q=(q||'').trim().toLowerCase();
  const matches=q?LANDING_DATA.cities.filter(c=>c.toLowerCase().includes(q)):LANDING_DATA.cities;
  SEARCH_HI=-1;
  if(!matches.length){ drop.classList.remove('on'); drop.innerHTML=''; return; }
  drop.innerHTML=matches.map(c=>
    `<div class="searchItem" onclick="goToCity('${c}')"><svg><use href="#${cityIcon(c)}"/></svg>${c}</div>`).join('');
  drop.classList.add('on');
}
function searchKeydown(e){
  const drop=document.getElementById('searchDrop');
  const items=[...drop.querySelectorAll('.searchItem')];
  if(!items.length)return;
  if(e.key==='ArrowDown'){ e.preventDefault(); SEARCH_HI=Math.min(SEARCH_HI+1,items.length-1); }
  else if(e.key==='ArrowUp'){ e.preventDefault(); SEARCH_HI=Math.max(SEARCH_HI-1,0); }
  else if(e.key==='Enter'){ e.preventDefault(); if(SEARCH_HI>=0)items[SEARCH_HI].click(); return; }
  else return;
  items.forEach((it,i)=>it.classList.toggle('hi',i===SEARCH_HI));
}
addEventListener('click',e=>{ if(!e.target.closest('.searchWrap'))document.getElementById('searchDrop')?.classList.remove('on'); });
```

- [ ] **Step 3: Browser verify** — reload; focus the search input with no text: all 10 cities list. Type "chen": only Chennai shown. Press ArrowDown then Enter: navigates to `/dashboard?city=Chennai`. Click outside: dropdown closes. No console errors.

- [ ] **Step 4: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "feat: city search bar honestly scoped to the 10 tracked cities

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 4: India map picker

**Files:**
- Modify: `app/templates/landing.html`

**Interfaces:**
- Consumes: `LANDING_DATA.ranking` (Task 1, for AQI/band per city), `bandOf`, `cityIcon`, `goToCity`.
- Produces: `function renderMap()`; section `#map`; constant `CITY_COORDS` (relative x/y within a `0 0 300 340` viewBox — approximate placement only, not a geographic projection).

- [ ] **Step 1: Markup** — insert right after the `#showcase` section's closing `</section>` and before `<section id="why">`:

```html
<section id="map">
  <div class="kicker reveal">Pick a city</div>
  <h2 class="reveal d1">Ten cities. One tap away.</h2>
  <p class="lead reveal d2">A simplified outline, not a survey map — each dot is one of the ten cities
    VayuSense actually tracks, colored by its current AQI band.</p>
  <div class="mapWrap reveal d3">
    <svg id="indiaMap" viewBox="0 0 300 340" style="width:100%;height:auto">
      <path d="M150,10 L180,15 L205,35 L225,55 L235,80 L225,100 L235,120 L250,140 L255,165 L245,185 L230,200 L220,225 L200,250 L180,275 L160,300 L145,320 L135,300 L120,275 L100,250 L90,225 L75,205 L65,180 L70,155 L60,130 L65,105 L55,85 L65,60 L85,40 L110,25 Z"
        fill="rgba(157,193,255,.06)" stroke="var(--line)" stroke-width="1.5"/>
      <g id="mapDots"></g>
    </svg>
  </div>
</section>
```

- [ ] **Step 2: `CITY_COORDS` + `renderMap()`** — add to the script:

```javascript
const CITY_COORDS={
  Delhi:[150,70], Lucknow:[185,95], Patna:[230,110], Kolkata:[210,150],
  Ahmedabad:[95,150], Mumbai:[100,195], Pune:[115,215], Hyderabad:[150,225],
  Bengaluru:[135,270], Chennai:[175,275],
};
function renderMap(){
  const g=document.getElementById('mapDots');
  if(!g)return;
  g.innerHTML=LANDING_DATA.ranking.map(r=>{
    const xy=CITY_COORDS[r.city]; if(!xy)return '';
    const [x,y]=xy; const b=bandOf(r.aqi);
    return `<g class="mapDot" tabindex="0" role="button" aria-label="${r.city}, AQI ${r.aqi}, ${r.category}"
        onclick="goToCity('${r.city}')" onkeydown="if(event.key==='Enter')goToCity('${r.city}')">
      <title>${r.city} — AQI ${r.aqi} (${r.category})</title>
      <circle cx="${x}" cy="${y}" r="6" fill="${b.color}" stroke="#0e1424" stroke-width="1.5"/>
      <text class="mapLabel" x="${x+9}" y="${y+3}">${r.city}</text>
    </g>`;
  }).join('');
}
```

- [ ] **Step 3: Browser verify** — reload; confirm the India outline renders with 10 colored dots roughly matching each city's real geography (Delhi north, Chennai/Bengaluru south, Mumbai/Ahmedabad west, Kolkata/Patna east); dot colors match `bandOf` for that city's real AQI from `/api/aqi`'s ranking; clicking a dot navigates to `/dashboard?city=<name>`; each `<g>` is keyboard-focusable and Enter triggers navigation; hovering enlarges the dot (`.mapDot:hover circle{r:8}` — confirm via computed style or visual check); no console errors.

- [ ] **Step 4: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "feat: India outline map picker with live AQI-colored city dots

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 5: Icon animation pass, hackathon-alignment audit, deploy, live verify

**Files:**
- Modify: `app/templates/landing.html`
- Review only: `PRODUCT.md`

- [ ] **Step 1: Confirm reveal + hover already apply** — Tasks 2-4 already added `.reveal` classes to the new showcase tiles, map section, and search wrap, and `.showTile:hover .ic{transform:scale(1.08) translateY(-2px)}` already covers the hover micro-interaction (Task 2 Step's CSS in Task 1). No further markup change needed; this step is a verification pass:
  - Reload the page with devtools' reduced-motion emulation OFF: scroll through and confirm the 4 showcase tiles and the map section fade/slide in individually as they cross into view (not all at once).
  - Emulate `prefers-reduced-motion: reduce` (devtools rendering tab): confirm all `.reveal` elements are visible immediately with no animation (existing CSS media query already handles this — verify it still does for the new elements, since they reuse the same class).

- [ ] **Step 2: Hackathon-alignment audit** — read `PRODUCT.md` and confirm, in a short note added to the bottom of this plan file's execution log (not a new file): the four evaluation criteria (Solution Architecture & Technical Execution; Innovation Quality & Functional Depth; Real-world Impact & Applicability; UX/Presentation/Technical Feasibility) each still map to at least one concrete, shipped feature. Report the mapping in the chat when this task completes — no code change from this step.

- [ ] **Step 3: Full regression check** — no new pytest surface was added in this phase, but confirm nothing broke:

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all 60 tests still passing (this phase touched only `landing.html`, not the app's Python code).

- [ ] **Step 4: Build + deploy**

`gcloud builds submit --config=/tmp/cloudbuild.yaml .` then
`gcloud run deploy vayusense --image=gcr.io/gen-lang-client-0133314577/vayusense --region=us-central1 --platform=managed`

- [ ] **Step 5: Live verify**

Run: `curl -s https://vayusense-663068003180.us-central1.run.app/ | grep -c 'searchInput\|indiaMap\|showcaseGrid'`
Expected: `3` (all three new elements present in the served HTML). Also load the live URL in a browser and visually confirm the showcase tiles, search, and map render with real data.

- [ ] **Step 6: Commit and push**

```bash
git add -A
git commit -m "feat: complete Phase 5A landing redesign (icon animation verified, hackathon alignment confirmed)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```
