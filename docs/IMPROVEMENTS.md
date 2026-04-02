# Breadfast Pricing Intelligence Tool — Opportunities for Improvement

*Cross-functional review by Business Analysis + UI/UX Design — April 2026*

---

## Summary Matrix

| Phase | Items | Timeline | Theme |
|-------|-------|----------|-------|
| **Phase 1 — Quick Wins** | 10 items | 1 week | Polish, accessibility, feedback |
| **Phase 2 — Medium Effort** | 11 items | 1–4 weeks | Workflows, navigation, scalability |
| **Phase 3 — Strategic** | 6 items | 1–3 months | Alerting, history, mobile, bulk ops |

---

## Phase 1 — Quick Wins (< 1 week each)

### 1.1 Add colorblind-safe PI indicators
- **Problem:** PI values rely solely on red/green/yellow text color. ~8% of male users have red-green color blindness.
- **Impact:** High — colorblind users can't distinguish competitive vs overpriced.
- **Suggestion:** Prepend arrows to PI values (▲ 1.05 vs ▼ 0.89). Extend `piTextClass` utility to return an icon alongside color.
- **Files:** `frontend/src/utils/piColor.js`, all components calling `piTextClass()`
- **Effort:** ~2 hours

### 1.2 Add undo toast for Match Review accept/reject
- **Problem:** Accepting/rejecting AI matches is immediate and irreversible. One misclick permanently changes data quality.
- **Impact:** High — master data team; prevents accidental rejections of good matches.
- **Suggestion:** Replace instant action with a 5-second undo toast: "Match accepted — Undo". Only commit after timeout.
- **Files:** `frontend/src/components/master-data/MatchReviewPanel.vue`
- **Effort:** ~4 hours

### 1.3 Persist competitor preference in localStorage
- **Problem:** BlendedPITable and ClassificationBreakdown hard-default to Talabat every session. Users tracking other competitors re-select daily.
- **Impact:** Medium — pricing analysts; eliminates daily friction.
- **Suggestion:** Save `selectedCompetitor` to `localStorage` keyed by view name. Read on mount, fall back to Talabat.
- **Files:** `BlendedPITable.vue` (line 174), `ClassificationBreakdown.vue` (line 86)
- **Effort:** ~1 hour

### 1.4 Unify PI color thresholds into single source
- **Problem:** Executive, Commercial, and Master Data views may use subtly different PI color logic. Hard to verify consistency.
- **Impact:** Medium — all users; reduces cognitive load.
- **Suggestion:** Audit all PI color usage. Ensure every component imports from `utils/piColor.js` with identical thresholds.
- **Files:** `piColor.js` + grep for any inline PI color logic
- **Effort:** ~2 hours

### 1.5 Context-aware empty states
- **Problem:** EmptyState shows "No products found" with no guidance on which filter to relax.
- **Impact:** Medium — all users; reduces trial-and-error filtering.
- **Suggestion:** Pass active filter count to EmptyState. Show: "No results with 4 active filters — try clearing Tier or Brand."
- **Files:** `frontend/src/components/shared/EmptyState.vue`, calling views
- **Effort:** ~3 hours

### 1.6 Add "Copy shareable link" button
- **Problem:** Users screenshot and paste into Slack. No way to share a filtered view.
- **Impact:** Medium — all users; enables collaboration without context loss.
- **Suggestion:** Button in FilterBar that copies current URL (with query params) to clipboard + shows toast "Link copied".
- **Files:** `frontend/src/components/layout/FilterBar.vue`
- **Effort:** ~2 hours

### 1.7 Inline success indicator on edited rows
- **Problem:** Price edit confirmation appears as a toast in the bottom-right corner that auto-dismisses. Users may miss it.
- **Impact:** Medium — pricing analysts; confirms action completed.
- **Suggestion:** Flash the edited cell green for 2 seconds after save, in addition to the toast.
- **Files:** `frontend/src/components/commercial/ProductPivotTable.vue` (saveEdit function)
- **Effort:** ~2 hours

### 1.8 Revenue tooltip with full number
- **Problem:** `formatRevenue` shows "1.2M" — useful for scanning but loses precision for close comparisons.
- **Impact:** Low — category managers.
- **Suggestion:** Add `title` attribute with full formatted number (e.g., "1,234,567 EGP").
- **Files:** `BlendedPITable.vue` (line 115), `ProductPivotTable.vue` (line 161)
- **Effort:** ~30 minutes

### 1.9 Highlight sorted column header
- **Problem:** Active sort column uses a 10px arrow that's easy to miss on wide tables.
- **Impact:** Low — all table users.
- **Suggestion:** Add `border-b-2 border-brand-primary` to the active sort `<th>`.
- **Files:** All table components with sort headers
- **Effort:** ~1 hour

### 1.10 Cache filter options in sessionStorage
- **Problem:** Filter options (categories, tiers, competitors) are re-fetched on every page load but rarely change.
- **Impact:** Low — all users; faster initial render.
- **Suggestion:** Cache in `sessionStorage` with 15-minute TTL. Invalidate on manual reload.
- **Files:** `frontend/src/stores/filters.js` (fetchFilterOptions)
- **Effort:** ~2 hours

---

## Phase 2 — Medium Effort (1–4 weeks each)

### 2.1 Competitor group visual separation in ProductPivotTable
- **Problem:** With 10+ competitors (20+ columns), it's hard to tell which "Price | PI" pair belongs to which competitor after scrolling.
- **Impact:** High — commercial team; prevents misreading data.
- **Suggestion:** (a) Alternate background tint per competitor group (white / grey-50). (b) Show competitor name in tooltip when hovering any cell in that group.
- **Files:** `ProductPivotTable.vue` template (competitor columns section)
- **Effort:** ~3 days

### 2.2 Show worst-competitor context in frozen area
- **Problem:** The "find overpriced product and adjust price" workflow requires scrolling right to find the worst competitor, then scrolling back to edit BF Price — 6 steps of friction.
- **Impact:** High — pricing analysts; eliminates scroll-right-scroll-left cycle.
- **Suggestion:** Add a small "vs [CompetitorName]" label under the Worst PI cell showing which competitor drives it. Clicking jumps to that competitor's columns.
- **Files:** `ProductPivotTable.vue` (Worst PI td, ~line 153)
- **Effort:** ~2 days

### 2.3 Price edit safety rails
- **Problem:** No confirmation for large changes. "Saved locally" vs "Catalog synced" is confusing. No undo. No audit trail.
- **Impact:** High — pricing analysts; prevents accidental catalog changes.
- **Suggestion:** (a) Confirmation modal when change >10%. (b) Clear language: "Updated in BF system" vs "Saved locally only — no catalog access". (c) 5-second undo in toast. (d) Show "Last edited by X" on hover.
- **Files:** `ProductPivotTable.vue` (saveEdit, lines 298-318)
- **Effort:** ~1 week

### 2.4 Default to top-5 competitors + compact mode
- **Problem:** 15+ competitors renders 30+ columns, making the pivot table nearly unusable.
- **Impact:** High — commercial team; keeps tool usable at scale.
- **Suggestion:** (a) Show top 5 competitors by revenue overlap by default with "Show all N" toggle. (b) Add compact mode showing PI only (no Price column) to halve column count.
- **Files:** `CommercialView.vue`, `ProductPivotTable.vue`, backend competitor ranking
- **Effort:** ~1 week

### 2.5 Saved filter views / bookmarks
- **Problem:** Daily users re-apply the same filter combination every session.
- **Impact:** High — all daily users; eliminates repetitive setup.
- **Suggestion:** "Save current view" button stores filters + sort + view name in localStorage. Dropdown to load saved views. Include 2-3 presets: "All Categories", "Top Tier Only", "Needs Action".
- **Files:** New component + `FilterBar.vue` + `stores/filters.js`
- **Effort:** ~1 week

### 2.6 Cross-view drill-down links
- **Problem:** Views are siloed. Seeing a bad PI on Executive requires manually navigating to Commercial and re-applying filters.
- **Impact:** High — executives, category managers; reduces navigation friction.
- **Suggestion:** (a) Executive CompetitorPITable rows link to Commercial filtered by competitor. (b) Master Data worklist "View in Commercial" button made larger and labeled. (c) Executive Top Actions link to product in Commercial.
- **Files:** `CompetitorPITable.vue`, `PriorityWorklist.vue`, router
- **Effort:** ~3 days

### 2.7 Breadcrumb bar for drill-down context
- **Problem:** After clicking a subcategory row in BlendedPITable, nothing shows which subcategory is active or how to go back.
- **Impact:** High — pricing analysts; prevents analysis on wrong data subset.
- **Suggestion:** Breadcrumb strip below FilterBar: "All Subcategories > Cheese > x". Clicking "All" clears the drill-down.
- **Files:** New `DrilldownBreadcrumb.vue` + `CommercialView.vue`
- **Effort:** ~2 days

### 2.8 Keyboard-accessible MultiSelect (WAI-ARIA combobox)
- **Problem:** Custom MultiSelect dropdown requires mouse clicks. No arrow-key navigation or type-ahead.
- **Impact:** High — keyboard-only users, accessibility compliance.
- **Suggestion:** Implement WAI-ARIA combobox pattern: arrow keys navigate, Enter selects/deselects, typing filters options.
- **Files:** `frontend/src/components/shared/MultiSelect.vue`
- **Effort:** ~1 week

### 2.9 Export buttons on all tables
- **Problem:** Only ProductPivotTable has CSV export. BlendedPITable, executive tables, and worklist have no export.
- **Impact:** Medium — category managers; need offline data for meetings.
- **Suggestion:** Add `ExportButton` to BlendedPITable, CompetitorPITable, PriorityWorklist headers.
- **Files:** Each table component
- **Effort:** ~2 days

### 2.10 Improved strip plot for large datasets
- **Problem:** PIStripPlot dots overlap on subcategories with 100+ products. Click targets are tiny.
- **Impact:** Medium — pricing analysts; can't identify outlier products.
- **Suggestion:** (a) Jitter dots vertically to reduce overlap. (b) Enlarge click target with invisible padding. (c) Show product count badge on hover.
- **Files:** `frontend/src/components/shared/PIStripPlot.vue`
- **Effort:** ~3 days

### 2.11 Tablet-friendly responsive layout
- **Problem:** All tables use fixed widths. On 1024px tablet screens, content is cramped and headers overflow.
- **Impact:** Medium — users checking data on tablets.
- **Suggestion:** (a) Test and fix layout at 1024px breakpoint. (b) Collapse FilterBar to slide-out panel on smaller screens. (c) Stack KPI cards to 2x2 grid below 1200px.
- **Files:** FilterBar, PageShell, ExecutiveView layout
- **Effort:** ~1 week

---

## Phase 3 — Strategic (> 1 month each)

### 3.1 PI threshold alerting system
- **Problem:** Users must manually check dashboards to discover problems. A PI dropping from 1.05 to 0.85 overnight goes unnoticed.
- **Impact:** High — commercial team; enables proactive pricing response.
- **Suggestion:** (a) Backend: nightly job compares current vs previous PI. (b) Alert rules: "Notify when subcategory PI drops below X or changes by >Y%." (c) Delivery: email digest + in-app notification badge on Executive view.
- **Components:** New backend service, notification model, email integration, UI badge
- **Effort:** ~6 weeks

### 3.2 "What changed?" historical comparison view
- **Problem:** PI trend shows a line, but users can't drill into what products changed and which competitor drove it.
- **Impact:** High — category managers, executives; root-cause analysis for PI movement.
- **Suggestion:** New view or panel: "Changes since [date picker]" showing products where PI moved by >X%, with before/after values, responsible competitor, and revenue impact.
- **Components:** Backend: historical snapshot storage. Frontend: new comparison table + date range picker.
- **Effort:** ~8 weeks

### 3.3 Bulk price editing
- **Problem:** Adjusting 15 products in a subcategory requires 15 individual click-edit-save cycles.
- **Impact:** High — pricing analysts; 10x faster batch repricing.
- **Suggestion:** (a) Checkbox selection on product rows. (b) "Bulk adjust" toolbar: "Match lowest competitor", "Set to X", "Adjust by +/-Y%". (c) Preview changes before commit. (d) Audit log of bulk operations.
- **Components:** New BulkEditToolbar component, backend batch endpoint, confirmation modal
- **Effort:** ~6 weeks

### 3.4 Query-time BigQuery filtering (replace in-memory)
- **Problem:** Full dataset loaded into Pandas DataFrame on startup. As catalog grows (10K+ products x 15 competitors), this hits memory limits and slows cold starts.
- **Impact:** High — all users; prevents scaling bottleneck.
- **Suggestion:** (a) Move filtering to BigQuery query-time with parameterized SQL. (b) Keep in-memory cache for hot data (last 7 days). (c) Implement incremental refresh instead of full reload.
- **Components:** Rewrite `bigquery_service.py`, add query builder, caching layer
- **Effort:** ~8 weeks

### 3.5 Mobile "quick check" view
- **Problem:** Current UI is desktop-only. Mobile is unusable. Users wanting a quick PI check on their phone have no option.
- **Impact:** Medium — executives, category managers on-the-go.
- **Suggestion:** (a) Responsive card layout for KPIs at <768px. (b) Simplified table as scrollable cards. (c) Bottom tab navigation instead of header nav. (d) Consider PWA for home screen install.
- **Components:** Responsive redesign of ExecutiveView, new mobile table component
- **Effort:** ~10 weeks

### 3.6 In-app collaboration (comments + annotations)
- **Problem:** Analysts spot issues and discuss via Slack screenshots. Context is lost between tool and communication.
- **Impact:** Medium — team coordination.
- **Suggestion:** (a) Phase A: "Add note" on any subcategory or product, stored in backend, visible to all users. (b) Phase B: @mention teammates, notification on mention. (c) Phase C: Threaded comments with resolution status.
- **Components:** New comments model + API + UI panel
- **Effort:** ~12 weeks

---

## Implementation Plan

```
Week 1          Phase 1 — Quick Wins (all 10 items)
                |-- Day 1-2: Items 1.1, 1.2, 1.3, 1.4
                |-- Day 3-4: Items 1.5, 1.6, 1.7, 1.8
                |-- Day 5:   Items 1.9, 1.10 + QA pass

Weeks 2-3       Phase 2A — High Impact
                |-- 2.1  Competitor group visual separation
                |-- 2.2  Worst-competitor context in frozen area
                |-- 2.3  Price edit safety rails
                |-- 2.4  Top-5 competitors + compact mode

Weeks 4-5       Phase 2B — Navigation & Workflow
                |-- 2.5  Saved filter views
                |-- 2.6  Cross-view drill-down links
                |-- 2.7  Breadcrumb bar
                |-- 2.8  Keyboard-accessible MultiSelect

Weeks 6-7       Phase 2C — Polish
                |-- 2.9  Export buttons on all tables
                |-- 2.10 Improved strip plot
                |-- 2.11 Tablet-friendly layout

Weeks 8-13      Phase 3A — Alerting + History
                |-- 3.1  PI threshold alerting system
                |-- 3.2  "What changed?" comparison view

Weeks 14-19     Phase 3B — Scale + Bulk Ops
                |-- 3.3  Bulk price editing
                |-- 3.4  Query-time BigQuery filtering

Weeks 20+       Phase 3C — Mobile + Collaboration
                |-- 3.5  Mobile quick-check view
                |-- 3.6  In-app comments & annotations
```

---

## Measuring Success

| Metric | Baseline | Target | Measured By |
|--------|----------|--------|-------------|
| Time to identify overpriced product | ~3 min (scroll + filter) | < 30 sec | User observation |
| Price adjustments per session | ~5 (limited by click-edit-save) | 20+ (bulk edit) | Backend logs |
| Filter re-application per session | 3-4x (no saved views) | 0 (saved views) | Analytics |
| Data quality incidents (wrong match) | Unknown | -50% (undo + confirm) | Support tickets |
| Accessibility compliance | Partial | WCAG 2.1 AA | Automated audit |
| Mobile usability | 0% (unusable) | 80% task completion | User testing |

---

*Generated from codebase review at commit `c0cfb32` on `main` branch.*
