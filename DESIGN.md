---
name: VayuSense
description: A calm, precise instrument for reading the air, not another SaaS dashboard
colors:
  night-bg: "#0e1424"
  night-bg-deep: "#111a30"
  ice: "#cfe0ff"
  ice-solid: "#9dc1ff"
  ultraviolet: "#b9a8fb"
  photon-green: "#9adb3f"
  signal-ok: "#4fe3ac"
  alert-rose: "#ff8aa3"
  amber-caution: "#ffce80"
  ink: "#f3f6fd"
  mist: "#a9b4d0"
  hairline: "#ffffff17"
  glass: "#ffffff0d"
  glass-deep: "#ffffff16"
typography:
  display:
    fontFamily: "Space Grotesk, sans-serif"
    fontSize: "clamp(2.75rem, 7.4vw, 6rem)"
    fontWeight: 700
    lineHeight: 1.04
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Space Grotesk, sans-serif"
    fontSize: "clamp(1.875rem, 4vw, 2.75rem)"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Space Grotesk, sans-serif"
    fontSize: "23px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  body:
    fontFamily: "IBM Plex Sans, -apple-system, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "IBM Plex Sans, -apple-system, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.14em"
rounded:
  xs: "8px"
  sm: "14px"
  md: "16px"
  lg: "22px"
  pill: "99px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.ice-solid}"
    textColor: "#071023"
    rounded: "{rounded.md}"
    padding: "15px 28px"
  button-primary-hover:
    backgroundColor: "{colors.ice}"
  button-ghost:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "15px 28px"
  card:
    backgroundColor: "{colors.glass}"
    rounded: "{rounded.lg}"
    padding: "24px"
  card-hover:
    backgroundColor: "{colors.glass-deep}"
  chip:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.mist}"
    rounded: "{rounded.pill}"
    padding: "8px 16px"
  input:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "13px 16px"
---

# Design System: VayuSense

## 1. Overview

**Creative North Star: "The Night Watch"**

VayuSense is a vigilant, quiet monitoring system, not a marketing dashboard. The whole surface reads as an instrument kept on through the night: a deep navy-black field, particles drifting like slow static, a soft aurora that answers the cursor rather than announcing itself, and a single glowing ring at the center that reports one number a person can trust. Nothing here performs urgency; the interface stays still and lets the data carry the weight. When a reading is hazardous, the number itself lands hard, not the chrome around it.

This system explicitly rejects the generic SaaS dashboard: no hero-metric-card cliche, no gradient text as decoration, no side-stripe accent borders, no identical card grids repeated for their own sake, no cookie-cutter admin template layout. If a screenshot of this could pass for any other analytics product with the labels swapped, it has failed The Night Watch.

**Key Characteristics:**
- Deep, near-black night backgrounds with drifting particulate haze and a cursor-reactive aurora glow
- One primary accent (Ice) doing the CTA/focus work, Ultraviolet reserved for AI/agent moments, Photon Green reserved for the acceleration story
- Flat glass surfaces at rest, lifted by soft ambient shadow and a firmer glow on interaction, never shadow-heavy by default
- A strict two-family pairing: Space Grotesk for display and data numerals, IBM Plex Sans for everything else — never a third
- Restrained motion: reveal-on-scroll, gentle hover lifts, a pulsing status dot; nothing choreographed or bouncy

## 2. Colors

The palette is one deep night neutral, one cool primary accent, and two narrowly-scoped secondary accents; everything else is text and glass.

### Primary
- **Ice Solid** (#9dc1ff): the one color allowed to ask for action. Primary buttons, focus rings, links, the CTA glow. Used on ≤10% of any given screen.
- **Ice** (#cfe0ff): the softer sibling of Ice Solid, used only inside gradient text treatments on hero headlines and the score-ring stroke gradient; never a flat fill on its own.

### Secondary
- **Ultraviolet** (#b9a8fb): reserved for anything that signals "the AI is reasoning here": the agent chat's user-message tint, the score-ring gradient's second stop, the "Ask VayuSense" tag. Never used as a generic decorative accent.
- **Photon Green** (#9adb3f): reserved exclusively for the acceleration story: the NVIDIA benchmark number, the live-status pulse dot, the "safe" trend arrows. If a green appears anywhere else on screen, it's the wrong token.

### Tertiary (status colors, dashboard only)
- **Signal OK** (#4fe3ac): safe/healthy pollutant readings.
- **Alert Rose** (#ff8aa3): hazardous readings, error states. Paired with an icon or label, never color alone, so meaning survives color blindness.
- **Amber Caution** (#ffce80): borderline/caution readings and warning banners.
- **Ember** (#ffab73): AQI ramp only — the "Poor" band.
- **Magenta Signal** (#ef7ac8): AQI ramp only — the "Severe" band.
- **Oxblood** (#b04a63): AQI ramp only — the "Hazardous" band.

### Neutral
- **Night BG** (#0e1424): the base field for the dashboard and every deep surface.
- **Night BG Deep** (#111a30): the landing page's secondary background stop, used only in the aurora gradient mix, never as a flat panel fill.
- **Ink** (#f3f6fd): primary text. Near-white, never pure #fff.
- **Mist** (#a9b4d0): secondary/muted text: labels, captions, timestamps, helper copy.
- **Hairline** (#ffffff17): the only border color in the system. One weight, one opacity, everywhere.
- **Glass** (#ffffff0d): the resting surface fill for every card, chip, input, and nav bar.
- **Glass Deep** (#ffffff16): the hover/active surface fill, one step up from Glass.

### Named Rules
**The One Signal Rule.** Photon Green means acceleration and only acceleration. Ultraviolet means the AI is reasoning and only that. Reusing either color for an unrelated purpose breaks the vocabulary the whole product depends on.

**The Status-Plus-Label Rule.** Alert Rose, Amber Caution, and Signal OK never carry meaning by hue alone; every status color ships with a text label or icon alongside it.

**Boxes are for objects, not sections.** Page sections (charts, calendars, tables,
the hero) sit open on the night background, separated by hairline top rules and
whitespace — never wrapped in cards. Cards exist only for true objects (a pollutant,
a city, a forecast method, an impact stat): radius 14px, flat fill, no gradient
border, with a 3px left severity edge-bar when the object has a severity.

**The AQI Ramp.** The only sanctioned 6-step severity scale: Good=Signal OK,
Moderate=Amber Caution, Poor=Ember, Unhealthy=Alert Rose, Severe=Magenta Signal,
Hazardous=Oxblood. Ember, Magenta Signal, and Oxblood may appear ONLY inside
AQI-severity visualizations (scale bar, calendar, rankings, charts), always with the
band label present. Ultraviolet and Photon Green are not part of the ramp.

**The Measured-vs-Projected Rule.** Forecasted/projected data is never given its own color. It reuses the existing hue for that series (e.g. Amber Caution for the 7-day trend line) and is distinguished only by line style: solid for measured, dotted/dashed for projected, with a soft fill band for uncertainty. Introducing a new color for "this is a guess" would imply it's a different kind of signal than it is — the honesty is in the line style, not a new token.

## 3. Typography

**Display Font:** Space Grotesk (headlines, section titles, and every stat numeral — always with `font-variant-numeric: tabular-nums` on numbers)
**Body Font:** IBM Plex Sans (body copy, labels, buttons, chat, captions; -apple-system, sans-serif fallback)

**Character:** A two-family instrument pairing. Space Grotesk's slightly quirky geometric terminals give the big numbers a "scientific instrument" voice; IBM Plex Sans keeps running text engineered and neutral. The pairing rule is strict: if it's a headline or a number the user reads as data, it's Space Grotesk; everything else is Plex. No third family, ever.

### Hierarchy
- **Display** (700, `clamp(2.75rem, 7.4vw, 6rem)`, 1.04 line-height, -0.02em tracking): the landing hero headline only. Appears once per page.
- **Headline** (650, `clamp(1.875rem, 4vw, 2.75rem)`, 1.15 line-height, -0.01em tracking): section titles on the landing page.
- **Title** (650, 23px, 1.2 line-height, -0.01em tracking): dashboard section headers, one notch quieter than a landing Headline since the dashboard is a working surface, not a pitch.
- **Body** (400, 17px, 1.6 line-height, max 70ch): lead paragraphs and descriptive copy. Dashboard body copy runs smaller (13-15px) for density; never below 12px for anything a user must read closely.
- **Label** (600, 12px, uppercase, 0.14em tracking): kickers, eyebrows, KPI captions, tag chips. The system's only uppercase-tracked text; reserve it for true labels, not for emphasis.

### Named Rules
**The Two Voices Rule.** Space Grotesk speaks headlines and data numbers; IBM Plex Sans speaks everything else. A third family — or swapping their roles — breaks the calibrated-instrument read.

## 4. Elevation

The Night Watch uses two elevation vocabularies, kept strictly separate: a neutral ambient shadow for structural lift, and a colored glow reserved for accent moments. Cards sit flat at rest and gain a soft, dark ambient shadow plus a one-step surface lift (Glass to Glass Deep) on hover, giving the "tactile and confident" weight the system calls for without turning the dashboard into a stack of drop-shadowed panels.

### Shadow Vocabulary
- **Ambient Rest** (`box-shadow: 0 8px 28px rgba(6,10,25,.35)`): the default lift under every card and elevated panel, always this same dark, diffuse tone regardless of what's inside the card.
- **Ambient Hover** (`box-shadow: 0 14px 40px rgba(6,10,25,.45)`): the firmer, deeper lift on hover/focus. Paired with a small `translateY(-2px)` for the confident, tactile feel.
- **Glow Primary** (`box-shadow: 0 10px 34px rgba(157,193,255,.4)`): reserved for the primary CTA button only.
- **Glow Accent** (`box-shadow: 0 0 28px rgba(154,219,63,.28)` / `text-shadow` equivalent): reserved for the NVIDIA benchmark number and other Photon Green moments.

### Named Rules
**The Two-Vocabulary Rule.** Ambient shadows convey structure (this thing is raised off the surface). Glows convey significance (this specific number matters). Never use a glow to fake structural depth, and never use an ambient shadow to try to draw attention to a value.

## 5. Components

### Buttons
- **Shape:** 16px radius (`{rounded.md}`), never the pill shape; buttons are instrument controls, not marketing pills.
- **Primary:** Ice Solid background, `#071023` near-black text (not pure black), Glow Primary shadow at rest, lightens to Ice on hover with an added Ambient Hover shadow and a 2px lift.
- **Ghost/Secondary:** Glass background, Hairline border, Ink text, no shadow at rest; on hover, shifts to Glass Deep with a light Ambient Hover shadow, matching the firmer feel of Primary rather than staying inert.

### Chips / Tags
- **Style:** Glass background, Hairline border, Mist text, full pill radius (`{rounded.pill}`), 8px/16px padding.
- **Live-status variant:** carries the small Photon Green pulsing dot (the system's one animated status indicator); reserve the pulse for genuinely live data, never decorative.

### Cards / Containers
- **Corner Style:** 22px radius (`{rounded.lg}`), consistent across landing feature cards and dashboard panels.
- **Background:** Glass at rest, Glass Deep on hover.
- **Shadow Strategy:** Ambient Rest at rest, Ambient Hover plus a subtle upward shift on hover/focus (see Elevation). This is new discipline for the system: previous flat-only cards now carry real, if restrained, structural lift.
- **Border:** 1px Hairline, always. Additionally, every card carries a 1px gradient top-edge highlight (white fading to transparent) via a masked pseudo-element, giving the glass a lit-from-above read without a literal light source.
- **Internal Padding:** 24px (`{spacing.lg}`), 16px on tighter dashboard grid cells.

### Inputs / Fields
- **Style:** Glass background, Hairline border, 14px radius (`{rounded.sm}`), Ink text.
- **Focus:** border shifts to Ice Solid at 50% opacity; no glow ring, keeping focus states in the same restrained register as the rest of the system.
- **Disabled (send button while a request is in flight):** 50% opacity, no lift on hover.

### Navigation
- A single floating glass pill, fixed and centered, 18px radius, blurred backdrop, Hairline border. Logo mark is a small conic-gradient dot (Ice Solid to Ultraviolet) with its own soft glow. Nav links sit in Mist at rest, shift to Ink on hover with no underline; the trailing CTA is a compact Primary button variant.

### Score Ring (signature component)
- An SVG circular gauge: a Hairline track with an Ice Solid-to-Ultraviolet gradient stroke animating its `stroke-dashoffset` on load. The number inside uses Display-scale weight at a smaller size, with a Mist caption beneath. This is the product's one true "hero metric," and it earns the treatment precisely because nothing else on screen competes for that same visual weight.

### Chat Bubbles (signature component)
- **User message:** a soft Ice Solid/Ultraviolet gradient tint at low opacity, right-aligned, signaling "a question is heading toward the AI."
- **Agent message:** flat Glass, left-aligned, no gradient; the agent's answers stay visually calm and neutral even when the content is a hazardous verdict.
- **Thinking state:** three low-opacity dots with a slow blink, never a spinner; keeps the instrument-panel restraint even mid-response.

## 6. Do's and Don'ts

### Do:
- **Do** keep every screen to one dominant accent (Ice Solid) with Ultraviolet and Photon Green appearing only in their named contexts (agent moments, acceleration moments).
- **Do** give cards real ambient lift (Ambient Rest/Hover) now that the system has moved past flat-only; keep that lift dark and diffuse, never colored.
- **Do** pair every status color (Alert Rose, Amber Caution, Signal OK) with a text label or icon.
- **Do** keep the pairing strict: Space Grotesk for display/numbers, IBM Plex Sans for text; let weight and tracking carry hierarchy within each.
- **Do** keep motion restrained: reveal-on-scroll, hover lifts, one pulsing status dot; always ship a prefers-reduced-motion alternative.

### Don't:
- **Don't** ship a generic SaaS dashboard: no hero-metric-card cliche, no gradient text as decoration, no side-stripe colored borders on cards or callouts, no identical repeated card grids, no cookie-cutter admin template layout.
- **Don't** make this look like a government/bureaucratic data portal: no dense unstyled tables, no default form-control chrome, no bureaucratic labeling.
- **Don't** make this look like a consumer weather app: no cartoonish icons, no playful illustration style, no rounded-mascot AQI badges.
- **Don't** use a glow to fake structural depth, or an ambient shadow to fake significance; the two vocabularies stay separate.
- **Don't** introduce a third type family, and don't set body copy in Space Grotesk or headlines in Plex.
- **Don't** rely on color alone for hazardous/safe/caution states.
