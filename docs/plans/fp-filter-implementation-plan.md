# FP Filter — Implementation Plan

**Branch:** `feature/fp-filter`
**Date:** 2026-05-17
**Author:** Mohammed Elgohary
**Status:** ✅ All questions resolved — ready to implement

---

## Decisions (resolved 2026-05-17)

| # | Question | Decision |
|---|---|---|
| Q1 | `is_active` column missing | **Implicit via INNER JOIN** — the FPS table only includes active (product, fp) pairs. Inactive products are simply absent. No disabled-row UI needed. |
| Q2 | `has_updated_price` definition | **`updated = TRUE`** — alias the existing column |
| Q3 | Load strategy for 4.5M rows | **Load all at startup (Option A)** — full table in memory, pandas filtering |
| Q4 | GLOBAL mode source | **New FPS table** — modal BF price from `is_recent_breadfast=TRUE` rows; modal competitor price from `is_recent_competitor=TRUE` rows, aggregated to (product, competitor) |
| Q5 | `competitor_regular_price` | **Drop it** |
| Q6 | FP list source | **Distinct `fp_name` values from loaded DataFrame** |
| Q7 | Views scope | **Commercial + Executive** |
| Q8 | FP dropdown UX | **Multi-select, default label "All FPs", modal aggregation when multiple FPs selected** |

---

## Overview

Add a Fulfillment Point (FP) multi-select dropdown to the Commercial and Executive
views. Users can select zero, one, or many FPs. Data — prices, PI, action types,
blended PI, KPIs, and CSV export — is scoped to the selected FP(s) using modal
price aggregation. With no FP selected ("All FPs"), the view aggregates across all
FPs using the same modal logic, making it the new Global default.

No disabled-row feature: the FPS table only contains active (product, fp) pairs
(built with INNER JOIN to `fps_available_products`), so inactive products simply
do not appear when an FP is selected.

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
| Avg rows per FP | ~88,000 |

### Schema (50 columns)

| Column | Type | Internal app name | Notes |
|---|---|---|---|
| product_id | INTEGER | product_id | Cast to STRING |
| product_key | STRING | — | Drop after load |
| product_name_en | STRING | product_name | Rename |
| commercial_category_name | STRING | commercial_category_name | |
| main_category_name | STRING | main_category_name | |
| sub_category_name | STRING | sub_category_name | |
| brand_name | STRING | brand_name | |
| rank_by_revenue | INTEGER | — | Drop |
| rank_by_quantity | INTEGER | — | Drop |
| avg_daily_revenue | NUMERIC | total_revenue | Rename |
| avg_daily_quantity | FLOAT | avg_daily_quantity | |
| global_tier | STRING | global_tier | |
| subcat_tier | STRING | subcat_tier | |
| cumulative_revenue_share | NUMERIC | cumulative_revenue_share | |
| norm_revenue_global | NUMERIC | norm_revenue | Rename |
| norm_quantity_global | FLOAT | norm_quantity | Rename |
| combined_score_global | FLOAT | weighted_score | Rename |
| norm_revenue_subcat | NUMERIC | — | Drop |
| norm_quantity_subcat | FLOAT | — | Drop |
| score_subcat_100rev | FLOAT | — | Drop |
| score_subcat_70rev | FLOAT | — | Drop |
| score_subcat_50rev | FLOAT | — | Drop |
| score_subcat_30rev | FLOAT | — | Drop |
| fp_id | STRING | fp_id | **NEW** |
| fp_name | STRING | fp_name | **NEW** |
| bf_regular_price | NUMERIC | bf_regular_price | |
| competitor_id | INTEGER | competitor_id | Cast to INT |
| competitor_name | STRING | competitor_name | |
| competitor_product_id | STRING | competitor_product_id | |
| competitor_product_name | STRING | competitor_product_name | |
| sale_PI | NUMERIC | sale_PI | |
| competitor_sale_price | NUMERIC | competitor_sale_price | |
| min_competitor_sale_price | NUMERIC | min_competitor_sale_price | |
| max_competitor_sale_price | NUMERIC | max_competitor_sale_price | |
| breadfast_sale_price | NUMERIC | bf_sale_price | Rename |
| is_recent_breadfast | BOOLEAN | is_recent_breadfast | |
| is_recent_competitor | BOOLEAN | is_recent_competitor | |
| breadfast_last_updated_day | DATE | bf_price_updated_at | Rename → ISO string |
| competitor_last_updated_day | DATE | competitor_price_updated_at | Rename → ISO string |
| prices_recently_updated | BOOLEAN | prices_recently_updated | |
| is_mapped | BOOLEAN | is_mapped | |
| eligible_product | BOOLEAN | eligible_product | |
| has_PI | BOOLEAN | has_PI | |
| used_product | BOOLEAN | used_product | |
| updated | BOOLEAN | updated / has_updated_price | Also exposed as `has_updated_price` |
| match_potential | BOOLEAN | match_potential | |
| similarity_score | NUMERIC | similarity_score | |
| match_potential_product_name | STRING | match_potential_product_name | |
| action_type | STRING | action_type | |
| classification | STRING | classification | |

### Dropped vs Current

| Current app column | Decision |
|---|---|
| `competitor_regular_price` | **Dropped** (not in new table) |
| `is_active` | **Not needed** — implicit (absent rows = inactive) |
| `now_price` | Keep — added via Catalog API enrichment post-load |
| `now_sale_price` | Keep — added via Catalog API enrichment post-load |
| `days_since_update` | Keep — derived from `competitor_price_updated_at` |
| `pi_deviation` | Keep — derived from `sale_PI - 1` |
| `bf_regular_price` | Keep — present in new table |

---

## GLOBAL Aggregation Logic (pandas)

When no FPs are selected (or "All FPs"), we collapse all 4.5M rows to
(product, competitor) grain using modal prices:

```python
def _aggregate_to_global(df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse (product, fp, competitor) → (product, competitor).
    Modal BF price from is_recent_breadfast=TRUE rows.
    Modal competitor price from is_recent_competitor=TRUE rows.
    All other product-level fields taken from first row per product.
    """
    # 1. Modal BF sale price — from recent BF rows only
    bf_recent = df[df["is_recent_breadfast"] == True]
    bf_modal = (
        bf_recent.groupby("product_id")["bf_sale_price"]
        .agg(lambda x: x.mode().iloc[0] if len(x) else None)
        .rename("bf_sale_price_modal")
    )

    # 2. Modal competitor sale price — from recent competitor rows only
    comp_recent = df[df["is_recent_competitor"] == True]
    comp_modal = (
        comp_recent.groupby(["product_id", "competitor_id"])["competitor_sale_price"]
        .agg(lambda x: x.mode().iloc[0] if len(x) else None)
        .rename("competitor_sale_price_modal")
    )

    # 3. Product-level base fields (deduped — same across FPs)
    product_cols = [
        "product_id", "product_name", "commercial_category_name",
        "main_category_name", "sub_category_name", "brand_name",
        "total_revenue", "avg_daily_quantity", "weighted_score",
        "norm_revenue", "norm_quantity", "global_tier", "subcat_tier",
        "cumulative_revenue_share", "eligible_product", "bf_regular_price",
    ]
    product_base = df.drop_duplicates("product_id")[product_cols]

    # 4. Competitor-level fields — worst/latest across FPs
    comp_cols = [
        "product_id", "competitor_id", "competitor_name",
        "competitor_product_id", "competitor_product_name",
        "is_mapped", "match_potential", "similarity_score",
        "match_potential_product_name", "action_type", "classification",
        "has_PI", "used_product", "updated",
    ]
    comp_base = df.drop_duplicates(["product_id", "competitor_id"])[comp_cols]

    # 5. Merge everything
    result = (
        comp_base
        .merge(product_base, on="product_id", how="left")
        .merge(bf_modal, on="product_id", how="left")
        .merge(comp_modal, on=["product_id", "competitor_id"], how="left")
    )

    # 6. Apply modal prices and recalculate PI
    result["bf_sale_price"] = result["bf_sale_price_modal"]
    result["competitor_sale_price"] = result["competitor_sale_price_modal"]
    result["sale_PI"] = result["bf_sale_price"] / result["competitor_sale_price"]

    return result.drop(columns=["bf_sale_price_modal", "competitor_sale_price_modal"])
```

When **one or more FPs are selected**, filter first then run the same aggregation:

```python
def _aggregate_for_fps(df: pd.DataFrame, fp_names: list[str]) -> pd.DataFrame:
    scoped = df[df["fp_name"].isin(fp_names)]
    return _aggregate_to_global(scoped)  # same modal logic, narrower input
```

---

## Section 1 — Backend Inventory

### FastAPI Routes Affected

| File | Endpoint | Change |
|---|---|---|
| `backend/routers/commercial.py:19-46` | All via `_filters()` | Add `fp_names` param (comma-sep) |
| `backend/routers/commercial.py:338-361` | `GET /commercial/export` | Add `fp_names`; add `has_updated_price` to export cols; drop `competitor_regular_price` |
| `backend/routers/executive.py` | All via `_filters()` | Add `fp_names` param |
| `backend/routers/filters.py` | New endpoint | `GET /filters/fps` |
| `backend/routers/master_data.py` | — | No change |

### BigQuery Query Replacement

**Current `BQ_QUERY`** — reads `dbt_gohary.pricing_index_analysis` (13,071 rows, pre-aggregated).

**New `FPS_QUERY`** — reads `dbt_gohary.competitor_price_monitoring_fps` (4,570,404 rows, FP grain).

```python
FPS_QUERY = """
SELECT
    product_id,
    product_name_en,
    commercial_category_name,
    main_category_name,
    sub_category_name,
    brand_name,
    CAST(avg_daily_revenue          AS FLOAT64) AS avg_daily_revenue,
    CAST(avg_daily_quantity         AS FLOAT64) AS avg_daily_quantity,
    CAST(combined_score_global      AS FLOAT64) AS combined_score_global,
    CAST(norm_revenue_global        AS FLOAT64) AS norm_revenue_global,
    CAST(norm_quantity_global       AS FLOAT64) AS norm_quantity_global,
    global_tier,
    subcat_tier,
    CAST(cumulative_revenue_share   AS FLOAT64) AS cumulative_revenue_share,
    fp_id,
    fp_name,
    CAST(bf_regular_price           AS FLOAT64) AS bf_regular_price,
    competitor_id,
    competitor_name,
    competitor_product_id,
    competitor_product_name,
    CAST(sale_PI                    AS FLOAT64) AS sale_PI,
    CAST(competitor_sale_price      AS FLOAT64) AS competitor_sale_price,
    CAST(min_competitor_sale_price  AS FLOAT64) AS min_competitor_sale_price,
    CAST(max_competitor_sale_price  AS FLOAT64) AS max_competitor_sale_price,
    CAST(breadfast_sale_price       AS FLOAT64) AS breadfast_sale_price,
    is_recent_breadfast,
    is_recent_competitor,
    breadfast_last_updated_day,
    competitor_last_updated_day,
    prices_recently_updated,
    is_mapped,
    eligible_product,
    has_PI,
    used_product,
    updated,
    match_potential,
    CAST(similarity_score           AS FLOAT64) AS similarity_score,
    match_potential_product_name,
    action_type,
    classification
FROM `{project}.{dataset}.competitor_price_monitoring_fps`
"""
```

### Updated `COLUMN_MAP`

```python
COLUMN_MAP = {
    "product_name_en":            "product_name",
    "avg_daily_revenue":          "total_revenue",
    "combined_score_global":      "weighted_score",
    "norm_revenue_global":        "norm_revenue",
    "norm_quantity_global":       "norm_quantity",
    "breadfast_sale_price":       "bf_sale_price",
    "breadfast_last_updated_day": "bf_price_updated_at",
    "competitor_last_updated_day":"competitor_price_updated_at",
}
```

### Updated `_apply_filters()`

Add FP branch. No SQL injection risk — filtering is in-memory pandas.

```python
if filters.get("fp_names"):
    names = [n.strip() for n in filters["fp_names"].split(",")]
    filtered = filtered[filtered["fp_name"].isin(names)]
```

### SQL Injection Risk

**None.** `FPS_QUERY` uses `.format()` with only `project`/`dataset` placeholders.
All user input is applied as pandas predicates post-load.

---

## Section 2 — Frontend Inventory

### Components to Modify

| File | Lines | Change |
|---|---|---|
| `frontend/src/components/layout/FilterBar.vue` | 19–60 | Add FP MultiSelect |
| `frontend/src/views/CommercialView.vue` | 91–111 | Add `filters.fpNames` to watcher |
| `frontend/src/views/ExecutiveView.vue` | — | Add `filters.fpNames` to watcher |

### Stores to Modify

| File | Change |
|---|---|
| `frontend/src/stores/filters.js` | Add `fpNames: []`, `fpOptions: []`; add `fp_names` to `activeFilters`; call `getFPs()`; add to `clearAll()` |

### FP Dropdown — Multi-Select, "All FPs" Default

Use existing `MultiSelect.vue` — no new component needed. Label: **"All FPs"**.
When empty selection → no `fp_names` param → GLOBAL aggregation.
When one or more selected → `fp_names=FP1,FP2` → modal aggregation over those FPs.

Add to active filter chips when any FP selected (show FP names as chips with ×).

### URL Sync

`frontend/src/composables/useUrlSync.js` — add:
```js
fpNames: 'fps',   // ?fps=New+Cairo+FP+%231,Maadi+FP+%234
```

---

## Section 3 — Data Layer

### Memory Impact

| | Current | New |
|---|---|---|
| Rows in `self._df` | 13,071 | 4,570,404 |
| Estimated RAM | ~10 MB | ~1.5–2 GB |
| Startup load time | ~10–30s | ~60–120s (estimate) |

**Mitigation:** Drop unused columns at load time (norm_revenue_subcat,
norm_quantity_subcat, score_subcat_*, rank_by_* etc.) to reduce memory footprint.
Estimated post-drop rows × columns: 4.5M × ~35 = manageable with 4+ GB server RAM.

### GLOBAL Aggregation

`_aggregate_to_global()` runs once at load and is stored as `self._global_df`
(the pre-aggregated Global view). FP-scoped views aggregate on demand from
`self._df` filtered to selected FPs. This keeps request latency low.

```
Startup:
  self._df        = full 4.5M-row FP table (raw)
  self._global_df = _aggregate_to_global(self._df)  # ~13K rows, same as today

Per request (fp_names filter present):
  scoped = self._df[self._df.fp_name.isin(fp_names)]
  result = _aggregate_to_global(scoped)   # ~88K rows → fast pandas op
```

### Caching

| Cache | Change |
|---|---|
| `self._df` | Rebuilt on `/api/reload` — same as today |
| `self._global_df` | Rebuilt on `/api/reload` |
| `bf_filter_options` sessionStorage | Bump key to `bf_filter_options_v2` to force refresh when FP list is added |

---

## Section 4 — Implementation Plan (14 Steps)

### Step 1 — Backend: Replace `BQ_QUERY` with `FPS_QUERY`

**File:** `backend/services/bigquery_service.py:52-87`

- Replace `BQ_QUERY` constant with `FPS_QUERY` (full SELECT above)
- Update `COLUMN_MAP` with new renames
- Drop unused columns immediately after load to save memory:
  ```python
  DROP_COLS = [
      "norm_revenue_subcat", "norm_quantity_subcat",
      "score_subcat_100rev", "score_subcat_70rev",
      "score_subcat_50rev", "score_subcat_30rev",
      "rank_by_revenue", "rank_by_quantity", "product_key",
  ]
  df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
  ```
- Update cast lists: add `fp_id` (str), `fp_name` (str), boolean columns

**File:** `backend/services/mock_data_service.py`

- Add `fp_id`, `fp_name` columns to mock data (generate 3 fake FPs for dev)
- Keep mock data small — no need to simulate 4.5M rows

### Step 2 — Backend: Add `_aggregate_to_global()` Method

**File:** `backend/services/bigquery_service.py`

Implement `_aggregate_to_global(df)` as described in the GLOBAL Aggregation Logic
section above. Call it at the end of `_load_from_bigquery()`:

```python
self._global_df = self._aggregate_to_global(self._df)
```

Add same method to `mock_data_service.py`.
Add abstract method signature to `data_interface.py`.

### Step 3 — Backend: Add `_aggregate_for_fps()` and Update `_apply_filters()`

**File:** `backend/services/bigquery_service.py:408-428`

```python
def _apply_filters(self, df: pd.DataFrame, filters: dict = None) -> pd.DataFrame:
    # Choose source DataFrame based on fp_names filter
    fp_names = filters.get("fp_names") if filters else None
    if fp_names:
        names = [n.strip() for n in fp_names.split(",")]
        source = self._aggregate_for_fps(names)
    else:
        source = self._global_df   # pre-aggregated global

    if not filters:
        return source

    filtered = source.copy()
    # ... existing filter branches (main_category, sub_category, etc.)
    # Remove: competitor filter (no longer applies — it's a column, not a row filter in global)
    return filtered
```

Identical change in `mock_data_service.py`.

### Step 4 — Backend: Add `fp_names` to All `_filters()` Dependency Functions

**File:** `backend/routers/commercial.py:19-46`

```python
def _filters(
    main_category: Optional[str] = Query(None),
    sub_category: Optional[str] = Query(None),
    global_tier: Optional[str] = Query(None),
    subcat_tier: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    competitor: Optional[str] = Query(None),
    exclude_private_label: Optional[bool] = Query(None),
    fp_names: Optional[str] = Query(None),   # ADD
) -> dict:
    params = { ... }  # existing
    if fp_names:
        params["fp_names"] = fp_names
    return params
```

**File:** `backend/routers/executive.py` — same addition.

### Step 5 — Backend: Add `GET /filters/fps` Endpoint

**File:** `backend/routers/filters.py`

```python
@router.get("/fps")
def get_fps(request: Request):
    svc = request.app.state.data_service
    return {"fps": svc.get_fp_options()}
```

**All service files** — add `get_fp_options()`:

```python
def get_fp_options(self) -> list[str]:
    return sorted(self._df["fp_name"].dropna().unique().tolist())
```

### Step 6 — Backend: Update Response Serialization

**File:** `backend/models/product.py`

- Add `has_updated_price: Optional[bool]` field to `ProductRow`
- Remove `competitor_regular_price` field

**File:** `backend/routers/commercial.py:184-226` (`get_products()`)

- Add `has_updated_price=bool(row["updated"])` to serialization
- Remove `competitor_regular_price` from serialization

**File:** `backend/routers/commercial.py:338-361` (`export_products()`)

```python
export_cols = [
    "product_id", "product_name", "brand_name", "commercial_category_name",
    "sub_category_name", "global_tier", "action_type",
    "bf_sale_price", "now_price", "now_sale_price",
    "competitor_name", "competitor_sale_price", "sale_PI",
    "total_revenue", "avg_daily_quantity", "days_since_update",
    "competitor_product_name", "match_potential_product_name",
    "similarity_score", "has_updated_price",   # added
    # competitor_regular_price REMOVED
]
```

### Step 7 — Frontend: Add FP State to Filters Store

**File:** `frontend/src/stores/filters.js`

```js
state: () => ({
  // ... existing
  fpNames: [],        // [] means All FPs (GLOBAL)
  fpOptions: [],
}),

getters: {
  activeFilters(state) {
    const params = {}
    // ... existing
    if (state.fpNames.length) params.fp_names = state.fpNames.join(',')
    return params
  },
  hasActiveFilters(state) {
    return !!(/* existing */ || state.fpNames.length)
  },
},

actions: {
  async fetchFilterOptions() {
    // ... existing fetches
    const fpsRes = await filtersApi.getFPs()
    this.fpOptions = fpsRes.data.fps || []
    // Bump cache key
  },
  clearAll() {
    // ... existing
    this.fpNames = []
  },
}
```

Bump sessionStorage key: `bf_filter_options` → `bf_filter_options_v2`.

### Step 8 — Frontend: Add `getFPs` to API Client

**File:** `frontend/src/api/client.js:40-45`

```js
export const filtersApi = {
  getCategories: () => api.get('/filters/categories'),
  getSubcategories: (main) => api.get('/filters/subcategories', { params: { main } }),
  getTiers: () => api.get('/filters/tiers'),
  getCompetitors: () => api.get('/filters/competitors'),
  getFPs: () => api.get('/filters/fps'),   // ADD
}
```

### Step 9 — Frontend: Add FP MultiSelect to FilterBar

**File:** `frontend/src/components/layout/FilterBar.vue`

Add before the Categories filter:

```html
<MultiSelect
  :model-value="filters.fpNames"
  :options="filters.fpOptions"
  label="All FPs"
  @update:model-value="filters.setFilter('fpNames', $event)"
/>
```

Add FP name chips to the active filter chips row:

```html
<span
  v-for="fp in filters.fpNames"
  :key="'fp-' + fp"
  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light"
>
  {{ fp }}
  <button class="hover:text-brand-dark" @click="removeChip('fpNames', fp)">&times;</button>
</span>
```

Add `fpNames` to `activeCount` computed and `removeChip` handler.

### Step 10 — Frontend: Wire FP into CommercialView Watcher

**File:** `frontend/src/views/CommercialView.vue:91-111`

```js
watchDebounced(
  () => [
    filters.mainCategory,
    filters.subCategory,
    filters.globalTier,
    filters.subcatTier,
    filters.actionType,
    filters.brand,
    filters.competitor,
    filters.includePrivateLabel,
    filters.fpNames,        // ADD
  ],
  async () => { ... },
  { debounce: 400, deep: true }
)
```

### Step 11 — Frontend: Wire FP into ExecutiveView Watcher

**File:** `frontend/src/views/ExecutiveView.vue`

Locate the existing `watchDebounced` / filter watcher and add `filters.fpNames`
to the source array, then trigger `store.fetchAll()` or equivalent.

### Step 12 — Frontend: Remove `competitor_regular_price` References

**Files:** Any Vue template or store that reads `row.competitor_regular_price`

Search and remove/replace across:
- `frontend/src/components/commercial/ProductDetailTable.vue`
- `frontend/src/components/commercial/ProductPivotTable.vue`
- `frontend/src/stores/commercial.js`

### Step 13 — Frontend: URL Sync for FP

**File:** `frontend/src/composables/useUrlSync.js`

Add to the key mapping object:
```js
fpNames: 'fps',
```

Comma-separated FP names in URL: `?fps=New+Cairo+FP+%231,Maadi+FP+%234`

### Step 14 — Frontend: FilterBar Visibility on Executive View

The Executive view currently uses `<FilterBar :loading="store.loading" />`.
The FP filter will appear automatically. No extra work needed unless the
Executive `FilterBar` needs `hide-competitor` or similar.

---

## Files to Create / Modify

### New Files

| File | Purpose |
|---|---|
| `docs/plans/fp-filter-implementation-plan.md` | This document |

### Modified Files

| File | Steps |
|---|---|
| `backend/services/bigquery_service.py` | 1, 2, 3, 5, 6 |
| `backend/services/mock_data_service.py` | 1, 2, 3, 5 |
| `backend/services/data_interface.py` | 2, 5 |
| `backend/models/product.py` | 6 |
| `backend/routers/commercial.py` | 4, 6 |
| `backend/routers/executive.py` | 4 |
| `backend/routers/filters.py` | 5 |
| `frontend/src/stores/filters.js` | 7 |
| `frontend/src/api/client.js` | 8 |
| `frontend/src/components/layout/FilterBar.vue` | 9 |
| `frontend/src/views/CommercialView.vue` | 10 |
| `frontend/src/views/ExecutiveView.vue` | 11 |
| `frontend/src/components/commercial/ProductDetailTable.vue` | 12 |
| `frontend/src/components/commercial/ProductPivotTable.vue` | 12 |
| `frontend/src/stores/commercial.js` | 12 |
| `frontend/src/composables/useUrlSync.js` | 13 |

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| ~2 GB RAM at startup | High | Drop unused columns immediately post-load; test on server before deploy |
| Startup time 2–3× longer | Medium | Show BQ load progress in startup screen (already exists) |
| `_aggregate_to_global()` pandas perf on 4.5M rows | Medium | Pre-compute `self._global_df` once at load; per-FP aggregation on ~88K rows is fast |
| sessionStorage cache serves stale FP list | Low | Bump key to `bf_filter_options_v2` |
| `Needs Price for FP` action type missing from `ActionBadge.vue` | Low | Add colour mapping entry |
| FP names in URL get long with many selections | Low | Acceptable; same pattern as other multi-select filters |

---

## Testing Strategy

| Layer | Test |
|---|---|
| BQ load | Row count after load matches table (4,570,404) |
| `_aggregate_to_global()` | With no FP filter → output row count matches old `pricing_index_analysis` within ±5% |
| `_aggregate_to_global()` | Modal BF price == most frequent `bf_sale_price` across FPs for a known product |
| `_aggregate_for_fps()` | Select one FP → products exactly match `SELECT DISTINCT product_id FROM table WHERE fp_name = X` |
| `_aggregate_for_fps()` | Select two FPs → union of products from both FPs |
| API | `GET /commercial/export` with no FP → CSV identical to today |
| API | `GET /commercial/export?fp_names=New+Cairo+FP+%231` → CSV scoped to that FP |
| API | `GET /filters/fps` → returns sorted list of 59 FP names |
| Frontend | Select 2 FPs → URL updates; refresh → selections restored |
| Frontend | Clear All → FP resets to empty (All FPs) |
| Frontend | Blended PI table updates when FP changes |
| Frontend | Executive KPIs update when FP changes |
| Frontend | CSV export honours selected FP |
