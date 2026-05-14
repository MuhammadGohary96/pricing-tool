# Phase 3 — Competitor Products Tab (4th Tab)

## Context
Add a new "Competitor Products" tab to the Pricing Intelligence Tool. Unlike the existing 3 tabs (which are BF-product-centric), this tab provides the **competitor-side perspective**: how many competitor products are being crawled, how fresh the data is, mapping coverage to BF, and category breakdown. Data source is a separate BigQuery table `dbt_gohary.competitor_products_analysis`.

**Branch:** `feature/competitor-products-tab` (from `main`)

---

## Files to Create

| # | File | Purpose |
|---|------|---------|
| 1 | `backend/routers/competitor_products.py` | FastAPI router — 6 endpoints |
| 2 | `frontend/src/stores/competitorProducts.js` | Pinia store |
| 3 | `frontend/src/views/CompetitorProductsView.vue` | Main view (PageShell + FilterBar + components) |
| 4 | `frontend/src/components/competitor-products/CrawlKpiCards.vue` | 4 KPI cards |
| 5 | `frontend/src/components/competitor-products/CrawlTimeline.vue` | ECharts bar chart — crawl freshness by date |
| 6 | `frontend/src/components/competitor-products/CompetitorCategoryTree.vue` | ECharts treemap — competitor categories |
| 7 | `frontend/src/components/competitor-products/MappingSummaryTable.vue` | Per-competitor mapping stats table |
| 8 | `frontend/src/components/competitor-products/CompetitorProductExplorer.vue` | Paginated product-level table |

## Files to Modify

| # | File | Change |
|---|------|--------|
| 9 | `backend/services/data_interface.py` | Add 6 abstract methods |
| 10 | `backend/services/bigquery_service.py` | Load 2nd BQ table + implement 6 methods |
| 11 | `backend/services/mock_data_service.py` | Generate mock competitor data + implement 6 methods |
| 12 | `backend/main.py` | Import & register new router |
| 13 | `backend/config.py` | Add `BQ_COMPETITOR_TABLE` setting |
| 14 | `frontend/src/api/client.js` | Add `competitorProductsApi` |
| 15 | `frontend/src/router/index.js` | Add `/competitor-products` route |
| 16 | `frontend/src/components/layout/AppHeader.vue` | Add 4th tab + import store for sync badge |

---

## Implementation Steps

### Step 1: Backend — Config & Data Interface

**`backend/config.py`** — Add:
```python
BQ_COMPETITOR_TABLE: str = "competitor_products_analysis"
```

**`backend/services/data_interface.py`** — Add 6 abstract methods:
```python
@abstractmethod
def get_competitor_products_kpis(self, filters: dict = None) -> dict: ...

@abstractmethod
def get_competitor_crawl_timeline(self, filters: dict = None) -> list[dict]: ...

@abstractmethod
def get_competitor_category_breakdown(self, filters: dict = None) -> list[dict]: ...

@abstractmethod
def get_competitor_mapping_summary(self, filters: dict = None) -> list[dict]: ...

@abstractmethod
def get_competitor_products_list(
    self, filters: dict = None, page: int = 1, page_size: int = 50,
    search: str = None, sort_by: str = None, sort_dir: str = "desc",
) -> dict: ...

@abstractmethod
def get_competitor_products_export(self, filters: dict = None) -> list[dict]: ...
```

### Step 2: Backend — BigQuery Service

**`backend/services/bigquery_service.py`**

**a) New BQ query constant** `COMPETITOR_BQ_QUERY`:
```sql
SELECT
    product_id,
    product_name_en,
    brand_name,
    main_category_name,
    sub_category_name,
    competitor_id,
    competitor_name,
    competitor_product_id,
    CAST(competitor_product_key AS STRING) AS competitor_product_key,
    competitor_product_name,
    category_level_1,
    category_level_2,
    category_level_3,
    CAST(competitor_sale_price AS FLOAT64) AS competitor_sale_price,
    CAST(competitor_regular_price AS FLOAT64) AS competitor_regular_price,
    CAST(min_competitor_sale_price AS FLOAT64) AS min_competitor_sale_price,
    CAST(max_competitor_sale_price AS FLOAT64) AS max_competitor_sale_price,
    CAST(breadfast_sale_price AS FLOAT64) AS breadfast_sale_price,
    competitor_last_updated_day,
    breadfast_last_updated_day,
    is_recent_competitor,
    is_recent_breadfast,
    has_PI,
    CAST(sale_PI AS FLOAT64) AS sale_PI,
    classification,
    match_potential,
    CAST(similarity_score AS FLOAT64) AS similarity_score,
    match_potential_product_name
FROM `{project}.{dataset}.{table}`
WHERE competitor_last_updated_day != '1970-01-01'
```

**b) Load in `__init__`** — after loading `self._df`:
```python
if self._startup_status:
    self._startup_status["stage"] = "Loading competitor products..."
self._competitor_df = self._load_competitor_products()
```

**c) New `_load_competitor_products()` method** — similar to `_load_from_bigquery()` but simpler:
- Format `COMPETITOR_BQ_QUERY` with project/dataset/table=`settings.BQ_COMPETITOR_TABLE`
- Execute, build DataFrame
- Cast numerics: `competitor_sale_price`, `competitor_regular_price`, `min_competitor_sale_price`, `max_competitor_sale_price`, `breadfast_sale_price`, `sale_PI`, `similarity_score`
- Cast booleans: `has_PI`, `is_recent_competitor`, `is_recent_breadfast`, `match_potential`
- Convert date columns to ISO strings
- Derive `days_since_crawl` = `(today - competitor_last_updated_day).days`

**d) New `_apply_competitor_filters()` method** — separate from `_apply_filters` since columns differ:
```python
def _apply_competitor_filters(self, df, filters):
    if not filters: return df
    f = df.copy()
    if filters.get("competitor"):
        f = self._multi_match(f, "competitor_name", filters["competitor"])
    if filters.get("category_level_1"):
        f = self._multi_match(f, "category_level_1", filters["category_level_1"])
    if filters.get("mapping_status"):
        status = filters["mapping_status"]
        if status == "Mapped":
            f = f[f["has_PI"] == True]
        elif status == "Unmapped":
            f = f[f["has_PI"] == False]
        elif status == "AI Match":
            f = f[(f["has_PI"] == False) & (f["match_potential"] == True)]
    if filters.get("freshness"):
        if filters["freshness"] == "Fresh":
            f = f[f["is_recent_competitor"] == True]
        elif filters["freshness"] == "Stale":
            f = f[f["is_recent_competitor"] == False]
    return f
```

**e) Implement 6 methods:**

`get_competitor_products_kpis(filters)` → dict:
- Apply filters on `self._competitor_df`
- total_crawled = count unique competitor_product_id
- mapped = count unique competitor_product_id where has_PI == True
- mapping_rate = mapped / total_crawled * 100
- fresh = count unique competitor_product_id where is_recent_competitor == True
- Return `{ total_crawled, mapped, mapping_rate, fresh }`

`get_competitor_crawl_timeline(filters)` → list[dict]:
- Group by `competitor_last_updated_day` + `competitor_name`
- Count distinct `competitor_product_id` per group
- Filter to last 30 days
- Return `[{ date, competitor_name, count }, ...]`

`get_competitor_category_breakdown(filters)` → list[dict]:
- Group by `category_level_1`, `category_level_2`, `category_level_3`
- Count total products and mapped products per group
- Return `[{ l1, l2, l3, total, mapped, mapping_rate }, ...]`

`get_competitor_mapping_summary(filters)` → list[dict]:
- Group by `competitor_name`
- Per group: total, mapped, unmapped, mapping_pct, with_ai_match, fresh, stale, avg_crawl_age
- Return sorted by total desc

`get_competitor_products_list(filters, page, page_size, search, sort_by, sort_dir)` → dict:
- Apply filters, search on `competitor_product_name` OR `product_name_en` (BF mapped name)
- Sort, paginate
- Return `{ items: [...], total_count: N }`

`get_competitor_products_export(filters)` → list[dict]:
- Same as products_list but all rows, no pagination

### Step 3: Backend — Mock Service

**`backend/services/mock_data_service.py`**

Add `_generate_competitor_products()` in `__init__`:
- Generate ~2000 competitor products across 3 competitors (Talabat, Carrefour, Instashop)
- Random category_level_1/2/3 hierarchy
- Random competitor prices, crawl dates (spread over 45 days)
- ~40% mapped to BF products (has_PI=True), ~15% with AI match candidates
- Store as `self._competitor_df`

Implement all 6 methods using the same Pandas patterns as BigQuery service.

### Step 4: Backend — Router

**New `backend/routers/competitor_products.py`:**
```python
from fastapi import APIRouter, Depends, Query, Request
from typing import Optional

router = APIRouter(prefix="/api/competitor-products", tags=["competitor-products"])

def _filters(
    competitor: Optional[str] = Query(None),
    category_level_1: Optional[str] = Query(None),
    mapping_status: Optional[str] = Query(None),   # Mapped | Unmapped | AI Match
    freshness: Optional[str] = Query(None),          # Fresh | Stale
) -> dict:
    params = {}
    if competitor:       params["competitor"] = competitor
    if category_level_1: params["category_level_1"] = category_level_1
    if mapping_status:   params["mapping_status"] = mapping_status
    if freshness:        params["freshness"] = freshness
    return params

@router.get("/kpis")
def get_kpis(request: Request, filters: dict = Depends(_filters)):
    return request.app.state.data_service.get_competitor_products_kpis(filters)

@router.get("/crawl-timeline")
def get_crawl_timeline(request: Request, filters: dict = Depends(_filters)):
    return request.app.state.data_service.get_competitor_crawl_timeline(filters)

@router.get("/category-breakdown")
def get_category_breakdown(request: Request, filters: dict = Depends(_filters)):
    return request.app.state.data_service.get_competitor_category_breakdown(filters)

@router.get("/mapping-summary")
def get_mapping_summary(request: Request, filters: dict = Depends(_filters)):
    return request.app.state.data_service.get_competitor_mapping_summary(filters)

@router.get("/products")
def get_products(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_dir: str = Query("desc"),
    filters: dict = Depends(_filters),
):
    return request.app.state.data_service.get_competitor_products_list(
        filters, page=page, page_size=page_size,
        search=search, sort_by=sort_by, sort_dir=sort_dir,
    )

@router.get("/export")
def export_products(request: Request, filters: dict = Depends(_filters)):
    return request.app.state.data_service.get_competitor_products_export(filters)
```

### Step 5: Backend — Register Router

**`backend/main.py`:**
- Add to import: `from backend.routers import competitor_products`
- Add: `app.include_router(competitor_products.router)`

### Step 6: Frontend — API Client

**`frontend/src/api/client.js`** — Add:
```js
export const competitorProductsApi = {
  getKPIs: (params) => api.get('/competitor-products/kpis', { params }),
  getCrawlTimeline: (params) => api.get('/competitor-products/crawl-timeline', { params }),
  getCategoryBreakdown: (params) => api.get('/competitor-products/category-breakdown', { params }),
  getMappingSummary: (params) => api.get('/competitor-products/mapping-summary', { params }),
  getProducts: (params) => api.get('/competitor-products/products', { params }),
  exportCSV: (params) => api.get('/competitor-products/export', { params }),
}
```

### Step 7: Frontend — Pinia Store

**New `frontend/src/stores/competitorProducts.js`** — follows `masterData.js` pattern:

State: kpis, crawlTimeline, categoryBreakdown, mappingSummary, products, productsTotal, loading, error, lastFetchedAt, currentPage, pageSize, plus tab-specific filters (competitorFilter, categoryL1Filter, mappingStatusFilter, freshnessFilter, searchQuery).

Key difference: This tab has its **own filter state** rather than using global `useFiltersStore`, because the filter dimensions are different (competitor categories vs BF categories).

### Step 8: Frontend — Router & Navigation

**`frontend/src/router/index.js`** — Add route before catch-all.

**`frontend/src/components/layout/AppHeader.vue`:**
- Import store, instantiate, add to `lastFetchedAt` timestamps array
- Add `{ label: 'Competitors', to: '/competitor-products' }` to tabs

### Step 9: Frontend — View

**`frontend/src/views/CompetitorProductsView.vue`:**

Template structure:
```
PageShell (loading/error/retry)
  ├── DefinitionsPanel (collapsible metric glossary)
  ├── Local filter controls (competitor + category + mapping status + freshness)
  ├── CrawlKpiCards (4 KPI cards)
  ├── CrawlTimeline (ECharts bar chart)
  ├── Split row:
  │   ├── CompetitorCategoryTree (ECharts treemap)
  │   └── MappingSummaryTable (per-competitor stats)
  └── CompetitorProductExplorer (paginated table, search, export)
```

### Step 10: Frontend — Components

**a) `CrawlKpiCards.vue`** — 4 KpiCard instances:
- Total Crawled Products (icon: Database, bg: bg-grey-100)
- Mapped to BF (icon: GitCompare, bg: bg-green-50)
- Mapping Rate % (icon: Percent, bg: bg-brand-50)
- Fresh ≤7d (icon: CalendarClock, bg: bg-blue-50)

**b) `CrawlTimeline.vue`** — ECharts stacked bar chart:
- X-axis: dates (last 30 days)
- Y-axis: product count
- One series per competitor (stacked)
- Mark line at today-7 threshold

**c) `CompetitorCategoryTree.vue`** — ECharts treemap:
- Hierarchy: L1 → L2 → L3
- Size = product count
- Color = mapping rate (green=high, red=low) via visualMap

**d) `MappingSummaryTable.vue`** — Static (no pagination, few rows):
- Columns: Competitor, Total, Mapped, Unmapped, Mapping %, AI Match, Fresh, Stale, Avg Age
- Mapping % shown as progress bar + text
- ExportButton for CSV

**e) `CompetitorProductExplorer.vue`** — Paginated table:
- Search, sort, pagination (50/page)
- Classification badges, "days ago" freshness badges
- ExportButton for CSV

---

## Implementation Order

1. **Backend foundation:** config → data_interface → bigquery_service → mock_data_service → router → main.py
2. **Frontend wiring:** API client → Pinia store → Router + AppHeader
3. **Frontend components:** KPI cards → Timeline → Category tree → Mapping table → Product explorer
4. **View assembly:** CompetitorProductsView.vue

## Verification

1. `cd frontend && npm run build` — 0 errors
2. Start backend with `DATA_SOURCE=mock` → `/api/competitor-products/kpis` returns valid JSON
3. All 6 API endpoints return data
4. Navigate to Competitor Products tab — KPI cards show animated values
5. Crawl timeline chart renders with stacked bars per competitor
6. Category treemap renders with color gradient
7. Mapping summary table shows correct per-competitor stats
8. Product explorer: search, sort, pagination all work
9. Filters update all components reactively
10. Export CSV works
11. AppHeader sync badge includes this store's timestamp
