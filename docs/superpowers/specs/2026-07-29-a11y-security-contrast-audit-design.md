# Accessibility Pass + Security Hardening + Contrast Audit — design spec

Three companion passes, each grounded in an actual audit of the current
code (not assumptions) before any change.

## A. Accessibility

**Audit findings**: a few interactive elements already have solid a11y
(`.cityRow` and `.sugg button` have `:focus-visible` rings and
`aria-label`s; rail dots already carry `aria-label`; `#scoreLive` is
already `aria-live="polite"`). Gaps found:
- No skip-to-content link on any of the three pages.
- No consistent, theme-matched `:focus-visible` ring for interactive
  elements broadly (search inputs, health tabs, nav links, rail dots,
  yearChip buttons) -- some rely on the browser default, which is
  inconsistent and sometimes low-contrast against this dark theme.
- Calendar day cells (`.calDay`) are plain, unfocusable `<div>`s with
  only a `title` attribute -- not discoverable by keyboard, and `title`
  tooltips are unreliable for screen readers.

**Fixes** (`index.html`, `summary.html`; `landing.html` gets the skip
link + focus rings, it has no calendar or health tabs):

1. Skip-to-content link: visually hidden until focused, jumps to the
   first main section (`#overview` on city/dashboard pages, the hero on
   landing).
   ```html
   <a href="#overview" class="skipLink">Skip to content</a>
   ```
   ```css
   .skipLink{position:fixed;top:-60px;left:16px;z-index:2000;background:var(--blueSolid);
     color:#071023;padding:10px 18px;border-radius:10px;font-weight:600;font-size:13.5px;
     text-decoration:none;transition:top .2s}
   .skipLink:focus{top:16px}
   ```
2. A single, broad `:focus-visible` rule so every interactive element
   gets the same visible ring, rather than relying on scattered
   per-component rules:
   ```css
   a:focus-visible,button:focus-visible,input:focus-visible,[tabindex]:focus-visible{
     outline:2px solid var(--blueSolid);outline-offset:2px;border-radius:4px}
   ```
   Existing more-specific rules (`.cityRow:focus-visible`,
   `.sugg button:focus-visible`) are left as-is; this rule only fills
   the gaps, it doesn't need to replace anything already correct.
3. Calendar day cells gain `role="img"` and a full `aria-label` (e.g.
   `"July 15, 2026, AQI 87, Moderate"`), in addition to (not instead of)
   the existing `title` tooltip. Not made keyboard-focusable
   individually -- 365 tab stops for a decorative-density calendar is
   worse UX than the current hover/tooltip pattern, same reasoning
   GitHub's own contribution graph uses.

## B. Security hardening

**Audit findings**: security is already substantially hardened --
`_CSP` covers script/style/font/img/connect/object/frame-ancestors,
plus `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
`Strict-Transport-Security`, per-endpoint sliding-window rate limits on
both billed AI endpoints (`/api/ask*` at 8/min, `/api/vision-check` at
5/min), a 500-char question cap, and an 8MB image cap enforced before
the body is fully read. No `CORSMiddleware` is registered, so
cross-origin requests are already same-origin-only by default. The one
real gap: no `Permissions-Policy` header, so the browser's default
(often permissive) policy for camera/microphone/geolocation/payment
applies, even though this app uses none of them.

**Fix**: add one header, defense-in-depth, zero behavior change since
nothing here uses any of these APIs:
```python
response.headers["Permissions-Policy"] = (
    "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
    "accelerometer=(), gyroscope=(), magnetometer=()"
)
```

## C. Contrast audit

**Audit findings**: computed real WCAG contrast ratios (not
guesses) for the severity ramp against the app's `#131b30` background:

| Category | Hex | Contrast vs bg | AA (4.5:1 text)? |
|---|---|---|---|
| good | `#3dfc9e` | 12.73:1 | pass |
| moderate | `#ffc247` | 10.64:1 | pass |
| poor | `#ff9640` | 7.90:1 | pass |
| unhealthy | `#ff5c85` | 5.80:1 | pass |
| severe | `#ef4fc0` | 5.34:1 | pass |
| hazardous | `#c93a5a` | 3.45:1 | **fail** |

This is exactly why `textSafeColor(key,color)` already exists (lightens
hazardous to `#d25c76`, which measures 4.51:1, just clearing AA) --
but auditing every call site that sets a severity color as literal
*text* found it isn't applied consistently: `alertBadgeColor()` (used
in both `index.html` and `summary.html`) returns the raw
`RAMP[a.severity]` for category-breach alerts, and that raw value is
used directly as the alert badge's text color, not routed through
`textSafeColor()`. A hazardous-severity alert badge's text currently
renders at 3.45:1, below AA.

Every other direct-color-as-text site audited (icon colors inside
tinted badges, YoY percentage-change text) either already uses a safe,
non-severity color set (`#ff5c85`/`#3dfc9e`/`#a9b4d0`, all pass AA) or
is a decorative icon subject to the lower 3:1 non-text contrast
threshold (WCAG 1.4.11), which hazardous already clears unaided.

**Fix**: route the alert badge's text color through the existing
helper at the one call site that skips it, in both files:
```js
<span class="alertBadge" style="background:${color}22;color:${textSafeColor(a.severity,color)}">
```
`border-left-color` on the same row keeps the raw `color` -- a
decorative border isn't text and has no contrast requirement.

## Explicitly out of scope

- A full WCAG 2.1 AA conformance audit (this fixes the one concrete
  contrast bug found and adds baseline keyboard/screen-reader support;
  a full audit is a larger, separate effort).
- Rewriting inline-script CSP to nonce-based (already documented in
  `main.py` as out of scope without a full template rewrite).
- Any change to rate limits or payload caps -- audited and found
  already reasonable, not touched.

## Testing

- Tab through each page from the URL bar: skip link appears first,
  jumps correctly; every subsequently focused control shows a visible
  ring.
- Verify a hazardous-severity alert badge (real production data, not a
  mock) now renders with the lightened text color.
- Confirm `Permissions-Policy` header present on a live response.
- No new Python code paths beyond one header line; existing 112-test
  suite must still pass unchanged.
