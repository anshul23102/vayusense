# Command Palette + Follow-up Chips + Momentum Highlight — design spec

Three additive features, each grounded in existing app state rather than
inventing new data or a new backend call.

## A. Command palette (Ctrl/Cmd+K)

**Scope: all three pages** (`landing.html`, `summary.html`, `index.html`),
since this is global navigation, not a per-page feature.

### Trigger and structure

```js
addEventListener('keydown', e=>{
  if((e.metaKey||e.ctrlKey) && e.key.toLowerCase()==='k'){ e.preventDefault(); openCmdPalette(); }
  else if(e.key==='Escape' && CMD_OPEN) closeCmdPalette();
});
```

```html
<div id="cmdPalette" class="cmdPalette" role="dialog" aria-modal="true" aria-label="Quick navigation" style="display:none">
  <div class="cmdBackdrop" onclick="closeCmdPalette()"></div>
  <div class="cmdBox">
    <input id="cmdInput" class="cmdInput" placeholder="Search a city or action…" autocomplete="off"
      oninput="filterCmdPalette(this.value)" onkeydown="cmdPaletteKeydown(event)">
    <div id="cmdList" class="cmdList" role="listbox"></div>
  </div>
</div>
```

Backdrop is a semi-transparent blurred overlay (`backdrop-filter:blur(6px)`,
consistent with the glass-panel language already used for the nav bar),
box is centered, `cmdList` shows up to 8 matches at a time.

### Item source (reuses data already on the page, no new fetch)

- `index.html`: `[...$('citySel').options].map(o=>o.value)` -- the
  dropdown `loadCities()` already populates.
- `summary.html`: the existing global `CITIES` array from `loadCities()`.
- `landing.html`: `LANDING_DATA.cities`, already populated by
  `loadLandingData()`.

Each city becomes a list item; selecting it calls the page's own existing
city-navigation function -- `selectCity(name)` on `index.html` (in-page
switch, reuses the smooth city-switch transition already built), or
`goToCity(name)` on `summary.html`/`landing.html` (navigates to
`/city/<slug>`). No new navigation logic, just wiring the palette to
what already exists.

A small fixed set of quick actions is prepended (filtered out of the
list when the search text doesn't match them): "Open Live Dashboard"
(all pages except `summary.html` itself), "Open Landing Page" (from
`summary.html`/`index.html`), and, on `index.html` only, "Ask
VayuSense" (scrolls to `#ask`).

### Filtering and keyboard nav

Case-insensitive substring match against item labels (not true fuzzy
matching -- substring search across 36 known city names is already fast
and predictable, a full fuzzy-match library is unjustified complexity
here). Arrow Up/Down moves a highlighted index, Enter activates the
highlighted item (or the first match if none highlighted yet), Escape
closes. Reuses the same `:focus-visible` styling already added in the
accessibility pass for the input itself.

## B. Contextual follow-up chips in Ask VayuSense

**Scope: `index.html` only** (the only page with the chat).

**Framing, precisely**: these are not a new LLM call -- they're a
deterministic, context-aware suggestion list computed from the turn
that just happened (which tools were actually called, which city is
current), styled identically to the existing preset `.sugg` buttons.
Calling them "AI-generated" would overclaim; the spec and any user-
facing copy call them "suggested next questions," not implying a new
model call happened.

### Mechanics

During the SSE loop in `ask()`, track which tools this turn actually
called (currently only rendered as chips, not retained as data):

```js
const usedTools=new Set();
// inside the existing `else if(msg.type==='tool')addChip(msg);` branch:
usedTools.add(msg.tool);
```

After the stream completes successfully (`gotAny` true, not an error),
compute up to 3 suggestions from a small template bank, skipping any
whose underlying question was already answered this turn (i.e. its
tool was already called), and append them as buttons using the
existing `preset(this)` handler -- clicking one asks it immediately,
exactly like the initial suggestion chips:

```js
function computeFollowups(usedTools){
  const bank=[
    {tool:'get_forecast', text:"What's the forecast for the next few days?"},
    {tool:'get_worst_stations', text:`Which areas in ${CITY} have the worst air?`},
    {tool:'get_year_over_year', text:`Is ${CITY}'s air better or worse than last year?`},
  ];
  const out=bank.filter(b=>!usedTools.has(b.tool)).map(b=>b.text).slice(0,2);
  const other=(RANKING_DATA[0]&&RANKING_DATA[0].city!==CITY) ? RANKING_DATA[0].city
    : (CITY==='Mumbai'?'Delhi':'Mumbai');
  out.push(`Compare ${CITY} with ${other}`);
  return out.slice(0,3);
}
```

The comparison suggestion always names a real, specific city (the
current national worst, or a sensible fallback), never a placeholder
like "another city."

## C. Momentum highlight on the AQI hero

**Scope: `index.html` only**. Uses data already being fetched for the
trend chart (`t.series`, from the existing `/api/trend` call in
`refresh()`) -- no new API call.

**Framing, precisely**: this reads the 7-day rolling trend (`roll7`) of
the *currently selected pollutant*, not a recomputed overall-AQI
series (no endpoint currently exposes daily overall-AQI history
without an extra fetch). Labeled accordingly ("PM2.5's 7-day trend"),
not "AQI has improved," to avoid overstating what's actually measured.

```js
function computeMomentum(series){
  if(!series||series.length<4) return null;
  const roll=series.map(d=>d.roll7).filter(v=>v!=null);
  if(roll.length<4) return null;
  let streak=0, dir=null;
  for(let i=roll.length-1;i>0;i--){
    const delta=roll[i]-roll[i-1];
    if(Math.abs(delta)<0.05) break;
    const thisDir=delta<0?'improving':'worsening';
    if(dir===null) dir=thisDir;
    else if(thisDir!==dir) break;
    streak++;
  }
  return streak>=3 ? {dir,streak} : null;
}
```

Only surfaced when a real, non-trivial streak (3+ consecutive days)
exists -- no manufactured narrative when the trend is flat or choppy,
consistent with this app's "everything real" discipline. Rendered as a
small line near `scoreTxt`/`aqiMeta`:  "📉 PM2.5's 7-day trend has been
improving for 4 straight days" (severity-good color) or the worsening
equivalent (severity-bad color).

## Reduced motion

- A: the palette's open/close transition (opacity + scale) is skipped
  under `prefers-reduced-motion: reduce` (instant show/hide instead) --
  the palette's *function* isn't motion-dependent, only its entrance
  animation is, so this is additive to the existing convention, not a
  new exception to it.
- B, C: no motion involved -- text content only.

## Explicitly out of scope

- True fuzzy-matching (e.g. Levenshtein/subsequence scoring) for the
  command palette -- substring match is sufficient at this list size.
- A new LLM call to generate follow-up questions -- deterministic
  template selection instead, per the framing note above.
- Recomputing overall-AQI history for the momentum highlight -- reuses
  the pollutant trend already being fetched.

## Testing

- A: Ctrl/Cmd+K opens the palette on all three pages; typing filters
  cities and actions; arrow keys + Enter navigate correctly; Escape
  closes; selecting a city on `index.html` uses the existing smooth
  transition, on the other two pages navigates to `/city/<slug>`.
- B: ask a question that triggers `get_forecast`, confirm the forecast
  follow-up is *not* suggested afterward (already answered); confirm
  the comparison suggestion always names a real, specific city.
- C: verify against real production data for a city with an actual
  multi-day trend in either direction; confirm nothing renders when the
  trend doesn't show a 3+ day streak.
- No new Python code; existing 112-test suite must still pass unchanged.
