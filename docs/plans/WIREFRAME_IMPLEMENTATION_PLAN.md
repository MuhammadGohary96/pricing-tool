# Implement Wireframe Designs — Keep Breadfast Magenta Palette

## Context
The `pricing-intelligence-wireframes/` folder contains 7 HTML wireframes defining the target UI design. The wireframes use a purple (#7C3AED) palette, but the user explicitly requires keeping the Breadfast magenta palette (#AB0184). This plan maps wireframe design patterns to the existing Vue app, substituting purple→magenta while implementing structural/layout changes from the wireframes.

**Key principle**: Keep the magenta brand colors (#AB0184 primary, #7A015E dark, #4A0038 darkest, #D4A1C7 light, #F3E4EF lightest). Use semantic colors (green/red/yellow) for PI data visualization as the wireframes do.

**Previous work already done** (from earlier session): Inter font, animation system (fadeInUp, shimmer, count-up, scroll reveal, page transitions, skeleton loaders, card-interactive hover), Toast bottom-right position. These are already in place and will be preserved.

---

## Phase 1: Dark Navigation Bar (1 file)

Wireframe shows a dark `--darkest` (#4A0038) top nav with logo SVG, pill-shaped tabs, avatar circle, and "Data synced" badge.

**File**: `frontend/src/components/layout/AppHeader.vue`

Changes:
- Replace white `bg-white border-b` header → dark `bg-brand-darkest` (56px height, sticky)
- Logo: Replace "B" box with inline SVG icon (cross/plus in rounded rect) + "Pricing Intelligence" text in white
- Tabs: Change from bottom-border indicator → rounded-pill style. Active = `bg-brand-primary text-white rounded-lg px-4 py-2`. Inactive = `text-white/65 hover:text-white hover:bg-white/10`
- Right side: Avatar circle with `bg-brand-primary`, user initials. Add "Data synced" badge with green dot (use store's last-fetched time if available, otherwise static placeholder)
- Remove subtitle "Product Tiering & Price Index"
- Logout button: restyle to white/translucent icon

---

## Phase 2: KPI Card Enhancement (2 files)

Wireframe shows: top 3px accent border on hover, `kpi-highlight` variant (left border), trend badges with colored backgrounds.

**File**: `frontend/src/components/layout/KpiCard.vue`

Changes:
- Add `::before` pseudo-element for top 3px primary accent bar, `opacity:0 → 1` on hover (via CSS)
- Add `highlight` boolean prop: when true, add 3px left border in `brand-primary`
- Add `trend` prop `{ value: number, direction: 'up'|'down' }`: render inline badge with ▲/▼, colored background (green for up, red for down)
- Add `subtitle` prop for secondary text line below value (e.g. "Across 7 categories")

**File**: `frontend/src/views/CommercialView.vue`

Changes:
- Pass `highlight` to "Blended PI" KpiCard
- Pass trend data (if available from store) to KpiCards that show trends
- Add subtitle text to KpiCards matching wireframe (e.g. "Across 7 categories", "Top 80% revenue")

---

## Phase 3: Coverage Funnel Redesign (1 file)

Wireframe shows: progressive-width bars (not equal-width), count INSIDE bars, labels and % BELOW bars, arrow separators between stages.

**File**: `frontend/src/components/commercial/CoverageFunnel.vue`

Changes:
- Replace equal-width `flex-1` columns → progressive-width using percentage or proportional widths based on count
- Each stage: colored bar (48px height, rounded-lg) with count INSIDE (white text, bold)
- Labels and percentages moved BELOW the bar
- Arrow separators (→) between stages
- First stage (All Products) gets max width; each subsequent stage gets proportionally smaller
- Keep celebration pulse on 100% stages
- Color gradient: darkest → dark → primary → light → lightest (brand palette)

---

## Phase 4: Treemap Semantic Coloring (1 file)

Wireframe uses green/yellow/red semantic colors based on PI value (green = BF cheaper, red = BF more expensive) instead of brand gradient.

**File**: `frontend/src/components/commercial/SubcategoryTreemap.vue`

Changes to `piToColor()`:
- PI >= 1.15 → `#059669` (deep green — very competitive)
- PI >= 1.10 → `#34D399` (green)
- PI >= 1.05 → `#BBF7D0` (light green)
- PI >= 1.00 → `#FEF9C3` (yellow/neutral — near parity)
- PI >= 0.95 → `#FECACA` (light red)
- PI >= 0.90 → `#FCA5A5` (red)
- PI < 0.90 → `#F87171` (strong red — BF expensive)
- Null → `#E5E7EB` (grey)

Update emphasis (hover) style to use brand shadow instead of a specific color.

---

## Phase 5: Action Summary Redesign (1 file)

Wireframe shows: icon circles with colored backgrounds, click-to-select with border state, horizontal layout (icon-left + data-right).

**File**: `frontend/src/components/master-data/ActionSummary.vue`

Changes:
- Add `selectedAction` state with `emit('select', actionType)` for click-to-filter
- Each card: flex row with 44px icon circle (colored background + icon) + data column (value + label)
- Selected state: `border-2 border-brand-primary bg-brand-50`
- Default state: `border-2 border-transparent`
- Icon circles: Total = danger bg/icon (⚠), Mapping = red bg (⊘), AI Review = warning bg (⚡), Update = blue bg (⟳)
- Card becomes clickable with cursor-pointer and hover border effect

**File**: `frontend/src/views/MasterDataView.vue`

Changes:
- Wire ActionSummary `@select` to filter by action type via `filters.setFilter('actionType', ...)`

---

## Phase 6: AI Match Panel Redesign (1 file)

Wireframe shows: full cards with product-pair boxes side-by-side, similarity badge, gradient score bar, prominent Accept/Reject buttons.

**File**: `frontend/src/components/master-data/AIMatchPanel.vue`

Changes:
- Replace compact rows → card-based layout:
  - Card wrapper: `border border-grey-200 rounded-lg p-3.5 hover:border-brand-light hover:shadow-card`
  - Header row: `#N · Category` label + similarity badge (`high` green / `mid` amber / `low` red)
  - Product pair: two boxes side-by-side (BF product left, Talabat right) with `↔` arrow between
  - Each box: `bg-grey-50 rounded-md p-2.5` with LABEL (tiny uppercase), NAME, PRICE
  - Score bar: `h-1 bg-grey-200 rounded-full` with filled portion using `bg-gradient-to-r from-brand-primary to-green-400`
  - Buttons: `flex gap-2`, Accept = `bg-green-600 text-white rounded-md py-1.5 font-semibold`, Reject = `bg-grey-100 text-grey-600 border rounded-md py-1.5`
- Add scroll container with `max-height: 420px, overflow-y: auto`
- Increase card padding and spacing vs. current compact list

---

## Phase 7: Executive Dashboard Overhaul (3 files)

### 7A: PI Gauge Ring — `frontend/src/components/executive/PIGauge.vue`

Wireframe shows a large conic-gradient ring (220px diameter) with PI value centered.

Changes:
- Replace plain text card → gauge card with `rounded-xl shadow-card-hover py-12 text-center`
- Add conic-gradient ring: 220x220px circle. Fill angle = `min(PI / 1.3, 1) * 360deg`. Green gradient for PI>1, red for PI<1
- Inner circle (180x180px, white bg) with large PI value (52px font, bold) + "Blended PI" label
- Interpretation text below: "Breadfast is X% cheaper overall" in success color
- Trend line: "vs. last week: ▲ X% improvement" in muted text

### 7B: Mini KPI Cards — `frontend/src/components/executive/MiniKpiCards.vue`

Wireframe shows icon circles with colored backgrounds + larger value text.

Changes:
- Each card: horizontal layout with 48px icon circle (SVG icon + colored bg) + data column
- Coverage: `bg-brand-lightest` icon circle, value colored by threshold (warning if <60%, success if >80%)
- Products Used: `bg-green-50` icon circle with checkmark SVG, show "↑ N from last week" sub-text
- Actions Remaining: `bg-red-50` icon circle with alert SVG, value in danger color, breakdown sub-text ("312 mapping · 87 AI review · 1,039 update")
- Larger card padding (24px), rounded-xl, larger value text (28px)

### 7C: Top/Bottom Subcategories — `frontend/src/components/executive/TopBottomSubcats.vue`

Wireframe shows two separate rank cards with numbered circles.

Changes:
- Split into two distinct cards side-by-side (currently one card with two halves)
- "Where We're Cheapest" card: green dot header, numbered rank circles with `bg-green-50 text-green-600`
- "Where We're Most Expensive" card: red dot header, numbered rank circles with `bg-red-50 text-red-600`
- Each rank item: flex row with rank circle + name + pi value + delta (direction arrow)
- Hover state: `bg-brand-50` on row
- Show WoW delta with ▲/▼ colored appropriately

---

## Phase 8: Table & Pagination Polish (2 files)

### 8A: Product Detail Table — `frontend/src/components/commercial/ProductDetailTable.vue`

Wireframe features not yet in current code:
- **Overpriced row highlighting**: rows where PI < 0.90 get `bg-red-50` background
- **Days staleness column**: show age with color coding (fresh=green ≤7d, stale=amber ≤30d, old=red >30d)
- **Pagination upgrade**: "Showing 1-50 of 4,392 products" text + numbered page buttons (1, 2, 3, ..., N) + Prev/Next
- **Sort icons**: Show ↕ for unsorted columns, ↑/↓ for active sort (matching wireframe)

### 8B: Blended PI Table — `frontend/src/components/commercial/BlendedPITable.vue`

Minor polish:
- Add `tr:hover td { background: brand-50 }` (already partially done)
- Sort icons: match wireframe ↕ → ↑/↓ pattern

---

## Phase 9: Card Headers & Filter Polish (3 files)

### 9A: Card Header Badges

Wireframe shows `card-badge` elements (small rounded pills with lightest bg) providing context like "Size = Revenue · Color = PI" on the treemap card.

**Files**: `SubcategoryTreemap.vue`, `BlendedPITable.vue`, `ActionBreakdown.vue`, `StalenessHeatmap.vue`

Changes:
- Add badge span to each card header: `<span class="text-micro px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary font-medium">context text</span>`
- Treemap: "Size = Revenue · Color = PI"
- PI Table: "Sorted by PI ▲"
- Action Breakdown: "Click a category to filter"
- Staleness: "Darker = more stale products"

### 9B: Filter Dropdown Active State — `frontend/src/components/layout/FilterBar.vue`

Wireframe shows active filter dropdowns with primary border + lightest background.

Changes:
- When a filter has a non-default value, add dynamic class: `border-brand-primary bg-brand-50`
- Currently the select only changes value; add conditional class binding based on `filters.mainCategory`, etc.

---

## Full File Manifest (~15 files modified, 0 new files)

| Phase | Files |
|-------|-------|
| 1 | `AppHeader.vue` |
| 2 | `KpiCard.vue`, `CommercialView.vue` |
| 3 | `CoverageFunnel.vue` |
| 4 | `SubcategoryTreemap.vue` |
| 5 | `ActionSummary.vue`, `MasterDataView.vue` |
| 6 | `AIMatchPanel.vue` |
| 7 | `PIGauge.vue`, `MiniKpiCards.vue`, `TopBottomSubcats.vue` |
| 8 | `ProductDetailTable.vue`, `BlendedPITable.vue` |
| 9 | `SubcategoryTreemap.vue`, `BlendedPITable.vue`, `ActionBreakdown.vue`, `StalenessHeatmap.vue`, `FilterBar.vue` |

## Verification
1. `cd frontend && npm run dev` — app runs without errors
2. Visual check: **Magenta palette preserved**, not purple
3. Dark nav bar with pill tabs, avatar, sync badge
4. KPI cards: top accent hover, highlight on PI card, trend badges
5. Coverage funnel: progressive-width bars, count inside, labels below
6. Treemap: green/yellow/red semantic coloring for PI
7. Action Summary: icon circles, click-to-select-and-filter
8. AI Match: card-based with product pairs, similarity badges
9. Executive: gauge ring, icon KPIs, separate rank cards
10. Tables: overpriced row highlight, numbered pagination, sort icons
11. Card headers with context badges
12. Filter dropdowns with active state styling
13. `npm run build` — production build succeeds
