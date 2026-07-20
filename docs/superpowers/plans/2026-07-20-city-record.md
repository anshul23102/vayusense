# City Record + Typography/Shape Overhaul Implementation Plan (Renovation Phase 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Inter + uniform glass boxes with Space Grotesk/IBM Plex Sans and an open, hairline-separated layout; add pollutant sub-AQI object cards, a full Air Quality Calendar, monthly/annual trend analytics, and a section subnav.

**Architecture:** Two new read-only analytics endpoints (`/api/calendar`, `/api/monthly`) compute per-day and per-month EPA-method AQI from the archive via `agents/aqi.py`, lru-cached. All layout changes are confined to the two templates + DESIGN.md; severity coloring reuses the AQI Ramp via a small band→color map shared into JS.

**Tech Stack:** FastAPI, pandas, agents/aqi.py (existing), Google Fonts (Space Grotesk, IBM Plex Sans), Plotly, vanilla JS/CSS, pytest.

## Global Constraints

- Working dir `/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense`; venv `.venv/bin/python`; dev server on :8090 auto-reloads.
- AQI ramp colors (from DESIGN.md): good `#4fe3ac`, moderate `#ffce80`, poor `#ffab73`, unhealthy `#ff8aa3`, severe `#ef7ac8`, hazardous `#b04a63`. Always paired with a label.
- Basis labeling: everything archive-derived says "EPA-method daily AQI from the archive".
- Inter must not remain anywhere (link or CSS) in either template.
- Shape rule name (verbatim in DESIGN.md): **"Boxes are for objects, not sections"**.
- Commits end with the Co-Authored-By Claude trailer; push after each task; deploy cadence as established (Cloud Build `/tmp/cloudbuild.yaml` → `gcloud run deploy vayusense --region=us-central1` → live verify → push).

---

### Task 1: Typography swap (both templates, DESIGN.md, impeccable config)

**Files:**
- Modify: `app/templates/index.html`, `app/templates/landing.html`, `DESIGN.md`, `.impeccable/config.json`

**Interfaces:**
- Produces: CSS var `--disp: 'Space Grotesk'` and body font IBM Plex Sans in both templates; class `.num{font-family:var(--disp);font-variant-numeric:tabular-nums}` available to later tasks.

- [ ] **Step 1: Swap the Google Fonts links** — in BOTH templates replace the Inter `<link href="https://fonts.googleapis.com/css2?family=Inter...">` with:

```html
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Swap font-family declarations** — in both templates:
  - `body{...font-family:'Inter',...}` → `font-family:'IBM Plex Sans',-apple-system,sans-serif`.
  - Add to `:root`: `--disp:'Space Grotesk',sans-serif;`
  - Add utility rule: `.num,h1,h2,h3,.sectionHead h1,.sectionHead h2{font-family:var(--disp)}` and `.num{font-variant-numeric:tabular-nums}`.
  - Apply `font-family:var(--disp)` to the big-number rules: `.ring .val b`, `.kpi .v`, `.impactStat .n`, `.bench .big` (index) and the hero display rules in landing.html (its `h1`, `.stat b`-equivalents — match by reading the file).

- [ ] **Step 3: DESIGN.md §3 Typography rewrite** — replace the section's font-family content: primary family IBM Plex Sans (body/UI), display family Space Grotesk (headlines + all stat numerals, tabular figures), weights as loaded; update any frontmatter `typography:` tokens naming Inter.

- [ ] **Step 4: Clean `.impeccable/config.json`** — remove the `ignoreValues` entry for `overused-font: inter` (leave the rest of the file intact).

- [ ] **Step 5: Verify in browser** — reload dashboard + landing; run in the browser pane:
`getComputedStyle(document.body).fontFamily` → starts with `"IBM Plex Sans"`; `getComputedStyle(document.querySelector('h1')).fontFamily` → starts with `"Space Grotesk"`; grep both templates for `Inter` → no hits.

- [ ] **Step 6: Commit and push**

```bash
git add app/templates/index.html app/templates/landing.html DESIGN.md .impeccable/config.json
git commit -m "feat: Space Grotesk + IBM Plex Sans replace Inter everywhere

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: De-boxing — open sections + object-card restyle (dashboard)

**Files:**
- Modify: `app/templates/index.html`, `DESIGN.md`

**Interfaces:**
- Produces: CSS classes later tasks use: `.section` (open block: `border-top:1px solid var(--line);padding:36px 0;margin-top:8px`), `.objCard` (radius 14px, flat fill `rgba(255,255,255,.035)`, optional `border-left:3px solid` severity edge via inline style), and section ids `#overview`, `#trend`, `#bench`, `#ask` on existing content.

- [ ] **Step 1: DESIGN.md Named Rule** — add to §4 Elevation Named Rules:

```markdown
**Boxes are for objects, not sections.** Page sections (charts, calendars, tables,
the hero) sit open on the night background, separated by hairline top rules and
whitespace — never wrapped in cards. Cards exist only for true objects (a pollutant,
a city, a forecast method, an impact stat): radius 14px, flat fill, no gradient
border, with a 3px left severity edge-bar when the object has a severity.
```

- [ ] **Step 2: CSS changes in index.html**
  - Add: `.section{border-top:1px solid var(--line);padding:36px 0 6px;margin-top:10px}`
  - Add: `.objCard{position:relative;padding:16px;border-radius:14px;background:rgba(255,255,255,.035);border:1px solid var(--line);transition:background .2s}` and `.objCard:hover{background:rgba(255,255,255,.06)}`
  - `.card` restyle (kept for chat panel + transitional uses): `border-radius:14px`, background `rgba(255,255,255,.035)`, delete the `.card::before` gradient-border block, drop `backdrop-filter` from `.card`.
  - `.kpi` and `.impactStat`: switch from boxed to open-row style — remove background/border, add `border-left:1px solid var(--line);border-radius:0;padding:6px 16px`.

- [ ] **Step 3: Markup restructure**
  - Hero: unwrap the AQI card — the first `s6` card's inner content moves into `<section class="section" id="overview">` alongside the human-impact stats (impact stats become a horizontal open row to the right/below on mobile); delete both wrapper `.card` divs. KPI strip becomes an open row inside `#overview` (drop its wrapper card).
  - Trend: replace the trend `.card` wrapper (s8) with `<section class="section" id="trend">`; NVIDIA panel becomes a compact `.objCard` floated in the trend section's corner (grid: chart 8 cols, NVIDIA aside 4 cols, both inside the open section).
  - Forecast bench: `#benchCard` card wrapper → `<section class="section" id="bench">`; each bench method entry rendered as `.objCard` (JS in place, only class rename); winner keeps the Ice Solid border highlight.
  - Ask: chat keeps its `.card` (now flatter) inside `<section class="section" id="ask">`; remove the surrounding grid wrapper.
  - Keep `.reveal` animations on the new sections.

- [ ] **Step 4: Browser verify** — dashboard renders with hairline-separated open sections, no gradient borders, chart directly on background; all data still loads (AQI, KPIs, chart, bench, chat box); no console errors.

- [ ] **Step 5: Commit and push**

```bash
git add app/templates/index.html DESIGN.md
git commit -m "feat: open-section layout — boxes are for objects, not sections

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 3: Major Pollutants section

**Files:**
- Modify: `app/templates/index.html`

**Interfaces:**
- Consumes: `/api/aqi` (`sub_aqi`, `category`, `source`, `basis`), `/api/snapshot` (`pollutants[param].daily_mean/times_who_limit/trend`), CSS `.objCard`, `.num`.
- Produces: section `#pollutants`; JS map `RAMP={good:'#4fe3ac',moderate:'#ffce80',poor:'#ffab73',unhealthy:'#ff8aa3',severe:'#ef7ac8',hazardous:'#b04a63'}` and `bandOf(aqi)` helper reused by Tasks 5-6.

- [ ] **Step 1: Markup** — after the `#overview` section, add:

```html
<section class="section" id="pollutants">
  <div class="sectionHead"><div class="kicker">Pollutants</div><h2>Major air pollutants</h2>
  <p id="pollBasis" class="scoreTxt"></p></div>
  <div class="grid" id="pollGrid"></div>
</section>
```

- [ ] **Step 2: JS** — add helpers near the top of the script:

```javascript
const RAMP={good:'#4fe3ac',moderate:'#ffce80',poor:'#ffab73',unhealthy:'#ff8aa3',severe:'#ef7ac8',hazardous:'#b04a63'};
const BANDS=[[0,50,'good','Good'],[51,100,'moderate','Moderate'],[101,150,'poor','Poor'],[151,200,'unhealthy','Unhealthy'],[201,300,'severe','Severe'],[301,9999,'hazardous','Hazardous']];
function bandOf(aqi){for(const [lo,hi,k,l] of BANDS)if(aqi>=lo&&aqi<=hi)return{key:k,label:l,color:RAMP[k]};return{key:'hazardous',label:'Hazardous',color:RAMP.hazardous}}
const POLL_NAMES={pm25:'Particulate Matter (PM2.5)',pm10:'Particulate Matter (PM10)',no2:'Nitrogen Dioxide (NO₂)',o3:'Ozone (O₃)',so2:'Sulfur Dioxide (SO₂)',co:'Carbon Monoxide (CO)'};
const POLL_UNITS={co:'mg/m³'};
```

In `refresh()`, inside the `/api/aqi` success block, render the grid (snapshot `s` is already fetched in scope — reorder so `s` is available, or store `window._lastSnap=s`):

```javascript
        $('pollBasis').textContent=`Sub-AQI per pollutant · ${a.basis}${a.source==='live'?'':' · archive'}`;
        $('pollGrid').innerHTML=Object.entries(a.sub_aqi).map(([p,sub])=>{
          const b=bandOf(sub); const sv=(window._lastSnap&&window._lastSnap.pollutants[p])||{};
          return `<div class="s4"><button type="button" class="objCard num" style="border-left:3px solid ${b.color};width:100%;text-align:left;cursor:pointer;color:inherit;font:inherit"
            onclick="document.getElementById('paramSel').value='${p}';document.getElementById('paramSel').dispatchEvent(new Event('change'));document.getElementById('trend').scrollIntoView({behavior:'smooth'})">
            <div class="l" style="color:var(--dim);font-size:11px;font-family:'IBM Plex Sans'">${POLL_NAMES[p]||p}</div>
            <div style="font-size:26px;font-weight:600;margin:4px 0">${sv.daily_mean!==undefined?sv.daily_mean:'–'}<span style="font-size:13px;color:var(--dim)"> ${POLL_UNITS[p]||'µg/m³'}</span></div>
            <div style="font-size:12px"><span style="color:${b.color}">● ${b.label}</span> · AQI ${sub}${sv.times_who_limit?` · ${sv.times_who_limit}× WHO`:''}</div>
          </button></div>`}).join('');
```

- [ ] **Step 3: Browser verify** — six cards with severity edge-bars and band dots; clicking NO₂ switches the trend chart to no2 and scrolls; values match KPI strip.

- [ ] **Step 4: Commit and push**

```bash
git add app/templates/index.html
git commit -m "feat: major-pollutants section with per-pollutant sub-AQI object cards

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 4: `/api/calendar` endpoint

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_calendar_api.py`

**Interfaces:**
- Consumes: `data_tools._daily()`, `overall_aqi`, `aqi_category`, `ARCHIVE_UNITS`.
- Produces: `_daily_overall(city) -> list[dict]` (`[{date:"YYYY-MM-DD", aqi:int, key:str}]`, all archive days, sorted) — reused by `/api/monthly` in Task 6; route `GET /api/calendar?city=&year=` → `{city, year, years_available:[int], basis, days:[...]}` or `{"error": ...}`.

- [ ] **Step 1: Write the failing test**

`tests/test_calendar_api.py`:
```python
from app.main import _daily_overall, calendar_api

VALID = {"good", "moderate", "poor", "unhealthy", "severe", "hazardous"}


def test_daily_overall_shape():
    days = _daily_overall("Delhi")
    assert len(days) >= 500          # ~2 years of archive
    assert days == sorted(days, key=lambda d: d["date"])
    assert all(isinstance(d["aqi"], int) and d["aqi"] > 0 for d in days[:50])
    assert all(d["key"] in VALID for d in days[:50])


def test_calendar_year_filter():
    out = calendar_api(city="Delhi", year=2025)
    assert out["year"] == 2025
    assert len(out["days"]) >= 300
    assert all(d["date"].startswith("2025-") for d in out["days"])
    assert set(out["years_available"]) >= {2024, 2025}
    assert out["basis"] == "EPA-method daily AQI from the archive"


def test_calendar_unknown_city():
    out = calendar_api(city="Atlantis", year=2025)
    assert "error" in out
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_calendar_api.py -v`
Expected: FAIL `ImportError: cannot import name '_daily_overall'`

- [ ] **Step 3: Implement in `app/main.py`** (after the `/api/aqi` route; add `from functools import lru_cache` to imports):

```python
@lru_cache(maxsize=32)
def _daily_overall_cached(city_key: str) -> tuple:
    df = data_tools._daily()
    d = df[df["city"].str.lower() == city_key]
    out = []
    for date, grp in d.groupby("date"):
        concs = dict(zip(grp["parameter"], grp["mean"].astype(float)))
        try:
            aqi, _dom, _subs = overall_aqi(concs, ARCHIVE_UNITS)
        except ValueError:
            continue
        out.append({"date": str(date.date()), "aqi": aqi,
                    "key": aqi_category(aqi)["key"]})
    out.sort(key=lambda x: x["date"])
    return tuple(tuple(sorted(o.items())) for o in out)


def _daily_overall(city: str) -> list[dict]:
    return [dict(t) for t in _daily_overall_cached(city.lower())]


@app.get("/api/calendar")
def calendar_api(city: str = "Delhi", year: int = 2025):
    days = _daily_overall(city)
    if not days:
        return {"error": f"no data for city '{city}'"}
    years = sorted({int(d["date"][:4]) for d in days})
    sel = [d for d in days if d["date"].startswith(f"{year}-")]
    return {"city": city, "year": year, "years_available": years,
            "basis": "EPA-method daily AQI from the archive", "days": sel}
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_calendar_api.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit and push**

```bash
git add app/main.py tests/test_calendar_api.py
git commit -m "feat: /api/calendar — per-day EPA-method AQI for calendar views

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 5: Air Quality Calendar UI

**Files:**
- Modify: `app/templates/index.html`

**Interfaces:**
- Consumes: `/api/calendar` (Task 4), `RAMP` (Task 3).
- Produces: section `#calendar` with `renderCalendar(city, year)` JS.

- [ ] **Step 1: Markup** — after `#trend` section:

```html
<section class="section" id="calendar">
  <div class="sectionHead"><div class="kicker">Calendar</div><h2>Air quality calendar</h2>
    <p class="scoreTxt">Every archive day, colored by its EPA-method daily AQI.</p></div>
  <div id="calYears" style="display:flex;gap:8px;margin-bottom:16px"></div>
  <div id="calGrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:22px"></div>
  <div id="calLegend" style="display:flex;flex-wrap:wrap;gap:14px;margin-top:18px;color:var(--dim);font-size:11.5px"></div>
</section>
```

- [ ] **Step 2: CSS**

```css
  .calMonth h4{font-family:var(--disp);font-size:13px;margin-bottom:8px;font-weight:600}
  .calRow{display:grid;grid-template-columns:repeat(7,1fr);gap:3px}
  .calHead span{font-size:9px;color:var(--dim);text-align:center}
  .calDay{aspect-ratio:1;display:flex;align-items:center;justify-content:center;border-radius:6px;
    font-size:9.5px;font-family:var(--disp);font-variant-numeric:tabular-nums;color:#0b1226;font-weight:600}
  .calDay.empty{background:rgba(255,255,255,.03);color:transparent}
  .yearChip{font:inherit;font-size:12.5px;padding:6px 14px;border-radius:99px;border:1px solid var(--line);
    background:transparent;color:var(--dim);cursor:pointer}
  .yearChip.on{color:var(--txt);border-color:rgba(157,193,255,.5)}
```

- [ ] **Step 3: JS** — add:

```javascript
const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
let CAL_YEAR=null;
async function renderCalendar(){
  try{
    const c=await (await fetch(`/api/calendar?city=${CITY}&year=${CAL_YEAR||2025}`)).json();
    if(!c.days){$('calendar').style.display='none';return}
    $('calendar').style.display='';
    if(CAL_YEAR===null)CAL_YEAR=c.years_available[c.years_available.length-1];
    $('calYears').innerHTML=c.years_available.map(y=>`<button type="button" class="yearChip ${y===c.year?'on':''}" onclick="CAL_YEAR=${y};renderCalendar()">${y}</button>`).join('');
    const byDate=Object.fromEntries(c.days.map(d=>[d.date,d]));
    let html='';
    for(let m=0;m<12;m++){
      const first=new Date(Date.UTC(c.year,m,1)); const dim=new Date(Date.UTC(c.year,m+1,0)).getUTCDate();
      let cells='<div class="calRow calHead">'+['S','M','T','W','T','F','S'].map(d=>`<span>${d}</span>`).join('')+'</div><div class="calRow">';
      for(let i=0;i<first.getUTCDay();i++)cells+='<div></div>';
      for(let day=1;day<=dim;day++){
        const key=`${c.year}-${String(m+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
        const d=byDate[key];
        cells+=d?`<div class="calDay" style="background:${RAMP[d.key]}" title="${key}: AQI ${d.aqi} (${bandOf(d.aqi).label})">${d.aqi}</div>`
               :`<div class="calDay empty">·</div>`;
      }
      cells+='</div>';
      html+=`<div class="calMonth"><h4>${MONTHS[m]}</h4>${cells}</div>`;
    }
    $('calGrid').innerHTML=html;
    $('calLegend').innerHTML=BANDS.map(([lo,hi,k,l])=>`<span><span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${RAMP[k]};vertical-align:-1px"></span> ${l} ${lo}${hi<9999?'–'+hi:'+'}</span>`).join('');
  }catch(e){}
}
```
Call `renderCalendar()` at the end of `refresh()` (city changes re-render; pollutant changes don't need to, harmless if they do).

- [ ] **Step 4: Browser verify** — 12 month grids with colored day cells and numbers; year chips toggle 2024/2025; hover title shows date + AQI + band; legend row present.

- [ ] **Step 5: Commit and push**

```bash
git add app/templates/index.html
git commit -m "feat: air quality calendar — every archive day colored by AQI band

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 6: `/api/monthly` + trends section

**Files:**
- Modify: `app/main.py`, `app/templates/index.html`
- Test: `tests/test_monthly_api.py`

**Interfaces:**
- Consumes: `_daily_overall` (Task 4), `RAMP`/`bandOf` (Task 3).
- Produces: `GET /api/monthly?city=` → `{city, basis, months:[{month:"2024-01", avg_aqi:int, key:str}], most_polluted:{month,avg_aqi}, least_polluted:{month,avg_aqi}, annual:[{year,avg_aqi}], annual_change_pct:float}`; section `#trends`.

- [ ] **Step 1: Write the failing test**

`tests/test_monthly_api.py`:
```python
from app.main import _daily_overall, monthly_api


def test_monthly_shape_and_math():
    out = monthly_api(city="Delhi")
    months = out["months"]
    assert months == sorted(months, key=lambda m: m["month"])
    assert len(months) >= 20                      # ~2 years
    # spot-check one month's average against the daily data
    days = _daily_overall("Delhi")
    m0 = months[0]["month"]
    vals = [d["aqi"] for d in days if d["date"].startswith(m0)]
    assert months[0]["avg_aqi"] == round(sum(vals) / len(vals))
    # extremes are true extremes
    avgs = {m["month"]: m["avg_aqi"] for m in months}
    assert out["most_polluted"]["avg_aqi"] == max(avgs.values())
    assert out["least_polluted"]["avg_aqi"] == min(avgs.values())
    # annual change consistent with annual averages
    a = out["annual"]
    assert len(a) >= 2
    expect = round((a[-1]["avg_aqi"] - a[0]["avg_aqi"]) / a[0]["avg_aqi"] * 100, 1)
    assert out["annual_change_pct"] == expect


def test_monthly_unknown_city():
    assert "error" in monthly_api(city="Atlantis")
```

- [ ] **Step 2: Run to verify failure** — `ImportError: cannot import name 'monthly_api'`.

- [ ] **Step 3: Implement in `app/main.py`** (after `calendar_api`):

```python
@app.get("/api/monthly")
def monthly_api(city: str = "Delhi"):
    days = _daily_overall(city)
    if not days:
        return {"error": f"no data for city '{city}'"}
    by_month: dict[str, list[int]] = {}
    by_year: dict[int, list[int]] = {}
    for d in days:
        by_month.setdefault(d["date"][:7], []).append(d["aqi"])
        by_year.setdefault(int(d["date"][:4]), []).append(d["aqi"])
    months = [{"month": m, "avg_aqi": round(sum(v) / len(v)),
               "key": aqi_category(round(sum(v) / len(v)))["key"]}
              for m, v in sorted(by_month.items())]
    most = max(months, key=lambda m: m["avg_aqi"])
    least = min(months, key=lambda m: m["avg_aqi"])
    annual = [{"year": y, "avg_aqi": round(sum(v) / len(v))}
              for y, v in sorted(by_year.items())]
    change = round((annual[-1]["avg_aqi"] - annual[0]["avg_aqi"])
                   / annual[0]["avg_aqi"] * 100, 1) if len(annual) >= 2 else 0.0
    return {"city": city, "basis": "EPA-method daily AQI from the archive",
            "months": months,
            "most_polluted": {"month": most["month"], "avg_aqi": most["avg_aqi"]},
            "least_polluted": {"month": least["month"], "avg_aqi": least["avg_aqi"]},
            "annual": annual, "annual_change_pct": change}
```

- [ ] **Step 4: Run tests** — 2 passed. Then full suite.

- [ ] **Step 5: Trends UI** — after `#calendar` section:

```html
<section class="section" id="trends">
  <div class="sectionHead"><div class="kicker">Long view</div><h2>Monthly & annual trends</h2></div>
  <div id="monthlyChart" style="height:300px"></div>
  <div class="grid" style="margin-top:18px">
    <div class="s4"><div class="objCard num" id="mostMonth"></div></div>
    <div class="s4"><div class="objCard num" id="leastMonth"></div></div>
    <div class="s4"><div class="objCard num" id="annualCompare"></div></div>
  </div>
</section>
```

JS:
```javascript
async function renderTrends(){
  try{
    const t=await (await fetch(`/api/monthly?city=${CITY}`)).json();
    if(!t.months){$('trends').style.display='none';return}
    $('trends').style.display='';
    Plotly.newPlot('monthlyChart',[{x:t.months.map(m=>m.month),y:t.months.map(m=>m.avg_aqi),type:'bar',
      marker:{color:t.months.map(m=>RAMP[m.key])},hovertemplate:'%{x}<br>AQI %{y} (%{customdata})<extra></extra>',
      customdata:t.months.map(m=>bandOf(m.avg_aqi).label)}],
      {paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:'#a9b4d0',family:'IBM Plex Sans',size:12},
       margin:{t:6,r:10,b:60,l:42},yaxis:{gridcolor:'rgba(255,255,255,.04)',title:'avg AQI'},xaxis:{tickangle:-40}},
      {displayModeBar:false});
    const fm=m=>{const [y,mo]=m.split('-');return MONTHS[+mo-1]+' '+y};
    $('mostMonth').innerHTML=`<div style="font-size:11px;color:var(--dim)">Most polluted month</div><div style="font-size:24px;font-weight:600;margin:3px 0">${t.most_polluted.avg_aqi}</div><div style="font-size:12px;color:var(--dim)">${fm(t.most_polluted.month)}</div>`;
    $('mostMonth').style.borderLeft=`3px solid ${RAMP[bandOf(t.most_polluted.avg_aqi).key]}`;
    $('leastMonth').innerHTML=`<div style="font-size:11px;color:var(--dim)">Least polluted month</div><div style="font-size:24px;font-weight:600;margin:3px 0">${t.least_polluted.avg_aqi}</div><div style="font-size:12px;color:var(--dim)">${fm(t.least_polluted.month)}</div>`;
    $('leastMonth').style.borderLeft=`3px solid ${RAMP[bandOf(t.least_polluted.avg_aqi).key]}`;
    const a=t.annual, dir=t.annual_change_pct<0?'improvement':'worsening';
    $('annualCompare').innerHTML=`<div style="font-size:11px;color:var(--dim)">Annual average</div><div style="font-size:17px;font-weight:600;margin:6px 0">${a.map(x=>`${x.year}: ${x.avg_aqi}`).join(' → ')}</div><div style="font-size:12px;color:var(--dim)">${Math.abs(t.annual_change_pct)}% ${dir} (${t.basis})</div>`;
  }catch(e){}
}
```
Call `renderTrends()` at the end of `refresh()`.

- [ ] **Step 6: Browser verify** — bar chart with band-colored bars over ~24 months; three callout cards with correct extremes and a worded annual change.

- [ ] **Step 7: Commit and push**

```bash
git add app/main.py app/templates/index.html tests/test_monthly_api.py
git commit -m "feat: monthly/annual AQI trends — /api/monthly + band-colored chart

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 7: Subnav, README, deploy, live verify

**Files:**
- Modify: `app/templates/index.html`, `README.md`

- [ ] **Step 1: Subnav** — inside `<nav>`, after the logo:

```html
  <div class="subnav">
    <a href="#overview">Overview</a><a href="#pollutants">Pollutants</a><a href="#calendar">Calendar</a><a href="#trends">Trends</a><a href="#bench">Forecast bench</a><a href="#ask">Ask</a>
  </div>
```
CSS: `.subnav{display:flex;gap:14px;margin-left:18px} .subnav a{color:var(--dim);font-size:12.5px;text-decoration:none} .subnav a:hover{color:var(--txt)} @media(max-width:940px){.subnav{display:none}}` and `html{scroll-behavior:smooth}` with a reduced-motion override `html{scroll-behavior:auto}` inside the existing media block. Add `scroll-margin-top:90px` to `.section`.

- [ ] **Step 2: README** — dashboard paragraph gains: per-pollutant sub-AQI cards, the air quality calendar (every archive day colored by EPA-method AQI band), monthly/annual trend analytics with most/least-polluted months; API table gains `/api/calendar` and `/api/monthly` rows; frontend stack line mentions Space Grotesk + IBM Plex Sans.

- [ ] **Step 3: Full suite + browser pass** — `.venv/bin/python -m pytest tests/` all green; browser: subnav anchors scroll to sections; final look-over of the whole page.

- [ ] **Step 4: Build + deploy + live verify**

`gcloud builds submit --config=/tmp/cloudbuild.yaml .` → `gcloud run deploy vayusense ...` → curl `/api/calendar?city=Delhi&year=2025 | days length ≥300`, `/api/monthly?city=Delhi | months ≥20`, load live dashboard, confirm fonts + calendar render.

- [ ] **Step 5: Commit and push**

```bash
git add app/templates/index.html README.md
git commit -m "feat: section subnav + docs for the city record

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```
