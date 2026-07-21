# Compact Calendar Implementation Plan (Renovation Phase 6B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 12-month-at-once calendar grid with a paged 2-month view (prev/next arrows), same data, same per-day cells, far less vertical space.

**Architecture:** Split the existing `renderCalendar()` into a data-fetch stage (`renderCalendar()`, unchanged endpoint, now caches the year's data in `CAL_DATA`) and a page-render stage (`renderCalendarPage()`, pure DOM update from cached data, no refetch). New `CAL_PAGE_START` state and a `calPage(delta)` stepper handle paging.

**Tech Stack:** Vanilla JS/CSS, `app/templates/index.html` only. No backend changes.

## Global Constraints

- `/api/calendar` is unchanged — same one fetch per year/city as today.
- Prev/next must never trigger a new fetch — purely re-renders from already-fetched data.
- Default page = the most recent 2-month pair containing real data for the selected city/year, clamped to `[0, 10]` (start index of month 0-11, always showing `start` and `start+1`).
- Switching city or year resets to the new default page.
- Commits end with the Co-Authored-By Claude trailer; push after each task. Deploy cadence: local verify → Cloud Build (`/tmp/cloudbuild.yaml`) → `gcloud run deploy vayusense --region=us-central1` → live verify → push.

---

### Task 1: Paged calendar rendering

**Files:**
- Modify: `app/templates/index.html`

**Interfaces:**
- Produces: `CAL_DATA` (`{year, byDate, years_available}` or `null`), `CAL_PAGE_START` (int 0-10), `renderCalendarPage()`, `calPage(delta)`.

- [ ] **Step 1: Markup** — find:

```html
  <div id="calYears" style="display:flex;gap:8px;margin-bottom:16px"></div>
  <div id="calGrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:22px"></div>
  <div id="calLegend" style="display:flex;flex-wrap:wrap;gap:14px;margin-top:18px;color:var(--dim);font-size:11.5px"></div>
```
replace with:
```html
  <div id="calYears" style="display:flex;gap:8px;margin-bottom:16px"></div>
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">
    <button type="button" id="calPrev" class="yearChip" onclick="calPage(-1)" aria-label="Previous months">◀</button>
    <span id="calPageLabel" style="font-family:var(--disp);font-size:14px;min-width:160px;text-align:center"></span>
    <button type="button" id="calNext" class="yearChip" onclick="calPage(1)" aria-label="Next months">▶</button>
  </div>
  <div id="calGrid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:22px;max-width:560px"></div>
  <div id="calLegend" style="display:flex;flex-wrap:wrap;gap:14px;margin-top:18px;color:var(--dim);font-size:11.5px"></div>
```

- [ ] **Step 2: Add paging state + `calPage()`** — near the `let CAL_YEAR=null;` line, add:

```javascript
let CAL_DATA=null, CAL_PAGE_START=0;
function calPage(delta){
  if(!CAL_DATA)return;
  const next=CAL_PAGE_START+delta*2;
  if(next<0||next>10)return;
  CAL_PAGE_START=next;
  renderCalendarPage();
}
```

- [ ] **Step 3: Split `renderCalendar()` into fetch + page-render** — replace the entire existing function body (from `async function renderCalendar(){` through its closing `}` that contains the `$('calLegend').innerHTML=...` line) with:

```javascript
async function renderCalendar(){
  try{
    const c=await (await fetch(`/api/calendar?city=${CITY}&year=${CAL_YEAR||2025}`)).json();
    if(!c.days){$('calendar').style.display='none';CAL_DATA=null;return}
    $('calendar').style.display='';
    if(CAL_YEAR===null||!c.years_available.includes(CAL_YEAR))CAL_YEAR=c.years_available[c.years_available.length-1];
    if(CAL_YEAR!==c.year){return renderCalendar()}
    $('calYears').innerHTML=c.years_available.map(y=>`<button type="button" class="yearChip ${y===c.year?'on':''}" onclick="CAL_YEAR=${y};renderCalendar()">${y}</button>`).join('');
    const byDate=Object.fromEntries(c.days.map(d=>[d.date,d]));
    CAL_DATA={year:c.year, byDate};
    let lastPopulated=0;
    for(let m=0;m<12;m++){
      const hasData=c.days.some(d=>d.date.startsWith(`${c.year}-${String(m+1).padStart(2,'0')}`));
      if(hasData)lastPopulated=m;
    }
    CAL_PAGE_START=Math.max(0,Math.min(10,lastPopulated-1));
    renderCalendarPage();
  }catch(e){$('calendar').style.display='none';CAL_DATA=null}
}
function renderCalendarPage(){
  if(!CAL_DATA)return;
  const {year,byDate}=CAL_DATA;
  let html='';
  for(let m=CAL_PAGE_START;m<CAL_PAGE_START+2;m++){
    const first=new Date(Date.UTC(year,m,1)); const dim=new Date(Date.UTC(year,m+1,0)).getUTCDate();
    let cells='<div class="calRow calHead">'+['S','M','T','W','T','F','S'].map(d=>`<span>${d}</span>`).join('')+'</div><div class="calRow">';
    for(let i=0;i<first.getUTCDay();i++)cells+='<div></div>';
    for(let day=1;day<=dim;day++){
      const key=`${year}-${String(m+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
      const d=byDate[key];
      cells+=d?`<div class="calDay" style="background:${RAMP[d.key]}" title="${key}: AQI ${d.aqi} (${bandOf(d.aqi).label})">${d.aqi}</div>`
             :`<div class="calDay empty">·</div>`;
    }
    cells+='</div>';
    html+=`<div class="calMonth"><h4>${MONTHS[m]}</h4>${cells}</div>`;
  }
  $('calGrid').innerHTML=html;
  $('calPageLabel').textContent=`${MONTHS[CAL_PAGE_START]} – ${MONTHS[CAL_PAGE_START+1]} ${year}`;
  $('calPrev').disabled=CAL_PAGE_START<=0; $('calPrev').style.opacity=CAL_PAGE_START<=0?.35:1;
  $('calNext').disabled=CAL_PAGE_START>=10; $('calNext').style.opacity=CAL_PAGE_START>=10?.35:1;
  $('calLegend').innerHTML=BANDS.map(([lo,hi,k,l])=>`<span><span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${RAMP[k]};vertical-align:-1px"></span> ${l} ${lo}${hi<9999?'–'+hi:'+'}</span>`).join('');
}
```

- [ ] **Step 4: Browser verify** — reload dashboard; confirm only 2 months render, defaulting to the most recent populated pair (not January); page label reads correctly (e.g. "December – January 2025"); click ◀/▶ and confirm exactly 2 months step per click with no network request fired (check via network tab/read_network_requests); arrows visibly dim and stop responding at the boundaries; switch city via the ranking table and confirm the calendar resets to that city's most-recent-data pair; no console errors.

- [ ] **Step 5: Commit and push**

```bash
git add app/templates/index.html
git commit -m "feat: paged 2-month calendar view replaces the 12-month grid

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: Deploy + live verify

- [ ] **Step 1: Full test suite**

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all 65 tests still passing.

- [ ] **Step 2: Build + deploy**

`gcloud builds submit --config=/tmp/cloudbuild.yaml .` then
`gcloud run deploy vayusense --image=gcr.io/gen-lang-client-0133314577/vayusense --region=us-central1 --platform=managed`

- [ ] **Step 3: Live verify**

Run: `curl -s https://vayusense-663068003180.us-central1.run.app/dashboard | grep -c 'calPage\|calPageLabel'`
Expected: `>=2`. Load the live dashboard and visually confirm the paged 2-month calendar with working arrows.
