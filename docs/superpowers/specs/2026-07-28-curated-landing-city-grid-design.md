# Curated Landing City Grid — design spec

## Concept

The landing page's "Pick a city" section (`#cities-grid` in `landing.html`)
currently renders all 36 cities as tiles, which is too much for a landing
page whose job is to make a case and move people forward, not to be the
dashboard. The hero already has a live search box (`#citySearch`) that
jumps straight to any of the 36 cities by name, so the grid's remaining
job is purely a showcase, not the only path to a specific city.

Replace the full 36-tile grid with the 8 worst-AQI cities (the most
compelling proof of the site's whole premise), plus a line stating how
many more are tracked and two explicit next steps: search, or go to the
full live dashboard.

## Mechanics

`renderCityGrid()` in `landing.html`, currently:

```js
grid.innerHTML=LANDING_DATA.ranking.map((r,i)=>{ ... }).join('');
```

Changes to slice the ranking (already sorted worst-first, confirmed by
existing usage elsewhere) to the top 8 before mapping:

```js
function renderCityGrid(){
  const grid=document.getElementById('cityGrid');
  if(!grid)return;
  const top8=LANDING_DATA.ranking.slice(0,8);
  grid.innerHTML=top8.map((r,i)=>{ ... same tile markup ... }).join('');
  document.querySelectorAll('#cityGrid .reveal').forEach(el=>io.observe(el));
}
```

Below `#cityGrid` in the section markup, add a footer row:

```html
<div class="cityGridFooter reveal">
  <p>+ <span id="moreCitiesCount"></span> more cities tracked live</p>
  <div class="cityGridActions">
    <button onclick="document.getElementById('citySearch').focus()">Search a city</button>
    <a href="/dashboard">Open Live Dashboard →</a>
  </div>
</div>
```

`moreCitiesCount` is set at render time from
`LANDING_DATA.ranking.length - 8`, not hardcoded, so it stays correct if
the tracked-city count ever changes.

Heading text updates from "Thirty-six cities. One tap away." to
"Where it's worst right now." — the old heading was a city-count boast;
the new one matches what's actually being shown (worst-first, not all).

## Explicitly out of scope

- The hero search box itself — unchanged, already does what "find one
  specific city" needs.
- `summary.html`'s (dashboard) city list — that page's job is already to
  show everything, correctly, and stays as-is.
- Any change to tile markup, styling, icons, or the reveal/tilt
  animations — only which/how-many cities are selected changes.

## Testing

- Confirm exactly 8 tiles render, worst-AQI-first, matching the same
  order already used elsewhere (e.g. rank-centered window, dashboard
  leaderboard).
- Confirm `moreCitiesCount` shows 28 (36 total - 8 shown) against real
  production data.
- Confirm "Search a city" focuses the existing hero input and "Open Live
  Dashboard" navigates to `/dashboard`.
- No new Python code; existing 112-test suite must still pass unchanged.
