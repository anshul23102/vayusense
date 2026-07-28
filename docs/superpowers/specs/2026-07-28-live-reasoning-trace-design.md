# Live Reasoning Trace — design spec

## Concept

Ask VayuSense's SSE stream already sends `tool` events as each Data Analyst
tool call actually happens, with real gaps in time as each call executes,
followed by `delta` events as the Health Advisor's answer streams in. The
frontend currently just accumulates `tool` events into an array and only
renders them -- all at once, no entrance animation -- when the first `delta`
arrives. The multi-step tool-calling that is genuinely happening live is
invisible until it is already over.

This pass fixes that rendering gap: each trace chip appears the moment its
real event arrives, and the handoff from analyst to advisor (the first
`delta` event) gets a visible moment. No fabricated timing, no new data --
this renders what the stream already sends, just no longer batched.

## Mechanics

### Stable bubble structure

Today, `render()` does `bubble.innerHTML = mdToHtml(full||'No answer.') +
renderTrace(trace)` on every update, rebuilding the whole bubble from
scratch. If chips got an entrance animation under this scheme, EVERY chip
would replay its animation on every subsequent update, since the whole
subtree is destroyed and recreated each time.

Instead, the bot bubble gets three stable child elements, created once
when the message is inserted, updated individually thereafter:

```html
<div class="msg bot thinking">
  <span class="thinkingLine" id="think-N">Analyst crunching data <i>●</i><i>●</i><i>●</i></span>
  <div class="ans" id="ans-N"></div>
  <div class="traceRow" id="trace-N" style="display:none"><span class="traceLabel">Data used</span></div>
</div>
```

(`N` is a per-message counter, so multiple turns in one session don't
collide on element IDs.)

- **On a `tool` event:** append exactly one new `<span class="traceChip
  chipIn">` to `#trace-N` (never touch existing chips), and set `#trace-N`'s
  `display` to `flex` the first time a chip is added.
- **On a `delta` event:** update `#ans-N`'s `innerHTML` via `mdToHtml(full)`
  (same accumulation logic as today -- replace on the final non-partial
  event, append on partial). On the *first* delta, add a `.done` class to
  `#think-N` that fades it out via CSS transition, and add a `.settled`
  class to `#trace-N` for a brief one-shot glow marking the analyst-to-
  advisor handoff.
- **On an `error` event:** unchanged from today -- hide the thinking line,
  show the error text.

### Chip entrance animation

```css
@keyframes chipIn{from{opacity:0;transform:translateY(4px) scale(.92)}to{opacity:1;transform:none}}
.traceChip.chipIn{animation:chipIn .3s cubic-bezier(.2,.8,.2,1) forwards}
```

Each chip gets this class only at the moment it is created via `insertAdjacentHTML`, so it plays exactly once per chip, never on re-render, because there is no re-render of existing chips anymore.

### Handoff glow

```css
@keyframes traceSettle{0%{box-shadow:0 0 0 rgba(127,176,255,0)}40%{box-shadow:0 0 16px rgba(127,176,255,.35)}100%{box-shadow:0 0 0 rgba(127,176,255,0)}}
.traceRow.settled{animation:traceSettle .8s ease-out}
```

A one-shot, non-looping soft glow on the trace row itself when the advisor
takes over -- reinforces "the analyst finished, here's the handoff" without
adding any new text or claiming anything not actually happening.

### `renderTrace()`

Kept as-is for one remaining use: a full trace render is still needed if a
message needs to be redrawn wholesale (there is currently no such call
site after this change removes the only one in `ask()`, but the function
stays rather than being deleted, since deleting a small, still-correct,
still-tested pure function to save a few lines is not worth the risk of
missing a call site elsewhere in the file).

## Reduced motion

`chipIn` and `traceSettle` both get suppressed the same way every other
continuous/one-shot decorative animation in this file already is:
`.traceChip{transition:none}` equivalent added to the existing
`prefers-reduced-motion: reduce` block -- chips still appear, just without
the pop-in, and the settle glow is skipped (chips get their final opacity/
position immediately, and `.traceRow.settled` gets no animation).

## Testing

- Live verification against production with a real question (same
  discipline as every other agent-facing change this session), confirming:
  chips appear incrementally rather than all at once, the thinking
  indicator fades out at the correct moment (first delta, not before), and
  the settle glow fires once, not repeatedly.
- Confirm a second question in the same session (after "New chat" or a
  follow-up) does not collide with the first message's element IDs.
- No new Python code; existing 112-test suite must still pass unchanged.

## Explicitly out of scope

- Any change to `/api/ask/stream` or the ADK agent pipeline itself -- this
  is a pure rendering change on data already sent.
- Any change to `summary.html` or `landing.html` -- neither has a chat
  interface.
