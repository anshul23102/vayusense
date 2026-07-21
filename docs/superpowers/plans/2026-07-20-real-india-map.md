# Real India Map + 3D Tilt Implementation Plan (Renovation Phase 5D)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unrecognizable hand-drawn India blob with an accurate outline generated from real public boundary data, put all 10 city dots at their true relative positions, and add a genuine 3D tilt interaction reusing the codebase's own proven `.tilt` pattern.

**Architecture:** The real India boundary (`world.geo.json`'s `IND.geo.json`, a 136-point polygon) and the 10 cities' real (lon, lat) — already used in `ingest/discover_live_locations.py` — were projected together through one equirectangular projection function into the existing `viewBox="0 0 300 340"`, so the outline and the dots share the exact same coordinate space and can never drift apart. This plan wires the already-computed path string and coordinate table into `landing.html`, then adds the 3D tilt/hover/grab interaction in vanilla JS/CSS — no new library, no backend change.

**Tech Stack:** Vanilla JS/CSS (existing `.tilt` mousemove pattern already in `landing.html`), hand-projected SVG path (source data: public `world.geo.json` country-boundary dataset).

## Global Constraints

- Working dir `/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense`; dev server on :8090 auto-reloads.
- Frontend-only change to `app/templates/landing.html`. No backend changes, no new pytest surface.
- The new path and `CITY_COORDS` must fully replace, not supplement, the Phase 5A hand-drawn versions.
- Tilt/hover/grab must be gated by the existing `reduceMotion` const — fully disabled under reduced motion, dots stay flat and clickable.
- Commits end with the Co-Authored-By Claude trailer; push after each task. Deploy cadence: local verify → Cloud Build (`/tmp/cloudbuild.yaml`) → `gcloud run deploy vayusense --region=us-central1` → live verify → push.

---

### Task 1: Swap in the real India path + real city coordinates

**Files:**
- Modify: `app/templates/landing.html`

**Interfaces:**
- Produces: the `#indiaMap` `<path>`'s `d` attribute replaced with the real projected outline; `CITY_COORDS` replaced with real-geography-derived values (same object shape as before: `{CityName: [x, y], ...}`).

- [ ] **Step 1: Replace the hand-drawn path** — find the current `<path d="M150,10 L180,15 ...">` inside `<svg id="indiaMap" ...>` and replace its `d` attribute value with:

```
M103.2,40.0 L113.4,51.1 L112.4,58.8 L116.2,63.6 L115.9,68.4 L109.1,67.2 L111.7,77.6 L121.0,83.6 L134.2,90.2 L128.2,94.4 L124.5,103.3 L133.6,106.9 L142.5,111.5 L154.9,116.8 L167.8,118.0 L173.3,122.8 L180.5,123.7 L191.9,125.9 L199.8,125.8 L200.9,122.0 L199.6,116.0 L200.3,112.0 L206.1,110.0 L206.9,117.4 L207.1,119.3 L215.7,122.9 L221.6,121.4 L229.6,122.0 L237.3,121.8 L238.0,116.0 L234.1,112.9 L241.7,111.8 L250.3,104.7 L261.2,98.7 L269.1,101.0 L275.9,97.1 L280.3,102.9 L277.1,106.9 L287.3,108.3 L288.0,111.9 L284.7,113.6 L285.5,119.4 L278.7,117.7 L266.5,124.3 L266.8,129.7 L261.6,137.6 L261.1,142.2 L256.9,150.0 L249.5,147.8 L249.1,157.6 L247.0,160.8 L248.0,164.8 L243.3,167.1 L238.4,152.1 L235.8,152.1 L234.2,158.1 L229.0,153.2 L232.0,147.9 L236.2,147.3 L240.5,139.3 L235.1,137.7 L226.3,137.9 L217.3,136.6 L216.5,130.0 L212.0,129.5 L204.5,125.5 L201.2,131.9 L208.0,136.9 L202.1,140.4 L200.0,143.8 L205.8,146.4 L204.2,152.0 L207.5,159.1 L209.0,166.9 L207.6,170.4 L201.2,170.3 L189.5,172.2 L190.1,179.3 L185.0,184.9 L171.4,191.3 L160.9,202.4 L153.8,208.3 L144.4,214.5 L144.3,218.9 L139.6,221.2 L131.1,224.6 L126.7,225.1 L123.9,232.3 L125.9,244.5 L126.4,252.4 L122.4,261.4 L122.3,277.4 L117.4,277.9 L113.1,285.1 L116.0,288.2 L107.4,290.8 L104.2,297.3 L100.4,300.0 L91.5,291.2 L87.1,277.9 L83.5,268.4 L80.2,264.0 L75.2,254.9 L72.8,243.1 L71.2,237.2 L62.6,224.2 L58.7,205.9 L55.9,193.8 L55.9,182.4 L54.1,173.5 L40.3,179.2 L33.7,178.1 L21.3,166.6 L25.9,163.2 L23.1,159.5 L12.0,151.5 L18.3,145.2 L39.1,145.2 L37.2,137.1 L31.9,132.3 L30.8,125.0 L24.6,120.8 L35.0,110.9 L46.0,111.6 L55.9,101.7 L61.8,92.1 L71.0,82.6 L70.8,75.9 L78.9,70.5 L71.3,65.8 L68.0,59.4 L64.6,51.1 L69.3,47.1 L83.6,49.4 L94.1,48.0 L103.2,40.0 Z
```

This is a 136-point outline of India's mainland border, projected (equirectangular, true aspect preserved, 12px padding) from the public `world.geo.json` country-boundary dataset into the same `0 0 300 340` viewBox already in use.

- [ ] **Step 2: Replace `CITY_COORDS`** — find the current hand-guessed object and replace it entirely with:

```javascript
const CITY_COORDS={
  Delhi:[97.3,105.0], Mumbai:[56.4,195.1], Kolkata:[202.6,162.0], Chennai:[126.2,251.7],
  Bengaluru:[100.9,252.7], Hyderabad:[109.4,211.0], Pune:[65.6,200.3], Ahmedabad:[53.5,157.8],
  Lucknow:[132.6,121.7], Patna:[172.2,133.5],
};
```

These come from the exact same (longitude, latitude) values as `ingest/discover_live_locations.py`'s `CITY_QUERIES`, run through the identical projection used for the outline above — so the dots are geographically correct relative to the real coastline, not hand-guessed.

- [ ] **Step 3: Browser verify** — reload `http://localhost:8090/`; scroll to "Ten cities. One tap away."; confirm the outline is recognizably India (northern landmass, western coastline indent, eastern bulge, tapering south to a point) and all 10 dots sit in plausible real positions (Delhi north-center, Mumbai/Ahmedabad west coast, Kolkata/Patna east, Chennai/Bengaluru south); no dots fall outside the outline; no console errors.

- [ ] **Step 4: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "fix: replace hand-drawn India blob with an accurate outline from real geo data

Sourced from the public world.geo.json country-boundary dataset (IND.geo.json),
projected equirectangularly into the existing viewBox. City dots now use the
same real (lon, lat) values already in ingest/discover_live_locations.py,
run through the identical projection, so outline and dots share one
coordinate space and can never drift apart.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: 3D tilt, hover-lift, and grab cursor

**Files:**
- Modify: `app/templates/landing.html`

**Interfaces:**
- Consumes: `reduceMotion` (existing const), `.mapWrap`/`.mapDot` (existing elements from Phase 5A).

- [ ] **Step 1: CSS for hover-lift and grab cursor** — add near the existing `.mapDot`/`.mapLabel` rules:

```css
  .mapWrap{cursor:grab;transition:transform .4s cubic-bezier(.2,.8,.2,1);transform-style:preserve-3d}
  .mapWrap.grabbing{cursor:grabbing}
  .mapDot circle{transition:r .15s,filter .15s}
  .mapDot:hover circle,.mapDot:focus circle{filter:drop-shadow(0 4px 8px rgba(0,0,0,.5))}
  .mapDot:hover .mapLabel,.mapDot:focus .mapLabel{fill:var(--txt)}
  @media (prefers-reduced-motion: reduce){
    .mapWrap{transition:none !important;transform:none !important;cursor:default}
  }
```

(`.mapWrap` already has `position:relative;max-width:420px;margin:24px auto 0` from Phase 5A — this step adds to those rules, not replaces them; edit the existing `.mapWrap` rule to include the new properties rather than duplicating the selector.)

- [ ] **Step 2: JS tilt handler** — add near the existing `renderMap()` function, after it:

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

- [ ] **Step 3: Browser verify** — reload; move the mouse across the map: it should tilt smoothly toward the cursor (perspective rotation, not a flat pan) and spring back flat (via the CSS `transition`) when the mouse leaves; press and hold the mouse button down over the map: cursor becomes a "grabbing" hand and the tilt becomes slightly more pronounced while held; hover a city dot: it lifts with a soft drop-shadow and its label brightens; emulate `prefers-reduced-motion: reduce` in devtools and reload: the map stays perfectly flat, cursor is default, dots are still clickable; no console errors.

- [ ] **Step 4: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "feat: 3D tilt, hover-lift, and grab cursor on the India map

Reuses the exact mousemove/perspective/rotateX/rotateY pattern already
proven on the landing page's .tilt feature cards — no new library, no
WebGL. Fully gated behind the existing reduceMotion check.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 3: Deploy + live verify

- [ ] **Step 1: Full test suite** (frontend-only change, confirming no regression)

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all 65 tests still passing.

- [ ] **Step 2: Build + deploy**

`gcloud builds submit --config=/tmp/cloudbuild.yaml .` then
`gcloud run deploy vayusense --image=gcr.io/gen-lang-client-0133314577/vayusense --region=us-central1 --platform=managed`

- [ ] **Step 3: Live verify**

Run: `curl -s https://vayusense-663068003180.us-central1.run.app/ | grep -o 'M103.2,40.0' `
Expected: one match (confirms the real path shipped, not the old blob). Load the live URL in a browser, scroll to the map section, and confirm the outline reads as India and the tilt/hover interactions work.
