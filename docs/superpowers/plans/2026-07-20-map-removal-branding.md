# Remove Map, Add City Chip Grid, Strengthen Branding Implementation Plan (Renovation Phase 5E)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the India map entirely (all markup, JS, CSS), replace it with a non-map city chip grid using data already loaded, and give the VayuSense brand more visual presence in the nav and hero.

**Architecture:** Pure deletion of the map subsystem from `app/templates/landing.html`, followed by one new render function (`renderCityGrid()`) that reuses `LANDING_DATA.ranking`, `cityIcon()`, `bandOf()`, and `goToCity()` — all already defined from Phase 5A. Branding changes are CSS + one new markup line, no JS.

**Tech Stack:** Vanilla JS/CSS (existing `landing.html` only). No backend changes, no new pytest surface.

## Global Constraints

- Working dir `/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense`; dev server on :8090 auto-reloads.
- Every map-related identifier must be fully removed: `#map` section, `.mapWrap`/`.mapDot` CSS (including the reduced-motion override), `CITY_COORDS`, `renderMap()`, the tilt mousemove/mouseleave/mousedown/mouseup listener block, and the `renderMap()` call in `loadLandingData()`. Zero dead references left behind.
- The new city grid must use only data already fetched in `loadLandingData()` — no new network call.
- No new colors/fonts/shape system for the branding changes — stay inside existing DESIGN.md tokens (Space Grotesk, existing palette, existing `.kicker` treatment).
- Commits end with the Co-Authored-By Claude trailer; push after each task. Deploy cadence: local verify → Cloud Build (`/tmp/cloudbuild.yaml`) → `gcloud run deploy vayusense --region=us-central1` → live verify → push.

---

### Task 1: Remove the map completely

**Files:**
- Modify: `app/templates/landing.html`

**Interfaces:** none (pure deletion).

- [ ] **Step 1: Remove the `#map` section markup** — delete the entire block:

```html
<section id="map">
  <div class="kicker reveal">Pick a city</div>
  <h2 class="reveal d1">Ten cities. One tap away.</h2>
  <p class="lead reveal d2">A simplified outline, not a survey map — each dot is one of the ten cities
    VayuSense actually tracks, colored by its current AQI band.</p>
  <div class="mapWrap reveal d3">
    <svg id="indiaMap" viewBox="0 0 300 340" style="width:100%;height:auto">
      <path d="M103.2,40.0 ...Z"
        fill="rgba(157,193,255,.06)" stroke="var(--line)" stroke-width="1.5"/>
      <g id="mapDots"></g>
    </svg>
  </div>
</section>
```

(The actual `d` attribute is the long real-India path from Phase 5D — delete the whole `<section id="map">...</section>` block regardless of its exact path string.)

- [ ] **Step 2: Remove map CSS** — delete these rules entirely:

```css
  .mapWrap{position:relative;max-width:420px;margin:24px auto 0;cursor:grab;
    transition:transform .4s cubic-bezier(.2,.8,.2,1);transform-style:preserve-3d}
  .mapWrap.grabbing{cursor:grabbing}
  .mapDot circle{transition:r .15s,filter .15s}
  .mapDot:hover circle,.mapDot:focus circle{filter:drop-shadow(0 4px 8px rgba(0,0,0,.5))}
  .mapDot:hover .mapLabel,.mapDot:focus .mapLabel{fill:var(--txt)}
  .mapDot{cursor:pointer;transition:r .15s}
  .mapDot:hover circle{r:8}
```

and this line from the `prefers-reduced-motion` media query block (leave the rest of that block intact):

```css
    .mapWrap{transition:none !important;transform:none !important;cursor:default}
```

- [ ] **Step 3: Remove `CITY_COORDS` and `renderMap()`** — delete:

```javascript
const CITY_COORDS={
  Delhi:[97.3,105.0], Mumbai:[56.4,195.1], Kolkata:[202.6,162.0], Chennai:[126.2,251.7],
  Bengaluru:[100.9,252.7], Hyderabad:[109.4,211.0], Pune:[65.6,200.3], Ahmedabad:[53.5,157.8],
  Lucknow:[132.6,121.7], Patna:[172.2,133.5],
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

- [ ] **Step 4: Remove the tilt listener block** — delete:

```javascript
if(!reduceMotion){
  const mapWrap=document.querySelector('.mapWrap');
  if(mapWrap){
    let grabbing=false;
    mapWrap.addEventListener('mousemove', e=>{
      const r=mapWrap.getBoundingClientRect();
      const x=(e.clientX-r.left)/r.width-.5, y=(e.clientY-r.top)/r.height-.5;
      const intensity=grabbing?16:10;
      mapWrap.style.transform=`perspective(900px) rotateY(${x*intensity}deg) rotateX(${-y*intensity}deg)`;
    });
    mapWrap.addEventListener('mouseleave', ()=>{ mapWrap.style.transform=''; grabbing=false; mapWrap.classList.remove('grabbing'); });
    mapWrap.addEventListener('mousedown', ()=>{ grabbing=true; mapWrap.classList.add('grabbing'); });
    mapWrap.addEventListener('mouseup', ()=>{ grabbing=false; mapWrap.classList.remove('grabbing'); });
  }
}
```

- [ ] **Step 5: Remove the `renderMap()` call** — in `loadLandingData()`, find:

```javascript
    renderShowcase();
    renderSearch();
    renderMap();
```

replace with:

```javascript
    renderShowcase();
    renderSearch();
    renderCityGrid();
```

(`renderCityGrid` is defined in Task 2 — this call is added now so the file stays syntactically complete after this task, even though the function body doesn't exist until Task 2. Since both tasks land in the same session before any deploy, this is safe; if executing Task 1 alone leaves a dangling reference, that's expected and resolved immediately by Task 2.)

- [ ] **Step 6: Grep-verify full removal**

Run: `grep -c "mapWrap\|mapDot\|CITY_COORDS\|renderMap\b\|indiaMap\|id=\"map\"" app/templates/landing.html`
Expected: `0` (after Task 1's edits — `renderCityGrid` reference from Step 5 doesn't match this pattern, so it won't cause a false positive).

- [ ] **Step 7: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "refactor: remove the India map entirely

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: City chip grid (map replacement)

**Files:**
- Modify: `app/templates/landing.html`

**Interfaces:**
- Consumes: `LANDING_DATA.ranking` (existing), `cityIcon()`, `bandOf()`, `goToCity()` (all existing from Phase 5A).
- Produces: `function renderCityGrid()`; markup section (same id-position as the old `#map`, i.e. right after `#showcase`'s closing `</section>`).

- [ ] **Step 1: Markup** — insert where `#map` used to be (right after `#showcase`'s closing `</section>` and before `<section id="why">`):

```html
<section id="cities-grid">
  <div class="kicker reveal">Pick a city</div>
  <h2 class="reveal d1">Ten cities. One tap away.</h2>
  <div class="showcase" id="cityGrid"></div>
</section>
```

- [ ] **Step 2: `renderCityGrid()`** — add near `renderShowcase()`:

```javascript
function renderCityGrid(){
  const grid=document.getElementById('cityGrid');
  if(!grid)return;
  grid.innerHTML=LANDING_DATA.ranking.map((r,i)=>{
    const b=bandOf(r.aqi);
    return `<div class="showTile reveal ${i%4===1?'d1':i%4===2?'d2':i%4===3?'d3':''}" style="cursor:pointer;border-left:3px solid ${b.color}"
        onclick="goToCity('${r.city}')" role="button" tabindex="0"
        onkeydown="if(event.key==='Enter')goToCity('${r.city}')">
      <div class="ic"><svg><use href="#${cityIcon(r.city)}"/></svg></div>
      <h3 class="num" style="font-size:20px">${r.city}</h3>
      <p><span class="num" style="font-size:18px;color:var(--txt)">${r.aqi}</span> AQI ·
        <span style="color:${b.color}">${r.category}</span></p>
    </div>`;
  }).join('');
  document.querySelectorAll('#cityGrid .reveal').forEach(el=>io.observe(el));
}
```

- [ ] **Step 3: Browser verify** — reload `http://localhost:8090/`; confirm the map is fully gone (no SVG outline anywhere on the page) and a "Ten cities. One tap away." grid of 10 chips renders instead, each showing the correct landmark icon, live AQI, and category color per city; clicking a chip navigates to `/city/<slug>`; keyboard Enter on a focused chip also navigates; no console errors.

- [ ] **Step 4: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "feat: city chip grid replaces the map (same 10-city browse, no geography)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 3: Strengthen branding

**Files:**
- Modify: `app/templates/landing.html`

- [ ] **Step 1: Nav wordmark CSS** — find:

```css
  .logo{font-weight:650;font-size:18px;letter-spacing:.2px;display:flex;align-items:center;gap:10px}
```
replace with:
```css
  .logo{font-weight:700;font-size:21px;letter-spacing:.2px;display:flex;align-items:center;gap:10px}
```

Find the `.logo .dot` rule's `box-shadow` value and increase its glow intensity — locate:
```css
  .logo .dot{width:26px;height:26px;border-radius:9px;background:conic-gradient(from 210deg,#9dc1ff,#b9a8fb,#9dc1ff);
```
Read the following line (the `box-shadow` declaration) and increase its opacity/blur by roughly 30-40% (e.g. if it currently reads `box-shadow:0 0 18px rgba(157,193,255,.55)`, change to `box-shadow:0 0 24px rgba(157,193,255,.7)`) — read the exact current value from the file first since it wasn't reproduced verbatim here, then apply the increase.

- [ ] **Step 2: Hero kicker label** — find the hero's opening:

```html
<div class="hero">
  <div class="chip reveal on"><span class="pulse"></span> GPU-accelerated · Multi-agent AI · <b>12.8M real sensor readings</b></div>
```

Insert a new kicker line between `<div class="hero">` and the `.chip` div:

```html
<div class="hero">
  <div class="kicker reveal on" style="text-align:center">VAYUSENSE</div>
  <div class="chip reveal on"><span class="pulse"></span> GPU-accelerated · Multi-agent AI · <b>12.8M real sensor readings</b></div>
```

(The existing `.kicker` class already provides the uppercase/tracked/colored treatment used elsewhere on the page — this reuses it, adding only inline centering since the hero is a centered layout unlike the left-aligned section kickers.)

- [ ] **Step 3: Browser verify** — reload; confirm the nav wordmark is visibly larger/bolder with a stronger glow on the mark; confirm "VAYUSENSE" appears as a small centered kicker label above the "Know when the air is safe" headline; no layout breakage on mobile width (resize browser narrow and check no wrapping issues); no console errors.

- [ ] **Step 4: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "feat: strengthen the VayuSense brand presence in nav and hero

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 4: Full deploy + live verify

- [ ] **Step 1: Full test suite** (frontend-only change, confirming no regression)

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all 65 tests still passing.

- [ ] **Step 2: Build + deploy**

`gcloud builds submit --config=/tmp/cloudbuild.yaml .` then
`gcloud run deploy vayusense --image=gcr.io/gen-lang-client-0133314577/vayusense --region=us-central1 --platform=managed`

- [ ] **Step 3: Live verify**

Run: `curl -s https://vayusense-663068003180.us-central1.run.app/ | grep -c 'indiaMap\|mapWrap\|mapDot'`
Expected: `0`. Then: `curl -s https://vayusense-663068003180.us-central1.run.app/ | grep -c 'cityGrid\|VAYUSENSE'`
Expected: `≥2`. Load the live URL in a browser and visually confirm the map is gone, the city chip grid works, and the branding reads more prominently.
