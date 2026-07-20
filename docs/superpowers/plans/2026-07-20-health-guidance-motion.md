# Health Guidance + Motion Polish Implementation Plan (Renovation Phase 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Instant, rule-based per-condition health guidance (6 conditions × 6 AQI categories, zero LLM calls) plus a scoped count-up animation for the AQI/cigarette/life-expectancy numbers.

**Architecture:** A pure-data Python module (`agents/health_guidance.py`) holds the 36-cell guidance table; a thin FastAPI endpoint serves it once per page load; the frontend caches it in a JS variable and re-renders the active tab instantly on tab click or AQI-category change — no per-click network round trip. Motion is a single reusable `countUp()` JS utility applied to three existing elements, gated by the page's existing `reduceMotion` flag.

**Tech Stack:** Python (pure functions, no new deps), FastAPI, vanilla JS/CSS, pytest.

## Global Constraints

- Working dir `/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense`; venv `.venv/bin/python`; dev server on :8090 auto-reloads.
- Condition keys (exact, used everywhere): `general`, `children`, `elderly`, `asthma`, `heart`, `outdoor_workers`.
- Category keys (exact, must match `agents/aqi.py` `CATEGORIES` order): `good`, `moderate`, `poor`, `unhealthy`, `severe`, `hazardous`.
- No new LLM/agent calls anywhere in this phase. No changes to forecast bench, calendar, trends, or ranking beyond placement of the new section.
- All new motion respects the existing `reduceMotion` JS const in `index.html` — reduced-motion users get the final value/state immediately, no animation frames.
- Commits end with the Co-Authored-By Claude trailer; push after each task. Deploy cadence: local verify → Cloud Build (`/tmp/cloudbuild.yaml`) → `gcloud run deploy vayusense --region=us-central1` → live verify → push.

---

### Task 1: `agents/health_guidance.py` — the 36-cell guidance table

**Files:**
- Create: `agents/health_guidance.py`
- Test: `tests/test_health_guidance.py`

**Interfaces:**
- Produces: `CONDITIONS: list[str]` (order = display order), `CONDITION_LABELS: dict[str, str]`, `GUIDANCE: dict[str, dict[str, str]]` (condition → category → text), `get_guidance(condition: str, category_key: str) -> str` (raises `KeyError` on unknown condition or category), `citation() -> str`.

- [ ] **Step 1: Write the failing test**

`tests/test_health_guidance.py`:
```python
import pytest

from agents.health_guidance import (
    CONDITIONS, CONDITION_LABELS, GUIDANCE, citation, get_guidance,
)

CATEGORY_KEYS = ["good", "moderate", "poor", "unhealthy", "severe", "hazardous"]


def test_all_conditions_have_labels():
    assert set(CONDITIONS) == set(CONDITION_LABELS)
    assert len(CONDITIONS) == 6


def test_every_cell_present_and_nonempty():
    for cond in CONDITIONS:
        assert set(GUIDANCE[cond]) == set(CATEGORY_KEYS)
        for cat in CATEGORY_KEYS:
            text = GUIDANCE[cond][cat]
            assert isinstance(text, str) and len(text) > 15


def test_no_duplicate_text_within_a_condition():
    for cond in CONDITIONS:
        texts = list(GUIDANCE[cond].values())
        assert len(texts) == len(set(texts)), f"duplicate guidance text in {cond}"


def test_get_guidance_returns_cell():
    assert get_guidance("asthma", "hazardous") == GUIDANCE["asthma"]["hazardous"]


def test_get_guidance_raises_on_unknown_inputs():
    with pytest.raises(KeyError):
        get_guidance("unknown_condition", "good")
    with pytest.raises(KeyError):
        get_guidance("general", "unknown_category")


def test_citation_nonempty():
    assert len(citation()) > 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_health_guidance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.health_guidance'`

- [ ] **Step 3: Implement `agents/health_guidance.py`**

```python
"""Instant, rule-based health guidance per condition and AQI category.

Deterministic and LLM-free by design: keeps the product's "facts before advice"
principle intact for a feature that would otherwise tempt a per-click agent call.
Category keys match agents/aqi.py's CATEGORIES exactly."""
from __future__ import annotations

CONDITIONS = ["general", "children", "elderly", "asthma", "heart", "outdoor_workers"]

CONDITION_LABELS = {
    "general": "General Population",
    "children": "Children",
    "elderly": "Elderly",
    "asthma": "Asthma / Respiratory",
    "heart": "Heart / Cardiovascular",
    "outdoor_workers": "Outdoor Workers & Athletes",
}

GUIDANCE = {
    "general": {
        "good": "Air quality poses little or no risk. Enjoy normal outdoor activities.",
        "moderate": "Air quality is acceptable for most people. Unusually sensitive individuals should consider reducing prolonged outdoor exertion.",
        "poor": "Reduce prolonged or heavy outdoor exertion, especially if you notice coughing or throat irritation.",
        "unhealthy": "Limit prolonged outdoor exertion. Consider moving strenuous activities indoors or to a later time.",
        "severe": "Avoid prolonged outdoor exertion. Keep windows closed and run an air purifier indoors if available.",
        "hazardous": "Avoid all outdoor physical activity. Remain indoors with air filtration running whenever possible.",
    },
    "children": {
        "good": "No restrictions. Outdoor play is safe.",
        "moderate": "Outdoor play remains fine, but watch for coughing or unusual tiredness during extended activity.",
        "poor": "Shorten outdoor playtime and swap vigorous games for lighter activity, particularly for children with an asthma history.",
        "unhealthy": "Move recess and sports practice indoors where possible. Children's developing lungs are more sensitive to sustained exposure.",
        "severe": "Keep children indoors. Schools should suspend outdoor activities and physical education.",
        "hazardous": "Keep children indoors at all times with windows closed. Seek medical advice if a child shows breathing difficulty.",
    },
    "elderly": {
        "good": "No precautions needed.",
        "moderate": "Generally safe, but elderly individuals with existing heart or lung conditions should monitor how they feel during outdoor activity.",
        "poor": "Reduce time spent outdoors, especially during the day's peak pollution hours.",
        "unhealthy": "Limit outdoor exposure and avoid unnecessary errands outside. Rest indoors if experiencing fatigue or breathlessness.",
        "severe": "Stay indoors as much as possible. Keep any prescribed inhalers or heart medication readily accessible.",
        "hazardous": "Remain indoors continuously. Contact a doctor promptly if chest tightness, dizziness, or breathing difficulty occurs.",
    },
    "asthma": {
        "good": "Air quality is unlikely to trigger symptoms.",
        "moderate": "Keep rescue medication on hand; most people with well-controlled asthma will be unaffected.",
        "poor": "Carry a reliever inhaler and reduce outdoor exertion. Pollution at this level can trigger symptoms in sensitive airways.",
        "unhealthy": "Avoid outdoor exertion entirely. Pre-treat with prescribed medication before any necessary outdoor exposure.",
        "severe": "Stay indoors with air filtration running. This level of pollution can provoke asthma attacks even at rest.",
        "hazardous": "Remain indoors and keep emergency medication within reach. Seek urgent care immediately if breathing worsens.",
    },
    "heart": {
        "good": "No added cardiovascular risk from air quality today.",
        "moderate": "Low added risk; people with heart disease can continue normal routines.",
        "poor": "Reduce strenuous outdoor activity. Fine particulate matter at this level has been linked to added strain on the cardiovascular system.",
        "unhealthy": "Avoid outdoor exertion. Sustained exposure at this level is associated with increased risk of cardiac events in vulnerable individuals.",
        "severe": "Stay indoors and avoid physical exertion of any kind. Monitor for chest pain, palpitations, or unusual shortness of breath.",
        "hazardous": "Remain indoors and minimize all exertion. Seek emergency care immediately for any chest pain or cardiac symptoms.",
    },
    "outdoor_workers": {
        "good": "Full outdoor training and work schedules are safe.",
        "moderate": "Normal outdoor work and training can continue; stay alert to any respiratory discomfort during intense exertion.",
        "poor": "Schedule the most strenuous outdoor work or training for early morning when pollution is typically lower, and take more frequent breaks.",
        "unhealthy": "Reduce training intensity and duration. Employers should provide more frequent indoor rest breaks for outdoor workers.",
        "severe": "Postpone outdoor training and non-essential outdoor work. Use N95-class masks if outdoor work cannot be avoided.",
        "hazardous": "Suspend outdoor training and non-essential outdoor labor entirely. Essential outdoor work should be minimized and use respiratory protection.",
    },
}


def get_guidance(condition: str, category_key: str) -> str:
    return GUIDANCE[condition][category_key]


def citation() -> str:
    return ("Guidance keyed to WHO Air Quality Guidelines and US EPA AQI category "
            "thresholds for sensitive groups.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_health_guidance.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit and push**

```bash
git add agents/health_guidance.py tests/test_health_guidance.py
git commit -m "feat: rule-based health guidance table (6 conditions x 6 AQI categories)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: `GET /api/health_guidance` endpoint

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_health_guidance_api.py`

**Interfaces:**
- Consumes: `agents.health_guidance` (Task 1).
- Produces: route `GET /api/health_guidance` → `{"conditions": [...], "labels": {...}, "guidance": {...}, "citation": "..."}`.

- [ ] **Step 1: Write the failing test**

`tests/test_health_guidance_api.py`:
```python
from agents.health_guidance import CONDITIONS
from app.main import health_guidance_api


def test_health_guidance_api_shape():
    out = health_guidance_api()
    assert out["conditions"] == CONDITIONS
    assert set(out["labels"]) == set(CONDITIONS)
    assert set(out["guidance"]) == set(CONDITIONS)
    for cond in CONDITIONS:
        assert set(out["guidance"][cond]) == {"good", "moderate", "poor", "unhealthy", "severe", "hazardous"}
    assert len(out["citation"]) > 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_health_guidance_api.py -v`
Expected: FAIL — `ImportError: cannot import name 'health_guidance_api'`

- [ ] **Step 3: Implement in `app/main.py`** — add import near the other `agents` imports:

```python
from agents.health_guidance import CONDITIONS, CONDITION_LABELS, GUIDANCE, citation as health_citation
```

Add the route after `/api/monthly`:

```python
@app.get("/api/health_guidance")
def health_guidance_api():
    return {"conditions": CONDITIONS, "labels": CONDITION_LABELS,
            "guidance": GUIDANCE, "citation": health_citation()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all green (53 existing + 6 + 1 = 60)

- [ ] **Step 5: HTTP smoke test**

Run: `curl -s "http://localhost:8090/api/health_guidance" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['conditions']), len(d['guidance']['asthma']))"`
Expected: `6 6`

- [ ] **Step 6: Commit and push**

```bash
git add app/main.py tests/test_health_guidance_api.py
git commit -m "feat: /api/health_guidance endpoint serving the full guidance table once

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 3: Health-condition tabs UI

**Files:**
- Modify: `app/templates/index.html`

**Interfaces:**
- Consumes: `/api/health_guidance` (Task 2), `RAMP`/`bandOf`/current AQI category from the existing `/api/aqi` fetch inside `refresh()`.
- Produces: section `#health`; JS state `HEALTH_DATA` (cached table), `ACTIVE_CONDITION` (default `"general"`); function `renderHealthPanel()`.

- [ ] **Step 1: Five new icon symbols** — add to the existing icon sprite (same block edited in Phase 3 Task 2), before its closing `</svg>`:

```html
  <symbol id="ic-child" viewBox="0 0 24 24"><circle cx="12" cy="6" r="2.4" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 8.5v6M8 12h8M9 20l1.5-5.5M15 20l-1.5-5.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-elder" viewBox="0 0 24 24"><circle cx="12" cy="5.5" r="2.2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M9 20l1-6-2-2 1-4h6l1 4-2 2 1 6M10 13h4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-asthma" viewBox="0 0 24 24"><path d="M9 3v5M9 8c-2 0-3.5 1.6-3.5 3.5S7 15 9 15h6c2 0 3.5-1.6 3.5-3.5S17 8 15 8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 15v3a2 2 0 1 1-4 0M15 15v3a2 2 0 1 0 4 0" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></symbol>
  <symbol id="ic-heart" viewBox="0 0 24 24"><path d="M12 20s-7-4.4-9-9c-1.4-3.3 1-6 4-6c2 0 3.6 1.4 5 3.4C13.4 6.4 15 5 17 5c3 0 5.4 2.7 4 6c-2 4.6-9 9-9 9z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M7 12h2l1.5-3 2 5 1.5-3H17" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="ic-worker" viewBox="0 0 24 24"><path d="M4 8l8-4 8 4M6 9v9M18 9v9M6 20h12M9 13h6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></symbol>
```

- [ ] **Step 2: Markup** — insert after the `#pollutants` section's closing `</section>`:

```html
<section class="section reveal" id="health">
  <div class="sectionHead"><div class="kicker">Health</div><h2>Guidance by condition</h2>
    <p id="healthCitation" class="scoreTxt"></p></div>
  <div id="healthTabs" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px"></div>
  <div class="objCard" id="healthPanel" style="min-height:70px"></div>
</section>
```

- [ ] **Step 3: CSS** — add near `.yearChip` rules:

```css
  .healthTab{display:flex;align-items:center;gap:7px;font:inherit;font-size:12.5px;padding:8px 14px;
    border-radius:99px;border:1px solid var(--line);background:transparent;color:var(--dim);cursor:pointer}
  .healthTab svg{width:15px;height:15px}
  .healthTab.on{color:var(--txt);border-color:rgba(157,193,255,.5);background:rgba(157,193,255,.08)}
```

- [ ] **Step 4: JS** — add near `CITY_ICON` (Phase 3's additions):

```javascript
const HEALTH_ICON={general:'ic-lungs',children:'ic-child',elderly:'ic-elder',asthma:'ic-asthma',heart:'ic-heart',outdoor_workers:'ic-worker'};
let HEALTH_DATA=null, ACTIVE_CONDITION='general', CURRENT_CATEGORY_KEY='moderate';
async function loadHealthGuidance(){
  try{ HEALTH_DATA=await (await fetch('/api/health_guidance')).json(); renderHealthPanel(); }catch(e){}
}
function selectHealthTab(c){ ACTIVE_CONDITION=c; renderHealthPanel(); }
function renderHealthPanel(){
  if(!HEALTH_DATA)return;
  $('healthTabs').innerHTML=HEALTH_DATA.conditions.map(c=>
    `<button type="button" class="healthTab ${c===ACTIVE_CONDITION?'on':''}" onclick="selectHealthTab('${c}')">
      <svg><use href="#${HEALTH_ICON[c]||'ic-lungs'}"/></svg>${HEALTH_DATA.labels[c]}</button>`).join('');
  $('healthPanel').innerHTML=`<p style="font-size:14.5px;line-height:1.6">${HEALTH_DATA.guidance[ACTIVE_CONDITION][CURRENT_CATEGORY_KEY]}</p>`;
  $('healthCitation').textContent=HEALTH_DATA.citation;
}
```

- [ ] **Step 5: Wire `CURRENT_CATEGORY_KEY` from the AQI fetch** — inside `refresh()`'s `/api/aqi` success block, add one line right after `$('aqiPointer').style.left=...;`:

```javascript
        CURRENT_CATEGORY_KEY=a.category.key; renderHealthPanel();
```

- [ ] **Step 6: Load once on page start** — in the bottom-of-file bootstrap line, add `loadHealthGuidance();` alongside the existing `loadBench();` call:

```javascript
loadCities().then(()=>{refresh();renderCalendar();renderTrends()});loadBench();loadHealthGuidance();
```

- [ ] **Step 7: Browser verify** — reload dashboard: 6 tabs render with icons, "General Population" active by default, panel text matches Delhi's current category; click "Asthma / Respiratory" and confirm text changes instantly (no network tab activity); switch city (via ranking table or selector) and confirm the active tab's text updates to the new city's category without a manual re-click; no console errors.

- [ ] **Step 8: Commit and push**

```bash
git add app/templates/index.html
git commit -m "feat: instant health-condition guidance tabs (rule-based, zero LLM calls)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 4: Count-up animation + smoke-puff accent

**Files:**
- Modify: `app/templates/index.html`

**Interfaces:**
- Consumes: existing `reduceMotion` const, `#aqiVal`/`#impCig`/`#impYears` elements.
- Produces: `countUp(el, target, opts)` JS utility; `.smokePuff` CSS accent.

- [ ] **Step 1: CSS smoke-puff** — add near `.livePulse`:

```css
  .smokeWrap{position:relative;width:26px;height:26px;display:inline-block;vertical-align:-8px;margin-left:6px}
  .puff{position:absolute;bottom:0;left:50%;width:8px;height:8px;border-radius:50%;background:rgba(169,180,208,.5);
    animation:puffRise 2.4s ease-in infinite}
  .puff:nth-child(2){animation-delay:.8s;left:40%}
  .puff:nth-child(3){animation-delay:1.6s;left:60%}
  @keyframes puffRise{0%{transform:translate(-50%,0) scale(.4);opacity:0}
    30%{opacity:.7}100%{transform:translate(-50%,-24px) scale(1.3);opacity:0}}
  @media (prefers-reduced-motion: reduce){ .puff{animation:none;opacity:0} }
```

- [ ] **Step 2: Leave the `impCig` markup as-is** — it already reads `<div class="n" id="impCig">–<span> /day</span></div>`. The smoke-puff wrapper is injected by JS in Step 5 once real data arrives (this avoids a flash of un-numbered smoke on first paint), so no HTML edit is needed here.

- [ ] **Step 3: `countUp` utility** — add near the top of the script, after the `reduceMotion` const:

```javascript
function countUp(el, target, {duration=900, decimals=0}={}){
  const from=parseFloat(el.dataset.raw||el.textContent)||0;
  if(reduceMotion || !isFinite(target)){ el.textContent=target.toFixed(decimals); el.dataset.raw=target; return; }
  const start=performance.now();
  function tick(now){
    const t=Math.min(1,(now-start)/duration);
    const eased=1-Math.pow(1-t,3);
    const val=from+(target-from)*eased;
    el.textContent=val.toFixed(decimals);
    if(t<1)requestAnimationFrame(tick); else el.dataset.raw=target;
  }
  requestAnimationFrame(tick);
}
```

- [ ] **Step 4: Apply to the AQI number** — inside `refresh()`'s `/api/aqi` block, replace:

```javascript
        $('aqiVal').textContent=a.aqi;
```
with:
```javascript
        countUp($('aqiVal'), a.aqi, {decimals:0});
```

- [ ] **Step 5: Apply to cigarette + life-expectancy numbers** — find the impact-update block (`imp.cigarettes_per_day_equivalent`) and replace the two innerHTML assignments. Current code sets `$('impCig').innerHTML` and `$('impYears').innerHTML` directly with the number plus a unit `<span>`; restructure so the number lives in its own child span that `countUp` can target without clobbering the unit/smoke markup:

```javascript
  if(imp.cigarettes_per_day_equivalent!==undefined){
    if(!$('impCigNum')){
      $('impCig').innerHTML=`<span id="impCigNum">0</span><span> /day</span><span class="smokeWrap" aria-hidden="true"><span class="puff"></span><span class="puff"></span><span class="puff"></span></span>`;
      $('impYears').innerHTML=`<span id="impYearsNum">0</span><span> yrs</span>`;
    }
    countUp($('impCigNum'), imp.cigarettes_per_day_equivalent, {decimals:1});
    countUp($('impYearsNum'), imp.estimated_life_expectancy_years_lost, {decimals:2});
  }
```
The JS-built template above replaces `impCig`'s contents entirely on first data load, injecting the smoke-puff wrapper only once real numbers exist — so the static markup never needs editing and there is no flash of un-numbered smoke on first paint.

- [ ] **Step 6: Browser verify** — reload dashboard: AQI number counts up from 0 (or previous value on city switch) to the correct final value over ~900ms; cigarette number counts up with one decimal and the smoke puffs loop continuously; life-expectancy number counts up with two decimals; switching to reduced-motion (`Emulate CSS prefers-reduced-motion: reduce` in devtools, or check via `matchMedia` override) makes all three jump straight to final values with the puffs invisible; final `textContent` values match the raw API numbers exactly (no rounding drift from the easing).

- [ ] **Step 7: Commit and push**

```bash
git add app/templates/index.html
git commit -m "feat: count-up animation for AQI/cigarette/life-expectancy numbers + smoke-puff accent

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 5: README, full deploy, live verify

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README updates**
  - Dashboard paragraph: add mention of the instant, rule-based health-condition guidance panel (6 conditions, zero added latency) and the count-up number animations.
  - API table: add `| /api/health_guidance | GET | The full rule-based health guidance table (6 conditions × 6 AQI categories) and citation |`.

- [ ] **Step 2: Full test suite**

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all green (60 tests).

- [ ] **Step 3: Build + deploy**

`gcloud builds submit --config=/tmp/cloudbuild.yaml .` then
`gcloud run deploy vayusense --image=gcr.io/gen-lang-client-0133314577/vayusense --region=us-central1 --platform=managed`

- [ ] **Step 4: Live verify**

Run: `curl -s "https://vayusense-663068003180.us-central1.run.app/api/health_guidance" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['conditions']), d['guidance']['heart']['hazardous'][:40])"`
Expected: `6` and the start of the heart/hazardous guidance text. Also load the live dashboard and confirm the health tabs + count-up animations render.

- [ ] **Step 5: Commit and push**

```bash
git add README.md
git commit -m "docs: document health guidance panel and motion polish

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```
