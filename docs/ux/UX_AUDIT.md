# Breadfast Pricing Tool — UI/UX Audit & Improvement Plan

---

## 1. Prioritized UX Audit

### CRITICAL (Blocks core workflows / causes data loss)

| # | Issue | Why It Matters |
|---|-------|---------------|
| C1 | **Match Review Accept/Reject is non-functional** | Users click Accept/Reject thinking they're saving decisions — but it's purely local state. Every page refresh loses all work. The entire Match Review workflow is broken. |
| C2 | **Client-side sort on server-paginated data** | When a user sorts by Revenue or PI, they think they're seeing the top items globally — but they're only reordering the current 50-item page. A product ranked #1 on page 3 won't appear when sorting desc on page 1. This leads to **wrong business decisions**. |
| C3 | **Search is page-scoped but appears global** | The search bar in ProductDetailTable and PriorityWorklist looks like a global search but only filters the current page's 50 items. Users searching for a specific product will conclude it doesn't exist when it's simply on another page. |
| C4 | **No confirmation before bulk price edits** | ConfirmModal exists but isn't used. A user can select 30 products and overwrite all their prices with one click — no "Are you sure?" step. Partial failures during sequential save leave data in an inconsistent state with no per-row error feedback or rollback. |
| C5 | **No filter debounce** | Every filter selection immediately fires API calls. Selecting 3 filters in quick succession triggers 3 full data re-fetches. This can cause race conditions where an earlier response arrives after a later one, showing stale data for the wrong filter combination. |

### HIGH (Significantly degrades daily productivity)

| # | Issue | Why It Matters |
|---|-------|---------------|
| H1 | **Commercial View is extremely long** | 5-6 stacked sections require heavy scrolling. The treemap and funnels — which provide critical context — sit below the fold on all but 27"+ monitors. Analysts waste time scrolling between the PI table and product table constantly. |
| H2 | **Scroll-within-scroll on tables** | BlendedPITable (280px max-height) and ProductDetailTable (520px max-height) create internal scroll contexts inside the page scroll. Users frequently lose their scroll position, and trackpad gestures get captured by the wrong scroll container. |
| H3 | **No cross-view navigation** | Executive sees "Dairy is most expensive" but cannot click to jump to Commercial view pre-filtered to Dairy. Master Data shows a product needs mapping but cannot link to it in the Commercial detail table. Each view is an island. |
| H4 | **Executive View is underpowered** | PI gauge is binary (all green or all red) — a PI of 0.999 looks identical to 0.70. No trend data available (no historical snapshots stored). Leadership gets a snapshot with no drill-down capability. |
| H5 | **12-column ProductDetailTable density** | At 13px body text with 12 columns, the table is overwhelming. Users can't scan rows quickly. No column hiding, pinning, or responsive strategy. Horizontal scroll is almost guaranteed, losing product name context. |
| H6 | **Inconsistent PI color thresholds** | PIInlineBar uses 0.95/1.05, treemap uses 7-stop scale (0.85–1.15), ProductDetailTable row highlight triggers at 0.90, PIGauge is binary at 1.0. The same PI value appears as different colors in different components, undermining trust. |
| H7 | **MultiSelect "Apply" pattern confusion** | Users check items and expect immediate filtering (like every other dropdown they've used). The staged Apply pattern is good for preventing API hammering but creates a perceived "nothing happened" moment. Clicking outside discards changes silently. |

### MEDIUM (Friction points that slow users down)

| # | Issue | Why It Matters |
|---|-------|---------------|
| M1 | **No saved filter presets** | Commercial analysts check the same 3-4 filter combinations daily (e.g., "Dairy + Top Tier + Needs Action"). They re-select these filters every session. |
| M2 | **Brand filter not in URL sync** | useUrlSync maps 5 of 6 filters — `brand` and `includePrivateLabel` are missing. Brand-filtered views can't be shared via URL or bookmarked. |
| M3 | **No global product search** | To find a specific product, users must know which view it's in, navigate there, set filters, and use the page-scoped search. There's no Cmd+K style global finder. |
| M4 | **Two concurrent paginations in Master Data** | Worklist pagination and MatchReview pagination sit visually close with identical styling. Users confuse which "Next" button controls which section. |
| M5 | **Treemap labels at 9px** | Small revenue subcategories have unreadable or invisible labels. The only way to identify them is hovering for tooltip — which doesn't work on touch or keyboard. |
| M6 | **No loading indicator for lazy route chunks** | First visit to a new tab shows a blank/frozen page while the JS chunk downloads. No skeleton or spinner during chunk load. |
| M7 | **Header overflow on narrow screens** | While this is a desktop-focused tool, laptop screens (13" MacBook) can clip the header when all 3 tabs + sync badge + avatar + logout are on one line. |
| M8 | **PageShell skeleton mismatches content** | The loading skeleton is hardcoded to approximate Commercial view layout. On Master Data or Executive, the skeleton shape doesn't match, creating a visible layout jump on load. |

### LOW (Polish items / edge cases)

| # | Issue | Why It Matters |
|---|-------|---------------|
| L1 | **No 404 route** | Unknown URLs show blank content. Minor since this is internal, but confusing for shared broken links. |
| L2 | **HelpTooltip is hover-only** | Keyboard and touch users can't access tooltip content. Low impact since the Definitions Panel covers the same information. |
| L3 | **Toast max-width truncates long names** | Product names in success toasts may clip. Cosmetic issue. |
| L4 | **Logout button has no text label** | Icon-only with title attribute. Minor since the icon is recognizable and all users are Google-authenticated. |
| L5 | **ChartSkeleton component is unused** | Dead code — exists but never rendered. Cleanup item. |
| L6 | **ActionBadge uses inline styles instead of Tailwind** | Color tokens are raw hex values, not from the design system. Maintenance issue, not user-facing. |

---

## 2. Improvement Plan

### C1: Wire Up Match Review Accept/Reject API

**What's wrong:** Accept/Reject buttons update a local `Set` and show a toast, but make no backend call. All decisions vanish on page refresh.

**Solution:**
- Add `POST /api/master-data/match-reviews/{product_id}/accept` and `POST /api/master-data/match-reviews/{product_id}/reject` endpoints
- In `MatchReviewPanel`, replace local `dismissed.add()` with an API call + optimistic UI update
- On success, decrement the `matchReviewsTotal` count and remove the card from the list (don't just fade it)
- Add an "Undo" action button in the toast (same pattern as price edit undo)
- Add error handling: if API fails, show error toast and restore the card

**Effort:** M | **Impact:** Unlocks the entire match review workflow — currently non-functional

---

### C2: Server-Side Sort + Search

**What's wrong:** Sort and search operate client-side on the current 50-item page, giving misleading results.

**Solution:**
- Add `sort_by` and `sort_dir` query params to `/commercial/products` and `/master-data/worklist` endpoints
- Add `search` query param that does server-side `ILIKE` / pandas `.str.contains()` filtering
- Update stores to pass sort/search params to API calls and reset to page 1 on sort/search change
- Remove client-side sort logic from ProductDetailTable and PriorityWorklist
- Add a subtle label: "Sorted across all X products" to confirm global scope

**Effort:** L | **Impact:** Eliminates the most dangerous data integrity issue

---

### C3: Add Filter Debounce

**What's wrong:** Each filter change immediately triggers full API re-fetch. Rapid multi-filter selection causes race conditions.

**Solution:**
- Add a 400ms debounce to the filter `watch` in CommercialView and MasterDataView using `watchDebounced` from `@vueuse/core`
- Add an `AbortController` per fetch cycle — when a new fetch starts, abort the previous in-flight request
- Show a subtle "Updating..." indicator on the FilterBar during the debounce delay

**Effort:** S | **Impact:** Prevents race conditions and reduces unnecessary API load by ~60%

---

### C4: Add Confirmation Before Bulk Price Edits

**What's wrong:** Bulk editing overwrites prices for many products with no confirmation step.

**Solution:**
- Wrap the bulk edit submit handler with `ConfirmModal`
- Show: "Update prices for X products?" with list of affected product names
- Add per-row error indicators if individual saves fail
- Add `aria-modal="true"` and focus trap to ConfirmModal

**Effort:** S | **Impact:** Prevents accidental bulk price changes

---

### C5: Complete URL Sync

**What's wrong:** `brand` and `includePrivateLabel` filters are not synced to URL.

**Solution:**
- Add `brand` and `private_label` to the `useUrlSync` key map
- Serialize `includePrivateLabel` as `private_label=0` (excluded) or omit when included (default)

**Effort:** S | **Impact:** Enables sharing and bookmarking of any filter state

---

### H1 + H2: Commercial View Layout Restructuring

**What's wrong:** 5 stacked sections create an extremely long page. Tables have internal scroll that conflicts with page scroll.

**Proposed layout — side-by-side with tabs:**
```
┌─────────────────────────────────────────────────────┐
│ [Definitions ▾]  [FilterBar]                         │
│ [KPI Strip — 5 cards + Export]                       │
├──────────────────────┬──────────────────────────────┤
│                      │                              │
│  Blended PI Table    │  [Tab: Product Detail]       │
│  (left panel ~40%)   │  [Tab: Coverage Map]         │
│                      │                              │
│  Full height,        │  Selected tab content fills  │
│  no max-height cap   │  remaining viewport height   │
│                      │                              │
└──────────────────────┴──────────────────────────────┘
```

**Effort:** XL | **Impact:** Transforms the primary daily workflow

---

### H3: Cross-View Navigation

**What's wrong:** Views are disconnected islands.

**Solution:**
- Executive → Commercial: Make TopBottomSubcats items clickable → navigate with filter
- Executive → Master Data: Make "Actions Remaining" KPI card clickable
- Master Data → Commercial: Add "View in Commercial" icon on worklist rows
- Commercial Treemap → Master Data: Badge on cells with high "Needs Action" count

**Effort:** M | **Impact:** Creates connected analytical flow

---

### H4: Executive View Enhancement

> **Constraint: No historical data exists for trend lines.** PITrendLine and CoverageTrendLine components cannot be used until a data snapshot pipeline is built.

**Solution (without trends):**
- **Multi-zone PI Gauge:** Replace binary green/red with 5-zone arc (deep green → yellow → deep red) with needle indicator. Show target zone (0.95–1.05) as highlighted band.
- **Add data freshness timestamp:** "Data as of: Mar 1, 2026 08:30"
- **Make all items clickable** for drill-down to Commercial/Master Data views
- **Add "Actions by urgency" mini-table** — replaces trend data with actionable items: top 5 products with highest revenue that need action
- **Future:** Build daily snapshot pipeline (cron job saving PI/coverage to a `pi_snapshots` table) to enable trends

**Effort:** L | **Impact:** Adds drill-down and better gauge visualization

---

### H5: ProductDetailTable Column Management

**Solution:**
- Pin first column (Product name) with `sticky left-0`
- Default 6 visible columns: Product, Brand, BF Price, Talabat Price, PI, Action
- Column toggle button with checkbox dropdown
- Persist column selection in localStorage

**Effort:** M | **Impact:** Reduces visual overwhelm dramatically

---

### H6: Standardize PI Color Thresholds

**Solution:**
- Create shared `piColor.js` utility with single threshold system (0.95 / 1.05)
- Use across all components: PIInlineBar, PIStripPlot, ProductDetailTable, SubcategoryTreemap, PIGauge

**Effort:** S | **Impact:** Consistent color language across entire app

---

### H7: Improve MultiSelect UX

**Solution:**
- Switch to auto-apply with 500ms debounce — remove Apply button
- As users check/uncheck, apply after inactivity pause
- Add "Updating..." shimmer on FilterBar during debounce
- Click-outside auto-applies (not discards)

**Effort:** M | **Impact:** Eliminates filter confusion

---

## 3. Quick Wins (Ship This Week)

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| QW1 | Add ConfirmModal to bulk price edit | 30 min | Prevents accidental mass price changes |
| QW2 | Add filter debounce (400ms `watchDebounced`) | 1 hr | Eliminates race conditions |
| QW3 | Standardize PI colors — extract shared `piColor.js` util | 2 hr | Consistent color language |
| QW4 | Complete URL sync — add `brand` + `includePrivateLabel` | 1 hr | Enables sharing filtered views |
| QW5 | Add 404 catch-all route → redirect to `/commercial` | 15 min | Prevents blank page on bad URLs |
| QW6 | Add "Updating..." indicator to FilterBar during data fetch | 30 min | Users know their filter is working |
| QW7 | Distinct visual styling for MatchReview pagination | 30 min | Eliminates pagination confusion |
| QW8 | Add data freshness timestamp to Executive View | 30 min | Executives know if data is stale |
| QW9 | Make TopBottomSubcats clickable → navigate to Commercial | 1 hr | First cross-view drill-down |
| QW10 | Remove unused ChartSkeleton component | 15 min | Code cleanup |

**Total quick wins: ~8 hours of work for significant UX improvement.**

---

## 4. Visual/Layout Recommendations

### Commercial View — Proposed Layout

**Current:** 5 vertically stacked full-width sections (heavy scrolling)

**Proposed:** 3-zone layout that fills the viewport
```
┌───────────────────────────────────────────────────────────┐
│ [Definitions ▾]  [FilterBar: Cat | Subcat | Tier | ...]   │
│ [KPI: Total | Eligible | Used | Actions | PI]   [Export]  │
├─────────────────────────┬─────────────────────────────────┤
│                         │                                 │
│  BLENDED PI TABLE       │  ┌─[Products]─[Coverage Map]─┐ │
│  (left panel, ~40%)     │  │                            │ │
│                         │  │  Product Detail Table      │ │
│  • Full height          │  │  (or Treemap + Funnels)    │ │
│  • Click row to filter  │  │                            │ │
│  • Sticky header        │  │  Full height, uses panel   │ │
│  • No max-height cap    │  │  scroll                    │ │
│                         │  │                            │ │
│                         │  └────────────────────────────┘ │
└─────────────────────────┴─────────────────────────────────┘
```

### Master Data View — Proposed Layout

**Current:** 6 vertically stacked sections

**Proposed:** Summary strip + primary worklist + side panel
```
┌───────────────────────────────────────────────────────────┐
│ [Definitions ▾]  [FilterBar]                              │
│ [ActionSummary: 4 KPI cards]  [ActionBreakdown mini-bar]  │
├───────────────────────────────────────┬───────────────────┤
│                                       │                   │
│  PRIORITY WORKLIST                    │  Side Panel:      │
│  (main area, ~65%)                    │  (right, ~35%)    │
│                                       │                   │
│  • Full height table                  │  [Tab: Match      │
│  • Server-side search + sort          │   Review]         │
│  • Pagination                         │  [Tab: Staleness  │
│                                       │   Heatmap]        │
│                                       │                   │
└───────────────────────────────────────┴───────────────────┘
```

### Executive View — Proposed Layout
```
┌───────────────────────────────────────────────────────────┐
│ [Definitions ▾]                   [Export]  [As of: date]  │
├──────────────┬────────────────────────────────────────────┤
│              │  Coverage ██████████ 84%     Used: 1,234   │
│  PI GAUGE    │  Actions Remaining: 156  [View →]          │
│  (multi-zone)│  Top 5 Revenue Items Needing Action        │
│              │  (actionable list replacing trends)        │
├──────────────┴────────────────────────────────────────────┤
│  Top 5 Cheapest (clickable)  │  Top 5 Expensive (click.) │
├──────────────────────────────┴───────────────────────────┤
│  Category Performance (horizontal bars, full width)       │
└───────────────────────────────────────────────────────────┘
```

---

## 5. Interaction Pattern Improvements

### Filter System
- Replace staged Apply with auto-apply + 500ms debounce
- Add filter presets: "Save current filters" → named presets in localStorage
- Subcategory dependency: show grouped subcategories with category section headers when no category selected

### Inline Price Editing
- Tab-to-next-row: after save, Tab moves to same column in next row (spreadsheet behavior)
- Batch edit confirmation: summary dialog with affected product names + "Download backup CSV" link
- Visual diff on save: old price struck through next to new price for 5 seconds

### Match Review Workflow
- Card-level loading spinner on Accept/Reject click
- Animate card out (slide left=reject, slide right=accept) instead of just fading
- Bulk accept for high-confidence: "Accept all ≥90%" button with count
- Progress indicator: "12 of 47 reviewed this session"

### Cross-View Navigation
- Breadcrumb state: "← Back to Executive" when navigating from Executive → Commercial
- Deep linking: every interactive element that sets a filter updates the URL

---

## 6. Missing Features (Priority-Ranked)

### Must-Have

1. **Saved filter presets** (M) — Name + save + recall from dropdown. Store in localStorage.
2. **Keyboard shortcuts** (S) — `F` focus filter, `/` focus search, `Esc` clear, `E` export, `1/2/3` switch tabs. Show `?` help modal.
3. **Data freshness indicators** (S) — Each view shows "Data as of" timestamp. Executive view especially needs this prominently.
4. **Audit log for price changes** (L) — Who, when, old value, new value. "History" icon on edited products.
5. **Server-side CSV export** (M) — Backend generates full dataset CSV, not just current page.

### Nice-to-Have

6. **Onboarding tour** (M) — First-login guided tour using `driver.js` or similar.
7. **PI snapshot pipeline** (L) — Daily cron saving PI/coverage to enable trend charts in Executive view. *Required before trend components can be rendered.*
8. **Favorites / watchlist** (M) — Star products or subcategories, filter to "Watching" only.
9. **Print / PDF report** (M) — Executive view as one-page PDF for weekly meetings.

---

## 7. Implementation Order

| Phase | Items | Timeline | Theme |
|-------|-------|----------|-------|
| **Week 1** | QW1–QW10 (quick wins) | 1-2 days | Safety, consistency, polish |
| **Week 2** | C1 (Match Review API), C3 (debounce), H6 (PI colors), H7 (MultiSelect) | 3-4 days | Fix broken workflows |
| **Week 3** | C2 (server-side sort/search), H5 (column management) | 3-4 days | Data integrity |
| **Week 4** | H1+H2 (Commercial layout restructure) | 4-5 days | Layout transformation |
| **Week 5** | H3 (cross-view nav), H4 (Executive enhancement) | 3-4 days | Connected experience |
| **Ongoing** | Missing features (presets, shortcuts, audit log) | Incremental | Power-user productivity |
| **Future** | PI snapshot pipeline → trend lines in Executive | TBD | Historical data dependency |

---

*Note: Trend line components (PITrendLine, CoverageTrendLine) exist in the codebase but cannot be used — no historical data snapshots are currently stored. A data pipeline must be built before trends can be displayed.*
