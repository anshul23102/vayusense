# Scroll-Driven Storytelling — design spec

## Concept

The city page (`index.html`) already reveals each section on scroll (via
the existing `io` IntersectionObserver, one-shot fade-up per `.reveal`
element), but each section reads as its own island -- nothing ties them
into a continuous experience as the visitor moves through the page.

This pass adds three synchronized effects, all driven by scroll position,
all skipped under `prefers-reduced-motion` (consistent with every other
motion feature this session):

1. **Chapter rail** -- a fixed vertical list of section labels tracking
   where the visitor is in the page's "story."
2. **Header parallax lag** -- section `<h2>` headers drift slightly slower
   than the page scroll, reading as depth rather than a flat stack.
3. **Scroll-linked atmosphere** -- the existing `#atmosphere` background
   glow (currently driven only by the current city's AQI severity) gets a
   second, subtler input: how far down the page the visitor has scrolled,
   so the whole page feels like one continuous space rather than
   independently-animated cards.

## Mechanics

### Chapters

Six waypoints, not all 13 sections -- a rail with every section would be
noise, not a story:

```js
const CHAPTERS=[
  {id:'overview',label:'Overview'},
  {id:'alerts',label:'Alerts'},
  {id:'cities',label:'Compare'},
  {id:'health',label:'Health'},
  {id:'trends',label:'Trends'},
  {id:'ask',label:'Ask'},
];
```

Sections between chapters (hotspots, pollutants, solutions, advisory,
visioncheck, trend, calendar) don't get their own rail entry -- scrolling
through them just keeps the most recent chapter highlighted, the same way
chapter markers work in a video scrubber.

### Rail markup & active-chapter tracking

```html
<nav id="storyRail" aria-hidden="true">
  <div class="railFill" id="railFill"></div>
  <!-- one .railDot per chapter, injected by JS -->
</nav>
```

- Fixed position, right edge, vertically centered, `display:none` under
  `max-width:900px` (rail has no room on mobile and duplicates the nav) and
  under `prefers-reduced-motion` (it's a motion-tracking affordance, not
  useful static).
- A single scroll listener (rAF-throttled, matching the existing haze/
  aurora pattern in this file) computes the active chapter: the last
  chapter section whose `getBoundingClientRect().top <= 140` (nav height +
  margin), falling back to the first chapter before any section has
  scrolled past. This is a standard scrollspy calculation, not a new
  dependency.
- Active dot gets a filled state in the current severity color (reusing
  `RAMP[CURRENT_CATEGORY_KEY]`, already computed elsewhere in this file);
  `railFill`'s height animates via CSS `transition:height .25s` to the
  active dot's vertical position, giving a continuous "progress" feel
  between discrete chapter jumps.
- Each dot is a real `<button>` (not `aria-hidden`) that scrolls its
  section into view on click -- the rail's outer nav wrapper is marked
  `aria-hidden` only for the connecting line, not the interactive dots
  themselves (correcting the markup sketch above: dots must stay in the
  accessibility tree).

### Header parallax

Existing `.sectionHead h2` elements get a small transform driven by the
same scroll listener:

```js
const lag = Math.max(-8, Math.min(8, (rect.top-innerHeight*.5)*-.02));
h2.style.transform = `translateY(${lag}px)`;
```

Clamped to ±8px -- enough to read as depth, never enough to cause layout
shift or overlap with adjacent text. Only applied to headers currently
within roughly one viewport of the visible area (checked via the same
`rect.top` already computed for chapter tracking) so the listener isn't
doing work on 13 off-screen elements every scroll tick.

### Scroll-linked atmosphere

`setAtmosphere(aqi)` already sets `ATMOSPHERE_SEVERITY` and
`ATMOSPHERE_RGB` module-level variables that the haze particle loop and
`#atmosphere` background both read. This pass adds one more factor,
`SCROLL_DEPTH` (0 at top of page, capping at 1 by ~60% scroll), and
`#atmosphere`'s opacity becomes
`baseOpacity * (0.7 + 0.3*SCROLL_DEPTH)` -- the glow is present but
subdued at the very top (where the hero/hero-adjacent content already has
its own visual weight) and reaches full intensity once the visitor is
into the content sections. Updated in the same rAF-throttled scroll
listener, clamped, no new CSS transition needed since `#atmosphere`
already transitions opacity.

## Reduced motion

Under `prefers-reduced-motion: reduce`:
- `#storyRail` is not rendered at all (`display:none` in the existing
  reduced-motion CSS block) -- it's fundamentally a motion-tracking
  affordance.
- Header parallax transform is never applied (the scroll listener checks
  `reduceMotion` before writing any `transform`, same guard used
  elsewhere in this file).
- Scroll-linked atmosphere opacity factor is skipped; `#atmosphere`
  keeps its existing severity-only opacity, matching how Living
  Atmosphere already behaves under reduced motion.

## Explicitly out of scope

- `summary.html` (dashboard) and `landing.html` -- neither has the
  multi-section long-scroll structure this targets; out of scope per the
  same reasoning used for the rank-centered window and Live Reasoning
  Trace passes.
- Any change to the existing one-shot `.reveal` fade-up behavior --
  additive only.
- Smooth-scroll library or scroll-snapping -- native `scrollIntoView`
  for rail-dot clicks is sufficient and matches patterns already used
  elsewhere in this file (e.g. `selectCity()`).

## Testing

- Verify against real production: scroll the full city page, confirm the
  rail's active dot advances through all six chapters in order, confirm
  clicking a dot jumps to that section, confirm the header parallax is
  visually present but subtle (screenshot comparison at two scroll
  depths), confirm atmosphere opacity visibly increases between page-top
  and mid-page.
- Confirm rail is absent (not just invisible) under
  `prefers-reduced-motion: reduce` and under a narrow (mobile) viewport.
- No new Python code; existing 112-test suite must still pass unchanged.
