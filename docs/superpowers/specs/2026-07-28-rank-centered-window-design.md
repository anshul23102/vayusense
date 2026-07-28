# Rank-Centered Ranking Window — design spec

## Concept

The per-city page's "India's cities, ranked" section (index.html only --
the dashboard already shows the full honest leaderboard unconditionally
and is out of scope) currently shows the top 5 cities nationally, then an
ellipsis, then the current city if it isn't already in that top 5. For
most cities that aren't near the top, this means leading with 5 cities
that have nothing to do with the one the visitor is actually looking at.

Replace the default (collapsed) view with a window of cities centered on
the current city's actual rank -- comparable neighbors, not unrelated
extremes. "Show all 36 cities" is unchanged: the full leaderboard,
including the true top-5, stays one click away.

## Mechanics

New windowing function in `index.html`, replacing the `top5`/`iShowMine`
branch inside `renderCitiesTable()`:

```js
function rankWindow(ranking, city, size=5){
  const idx = ranking.findIndex(r=>r.city===city);
  if(idx<0) return ranking.slice(0, size); // city not found: fall back, don't crash
  const half = Math.floor(size/2);
  let start = idx - half;
  let end = start + size;
  if(start < 0){ end -= start; start = 0; }
  if(end > ranking.length){ start -= (end - ranking.length); end = ranking.length; }
  start = Math.max(0, start);
  return ranking.slice(start, end);
}
```

`renderCitiesTable()`'s collapsed branch becomes:

```js
const win = rankWindow(ranking, CITY, 5);
let html = win.map((r,i)=>cityRowHtml(r, ranking.indexOf(r))).join('');
html += `<button ...>Show all ${ranking.length} cities ↓</button>`;
box.innerHTML = html;
```

`cityRowHtml(r, i)` already exists and uses `i` only for stagger-animation
delay timing (`animation-delay:${Math.min(i,8)*30}ms`), not for the
displayed rank number itself (the rank number, if shown, would come from
the city's position in the full `ranking` array, which `ranking.indexOf(r)`
recovers correctly regardless of the window's own local index).

The current city keeps its existing `.current` highlight class -- that
logic already lives in `cityRowHtml()` (`r.city===CITY?'current':''`) and
needs no change.

### Edge behavior, verified not assumed

- City ranked #1 or #2: window can't extend 2 rows above, so it slides
  down and shows ranks 1-5 (or 1-4 if only 4 cities existed, though that
  never happens here with a fixed 36-city set).
- City ranked #35 or #36: symmetric case at the bottom, window slides up.
- Exactly 36 cities always, so the "not found" fallback in `rankWindow()`
  is defensive-only and not expected to trigger in production, but it's
  there so a data hiccup produces a sane top-5 fallback rather than a
  crash.

## Testing

- Verify the window is correct for a city near the top (e.g. rank 1-2), a
  city in the middle, and a city near the bottom (rank 35-36) -- three
  distinct edge cases, not just the common middle case.
- Confirm "Show all 36 cities" still expands to the complete, correctly
  ordered list, unchanged from today.
- Confirm the current city's `.current` highlight and the reveal/stagger
  animation both still work inside the new window.
- No new Python code; existing 112-test suite must still pass unchanged.

## Explicitly out of scope

- Any change to `summary.html`'s city list (full list is the correct,
  unrelated-to-this-complaint framing there).
- Any change to the "Show all 36 cities" expanded view's own layout or
  ordering.
