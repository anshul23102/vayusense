# Vivid Palette + Larger Icons Implementation Plan (Renovation Phase 6A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise saturation/brightness across the existing color token set (same tokens, same meanings) and add + enlarge informational icons (pollutant gas icons are currently missing entirely; city/health icons need sizing up).

**Architecture:** Global hex-value substitution across `DESIGN.md`, `app/templates/index.html`, and `app/templates/landing.html` (same token names, new values) plus 6 new monoline gas-icon SVG symbols added to `index.html`'s sprite and wired into the pollutant card render, and CSS size bumps on existing icon-badge classes.

**Tech Stack:** CSS custom properties, hand-authored SVG (existing monoline technique), vanilla JS template strings.

## Global Constraints

- Working dir `/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense`; dev server on :8090 auto-reloads.
- Exact hex replacements (old → new), verified WCAG-safe against `#0e1424` in the spec — use these exact values, no further adjustment:
  - `#4fe3ac` → `#3dfc9e` (Good/signal-ok)
  - `#ffce80` → `#ffc247` (Moderate/amber-caution)
  - `#ffab73` → `#ff9640` (Poor/Ember)
  - `#ff8aa3` → `#ff5c85` (Unhealthy/alert-rose)
  - `#ef7ac8` → `#ef4fc0` (Severe/Magenta Signal)
  - `#b04a63` → `#c93a5a` (Hazardous/Oxblood)
  - `#9dc1ff` → `#7fb0ff` (ice-solid)
  - `#b9a8fb` → `#a688fb` (ultraviolet)
  - `#9adb3f` → `#8ef22a` (photon-green)
- No backend changes, no new pytest surface.
- Commits end with the Co-Authored-By Claude trailer; push after each task. Deploy cadence: local verify → Cloud Build (`/tmp/cloudbuild.yaml`) → `gcloud run deploy vayusense --region=us-central1` → live verify → push.

---

### Task 1: Global color value replacement

**Files:**
- Modify: `DESIGN.md`, `app/templates/index.html`, `app/templates/landing.html`

**Interfaces:** none (value substitution only, same token names/CSS var names).

- [ ] **Step 1: Replace in DESIGN.md frontmatter** — update the `colors:` block values for `signal-ok`, `amber-caution`, `ice-solid`, `ultraviolet`, `photon-green` to their new hex values from Global Constraints (Ember/Magenta Signal/Oxblood live in the prose "Tertiary" section, not frontmatter — update those three hex mentions there too).

- [ ] **Step 2: Replace in `app/templates/index.html`** — run a global find-replace for each of the 9 old→new hex pairs across the file (CSS custom properties block, inline styles, and the JS `RAMP` object all contain these values and must all update consistently):

```bash
cd "/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense"
python3 - <<'EOF'
import re
pairs = {
    "#4fe3ac": "#3dfc9e", "#ffce80": "#ffc247", "#ffab73": "#ff9640",
    "#ff8aa3": "#ff5c85", "#ef7ac8": "#ef4fc0", "#b04a63": "#c93a5a",
    "#9dc1ff": "#7fb0ff", "#b9a8fb": "#a688fb", "#9adb3f": "#8ef22a",
}
for path in ["app/templates/index.html", "app/templates/landing.html", "DESIGN.md"]:
    text = open(path).read()
    for old, new in pairs.items():
        text = text.replace(old, new)
    open(path, "w").write(text)
print("done")
EOF
```

- [ ] **Step 3: Verify no old hex values remain**

Run: `grep -rc "#4fe3ac\|#ffce80\|#ffab73\|#ff8aa3\|#ef7ac8\|#b04a63\|#9dc1ff\|#b9a8fb\|#9adb3f" app/templates/index.html app/templates/landing.html DESIGN.md`
Expected: `0` for each file (or the grep reports no matches at all).

- [ ] **Step 4: Browser verify** — reload `http://localhost:8090/dashboard`; confirm the AQI ring, category chip, and pollutant severity edge-bars render in the new, more saturated colors; reload `http://localhost:8090/`; confirm the map-replacement city chips and showcase tiles also reflect new colors; no console errors.

- [ ] **Step 5: Commit and push**

```bash
git add DESIGN.md app/templates/index.html app/templates/landing.html
git commit -m "feat: more vivid, saturated color palette (same tokens, new values)

All 9 updated hex values verified WCAG-AA (>=3.0:1) against the night
background before this change; see docs/superpowers/specs/2026-07-21-vivid-palette-icons-design.md.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: Pollutant gas icons (new) + larger icon sizing

**Files:**
- Modify: `app/templates/index.html`

**Interfaces:**
- Produces: 6 new icon symbols (`ic-pm25`, `ic-pm10`, `ic-co`, `ic-so2`, `ic-no2`, `ic-o3`); `POLL_ICON` JS map; pollutant cards gain an icon slot (previously had none).

- [ ] **Step 1: Add 6 new gas icon symbols** to the existing sprite (same block edited in prior phases), before its closing `</svg>`:

```html
  <symbol id="ic-pm25" viewBox="0 0 24 24"><circle cx="7" cy="8" r="1.4" fill="currentColor"/><circle cx="14" cy="6" r="1" fill="currentColor"/><circle cx="17" cy="13" r="1.7" fill="currentColor"/><circle cx="9" cy="15" r="1.1" fill="currentColor"/><circle cx="15" cy="18" r="0.9" fill="currentColor"/><circle cx="6" cy="17" r="0.8" fill="currentColor"/></symbol>
  <symbol id="ic-pm10" viewBox="0 0 24 24"><circle cx="8" cy="9" r="2.4" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="16" cy="9" r="1.9" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="16" r="2.7" fill="none" stroke="currentColor" stroke-width="1.6"/></symbol>
  <symbol id="ic-co" viewBox="0 0 24 24"><circle cx="8" cy="12" r="4.2" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="16.5" cy="12" r="3.2" fill="none" stroke="currentColor" stroke-width="1.7"/></symbol>
  <symbol id="ic-so2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="5.5" cy="8" r="2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="18.5" cy="8" r="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8.8 10.3L9.6 9.6M15.2 10.3L14.4 9.6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></symbol>
  <symbol id="ic-no2" viewBox="0 0 24 24"><circle cx="12" cy="9" r="3.2" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="5.5" cy="16" r="2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="18.5" cy="16" r="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M9.5 11.3L8 14.3M14.5 11.3L16 14.3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></symbol>
  <symbol id="ic-o3" viewBox="0 0 24 24"><circle cx="12" cy="7" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="6.5" cy="16" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="17.5" cy="16" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/></symbol>
```

- [ ] **Step 2: `POLL_ICON` map** — add near `POLL_NAMES`:

```javascript
const POLL_ICON={pm25:'ic-pm25',pm10:'ic-pm10',co:'ic-co',so2:'ic-so2',no2:'ic-no2',o3:'ic-o3'};
```

- [ ] **Step 3: Wire the icon into the pollutant card render** — find the pollutant card template string (inside the `$('pollGrid').innerHTML=...` map callback) and add an icon slot before the existing label div. Replace:

```javascript
          return `<div class="s4"><button type="button" class="objCard cardIn" style="animation-delay:${i*40}ms;border-left:3px solid ${b.color};width:100%;text-align:left;cursor:pointer;color:inherit;font:inherit"
            onclick="$('paramSel').value='${p}';$('paramSel').dispatchEvent(new Event('change'));$('trend').scrollIntoView({behavior:'smooth'})">
            <div style="color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.8px">${POLL_NAMES[p]||p}</div>
```

with:

```javascript
          return `<div class="s4"><button type="button" class="objCard cardIn" style="animation-delay:${i*40}ms;border-left:3px solid ${b.color};width:100%;text-align:left;cursor:pointer;color:inherit;font:inherit"
            onclick="$('paramSel').value='${p}';$('paramSel').dispatchEvent(new Event('change'));$('trend').scrollIntoView({behavior:'smooth'})">
            <div style="width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:10px;background:${b.color}1f;color:${b.color}"><svg style="width:20px;height:20px"><use href="#${POLL_ICON[p]||'ic-pm25'}"/></svg></div>
            <div style="color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.8px">${POLL_NAMES[p]||p}</div>
```

- [ ] **Step 4: Scale up existing icon-anchor CSS** — find and update:

```css
  .cityIconBadge{width:32px;height:32px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex:none}
  .cityIconBadge svg{width:18px;height:18px}
```
replace with:
```css
  .cityIconBadge{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex:none}
  .cityIconBadge svg{width:24px;height:24px}
```

and:
```css
  .healthTab svg{width:15px;height:15px}
```
replace with:
```css
  .healthTab svg{width:20px;height:20px}
```

- [ ] **Step 5: Browser verify** — reload dashboard; confirm all 6 pollutant cards now show a distinct icon (particulate dots for PM2.5/PM10, molecule shapes for CO/SO2/NO2/O3) above the label, tinted to that pollutant's severity color; city ranking-row icon badges are visibly larger (42px vs 32px); health-condition tab icons are visibly larger (20px vs 15px); no layout overflow/wrapping issues; no console errors.

- [ ] **Step 6: Commit and push**

```bash
git add app/templates/index.html
git commit -m "feat: add pollutant gas icons (previously missing) + enlarge informational icons

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 3: Deploy + live verify

- [ ] **Step 1: Full test suite**

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all 65 tests still passing (frontend-only change).

- [ ] **Step 2: Build + deploy**

`gcloud builds submit --config=/tmp/cloudbuild.yaml .` then
`gcloud run deploy vayusense --image=gcr.io/gen-lang-client-0133314577/vayusense --region=us-central1 --platform=managed`

- [ ] **Step 3: Live verify**

Run: `curl -s https://vayusense-663068003180.us-central1.run.app/dashboard | grep -o '#3dfc9e\|#ff9640\|ic-pm25' | sort -u`
Expected: all three strings present. Load the live dashboard in a browser and visually confirm the more vivid colors and the new pollutant icons.
