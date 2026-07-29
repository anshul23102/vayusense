# Mobile Chapter Awareness — design spec

## Concept

The story rail (`index.html`, `summary.html`) is hidden under 900px --
correctly, there's no room for it -- but that leaves mobile visitors with
only the generic top progress bar (`#scrollProgress`, a plain % filled
bar, no chapter names). This adds a small pill label, visible only under
900px, that names the current chapter -- the same information desktop
gets from the rail's always-visible active-dot label, just delivered
differently since the rail itself can't fit.

## Mechanics

Single source of truth: `updateStory()` already computes `activeIdx` and
the current severity color every scroll tick (rail dots included or
not). This reuses that exact computation rather than re-deriving chapter
state separately -- no duplicate scroll-tracking logic.

```html
<div id="mobileChapter" aria-hidden="true"></div>
```

Placed once, near `#scrollProgress` in the body (same fixed-layer
region, not inside the rail nav -- it needs to render even though the
rail itself is `display:none` below 900px).

```css
#mobileChapter{position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:1000;
  font-size:11px;font-weight:600;color:var(--dim);background:rgba(15,21,40,.85);
  padding:4px 12px;border-radius:99px;border:1px solid var(--line);
  opacity:0;transition:opacity .25s,color .25s;pointer-events:none}
@media(min-width:900px){#mobileChapter{display:none}}
```

Hidden by default (`opacity:0`) until the first chapter update actually
runs, and hidden entirely at desktop widths via the same 900px
breakpoint the rail already uses (the two are complementary, not
independent thresholds that could drift apart).

In `updateStory()`, right where the rail dots get their active/color
state:

```js
const mobileLabel=$('mobileChapter');
if(mobileLabel){
  mobileLabel.textContent=chapterSections[activeIdx]?.label||'';
  mobileLabel.style.color=color;
  mobileLabel.style.opacity=chapterSections.length?'1':'0';
}
```

Guarded the same way the rest of chapter tracking already is (inside
the `if(!reduceMotion){...}` block) -- a user with reduced motion simply
doesn't get chapter tracking on any device or viewport, consistent with
how the rail itself already behaves.

## Explicitly out of scope

- `landing.html` -- no `CHAPTERS`/rail concept exists there at all,
  nothing to mirror.
- Any change to `#scrollProgress` itself, or to the rail's own desktop
  behavior -- purely additive, mobile-only.

## Testing

- Verify under a narrow viewport (e.g. 480px): label appears, updates as
  you scroll through chapters, color matches the current severity.
- Verify at desktop width (e.g. 1600px): label is not rendered at all
  (`display:none`, not just invisible).
- Confirm under `prefers-reduced-motion: reduce`: no label, consistent
  with the rail itself being absent there too.
- No new Python code; existing 112-test suite must still pass unchanged.
