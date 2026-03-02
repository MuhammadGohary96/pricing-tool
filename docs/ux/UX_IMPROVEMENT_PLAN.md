# UX Improvement Plan — Pricing Intelligence Dashboard

## Assessment Summary

**Overall Score: 7.5/10** — Solid enterprise dashboard with good visual hierarchy, consistent patterns, and strong data visualization. Key gaps in accessibility, discoverability, and workflow completeness.

### Top Issues

| Priority | Issue | Impact |
|----------|-------|--------|
| HIGH | No data freshness indicator — analysts don't know how old the data is | Trust/decision risk |
| HIGH | No bulk edit — editing 50 products one-by-one is tedious | Productivity blocker |
| HIGH | No undo/rollback after price edits | Data integrity risk |
| MEDIUM | No product search in tables | Finding specific products requires scrolling |
| MEDIUM | No help/tooltip system — "Blended PI", "Coverage Rate" never explained | New user confusion |
| MEDIUM | Empty states are generic ("No data available") with no CTA or context | Dead-end UX |
| MEDIUM | Accessibility gaps — no aria-labels on charts, no skip-to-content, toast missing `role="alert"` | WCAG non-compliance |
| LOW | Sort indicators too small (10px), touch targets under 44px | Usability friction |
| LOW | No export on Master Data or Executive views | Workflow gap |

---

## App Context

**App:** Vue 3 + Tailwind CSS + ECharts pricing intelligence dashboard for Breadfast (Egyptian grocery delivery). Used by pricing analysts to compare Breadfast vs Talabat (competitor) prices across 3 views: Commercial, Master Data, Executive.

**Tech Stack:** Vue 3 Composition API (`<script setup>`), Pinia stores, vue-echarts, Tailwind CSS with custom design tokens (brand colors, typography scale in `tailwind.config.js`), system font stack.

**Current State:** Functional app with 21 components, 3 views, filter system, inline price editing, AI match accept/reject, export CSV. Build passes clean (705 modules, 0 errors). Brand theme aligned with breadfast.com (`#a3007c` primary).

**Note:** The app does NOT have historical data. There are no time-series or trend features.

---

## Phase 1: Quick Wins (Priority: HIGH, Effort: 1–2 days)

### 1.1 Data Freshness Indicator
- Add "Last synced: X mins ago" next to the green dot in `AppHeader.vue` (currently just says "Data synced")
- Pull timestamp from backend startup API or store a `lastFetchedAt` in each Pinia store
- Auto-refresh indicator every 60s

### 1.2 Product Search
- Add a text input above `ProductDetailTable` and `PriorityWorklist` for instant product name filtering
- Client-side filter on the already-loaded page data (debounce 300ms)
- Clear button (x) when search is active
- Design: match FilterBar styling — `bg-white rounded-lg border border-grey-200 px-3 py-1.5 text-body`

### 1.3 Improve Empty States
- Create a reusable `EmptyState.vue` component with props: `icon`, `title`, `message`, `actionLabel`, `@action`
- Replace all "No data available" / "No data" / "No match candidates" with contextual messages:
  - Charts: "No data for current filters. Try broadening your selection." + "Clear Filters" button
  - AIMatchPanel: "All matches reviewed! Check back after the next data sync."
  - Tables: "No products match the current filters."

### 1.4 Toast Accessibility
- Add `role="alert"` and `aria-live="assertive"` to the toast container in `Toast.vue`
- Ensure toasts are announced by screen readers

---

## Phase 2: Workflow Improvements (Priority: HIGH, Effort: 3–5 days)

### 2.1 Bulk Price Edit
- Add checkbox column to `ProductDetailTable.vue` (leftmost column)
- "Select All" checkbox in header
- When 1+ products selected, show floating action bar at bottom: "X selected — Bulk Edit Prices"
- Bulk edit modal: set new `now_price` and/or `now_sale_price` for all selected
- Use existing `store.updateProductPrice()` in a loop with progress indicator

### 2.2 Undo/Edit History
- Track last 10 price edits in a `editHistory` array in the commercial store
- Show "Undo" button in toast after successful edit (replaces auto-dismiss for 5s)
- On undo, call `store.updateProductPrice()` with previous values

### 2.3 Price Gap Column
- Add "Gap %" column to `ProductDetailTable` and `BlendedPITable`
- Formula: `((bf_sale_price - talabat_sale_price) / talabat_sale_price * 100).toFixed(1)`
- Color: green if BF is cheaper (negative gap), red if more expensive (positive gap)
- Show "—" if no competitor price

### 2.4 Export on All Views
- Add `ExportButton` to `PriorityWorklist` header (export worklist as CSV)
- Add `ExportButton` to Executive view (export summary metrics)

---

## Phase 3: Discoverability & Help (Priority: MEDIUM, Effort: 2–3 days)

### 3.1 Metric Help Tooltips
- Create a `HelpTooltip.vue` component: small `?` icon that shows popover on hover
- Add to card headers for: "Blended PI", "Coverage Rate", "Staleness", "Tier", "Eligible Products"
- Definitions:
  - **Blended PI** = Weighted price index comparing Breadfast vs competitor for eligible products
  - **Coverage Rate** = % of eligible products with matched competitor prices
  - **Staleness** = Days since last competitor price update
  - **Tier** = Revenue-based product ranking (Top+, Top, High, Mid, Low, Very Low)
  - **Eligible** = Products in top 80% of revenue

### 3.2 Active Filter Visibility
- When filters are active, show a persistent chip/badge bar below FilterBar:
  `"Filtered: Category = Dairy · Tier = Top+ · [Clear All]"`
- Visible on all views (since filters are global in Pinia store)

### 3.3 Treemap Click Affordance
- Add instruction text to SubcategoryTreemap header badge: "Click a region to filter products"
- When a subcategory is selected via treemap, show highlighted state: "Viewing: [Subcategory Name] × Clear"

---

## Phase 4: Accessibility (Priority: MEDIUM, Effort: 2–3 days)

Follow WCAG 2.1 AA compliance:

### 4.1 ARIA Labels
- Add `aria-label` to all chart containers describing key insight (e.g., `aria-label="Treemap showing subcategory revenue distribution colored by price index"`)
- Add `aria-sort="ascending|descending|none"` to sortable table headers
- Add `aria-label` to filter dropdowns (currently no `<label>` elements)

### 4.2 Focus Management
- Add `:focus-visible` ring styles to all interactive elements (buttons, table headers, cards)
- Add `tabindex="0"` to clickable ActionSummary cards
- Add skip-to-content link: `<a href="#main" class="sr-only focus:not-sr-only">Skip to content</a>`

### 4.3 Color Contrast
- Audit all text-on-background combinations for 4.5:1 minimum ratio
- Key fixes: sort indicator `text-grey-300` → `text-grey-400`, brand-primary on white needs verification
- Ensure PI color coding has text label supplement (not color-only information)

### 4.4 Touch Targets
- Increase minimum button size to 36×36px (desktop) / 44×44px (mobile)
- Pagination buttons, sort headers, and filter dropdowns should meet this minimum

---

## Phase 5: Polish (Priority: LOW, Effort: 1–2 days)

### 5.1 Chart Loading Skeletons
- Create `ChartSkeleton.vue` — gradient shimmer placeholder matching chart container height
- Use in PIGauge, SubcategoryTreemap, all ECharts components during data fetch

### 5.2 Inline Edit Feedback
- Show "Saving..." text with spinner icon during API call in ProductDetailTable
- Replace current opacity-50 approach with explicit loading state

### 5.3 Keyboard Shortcuts
- `Cmd/Ctrl + E` = Export CSV
- `Cmd/Ctrl + F` = Focus search input (when added)
- `Escape` = Clear active filters
- Document shortcuts in a `?` help modal accessible from header

---

## Design System Rules

- **Colors:** Brand `#a3007c`, semantic green `#059669` / red `#EF4444` / amber `#D97706` / blue `#2563EB`
- **Font sizes:** Use Tailwind config tokens only — `text-kpi` (28px), `text-heading` (18px), `text-subheading` (14px), `text-body` (13px), `text-caption` (12px), `text-micro` (11px). No arbitrary `text-[Npx]`.
- **Spacing:** `gap-4` between sections, `gap-3` for tight groups, `px-4 py-3` for card padding
- **Shadows:** `shadow-card` for cards, `shadow-card-hover` for interactive cards
- **Animations:** `animate-fade-in-up` with stagger delays (`0.06s` per item)
- **Font stack:** System fonts (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`)
- **No new dependencies** without discussion. Prefer native solutions over libraries.

---

## Verification After Each Phase

1. `npm run build` — 0 errors
2. Test at 1280px and 1440px viewport widths
3. Verify no horizontal page scroll
4. Test keyboard Tab navigation through all interactive elements
5. Check toast notifications appear and auto-dismiss correctly
