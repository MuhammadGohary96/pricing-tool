# UX Improvement — Implementation Plan

> Based on [UX_AUDIT.md](UX_AUDIT.md). Organized into phases with exact file changes, code approach, and dependencies.
>
> **Constraint:** No historical data exists for PI/coverage trends. Trend components cannot be used until a snapshot pipeline is built.

---

## Phase 1: Quick Wins (Day 1-2)

### 1.1 Add ConfirmModal to Bulk Price Edit
**Files:** `frontend/src/components/commercial/ProductDetailTable.vue`

- Import existing `ConfirmModal` component
- Wrap `submitBulkEdit()` — before the sequential save loop, show modal:
  - Title: `"Update ${selectedIds.length} products?"`
  - Message: `"Set Now Price to EGP ${bulkPrice} for all selected products."`
  - Confirm label: `"Update All"`
- On confirm → proceed with existing save loop
- Also add `aria-modal="true"` and `role="dialog"` to `ConfirmModal.vue`

---

### 1.2 Add Filter Debounce
**Files:** `frontend/src/views/CommercialView.vue`, `frontend/src/views/MasterDataView.vue`

- Replace `watch(() => filters.activeFilters, ...)` with `watchDebounced` from `@vueuse/core`:
  ```js
  import { watchDebounced } from '@vueuse/core'
  watchDebounced(() => filters.activeFilters, () => {
    store.fetchAll()
  }, { debounce: 400, deep: true })
  ```
- Add `AbortController` to stores — each `fetchAll()` call creates a new controller and aborts the previous
- No new dependencies needed (`@vueuse/core` already installed)

---

### 1.3 Standardize PI Color Thresholds
**Files (new):** `frontend/src/utils/piColor.js`
**Files (edit):** `PIInlineBar.vue`, `PIStripPlot.vue`, `ProductDetailTable.vue`, `SubcategoryTreemap.vue`, `PIGauge.vue`, `PriorityWorklist.vue`

Create shared utility:
```js
// Single source of truth for PI thresholds
export const PI_CHEAP = 0.95    // BF cheaper
export const PI_EXPENSIVE = 1.05 // BF more expensive

export function piTextClass(pi) {
  if (pi == null) return 'text-grey-400'
  if (pi >= PI_EXPENSIVE) return 'text-red-600'
  if (pi <= PI_CHEAP) return 'text-green-600'
  return 'text-amber-600'
}

export function piBgClass(pi) { /* same thresholds, bg- variants */ }

export function piToHex(pi) {
  // For ECharts — interpolate within zones
  if (pi >= 1.15) return '#991B1B'
  if (pi >= PI_EXPENSIVE) return '#DC2626'
  if (pi >= 1.02) return '#F59E0B'
  if (pi >= 0.98) return '#EAB308'
  if (pi >= PI_CHEAP) return '#65A30D'
  if (pi >= 0.85) return '#16A34A'
  return '#166534'
}
```

Replace all inline threshold logic in each component with imports from this utility.

---

### 1.4 Complete URL Sync
**Files:** `frontend/src/composables/useUrlSync.js`, `frontend/src/stores/filters.js`

Add missing keys to URL sync map:
```js
const keyMap = {
  main_category: 'mainCategory',
  sub_category: 'subCategory',
  tier: 'tier',
  action_type: 'actionType',
  brand: 'brand',              // ADD
  private_label: 'includePrivateLabel', // ADD (serialize as '0'/'1')
}
```

Handle boolean serialization for `includePrivateLabel`:
- URL param `private_label=0` → `includePrivateLabel = false`
- Omitted from URL → `includePrivateLabel = true` (default)

---

### 1.5 Add 404 Catch-All Route
**Files:** `frontend/src/router/index.js`

```js
{
  path: '/:pathMatch(.*)*',
  redirect: '/commercial',
}
```

---

### 1.6 Add "Updating..." Indicator to FilterBar
**Files:** `frontend/src/components/layout/FilterBar.vue`, `frontend/src/stores/commercial.js`, `frontend/src/stores/masterData.js`

- Each store already has `loading` state
- In FilterBar, accept a `loading` prop from the parent view
- Show a subtle animated indicator next to the filter chips:
  ```html
  <div v-if="loading" class="flex items-center gap-1.5 text-caption text-brand-primary">
    <Loader2 class="w-3.5 h-3.5 animate-spin" />
    Updating...
  </div>
  ```

---

### 1.7 Distinct MatchReview Pagination Style
**Files:** `frontend/src/components/master-data/MatchReviewPanel.vue`

- Change pagination buttons to pill/rounded style (`rounded-full` instead of `rounded-lg`)
- Add a left border accent: `border-l-2 border-brand-primary` on the pagination container
- Change "Prev/Next" text to arrow icons only (←/→) to visually differentiate from Worklist pagination

---

### 1.8 Add Data Freshness to Executive View
**Files:** `frontend/src/views/ExecutiveView.vue`

- Import `useCommercialStore` (or use the executive store's `lastFetchedAt`)
- Display timestamp in the header area next to the Export button:
  ```html
  <span class="text-micro text-grey-400">
    Data as of {{ formatDate(store.lastFetchedAt) }}
  </span>
  ```

---

### 1.9 Make TopBottomSubcats Clickable
**Files:** `frontend/src/components/executive/TopBottomSubcats.vue`

- Wrap each subcategory item in a clickable element
- On click: `router.push({ path: '/commercial', query: { sub_category: item.subcategory } })`
- Add hover effect: `cursor-pointer hover:bg-grey-50 rounded-lg transition-colors`
- Add a small arrow icon (`ChevronRight` from Lucide) on hover

---

### 1.10 Remove Unused ChartSkeleton
**Files:** Delete `frontend/src/components/shared/ChartSkeleton.vue`

- Verify no imports reference it (grep for `ChartSkeleton`)
- Remove the file

---

## Phase 2: Fix Broken Workflows (Day 3-6)

### 2.1 Match Review Accept/Reject API

#### Backend Changes
**Files (new):** `backend/routers/master_data.py` (add endpoints), `backend/services/mock_data_service.py`, `backend/services/bigquery_service.py`

Add two new endpoints:
```python
@router.post("/match-reviews/{product_id}/accept")
def accept_match(product_id: int, request: Request):
    svc = _svc(request)
    svc.accept_match(product_id)
    return {"ok": True, "action": "accepted"}

@router.post("/match-reviews/{product_id}/reject")
def reject_match(product_id: int, request: Request):
    svc = _svc(request)
    svc.reject_match(product_id)
    return {"ok": True, "action": "rejected"}
```

In data services:
- `accept_match(product_id)`: Update product's action type from "Review Match" → "Complete", store the accepted competitor match
- `reject_match(product_id)`: Update product's action type from "Review Match" → "Needs Mapping", clear the suggested match
- Mock service: update in-memory DataFrame
- BigQuery service: write to a `match_decisions` table or update the source table

#### Frontend Changes
**Files:** `frontend/src/api/client.js`, `frontend/src/components/master-data/MatchReviewPanel.vue`, `frontend/src/stores/masterData.js`

API client:
```js
acceptMatch: (productId) => api.post(`/master-data/match-reviews/${productId}/accept`),
rejectMatch: (productId) => api.post(`/master-data/match-reviews/${productId}/reject`),
```

MatchReviewPanel:
- Replace `dismissed.value.add(match.product_id)` with API call
- Add loading state per card (`loadingId` ref)
- On success: animate card out (slide + fade), decrement total, show undo toast
- On error: show error toast, keep card visible
- Undo toast action: call a `/match-reviews/{id}/undo` endpoint or re-submit to opposite state

Store:
- Add `acceptMatch(productId)` and `rejectMatch(productId)` actions
- After accept/reject, decrement `matchReviewsTotal` and remove from `matchReviews` array
- Optionally re-fetch match reviews to get next page items

---

### 2.2 Standardize PI Colors (continued from 1.3)

Complete the migration across all components. This is the follow-up work after the utility is created.

For ECharts components (SubcategoryTreemap, CategoryPerformance):
- Replace inline color functions with `piToHex()` from the shared utility
- Update treemap's `visualMap` to use the standardized color stops

---

### 2.3 MultiSelect Auto-Apply with Debounce
**Files:** `frontend/src/components/shared/MultiSelect.vue`, `frontend/src/components/layout/FilterBar.vue`

Replace staged Apply pattern with immediate emit + parent debounce:
- Remove `staged` ref — selections directly update `modelValue` via emit
- Remove Apply/Clear footer buttons
- Keep search and Select All functionality
- Each checkbox change immediately emits `update:modelValue`
- The parent (FilterBar → View) handles debounce via `watchDebounced` (already added in Phase 1)
- Click-outside: just closes dropdown (selections already applied)
- Add subtle transition on filter chips appearing/disappearing to confirm changes

---

## Phase 3: Data Integrity (Day 7-10)

### 3.1 Server-Side Sort

#### Backend Changes
**Files:** `backend/routers/commercial.py`, `backend/routers/master_data.py`, `backend/services/mock_data_service.py`, `backend/services/bigquery_service.py`, `backend/services/data_interface.py`

Add params to `_filters()` dependency:
```python
def _filters(
    # ... existing params ...
    sort_by: str = Query("total_revenue", alias="sort_by"),
    sort_dir: str = Query("desc", alias="sort_dir"),
    search: str = Query(None),
):
```

In data services `get_products()` and `get_worklist()`:
- Apply `search` filter: `df[df['product_name'].str.contains(search, case=False, na=False)]`
- Apply sort: `df.sort_values(by=sort_by, ascending=(sort_dir == 'asc'))`
- Then paginate: `df.iloc[(page-1)*page_size : page*page_size]`

#### Frontend Changes
**Files:** `frontend/src/components/commercial/ProductDetailTable.vue`, `frontend/src/components/master-data/PriorityWorklist.vue`, `frontend/src/stores/commercial.js`, `frontend/src/stores/masterData.js`

Store changes:
```js
state: () => ({
  // ... existing ...
  sortBy: 'total_revenue',
  sortDir: 'desc',
  search: '',
}),
actions: {
  async setSort(sortBy, sortDir) {
    this.sortBy = sortBy
    this.sortDir = sortDir
    this.currentPage = 1  // Reset to page 1
    await this.fetchProducts()
  },
  async setSearch(search) {
    this.search = search
    this.currentPage = 1
    await this.fetchProducts()
  },
}
```

Component changes:
- Remove local `sortKey`, `sortDir` refs and client-side sort logic
- Column header click → emit `sort` event or call store's `setSort()`
- Search input → debounced call to store's `setSearch()` (300ms debounce)
- Add indicator: `"Showing ${total} results"` to confirm server-side scope
- Remove local `filteredRows` computed that was doing client-side filtering

---

### 3.2 Column Management for ProductDetailTable
**Files:** `frontend/src/components/commercial/ProductDetailTable.vue`

Add column configuration:
```js
const allColumns = [
  { key: 'product_name', label: 'Product', pinned: true, default: true },
  { key: 'brand_name', label: 'Brand', default: true },
  { key: 'bf_price', label: 'BF Price', default: true },
  { key: 'now_price', label: 'Now Price', default: false },
  { key: 'now_sale_price', label: 'Sale Price', default: false },
  { key: 'talabat_price', label: 'Talabat Price', default: true },
  { key: 'pi', label: 'PI', default: true },
  { key: 'global_tier', label: 'Global Tier', default: false },
  { key: 'sub_tier', label: 'Sub Tier', default: false },
  { key: 'action_type', label: 'Action', default: true },
  { key: 'competitor_match', label: 'Competitor', default: false },
  { key: 'edit_status', label: 'Edit Status', default: false },
]

const visibleColumns = ref(
  JSON.parse(localStorage.getItem('productTableColumns'))
  || allColumns.filter(c => c.default).map(c => c.key)
)
```

Add "Columns" dropdown button in table header:
- Checkbox list of all columns (pinned columns can't be unchecked)
- Changes persist to localStorage
- Product name column uses `sticky left-0 z-10 bg-white` for pinning

---

## Phase 4: Commercial View Layout Restructure (Day 11-15)

### 4.1 Side-by-Side Layout with Tabs
**Files:** `frontend/src/views/CommercialView.vue`, `frontend/src/components/commercial/BlendedPITable.vue`, `frontend/src/components/commercial/ProductDetailTable.vue`

#### CommercialView.vue — New Layout Structure

```html
<template>
  <PageShell :loading="store.loading" :error="store.error" @retry="store.fetchAll()">
    <!-- Top: Definitions + Filters + KPIs (unchanged) -->
    <DefinitionsPanel ... />
    <FilterBar :loading="store.loading" />
    <div class="flex items-center gap-3 flex-wrap">
      <KPICard v-for="kpi in kpis" ... />
      <ExportButton ... />
    </div>

    <!-- Main: Side-by-side panels -->
    <div class="flex gap-4 mt-4" style="height: calc(100vh - 220px)">
      <!-- Left: Blended PI Table -->
      <div class="w-2/5 bg-white rounded-lg shadow-card flex flex-col overflow-hidden">
        <BlendedPITable
          :data="store.blendedPI"
          class="flex-1 overflow-y-auto"
          @select="onTreemapSelect"
          @select-product="onSelectProduct"
        />
      </div>

      <!-- Right: Tabbed Panel -->
      <div class="w-3/5 bg-white rounded-lg shadow-card flex flex-col overflow-hidden">
        <!-- Tab header -->
        <div class="flex border-b border-grey-100 px-4">
          <button
            v-for="tab in ['Products', 'Coverage Map']"
            :key="tab"
            @click="activeTab = tab"
            class="px-4 py-2.5 text-body font-medium border-b-2 transition-colors"
            :class="activeTab === tab
              ? 'border-brand-primary text-brand-primary'
              : 'border-transparent text-grey-500 hover:text-grey-700'"
          >{{ tab }}</button>
        </div>

        <!-- Tab content -->
        <div class="flex-1 overflow-y-auto">
          <ProductDetailTable v-if="activeTab === 'Products'" ... />
          <div v-else class="p-4 flex flex-col gap-4">
            <SubcategoryTreemap ... />
            <div class="grid grid-cols-2 gap-4">
              <CoverageFunnel ... />
              <CoverageFunnel ... />
            </div>
          </div>
        </div>
      </div>
    </div>
  </PageShell>
</template>
```

#### BlendedPITable Changes
- Remove `max-height: 280px` — let parent control height via `flex-1 overflow-y-auto`
- Keep sticky header

#### ProductDetailTable Changes
- Remove `max-height: 520px` — let parent control height
- Keep sticky header

---

## Phase 5: Connected Experience (Day 16-19)

### 5.1 Cross-View Navigation
**Files:** `frontend/src/components/executive/TopBottomSubcats.vue` (done in QW), `frontend/src/components/executive/MiniKpiCards.vue`, `frontend/src/components/executive/PIGauge.vue`, `frontend/src/components/executive/CategoryPerformance.vue`, `frontend/src/components/master-data/PriorityWorklist.vue`

#### MiniKpiCards — "Actions Remaining" clickable
```html
<div @click="router.push('/master-data')" class="cursor-pointer hover:shadow-card-hover transition-shadow">
  <!-- Actions Remaining card content -->
  <ChevronRight class="w-4 h-4 text-grey-400" />
</div>
```

#### CategoryPerformance — Bar click navigates
```js
chart.on('click', (params) => {
  router.push({
    path: '/commercial',
    query: { main_category: params.name }
  })
})
```

#### PriorityWorklist — "View in Commercial" icon
Add a small icon button in the last column:
```html
<button
  @click.stop="router.push({ path: '/commercial', query: { search: row.product_name } })"
  class="text-grey-400 hover:text-brand-primary transition-colors"
  title="View in Commercial"
>
  <ExternalLink class="w-3.5 h-3.5" />
</button>
```

---

### 5.2 Executive View Enhancement
**Files:** `frontend/src/views/ExecutiveView.vue`, `frontend/src/components/executive/PIGauge.vue`

#### Multi-Zone PI Gauge
Replace binary green/red conic gradient with 5-zone arc:
```js
const zones = [
  { min: 0.70, max: 0.90, color: '#166534' }, // deep green — much cheaper
  { min: 0.90, max: 0.95, color: '#16A34A' }, // green — cheaper
  { min: 0.95, max: 1.05, color: '#EAB308' }, // yellow — parity
  { min: 1.05, max: 1.10, color: '#DC2626' }, // red — expensive
  { min: 1.10, max: 1.30, color: '#991B1B' }, // deep red — very expensive
]
```

- Render as SVG arc segments instead of CSS conic gradient (more control)
- Add a needle indicator pointing to the current PI value
- Show target zone (0.95-1.05) with a subtle highlighted band
- Keep interpretation text: "Breadfast is X% cheaper/more expensive"

#### Add "Top Actions by Revenue" Panel
Since we have no trend data, replace the trend line area with an actionable list:
```html
<div class="bg-white rounded-lg shadow-card p-4">
  <h3 class="text-subheading font-bold text-grey-900 mb-3">
    Top Revenue Items Needing Action
  </h3>
  <div v-for="item in topActionItems" class="flex items-center justify-between py-2 border-b border-grey-50">
    <div>
      <div class="text-body text-grey-800">{{ item.product_name }}</div>
      <div class="text-caption text-grey-500">{{ item.subcategory }}</div>
    </div>
    <div class="flex items-center gap-3">
      <ActionBadge :action="item.action_type" />
      <span class="text-caption text-grey-600">EGP {{ item.revenue }}</span>
      <button @click="navigateToProduct(item)">
        <ChevronRight class="w-4 h-4 text-grey-400" />
      </button>
    </div>
  </div>
</div>
```

Backend: Add `GET /executive/top-actions` endpoint returning top 5-10 highest-revenue products that need action, sorted by revenue desc.

---

## Phase 6: Power-User Features (Ongoing)

### 6.1 Saved Filter Presets
**Files (new):** `frontend/src/components/shared/FilterPresets.vue`
**Files (edit):** `frontend/src/components/layout/FilterBar.vue`, `frontend/src/stores/filters.js`

Store presets in localStorage:
```js
// filters.js store
state: () => ({
  // ... existing ...
  presets: JSON.parse(localStorage.getItem('filterPresets') || '[]'),
}),
actions: {
  savePreset(name) {
    const preset = { name, filters: { ...this.activeFilters }, createdAt: Date.now() }
    this.presets.push(preset)
    localStorage.setItem('filterPresets', JSON.stringify(this.presets))
  },
  loadPreset(preset) {
    // Restore all filter arrays from preset.filters
  },
  deletePreset(index) {
    this.presets.splice(index, 1)
    localStorage.setItem('filterPresets', JSON.stringify(this.presets))
  },
}
```

FilterPresets component: dropdown next to Clear All showing saved presets + "Save current" option.

---

### 6.2 Keyboard Shortcuts
**Files (new):** `frontend/src/composables/useKeyboardShortcuts.js`
**Files (edit):** `frontend/src/App.vue`

```js
export function useKeyboardShortcuts() {
  const shortcuts = {
    'f': () => document.querySelector('[data-shortcut="filter"]')?.focus(),
    '/': () => document.querySelector('[data-shortcut="search"]')?.focus(),
    'e': () => document.querySelector('[data-shortcut="export"]')?.click(),
    '1': () => router.push('/commercial'),
    '2': () => router.push('/master-data'),
    '3': () => router.push('/executive'),
    '?': () => showShortcutsModal.value = true,
  }

  onMounted(() => {
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      const handler = shortcuts[e.key]
      if (handler) { e.preventDefault(); handler() }
    })
  })
}
```

Add `?` modal showing all shortcuts in a grid.

---

### 6.3 Server-Side CSV Export
**Files:** `backend/routers/commercial.py`, `frontend/src/components/shared/ExportButton.vue`

Backend: modify existing `/commercial/export` to accept `format=csv` and return streaming response with all products (no pagination):
```python
from fastapi.responses import StreamingResponse
import io, csv

@router.get("/export")
def export_csv(request: Request, ...filters...):
    svc = _svc(request)
    df = svc.get_all_products(filters)  # No pagination
    output = io.StringIO()
    df.to_csv(output, index=False)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pricing-export.csv"}
    )
```

Frontend: change ExportButton to fetch from this endpoint directly (browser handles download via `<a>` with blob URL).

---

## Future: Historical Data Pipeline (Prerequisite for Trends)

> **This is not implementable now — requires infrastructure work.**

### What's needed:
1. **Daily snapshot cron job** — Store daily PI and coverage values per subcategory/category in a `pi_snapshots` BigQuery table
2. **Schema:** `snapshot_date | main_category | sub_category | blended_pi | coverage_rate | total_eligible | total_used`
3. **Backend endpoint:** `GET /executive/pi-trend?weeks=12` returns weekly aggregated snapshots
4. **Once data exists (4+ weeks):** Render `PITrendLine` and `CoverageTrendLine` components in Executive View

### Estimated timeline:
- Pipeline setup: 2-3 days
- Data accumulation: 4-8 weeks minimum for meaningful trends
- Frontend integration: 1 day (components already built)

---

## File Change Summary

| Phase | New Files | Edited Files | Deleted Files |
|-------|-----------|-------------|---------------|
| 1 (Quick Wins) | `utils/piColor.js` | 12 files | `ChartSkeleton.vue` |
| 2 (Broken Workflows) | — | 8 files | — |
| 3 (Data Integrity) | — | 8 files | — |
| 4 (Layout) | — | 3 files | — |
| 5 (Connected) | — | 6 files | — |
| 6 (Power User) | `FilterPresets.vue`, `useKeyboardShortcuts.js` | 5 files | — |
| **Total** | **3 new** | **~30 edits** | **1 deleted** |
