# Dedicated City Pages Implementation Plan (Renovation Phase 5B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every tracked city gets a real, shareable `/city/<slug>` URL that pre-loads the existing dashboard set to that city; in-dashboard city switches keep the URL in sync via `history.pushState` without reintroducing full-page reloads.

**Architecture:** A new FastAPI route does a single case-insensitive city-name match and a one-line string substitution on the same `index.html` text `/dashboard` already serves — no templating engine, no duplicated markup. Client-side, the two existing city-switch call sites (`selectCity()` and the `citySel` dropdown handler) gain a `pushState` call and a `document.title` update; a `popstate` listener and a page-load initializer read the city from the URL using the same switch logic in reverse.

**Tech Stack:** FastAPI (existing `app/main.py`), vanilla JS (existing `index.html`/`landing.html`), pytest.

## Global Constraints

- Working dir `/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense`; venv `.venv/bin/python`; dev server on :8090 auto-reloads.
- `/dashboard` and `/dashboard?city=X` must keep working unchanged — `/city/<slug>` is additive.
- All 10 tracked city names today are single words (Delhi, Mumbai, Kolkata, Chennai, Bengaluru, Hyderabad, Pune, Ahmedabad, Lucknow, Patna); slug matching is case-insensitive exact match against `data_tools.list_cities()`.
- No full-page reload on in-dashboard city switches — `pushState`, never `location.href`, for those paths.
- Commits end with the Co-Authored-By Claude trailer; push after each task. Deploy cadence: local verify → Cloud Build (`/tmp/cloudbuild.yaml`) → `gcloud run deploy vayusense --region=us-central1` → live verify → push.

---

### Task 1: `GET /city/{slug}` route

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_city_pages.py`

**Interfaces:**
- Consumes: `data_tools.list_cities()` (existing).
- Produces: route `GET /city/{slug}` → `HTMLResponse` (200, `index.html` text with `let CITY='Delhi';` replaced by the matched city) or `JSONResponse({"error": ...}, status_code=404)`.

- [ ] **Step 1: Write the failing test**

`tests/test_city_pages.py`:
```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_city_page_sets_correct_city():
    r = client.get("/city/delhi")
    assert r.status_code == 200
    assert "let CITY='Delhi';" in r.text


def test_city_page_case_insensitive():
    r = client.get("/city/DELHI")
    assert r.status_code == 200
    assert "let CITY='Delhi';" in r.text


def test_city_page_different_city():
    r = client.get("/city/mumbai")
    assert r.status_code == 200
    assert "let CITY='Mumbai';" in r.text


def test_city_page_unknown_slug_404s():
    r = client.get("/city/atlantis")
    assert r.status_code == 404
    assert "error" in r.json()


def test_dashboard_route_unchanged():
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "let CITY='Delhi';" in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_city_pages.py -v`
Expected: FAIL — `404 Not Found` for `/city/delhi` (route doesn't exist yet).

- [ ] **Step 3: Implement in `app/main.py`** — add after the existing `/dashboard` route:

```python
@app.get("/city/{slug}", response_class=HTMLResponse)
def city_page(slug: str):
    cities = json.loads(data_tools.list_cities())
    match = next((c for c in cities if c.lower() == slug.lower()), None)
    if match is None:
        return JSONResponse({"error": f"unknown city '{slug}'"}, status_code=404)
    html = (ROOT / "app" / "templates" / "index.html").read_text()
    return html.replace("let CITY='Delhi';", f"let CITY='{match}';")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_city_pages.py -v`
Expected: 5 passed

- [ ] **Step 5: Full suite regression check**

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all passing (60 existing + 5 new = 65)

- [ ] **Step 6: Commit and push**

```bash
git add app/main.py tests/test_city_pages.py
git commit -m "feat: /city/{slug} route serves the dashboard pre-set to that city

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 2: URL sync on in-dashboard city switches

**Files:**
- Modify: `app/templates/index.html`

**Interfaces:**
- Consumes: `selectCity(c)` (existing, Phase 3), the `citySel` onchange handler (existing).
- Produces: `function syncCityUrl(c)`; `popstate` listener; page-load city initializer from `location.pathname`.

- [ ] **Step 1: Add `syncCityUrl` helper** — near the top of the script, after the `CITY_ICON`/`cityIcon` block:

```javascript
function syncCityUrl(c){
  document.title = `VayuSense — ${c} Air Quality`;
  const path = '/city/' + c.toLowerCase();
  if(location.pathname !== path) history.pushState({city:c}, '', path);
}
```

- [ ] **Step 2: Call it from `selectCity`** — find:
```javascript
function selectCity(c){
  CITY=c;$('citySel').value=c;refresh();renderCalendar();renderTrends();
```
Replace with:
```javascript
function selectCity(c){
  CITY=c;$('citySel').value=c;syncCityUrl(c);refresh();renderCalendar();renderTrends();
```

- [ ] **Step 3: Call it from the `citySel` dropdown handler** — find:
```javascript
  $('citySel').onchange=()=>{CITY=$('citySel').value;refresh();renderCalendar();renderTrends()};
```
Replace with:
```javascript
  $('citySel').onchange=()=>{CITY=$('citySel').value;syncCityUrl(CITY);refresh();renderCalendar();renderTrends()};
```

- [ ] **Step 4: Add a `popstate` listener** — right after the `syncCityUrl` function definition. It matches the URL against the real city list once `loadCities()` has populated the `citySel` dropdown, so it can resolve case-insensitively against known options:

```javascript
addEventListener('popstate', ()=>{
  const m = location.pathname.match(/^\/city\/([^/]+)$/i);
  if(!m) return;
  const slug = m[1].toLowerCase();
  const opts = [...$('citySel').options].map(o=>o.value);
  const match = opts.find(c=>c.toLowerCase()===slug);
  if(match){ CITY=match; $('citySel').value=match; document.title=`VayuSense — ${match} Air Quality`; refresh(); renderCalendar(); renderTrends(); }
});
```

- [ ] **Step 5: Browser verify** — reload `http://localhost:8090/dashboard`; click a different city in the ranking table; confirm the address bar changes to `/city/<name>` without a page reload (Network tab shows no full document fetch) and the tab title updates; press the browser Back button; confirm it returns to the previous city instantly (no navigation/reload) with the dashboard content updating; no console errors.

- [ ] **Step 6: Commit and push**

```bash
git add app/templates/index.html
git commit -m "feat: sync the URL to the current city on every in-dashboard switch

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 3: Landing page links to real city pages

**Files:**
- Modify: `app/templates/landing.html`

**Interfaces:**
- Consumes: `goToCity(name)` (existing, Phase 5A).

- [ ] **Step 1: Update `goToCity`** — find:
```javascript
function goToCity(name){ location.href=`/dashboard?city=${encodeURIComponent(name)}`; }
```
Replace with:
```javascript
function goToCity(name){ location.href=`/city/${encodeURIComponent(name.toLowerCase())}`; }
```

- [ ] **Step 2: Browser verify** — reload `http://localhost:8090/`; search "chennai" and select it; confirm navigation lands on `/city/chennai` and the dashboard shows Chennai pre-selected on first paint (no flash of Delhi). Click a map dot for a different city; confirm it also navigates to the matching `/city/<slug>` URL.

- [ ] **Step 3: Commit and push**

```bash
git add app/templates/landing.html
git commit -m "feat: landing search/map navigate to dedicated /city/<slug> pages

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```

---

### Task 4: Full deploy + live verify

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README update** — add one line to the API/routes description noting `/city/<slug>` as a dedicated per-city entry point alongside `/dashboard`.

- [ ] **Step 2: Full test suite**

Run: `.venv/bin/python -m pytest tests/ 2>&1 | tail -1`
Expected: all green (65 tests).

- [ ] **Step 3: Build + deploy**

`gcloud builds submit --config=/tmp/cloudbuild.yaml .` then
`gcloud run deploy vayusense --image=gcr.io/gen-lang-client-0133314577/vayusense --region=us-central1 --platform=managed`

- [ ] **Step 4: Live verify**

Run: `curl -s https://vayusense-663068003180.us-central1.run.app/city/chennai | grep -o "let CITY='[A-Za-z]*'"`
Expected: `let CITY='Chennai'`. Then: `curl -s -o /dev/null -w "%{http_code}" https://vayusense-663068003180.us-central1.run.app/city/atlantis` → `404`. Load the live `/city/mumbai` URL in a browser and confirm it renders Mumbai pre-selected.

- [ ] **Step 5: Commit and push**

```bash
git add README.md
git commit -m "docs: document /city/<slug> dedicated city pages

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" && git push
```
