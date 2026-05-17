# FP Filter — Implementation Plan

**Branch:** `feature/fp-filter`  
**Date:** 2026-05-17  
**Author:** Mohammed Elgohary  
**Status:** Awaiting clarification on open questions (see Section 5)

---

## Overview

Add a Fulfillment Point (FP) dropdown to the Commercial view that lets users scope
all product data — prices, PI, action types, and the CSV export — to a single FP
or view the current Global aggregate. Products inactive in the selected FP are
shown as disabled rows (greyed out, no edit actions available).

---

## New Data Source

**Table:** `bf-data-dev-qz06.dbt_gohary.competitor_price_monitoring_fps`

| Fact | Value |
|---|---|
| Row count | 4,570,404 |
| Grain | (product, fp, competitor) |
| FPs | 59 distinct `fp_name` values |
| Products | ~12,683 distinct `product_id` |
| Competitors | 12 distinct `competitor_id` |

### Schema (50 columns)

| Column | Type | Notes |
|---|---|---|
| product_id | INTEGER | Cast to STRING in app |
| product_key | STRING | |
| product_name_en | STRING | → `product_name` in app |
| commercial_category_name | STRING | |
| main_category_name | STRING | |
| sub_category_name | STRING | |
| brand_name | STRING | |
| rank_by_revenue | INTEGER | |
| rank_by_quantity | INTEGER | |
| avg_daily_revenue | NUMERIC | → `total_revenue` in app |
| avg_daily_quantity | FLOAT | |
| global_tier | STRING | |
| subcat_tier | STRING | |
| cumulative_revenue_share | NUMERIC | |
| norm_revenue_global | NUMERIC | |
| norm_quantity_global | FLOAT | |
| combined_score_global | FLOAT | → `weighted_score` in app |
| norm_revenue_subcat | NUMERIC | |
| norm_quantity_subcat | FLOAT | |
| score_subcat_100rev | FLOAT | |
| score_subcat_70rev | FLOAT | |
| score_subcat_50rev | FLOAT | |
| score_subcat_30rev | FLOAT | |
| fp_id | STRING | **NEW** |
| fp_name | STRING | **NEW** |
| bf_regular_price | NUMERIC | |
| competitor_id | INTEGER | |
| competitor_name | STRING | |
| competitor_product_id | STRING | |
| competitor_product_name | STRING | |
| sale_PI | NUMERIC | |
| competitor_sale_price | NUMERIC | |
| min_competitor_sale_price | NUMERIC | |
| max_competitor_sale_price | NUMERIC | |
| breadfast_sale_price | NUMERIC | → `bf_sale_price` in app |
| is_recent_breadfast | BOOLEAN | |
| is_recent_competitor | BOOLEAN | |
| breadfast_last_updated_day | DATE | → `bf_price_updated_at` in app |
| competitor_last_updated_day | DATE | → `competitor_price_updated_at` in app |
| prices_recently_updated | BOOLEAN | |
| is_mapped | BOOLEAN | |
| eligible_product | BOOLEAN | |
| has_PI | BOOLEAN | |
| used_product | BOOLEAN | |
| updated | BOOLEAN | |
| match_potential | BOOLEAN | |
| similarity_score | NUMERIC | |
| match_potential_product_name | STRING | |
| action_type | STRING | |
| classification | STRING | |

### ⚠️ Columns Present in Current App but Missing from New Table

| Current app column | Status |
|---|---|
| `is_active` | **NOT in table** — see Q1 |
| `has_updated_price` | **NOT in table** — see Q2 |
| `competitor_regular_price` | **NOT in table** — see Q3 |
| `now_price` | Not in BQ — added via Catalog API enrichment (keep as-is) |
| `now_sale_price` | Not in BQ — added via Catalog API enrichment (keep as-is) |
| `days_since_update` | Derived from `competitor_last_updated_day` (keep derivation) |
| `pi_deviation` | Derived from `sale_PI - 1` (keep derivation) |

---

## Section 1 — Backend Inventory

### FastAPI Routes Affected

| Router file | Endpoint | Change needed |
|---|---|---|
| `backend/routers/commercial.py:19-46` | All commercial endpoints via `_filters()` | Add `fp_name` param |
| `backend/routers/commercial.py:338-361` | `GET /commercial/export` | Add `fp_name`; add `is_active`, `has_updated_price` to export cols |
| `backend/routers/master_data.py` | All master-data endpoints | Add `fp_name` param (scope TBD — see Q7) |
| `backend/routers/executive.py` | All executive endpoints | Likely NO change — executives see Global |
| `backend/routers/filters.py` | Add new endpoint | `GET /filters/fps` |

### BigQuery Query — Current vs New

**Current:** `BQ_QUERY` constant in `bigquery_service.py:52-87` reads
`bf-data-dev-qz06.dbt_gohary.pricing_index_analysis` — 13,071 rows at
(product, competitor) grain, loaded once at startup.

**New:** Read from `bf-data-dev-qz06.dbt_gohary.competitor_price_monitoring_fps`
— 4,570,404 rows at (product, fp, competitor) grain.

**⚠️ Scale impact:** 350× more rows. Load strategy TBD — see Q4.

### `_apply_filters()` — Change Required

File: `backend/services/bigquery_service.py:408-428` (identical in mock service)

Add:
```python
if filters.get("fp_name"):
    filtered = self._multi_match(filtered, "fp_name", filters["fp_name"])
```

### Column Rename Map (additions to `COLUMN_MAP`)

```python
COLUMN_MAP = {
    # Existing renames
    "product_name_en":           "product_name",
    "avg_daily_revenue":         "total_revenue",
    "breadfast_sale_price":      "bf_sale_price",       # renamed in new table
    "combined_score_global":     "weighted_score",
    "norm_revenue_global":       "norm_revenue",
    "norm_quantity_global":      "norm_quantity",
    "breadfast_last_updated_day":"bf_price_updated_at",
    "competitor_last_updated_day":"competitor_price_updated_at",
}
```

### SQL Injection Risk

**None.** All filtering is in-memory pandas. User input never reaches a SQL string.
The BQ query uses `.format()` with only controlled table/dataset/project values.

---

## Section 2 — Frontend Inventory

### Components to Modify

| File | Change |
|---|---|
| `frontend/src/components/layout/FilterBar.vue` | Add FP single-select dropdown |
| `frontend/src/components/commercial/ProductPivotTable.vue:86-105` | Add disabled-row rendering for `is_active = false` |
| `frontend/src/views/CommercialView.vue:91-111` | Add `filters.fpName` to `watchDebounced` source array |

### Stores to Modify

| File | Change |
|---|---|
| `frontend/src/stores/filters.js` | Add `fpName: 'GLOBAL'`, `fpOptions: []` state; add `fp_name` to `activeFilters` getter; add `getFPs()` call in `fetchFilterOptions()`; add `fpName` to `clearAll()` |

### API Client to Modify

`frontend/src/api/client.js:40-45` — add:
```js
filtersApi: {
  // ... existing
  getFPs: () => api.get('/filters/fps'),
}
```

### URL Sync

`frontend/src/composables/useUrlSync.js` — add mapping:
```
fpName → fp   (URL query param)
```

### Existing Filter UI Pattern

`FilterBar.vue` uses `MultiSelect.vue` for every dimension. FP is
**single-select** (only one FP at a time + "Global" sentinel). Options:
- Add single-select mode to `MultiSelect.vue` via `:max="1"` prop, **OR**
- Create `frontend/src/components/shared/SingleSelect.vue` (preferred — cleaner API)

### Row Disabled State (ProductPivotTable)

```html
<tr
  v-for="row in data"
  :key="row.product_id"
  :class="[
    row.is_active === false ? 'opacity-40 pointer-events-none bg-grey-50' : '',
    row.sale_PI < 0.90 ? 'bg-red-50' : '',
  ]"
>
```

- Inline price edit `startEdit()` must guard: `if (!row.is_active) return`
- Row checkbox must be disabled for inactive rows
- Add `INACTIVE` badge in product name cell

---

## Section 3 — Data Layer Inventory

### FP Distribution

59 active FPs. Sample:

| FP Name | Products | Competitors | Rows |
|---|---|---|---|
| Sheikh Zayed City FP #1 | 7,728 | 12 | 92,813 |
| Sheikh Zayed City FP #2 | 7,675 | 12 | 92,100 |
| 6th of October FP #2 | 7,621 | 12 | 91,458 |
| … | | | |
| *Per FP average* | ~7,400 | 12 | ~88,000 |

### Load Strategy Options

**Option A — Load all 4.5M rows at startup (pandas in-memory)**
- Pros: Zero-latency FP switching, consistent with current pattern
- Cons: ~350× memory increase vs today (13K → 4.5M rows). Est. ~2–4 GB RAM.

**Option B — Load Global at startup + query single FP on demand (recommended)**
- Keep `self._df` loaded from new table aggregated to Global grain (or from existing `pricing_index_analysis` for backward compat)
- When `fp_name` filter is selected, execute a targeted BQ query: `SELECT * FROM competitor_price_monitoring_fps WHERE fp_name = @fp`  (~88K rows, ~2–5s query time)
- Store result in `self._fp_cache[fp_name]` with TTL
- Pros: Low baseline memory, reasonable FP-switch latency
- Cons: First FP selection has 2–5s delay; needs cache invalidation on reload

**Option C — Pre-load all FPs but use separate DataFrame**
- `self._df` = Global data (existing table, 13K rows)
- `self._fp_df` = full FP table (4.5M rows)
- Switch between them based on `fp_name` filter
- Pros: Zero latency, single startup load
- Cons: High memory

**Recommendation: Option B.** Awaiting confirmation — see Q4.

### Existing Caching

| Cache | Location | Impact |
|---|---|---|
| BQ DataFrame | In-memory, startup + `/api/reload` | New query replaces `BQ_QUERY` |
| Filter options | `filters.js` sessionStorage 15min, key `bf_filter_options` | Must add `fps` to cache payload; bump cache key to `bf_filter_options_v2` |
| OAuth tokens | `auth.py` in-memory dict | Not affected |

---

## Section 4 — Implementation Plan (Step-by-Step)

### Step 1 — Resolve open questions (Section 5)
No code. Get answers to Q1–Q8 before proceeding.

### Step 2 — Backend: New BQ Query Constant

**File:** `backend/services/bigquery_service.py`

Replace `BQ_QUERY` constant (lines 52–87) with a query reading
`competitor_price_monitoring_fps`. For GLOBAL mode this query either:
- Aggregates across FPs using `APPROX_TOP_COUNT` for modal price (Option A/C), **or**
- Is the same as today's query (Option B — GLOBAL still reads `pricing_index_analysis`)

Add `FP_QUERY` constant for FP-scoped query:
```python
FP_QUERY = """
SELECT * FROM `{project}.{dataset}.competitor_price_monitoring_fps`
WHERE fp_name = @fp_name
"""
```

Update `COLUMN_MAP` with new column renames (see Section 1).

### Step 3 — Backend: Update `_load_from_bigquery()`

**File:** `backend/services/bigquery_service.py:160-226`

- Update column cast lists to include new columns
- Add casts for: `fp_id` (str), `fp_name` (str), `is_active` (bool, if added to table), `has_updated_price` (bool, if added)
- Keep derivations: `pi_deviation`, `days_since_update`
- If Option B: load Global data only at startup (existing table or aggregated query)

### Step 4 — Backend: Add `load_fp_data()` Method (Option B only)

**File:** `backend/services/bigquery_service.py`

```python
def load_fp_data(self, fp_name: str) -> pd.DataFrame:
    """Load and cache a single FP's data from BQ on demand."""
    if fp_name in self._fp_cache:
        cached_at, df = self._fp_cache[fp_name]
        if (datetime.now() - cached_at).seconds < 3600:  # 1hr TTL
            return df
    # Execute FP_QUERY with QueryJobConfig(query_parameters=[...])
    ...
    self._fp_cache[fp_name] = (datetime.now(), df)
    return df
```

### Step 5 — Backend: Update `_apply_filters()`

**Files:** `bigquery_service.py:408-428`, `mock_data_service.py:317-337`

Add `fp_name` branch:
```python
if filters.get("fp_name"):
    filtered = self._multi_match(filtered, "fp_name", filters["fp_name"])
```

If Option B, modify `_apply_filters()` to detect `fp_name` in filters and switch the
source DataFrame from `self._df` to `self.load_fp_data(fp_name)` before filtering.

### Step 6 — Backend: Add `fp_name` to All `_filters()` Dependency Functions

**Files:** `commercial.py:19-46`, `master_data.py`, `executive.py`

```python
fp_name: Optional[str] = Query(None),

# In body:
if fp_name and fp_name != 'GLOBAL':
    params["fp_name"] = fp_name
```

### Step 7 — Backend: Add `/api/filters/fps` Endpoint

**File:** `backend/routers/filters.py`

```python
@router.get("/fps")
def get_fps(request: Request):
    svc = request.app.state.data_service
    return {"fps": svc.get_fp_options()}
```

**Files:** `bigquery_service.py`, `mock_data_service.py`, `data_interface.py`

Add `get_fp_options()` method returning sorted distinct `fp_name` values
from `self._df` (or `self._fp_df`), with `"GLOBAL"` prepended.

### Step 8 — Backend: Add `is_active` to Response Serialization

**File:** `backend/routers/commercial.py:184-226`

Add `is_active` and `has_updated_price` to:
- `ProductRow` Pydantic model (`backend/models/product.py`)
- `get_products()` serialization loop
- `get_products_pivoted()` serialization
- `export_products()` `export_cols` list

### Step 9 — Frontend: Add FP State to Filters Store

**File:** `frontend/src/stores/filters.js`

```js
state: () => ({
  // existing...
  fpName: 'GLOBAL',
  fpOptions: [],
}),

getters: {
  activeFilters(state) {
    const params = {}
    // existing params...
    if (state.fpName && state.fpName !== 'GLOBAL')
      params.fp_name = state.fpName
    return params
  },
},

actions: {
  async fetchFilterOptions() {
    // existing fetches...
    const fpsRes = await filtersApi.getFPs()
    this.fpOptions = fpsRes.data.fps || []
  },
  clearAll() {
    // existing...
    this.fpName = 'GLOBAL'
  },
}
```

Bump sessionStorage cache key from `bf_filter_options` → `bf_filter_options_v2`.

### Step 10 — Frontend: Add `getFPs` to API Client

**File:** `frontend/src/api/client.js:40-45`

```js
export const filtersApi = {
  // existing...
  getFPs: () => api.get('/filters/fps'),
}
```

### Step 11 — Frontend: Add FP Dropdown to FilterBar

**File:** `frontend/src/components/layout/FilterBar.vue`

Create or use `SingleSelect.vue` (new shared component). Add before the Categories filter:

```html
<SingleSelect
  :model-value="filters.fpName"
  :options="filters.fpOptions"
  label="Fulfillment Point"
  @update:model-value="filters.setFilter('fpName', $event)"
/>
```

The component should have "Global" as the default/first option.
Add FP chip to the active filter chips row when `fpName !== 'GLOBAL'`.

### Step 12 — Frontend: Wire FP into CommercialView Watcher

**File:** `frontend/src/views/CommercialView.vue:91-111`

```js
watchDebounced(
  () => [
    filters.mainCategory,
    filters.subCategory,
    // ... existing
    filters.fpName,        // ADD THIS
  ],
  async () => { ... },
  { debounce: 400, deep: true }
)
```

### Step 13 — Frontend: Disabled Row Rendering

**File:** `frontend/src/components/commercial/ProductPivotTable.vue:86-105`

- Add `opacity-40 pointer-events-none` classes when `row.is_active === false`
- Guard `startEdit()`: early return if `!row.is_active`
- Disable row checkbox: `:disabled="!row.is_active"`
- Add `INACTIVE` badge in product name cell

### Step 14 — Frontend: URL Sync for FP

**File:** `frontend/src/composables/useUrlSync.js`

Add to the key mapping:
```js
fpName: 'fp',
```

---

## Section 5 — Open Questions *(Answers needed before implementation)*

### Q1 — `is_active` not in table *(Critical)*
The FP SQL design includes `is_active = TRUE` if the SKU was live in the app in
the selected FP in the last 7 days (from `dim_fps_products_daily_availability`).
This column is **not present** in `competitor_price_monitoring_fps`.

Options:
- a) Add `is_active` to the dbt model that produces the table
- b) Join `dim_fps_products_daily_availability` in the Python service at load time
- c) Omit the disabled-row feature for now; hide inactive products instead

**What would you like to do?**

### Q2 — `has_updated_price` definition *(Critical)*
Mentioned as a required new response field but not in the table. Is it:
- a) Same as `updated` (alias)?
- b) Same as `prices_recently_updated`?
- c) A new derived field to be computed?

### Q3 — `competitor_regular_price` missing
The current app serializes `competitor_regular_price` (used in some calculations).
It is not in the new table. Is it needed, or can it be dropped?

### Q4 — Load strategy: all FPs vs. on-demand *(Critical)*
The new table has 4.5M rows (59 FPs × ~12,500 products × 12 competitors).
Loading everything at startup would use ~2–4 GB RAM vs ~50 MB today.

Recommended: load Global data at startup + query the ~88K rows for a single FP
on demand (~2–5s BQ query, cached in memory for 1 hour).

**Do you approve Option B (on-demand + cache)?**

### Q5 — GLOBAL mode data source
With Option B, GLOBAL mode still reads the existing `pricing_index_analysis` table
(unchanged today). Should GLOBAL eventually also read from `competitor_price_monitoring_fps`
aggregated, or is the existing table fine for now?

### Q6 — FP list source
59 FPs appear in the table. Should the FP dropdown be populated from:
- a) Distinct `fp_name` values in the loaded DataFrame (only FPs with data), **or**
- b) A live query to `dim_fps` (authoritative, includes FPs with no price data)?

### Q7 — FP filter scope across views
Should the FP filter apply to:
- [x] Commercial view (products, blended PI, export) — **yes, confirmed**
- [ ] Executive view (KPI summary, competitor PI table)?
- [ ] Master Data worklist?
- [ ] Competitor Products view?

### Q8 — FP dropdown placement & default label
- Should the default option read **"Global"** or **"All FPs"**?
- Should the FP dropdown appear in the shared `FilterBar` or as a standalone
  scope selector above the FilterBar (visually separated to signal it changes
  data grain, not just filters)?

---

## Files to Create / Modify Summary

### New Files
| File | Purpose |
|---|---|
| `frontend/src/components/shared/SingleSelect.vue` | Single-select dropdown for FP |
| `docs/plans/fp-filter-implementation-plan.md` | This document |

### Modified Files
| File | Section |
|---|---|
| `backend/services/bigquery_service.py` | Steps 2, 3, 4, 5, 7 |
| `backend/services/mock_data_service.py` | Steps 3, 5, 7 |
| `backend/services/data_interface.py` | Step 7 |
| `backend/models/product.py` | Step 8 |
| `backend/routers/commercial.py` | Steps 6, 8 |
| `backend/routers/master_data.py` | Step 6 |
| `backend/routers/executive.py` | Step 6 (scope TBD) |
| `backend/routers/filters.py` | Step 7 |
| `frontend/src/stores/filters.js` | Step 9 |
| `frontend/src/api/client.js` | Step 10 |
| `frontend/src/components/layout/FilterBar.vue` | Step 11 |
| `frontend/src/views/CommercialView.vue` | Step 12 |
| `frontend/src/components/commercial/ProductPivotTable.vue` | Step 13 |
| `frontend/src/composables/useUrlSync.js` | Step 14 |

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| 4.5M row load crashes backend | High | Use Option B (on-demand per FP) |
| `is_active` missing from table | High | Resolve Q1 before any coding |
| GLOBAL results differ from today | Medium | Keep using `pricing_index_analysis` for GLOBAL (Option B) |
| FP query latency (2–5s) | Medium | In-memory cache per fp_name with 1hr TTL |
| `Needs Price for FP` action type not handled in frontend | Low | Add to `ActionBadge.vue` colour map |
| sessionStorage cache serves stale FP list | Low | Bump cache key to v2 |
