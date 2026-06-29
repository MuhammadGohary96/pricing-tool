# Design System — Breadfast Pricing Tool (frontend)

The product voice is **confident, precise, calm** (see `PRODUCT.md`). One accent, color used to encode state, motion that conveys state not spectacle. This file is the contract that keeps every view feeling like one product. When in doubt, copy an existing reference component rather than inventing.

## Tokens (defined in `tailwind.config.js` + `src/assets/styles/breadfast.css`)

- **Surface:** page ground is `bg-paper` (`#FAF8FC`); panels are `bg-white`.
- **Typeface:** `Geist` (UI) + `Geist Mono` (all numerics, `font-mono` → tabular). Loaded via `<link>` in `index.html`.
- **Type scale:** use the tokens `text-kpi / title / heading / subheading / body / caption / micro`. Avoid ad-hoc `text-2xl`, `text-[22px]` etc. except for one-off display headings.
- **Accent:** a single brand magenta `#a3007c` (`brand-primary`, with `dark/darkest/light/lightest/50`). **Do not introduce a second UI accent** (no blue, teal, indigo, violet for chrome).
- **Letter-spacing:** `tracking-tightish` (display headings).
- **Easing:** `ease-premium` utility / `--ease-premium` CSS var. No `linear`/`ease-in-out` for premium motion.

## Elevation & shape (the panel recipe)

- **Panel:** `bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70`. Interactive panels add `shadow-panel-hover`.
- **Dropdown/overlay:** `rounded-xl shadow-dropdown ring-1 ring-grey-200/70`.
- **Controls** (inputs, small buttons): `rounded-lg`. **Pills/badges:** full radius.
- **Never** use the legacy `shadow-card`/`shadow-lg` on panels, and **never** a pure-black shadow (`rgba(0,0,0,…)`); tinted ink (`rgba(40,16,48,…)`) only. (Legacy `shadow-card` is repointed to tinted ink for safety, but use `shadow-panel`.)
- **Banned:** `border-l-2` side-stripes for state. Use a `bg-brand-50` tint + indentation instead.

## Color encoding (semantic, separate from the accent)

- **Price Index** is the only place hue carries data meaning — owned by `src/utils/piColor.js` ("both tails bad": cheaper = cool/blue, parity = green, pricier = warm/red). The `▼ ◆ ▲` glyphs are an intentional colorblind/greyscale-safe encoding — **keep them**, don't swap for icons.
- **Action states** are owned by `src/components/shared/ActionBadge.vue` (the single source): Needs Mapping = red, Review Match = amber, Needs Price Update = **brand magenta** (not blue, which collides with the PI cheaper-tail), Complete = green. Other surfaces must reuse this mapping.
- **Status** green/amber/red (success/warning/error) is allowed and is not "a second accent".
- **PI precision:** always 2 decimals (`toFixed(2)`); `KpiCard` `format:'pi'` is the source.

## Icons & glyphs

- **Lucide only** (`lucide-vue-next`). No hand-rolled `<svg>` icon paths, no emoji-as-glyph, no `&times;`/`&larr;`/`↑↓↕`/`↔`. Exceptions: real brand logos (e.g. the Google "G"), and genuine data-viz SVG/canvas (sparklines, strip plots).

## Motion

- Reuse `animate-fade-in-up` + `stagger-1..5` for above-the-fold entrances; `composables/useScrollReveal.js` for below-the-fold. `AnimatedNumber.vue` for count-ups.
- All motion is reduced-motion-safe via the global block in `breadfast.css`. **ECharts ignores that block** — chart options must set `animation: !prefersReducedMotion()` (`src/utils/motion.js`).
- The `:active` press feedback (`active:scale-[0.98]`) and the pill CTA live in `src/components/shared/PillButton.vue`.

## Copy

- **No em-dashes** (`—`/`–`) in visible strings; use periods, commas, parentheses, or a hyphen for ranges. (The `—` null-cell placeholder in data tables is an allowed data indicator, not prose.)
- Active voice; a control says what it does. No fake-precise invented numbers; mark sample data as illustrative.

## Reference components (copy these, don't reinvent)

`KpiCard`, `EmptyState`, `PILegend`, `AnimatedNumber`, `FilterBar`, `ActionBadge`, `PillButton`, `PIMeter`, `PageShell`.

## Quick pre-ship grep gates

```sh
cd frontend/src
grep -rn "shadow-card\b" . --include=*.vue | grep -v shimmer   # → only token def
grep -rn "border-l-2\|bg-blue-\|bg-indigo-\|bg-teal-" . --include=*.vue   # → only PI-semantic uses
grep -rn "<svg" components --include=*.vue   # → only brand logos / data-viz
grep -rn "toFixed(4)" . --include=*.vue   # → none (PI is 2dp)
```
