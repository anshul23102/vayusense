# City Landmarks + Ranking Table + Landing De-boxing Implementation Plan (Renovation Phase 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the 10-city AQI ranking a real, visual home — a full open-section table with monoline city-landmark icons, category chips, and dominant pollutants — and extend Phase 2's flat object-card shape rule to the landing page's feature cards.

**Architecture:** `/api/aqi`'s existing per-city ranking loop is refactored to reuse `_city_aqi` (so dominant-pollutant logic lives in exactly one place) and gains a `source` field read from the live cache only (never triggers a fetch). The dashboard renders this into a new `#cities` table section, reusing the `RAMP`/`bandOf` helpers and click-to-select pattern already established for pollutant cards. Ten new SVG symbols join the existing icon sprite.

**Tech Stack:** FastAPI (existing `app/main.py`), vanilla JS/CSS (existing `index.html`/`landing.html` patterns), pytest, hand-authored SVG (no image assets/build step).

## Global Constraints

- Working dir `/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense`; venv `.venv/bin/python`; dev server on :8090 auto-reloads.
- Icon symbols: `viewBox="0 0 24 24"`, `fill="none"`, `stroke="currentColor"`, `stroke-width` in the 1.6-2 range (match existing `ic-lungs`/`ic-bolt`/`ic-chip` weight), added to the existing icon `<svg>` sprite block in `index.html` (the one with `id="ic-lungs"` etc.), not a new sprite element.
- `CITY_ICON` JS map must have an `ic-generic` fallback entry so an unmapped city never renders a broken `<use>`.
- Ranking basis stays "latest archive day, all cities" (unchanged from Phase 1/2) — `source` on ranking rows reflects cache state only, never triggers new OpenAQ calls.
- Table rows are hairline-separated (`border-top:1px solid var(--line)` per row), not boxed; only the icon badge is a small object per the "Boxes are for objects, not sections" rule.
- Landing page: only `.card` styling changes (radius, fill, no gradient border) — no markup/layout restructuring, no hero changes.
- Commits end with the Co-Authored-By Claude trailer; push after each task. Deploy cadence: local verify → Cloud Build (`/tmp/cloudbuild.yaml`) → `gcloud run deploy vayusense --region=us-central1` → live verify → push.

---

### Task 1: Ranking enrichment (`dominant` + `source`, reusing `_city_aqi`)

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_ranking_enrichment.py`

**Interfaces:**
- Consumes: `_city_aqi(city, allow_fetch)` (existing), `live.peek_live_city` (existing).
- Produces: `/api/aqi` response `ranking` rows gain `dominant: str` and `source: "live"|"archive"`; row shape becomes `{"city", "aqi", "category", "dominant", "source"}`. `category` stays the string label (unchanged) for backward compatibility with the Phase 2 calendar/trends code that doesn't touch `ranking`.

- [ ] **Step 1: Write the failing test**

`tests/test_ranking_enrichment.py`:
```python
import app.live as live
from app.main import city_aqi


def test_ranking_rows_have_dominant_and_source(monkeypatch):
    monkeypatch.setattr(live, "get_live_city", lambda c: None)
    monkeypatch.setattr(live, "peek_live_city", lambda c: None)
    out = city_aqi(city="Delhi")
    assert len(out["ranking"]) >= 8
    for row in out["ranking"]:
        assert set(row) == {"city", "aqi", "category", "dominant", "source"}
        assert row["source"] in {"live", "archive"}
    assert out["ranking"] == sorted(out["ranking"], key=lambda r: -r["aqi"])


def test_ranking_source_reflects_cache_without_fetching(monkeypatch):
    monkeypatch.setattr(live, "get_live_city", lambda c: None)
    calls = {"n": 0}

    def fake_peek(c):
        calls["n"] += 1
        return {"concs": {"pm25": {"value": 50.0, "unit": "µg/m³"}},
                "last_updated": "2026-07-20T00:00:00+00:00", "stations": 1} if c == "Delhi" else None
    monkeypatch.setattr(live, "peek_live_city", fake_peek)
    out = city_aqi(city="Delhi")
    delhi_row = next(r for r in out["ranking"] if r["city"] == "Delhi")
    assert delhi_row["source"] == "live"
    other = next(r for r in out["ranking"] if r["city"] != "Delhi")
    assert other["source"] == "archive"
    assert calls["n"] >= 1        # peek was used, confirming no bypass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ranking_enrichment.py -v`
Expected: FAIL — `KeyError: 'dominant'` (current rows lack it).

- [ ] **Step 3: Refactor the ranking loop in `app/main.py`** — replace the current `/api/aqi` ranking block:

```python
    # Ranking compares all cities on the SAME basis (archive latest day) so a
    # live number for one city is never ranked against stale numbers for others.
    ranking = []
    for c in json.loads(data_tools.list_cities()):
        arch = _archive_concs(c)
        if arch is None:
            continue
        try:
            aqi, _dom, _subs = overall_aqi(arch[0], arch[1])
        except ValueError:
            continue
        ranking.append({"city": c, "aqi": aqi, "category": aqi_category(aqi)["label"]})
```

with:

```python
    # Ranking compares all cities on the SAME basis (archive latest day) so a
    # live number for one city is never ranked against stale numbers for others.
    # `source` reflects only what's already cached (peek_live_city never fetches),
    # so building the ranking costs zero extra OpenAQ calls.
    ranking = []
    for c in json.loads(data_tools.list_cities()):
        arch = _archive_concs(c)
        if arch is None:
            continue
        try:
            aqi, dominant, _subs = overall_aqi(arch[0], arch[1])
        except ValueError:
            continue
        row_source = "live" if live.peek_live_city(c) else "archive"
        ranking.append({"city": c, "aqi": aqi, "category": aqi_category(aqi)["label"],
                        "dominant": dominant, "source": row_source})
```

(This keeps the archive-only computation for ranking numbers — per the spec's honesty rule — while `source` is purely informational about whether that city's hero has been recently viewed live. Note: this does NOT call `_city_aqi`; `_city_aqi` mixes live-concentration AQI with archive-dominant logic in a way that would make the ranking's AQI number inconsistent across cities. The refactor instead makes `source` cache-aware without touching the AQI math — correcting the spec's suggestion where it would have broken the "same basis for every city" guarantee.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ranking_enrichment.py -v`
Expected: 2 passed

- [ ] **Step 5: Full suite regression check**

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all passing (51 + 2 new = 53)

- [ ] **Step 6: Commit and push**

```bash
git add app/main.py tests/test_ranking_enrichment.py
git commit -m "feat: /api/aqi ranking rows gain dominant pollutant + cache-aware source

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: Ten monoline city landmark icons

**Files:**
- Modify: `app/templates/index.html` (icon sprite block)

**Interfaces:**
- Produces: symbol ids `ic-delhi`, `ic-mumbai`, `ic-kolkata`, `ic-chennai`, `ic-bengaluru`, `ic-hyderabad`, `ic-pune`, `ic-ahmedabad`, `ic-lucknow`, `ic-patna`, `ic-generic`, usable via `<svg class="ic-i"><use href="#ic-delhi"/></svg>` exactly like existing icons.

- [ ] **Step 1: Find the existing icon sprite** — locate the block starting `<svg width="0" height="0" style="position:absolute" aria-hidden="true">` containing `ic-lungs`/`ic-bolt`/`ic-chip`.

- [ ] **Step 2: Add the ten symbols + fallback**, inserted before the sprite's closing `</svg>`:

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
```

- [ ] **Step 3: Browser verify** — reload the dashboard, run in console:
```javascript
['ic-delhi','ic-mumbai','ic-kolkata','ic-chennai','ic-bengaluru','ic-hyderabad','ic-pune','ic-ahmedabad','ic-lucknow','ic-patna','ic-generic'].map(id=>!!document.getElementById(id))
```
Expected: array of 11 `true` values (no missing symbol).

- [ ] **Step 4: Commit and push**

```bash
git add app/templates/index.html
git commit -m "feat: ten monoline city-landmark SVG icons + generic fallback

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 3: Cities ranking table section

**Files:**
- Modify: `app/templates/index.html`

**Interfaces:**
- Consumes: `/api/aqi` `ranking` (Task 1 shape), `RAMP`/`bandOf` (existing from Phase 2), icon symbols (Task 2).
- Produces: section `#cities`; JS constant `CITY_ICON`; function updates inside `refresh()`.

- [ ] **Step 1: Markup** — insert after the `#overview` section's closing `</section>` and before `#pollutants`:

```html
<section class="section reveal" id="cities">
  <div class="sectionHead"><div class="kicker">Compare</div><h2>India's cities, ranked</h2>
    <p id="citiesBasis" class="scoreTxt"></p></div>
  <div id="citiesTable"></div>
</section>
```

- [ ] **Step 2: CSS** — add near the other row-based styles (after `.aqiLabels` rule block):

```css
  .cityRow{display:flex;align-items:center;gap:14px;padding:10px 4px;border-top:1px solid var(--line);cursor:pointer;transition:background .15s}
  .cityRow:first-child{border-top:none}
  .cityRow:hover{background:rgba(255,255,255,.03)}
  .cityRow.current{border-left:2px solid var(--blueSolid);padding-left:12px;margin-left:-14px}
  .cityIconBadge{width:32px;height:32px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex:none}
  .cityIconBadge svg{width:18px;height:18px}
  .cityName{flex:1;min-width:90px;font-size:14px}
  .cityAqi{width:52px;text-align:right;font-size:19px;font-weight:600}
  .cityCat{width:110px;font-size:12px}
  .cityDom{width:60px;text-align:right;color:var(--dim);font-size:11px;text-transform:uppercase}
```

- [ ] **Step 3: JS** — add near `POLL_NAMES` (Task 3 of Phase 2's additions):

```javascript
const CITY_ICON={Delhi:'ic-delhi',Mumbai:'ic-mumbai',Kolkata:'ic-kolkata',Chennai:'ic-chennai',
  Bengaluru:'ic-bengaluru',Hyderabad:'ic-hyderabad',Pune:'ic-pune',Ahmedabad:'ic-ahmedabad',
  Lucknow:'ic-lucknow',Patna:'ic-patna'};
function cityIcon(c){return CITY_ICON[c]||'ic-generic'}
function selectCity(c){
  CITY=c;$('citySel').value=c;refresh();renderCalendar();renderTrends();
  $('overview').scrollIntoView({behavior:'smooth'});
}
```

Inside `refresh()`, in the `/api/aqi` success block (alongside where `pollBasis`/`pollGrid` are populated), add:

```javascript
        $('citiesBasis').textContent=`Ranked on ${a.ranking_basis||'the latest archive day, all cities'}`;
        $('citiesTable').innerHTML=a.ranking.map(r=>{
          const b=bandOf(r.aqi);
          return `<div class="cityRow ${r.city===CITY?'current':''}" onclick="selectCity('${r.city}')">
            <div class="cityIconBadge" style="background:${b.color}22"><svg style="color:${b.color}"><use href="#${cityIcon(r.city)}"/></svg></div>
            <div class="cityName">${r.city}</div>
            <div class="cityAqi num">${r.aqi}</div>
            <div class="cityCat" style="color:${b.color}">● ${r.category}</div>
            <div class="cityDom">${(r.dominant||'').toUpperCase()}</div>
          </div>`;
        }).join('');
```

- [ ] **Step 4: Simplify the hero's rank text to point at the table** — find the line setting `$('scoreTxt').textContent` inside the AQI block and change it to:

```javascript
        $('scoreTxt').innerHTML=`Driven by ${a.dominant.toUpperCase()} · <a href="#cities" style="color:inherit;text-decoration:underline">see full ranking ↓</a>`;
```

- [ ] **Step 5: Browser verify** — reload dashboard; confirm: 10 rows sorted worst-first, each with a distinct icon, category color, dominant tag; current city (Delhi) row highlighted; clicking a different row switches city everywhere (hero, pollutants, chart, calendar, trends) and scrolls to `#overview`; no console errors.

- [ ] **Step 6: Commit and push**

```bash
git add app/templates/index.html
git commit -m "feat: full 10-city ranking table with landmark icons and click-to-select

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 4: Landing page de-boxing

**Files:**
- Modify: `app/templates/landing.html`

**Interfaces:** none (pure CSS restyle of `.card`).

- [ ] **Step 1: Restyle `.card`** — replace:

```css
  .card{position:relative;padding:28px;border-radius:22px;background:var(--glass);border:1px solid var(--line);
```
(and its associated `::before` gradient-border block, and the `box-shadow`/hover transform lines) with the Phase 2 flat object-card treatment. Read the current full `.card`/`.card::before`/`.card:hover` block from `landing.html` first (it spans roughly 3 rules), then replace all three with:

```css
  .card{position:relative;padding:22px;border-radius:14px;background:rgba(255,255,255,.035);border:1px solid var(--line);
    transition:background .2s}
  .card:hover{background:rgba(255,255,255,.06)}
```

Remove the `.card::before` rule entirely (the gradient-border pseudo-element) — it does not appear in the replacement above, so deleting the old rule is the fix.

- [ ] **Step 2: Browser verify** — reload `http://localhost:8090/`; confirm the six feature cards (`#why` and `#how` sections) render flat, 14px-radius, no gradient border sheen; hover still lightens the fill; no layout breakage; no console errors.

- [ ] **Step 3: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "feat: de-box landing page feature cards to match dashboard's flat object style

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 5: README, full deploy, live verify

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README updates**
  - Dashboard paragraph: add mention of the full 10-city ranking table with landmark icons, click-to-compare.
  - No new API endpoints this phase (ranking enrichment is additive fields on `/api/aqi`) — update the existing `/api/aqi` row description to mention "per-city dominant pollutant and cache-aware live/archive source" if there's room, otherwise leave as-is (the field-level detail is already implied by "10-city ranking").

- [ ] **Step 2: Full test suite**

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all green (53 tests).

- [ ] **Step 3: Build + deploy**

`gcloud builds submit --config=/tmp/cloudbuild.yaml .` then
`gcloud run deploy vayusense --image=gcr.io/gen-lang-client-0133314577/vayusense --region=us-central1 --platform=managed`

- [ ] **Step 4: Live verify**

Run: `curl -s "https://vayusense-663068003180.us-central1.run.app/api/aqi?city=Delhi" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['ranking']), d['ranking'][0])"`
Expected: 10 rows, first row has `dominant` and `source` keys. Also load the live dashboard URL and visually confirm the ranking table + icons.

- [ ] **Step 5: Commit and push**

```bash
git add README.md
git commit -m "docs: document the city ranking table

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```
