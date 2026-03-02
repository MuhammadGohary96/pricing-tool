# Pricing Intelligence Web App — Planning Prompt

## Context & Background

I work on the analytics team at **Breadfast**, a quick-commerce grocery delivery company operating in Egypt. We compete primarily against **Talabat** (our main competitor) on price. I need to build an internal **Pricing Intelligence Web Application** using **FastAPI** (backend) + **Vue.js** (frontend) + **Google BigQuery** (data source).

The tool serves three audiences:

1. **Commercial Team** — Uses blended price index data to make pricing decisions at subcategory and product level.
2. **Master Data Team** — Works through a prioritized queue of products that need mapping, AI match review, or price refreshes.
3. **Executive Leadership** — Monitors high-level competitive position, coverage health, and pricing trends over time.

---

## Data Foundation

### Source Table

The tool is powered by a single materialized BigQuery table: `dbt_gohary.pricing_index_analysis`, refreshed daily via dbt. Each row represents one Breadfast product.

**Schema:**

```sql
-- Product Identity
product_id              STRING      -- Breadfast product ID
product_name            STRING      -- Product display name
brand_name              STRING      -- Brand (e.g., Juhayna, Persil)
main_category_name      STRING      -- Top-level category
commercial_category_name STRING     -- Commercial grouping
sub_category_name       STRING      -- Granular subcategory (180 unique values)

-- Revenue & Volume
total_revenue           FLOAT64     -- Cumulative revenue (EGP)
avg_daily_quantity      FLOAT64     -- Average daily units sold
norm_revenue            FLOAT64     -- Min-max normalized revenue (0–1, within subcategory)
norm_quantity           FLOAT64     -- Min-max normalized quantity (0–1, within subcategory)
weighted_score          FLOAT64     -- norm_revenue × 0.5 + norm_quantity × 0.5

-- Tiering (percentile-based on weighted_score)
global_tier             STRING      -- Tier across all products: Top+, Top, Medium, Low, Very Low
subcat_tier             STRING      -- Tier within subcategory peers
-- Thresholds: Top+ (p90–p100), Top (p70–p90), Medium (p40–p70), Low (p20–p40), Very Low (p0–p20)

-- Eligibility
eligible_product        BOOLEAN     -- Within top 80% cumulative subcategory revenue

-- Pricing
bf_sale_price           FLOAT64     -- Breadfast sale price (EGP)
bf_regular_price        FLOAT64     -- Breadfast regular price (EGP)
talabat_sale_price      FLOAT64     -- Talabat sale price (EGP)
talabat_regular_price   FLOAT64     -- Talabat regular price (EGP)
sale_PI                 FLOAT64     -- Price Index = talabat_sale_price / bf_sale_price
has_PI                  BOOLEAN     -- Has a confirmed competitor price match

-- Freshness
bf_price_updated_at     TIMESTAMP   -- Last BF price update
talabat_price_updated_at TIMESTAMP  -- Last Talabat price update
updated                 BOOLEAN     -- Talabat price refreshed within last 7 days

-- AI Matching
similarity_score        FLOAT64     -- ML model confidence (0–1) for unmapped matches
match_potential         BOOLEAN     -- similarity_score >= 0.85

-- Derived
used_product            BOOLEAN     -- eligible_product AND has_PI AND updated
```

### Key Calculated Metrics

```python
# Blended PI (subcategory-level, quantity-weighted)
blended_pi = sum(sale_PI * avg_daily_quantity) / sum(avg_daily_quantity)
# — calculated only where used_product = True

# Action Type (per product)
def get_action_type(row):
    if not row.has_PI and not row.match_potential:
        return "Needs Mapping"
    elif not row.has_PI and row.match_potential:
        return "Review AI Match"
    elif row.has_PI and not row.updated:
        return "Needs Price Update"
    else:
        return "Complete"

# Coverage Funnel (progressive filtering)
# All Products → Eligible → Mapped (has_PI) → Recently Updated → Used Products

# PI Deviation from parity
pi_deviation = sale_PI - 1  # Positive = BF cheaper, Negative = BF more expensive
```

---

## Technical Architecture

### Stack

```
┌─────────────────────────────────────────────────────────┐
│                      FRONTEND                           │
│                   Vue.js 3 + Vite                       │
│          Pinia (state) · Vue Router · Axios             │
│      ECharts/Apache ECharts (treemap, charts)           │
│          AG Grid (tables) · TailwindCSS                 │
└────────────────────────┬────────────────────────────────┘
                         │ REST API (JSON)
                         │
┌────────────────────────▼────────────────────────────────┐
│                      BACKEND                            │
│                   FastAPI (Python)                      │
│         Pydantic models · async endpoints               │
│        google-cloud-bigquery client library             │
│    Caching layer (Redis or in-memory TTL cache)         │
└────────────────────────┬────────────────────────────────┘
                         │ BigQuery API
                         │
┌────────────────────────▼────────────────────────────────┐
│                    DATA LAYER                           │
│               Google BigQuery                           │
│    dbt_gohary.pricing_index_analysis (daily refresh)    │
│         Service account authentication                  │
└─────────────────────────────────────────────────────────┘
```

### BigQuery Connection Pattern

Follow this pattern for the BigQuery client (based on existing Breadfast tooling):

```python
"""
Pricing Intelligence Tool — BigQuery Service Layer

Connection pattern follows the established Breadfast analytics stack.
Uses google-cloud-bigquery client with service account authentication.
"""

from google.cloud import bigquery
from functools import lru_cache
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


class PricingDataService:
    """
    BigQuery data service for the Pricing Intelligence tool.

    Handles all data extraction, aggregation, and metric computation.
    Caches expensive queries with TTL to avoid repeated BigQuery calls.

    Connection follows the same pattern as the SubareaForecaster:
    - Project: followbreadfast
    - Auth: Service account (GOOGLE_APPLICATION_CREDENTIALS env var)
    - Table: dbt_gohary.pricing_index_analysis
    """

    # Cache TTL: 15 minutes (data refreshes daily, so aggressive caching is fine)
    CACHE_TTL_SECONDS = 900

    # Tier ordering for sorting
    TIER_ORDER = {"Top+": 5, "Top": 4, "Medium": 3, "Low": 2, "Very Low": 1}

    # Action type definitions
    ACTION_TYPES = {
        "Needs Mapping": {"symbol": "⊘", "priority": 1},
        "Review AI Match": {"symbol": "⚡", "priority": 2},
        "Needs Price Update": {"symbol": "⟳", "priority": 3},
        "Complete": {"symbol": "✓", "priority": 4},
    }

    def __init__(self, project_id: str = "followbreadfast"):
        """
        Initialize the Pricing Data Service.

        Args:
            project_id: Google Cloud project ID for BigQuery
        """
        self.project_id = project_id
        self.client = bigquery.Client(project=project_id)
        self._cache = {}
        self._cache_timestamps = {}

        print(f"[PricingDataService] Connected to BigQuery project: {project_id}")

    def _is_cache_valid(self, key: str) -> bool:
        """Check if a cached result is still within TTL."""
        if key not in self._cache_timestamps:
            return False
        elapsed = (datetime.now() - self._cache_timestamps[key]).total_seconds()
        return elapsed < self.CACHE_TTL_SECONDS

    def _query_with_cache(self, query: str, cache_key: str) -> pd.DataFrame:
        """Execute a BigQuery query with TTL-based caching."""
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        df = self.client.query(query).to_dataframe()
        self._cache[cache_key] = df
        self._cache_timestamps[cache_key] = datetime.now()
        return df

    # ─── Core Data Extraction ─────────────────────────────────────

    def get_all_products(self) -> pd.DataFrame:
        """
        Fetch all products from the pricing analysis table.

        Returns:
            DataFrame with all product rows and computed action_type column
        """
        query = """
        SELECT
            product_id,
            product_name,
            brand_name,
            main_category_name,
            commercial_category_name,
            sub_category_name,
            total_revenue,
            avg_daily_quantity,
            norm_revenue,
            norm_quantity,
            weighted_score,
            global_tier,
            subcat_tier,
            eligible_product,
            bf_sale_price,
            bf_regular_price,
            talabat_sale_price,
            talabat_regular_price,
            sale_PI,
            has_PI,
            bf_price_updated_at,
            talabat_price_updated_at,
            updated,
            similarity_score,
            match_potential,
            used_product
        FROM `dbt_gohary.pricing_index_analysis`
        ORDER BY total_revenue DESC
        """
        df = self._query_with_cache(query, "all_products")

        # Compute action type
        df["action_type"] = df.apply(self._compute_action_type, axis=1)

        # Compute PI deviation
        df["pi_deviation"] = df["sale_PI"].apply(
            lambda x: round(x - 1, 4) if pd.notna(x) else None
        )

        # Compute staleness in days
        df["days_since_update"] = df["talabat_price_updated_at"].apply(
            lambda x: (datetime.now() - x).days if pd.notna(x) else None
        )

        return df

    def _compute_action_type(self, row) -> str:
        """Determine the action type for a single product row."""
        if not row.get("has_PI") and not row.get("match_potential"):
            return "Needs Mapping"
        elif not row.get("has_PI") and row.get("match_potential"):
            return "Review AI Match"
        elif row.get("has_PI") and not row.get("updated"):
            return "Needs Price Update"
        else:
            return "Complete"

    # ─── Aggregated Metrics ───────────────────────────────────────

    def get_blended_pi_by_subcategory(self) -> pd.DataFrame:
        """
        Calculate quantity-weighted Blended PI per subcategory.

        Only includes used_product = True (eligible + mapped + updated).

        Returns:
            DataFrame: sub_category_name, blended_pi, product_count,
                       total_revenue, avg_tier, direction
        """
        query = """
        SELECT
            sub_category_name,
            SAFE_DIVIDE(
                SUM(sale_PI * avg_daily_quantity),
                SUM(avg_daily_quantity)
            ) AS blended_pi,
            COUNT(DISTINCT product_id) AS used_product_count,
            SUM(total_revenue) AS total_revenue
        FROM `dbt_gohary.pricing_index_analysis`
        WHERE used_product = TRUE
        GROUP BY sub_category_name
        ORDER BY blended_pi DESC
        """
        df = self._query_with_cache(query, "blended_pi_subcat")

        # Direction indicator
        df["pi_deviation"] = (df["blended_pi"] - 1).round(4)
        df["direction"] = df["pi_deviation"].apply(
            lambda d: "▲" if d > 0 else ("▼" if d < 0 else "—")
        )

        return df

    def get_coverage_funnel(self, filters: dict = None) -> dict:
        """
        Calculate the coverage funnel counts.

        Returns:
            dict with stage counts: all, eligible, mapped, updated, used
        """
        base_where = "WHERE 1=1"
        if filters:
            if filters.get("main_category"):
                base_where += f" AND main_category_name = '{filters['main_category']}'"
            if filters.get("sub_category"):
                base_where += f" AND sub_category_name = '{filters['sub_category']}'"

        query = f"""
        SELECT
            COUNT(DISTINCT product_id) AS all_products,
            COUNTIF(eligible_product = TRUE) AS eligible,
            COUNTIF(eligible_product = TRUE AND has_PI = TRUE) AS mapped,
            COUNTIF(eligible_product = TRUE AND has_PI = TRUE AND updated = TRUE) AS recently_updated,
            COUNTIF(used_product = TRUE) AS used_products
        FROM `dbt_gohary.pricing_index_analysis`
        {base_where}
        """
        df = self._query_with_cache(query, f"funnel_{str(filters)}")
        row = df.iloc[0]

        total = int(row["all_products"])
        return {
            "stages": [
                {
                    "name": "All Products",
                    "count": total,
                    "pct": 100.0,
                    "symbol": "📦",
                },
                {
                    "name": "Eligible",
                    "count": int(row["eligible"]),
                    "pct": round(row["eligible"] / total * 100, 1) if total else 0,
                    "symbol": "★",
                },
                {
                    "name": "Mapped",
                    "count": int(row["mapped"]),
                    "pct": round(row["mapped"] / total * 100, 1) if total else 0,
                    "symbol": "🔗",
                },
                {
                    "name": "Recently Updated",
                    "count": int(row["recently_updated"]),
                    "pct": round(row["recently_updated"] / total * 100, 1) if total else 0,
                    "symbol": "⏱",
                },
                {
                    "name": "Used Products",
                    "count": int(row["used_products"]),
                    "pct": round(row["used_products"] / total * 100, 1) if total else 0,
                    "symbol": "✔",
                },
            ]
        }

    def get_action_summary(self) -> dict:
        """
        Get action type counts for the Master Data Team KPI bar.

        Returns:
            dict with counts per action type
        """
        query = """
        SELECT
            COUNTIF(
                eligible_product = TRUE
                AND NOT (has_PI = TRUE AND updated = TRUE)
            ) AS total_needs_action,
            COUNTIF(
                eligible_product = TRUE
                AND has_PI = FALSE
                AND (match_potential IS NULL OR match_potential = FALSE)
            ) AS needs_mapping,
            COUNTIF(
                eligible_product = TRUE
                AND has_PI = FALSE
                AND match_potential = TRUE
            ) AS review_ai_match,
            COUNTIF(
                eligible_product = TRUE
                AND has_PI = TRUE
                AND updated = FALSE
            ) AS needs_price_update
        FROM `dbt_gohary.pricing_index_analysis`
        """
        df = self._query_with_cache(query, "action_summary")
        row = df.iloc[0]

        return {
            "total_needs_action": int(row["total_needs_action"]),
            "needs_mapping": int(row["needs_mapping"]),
            "review_ai_match": int(row["review_ai_match"]),
            "needs_price_update": int(row["needs_price_update"]),
        }

    def get_kpi_summary(self) -> dict:
        """
        Get headline KPIs for the Commercial View.

        Returns:
            dict with: total_products, eligible, used, avg_blended_pi, needs_action
        """
        query = """
        SELECT
            COUNT(DISTINCT product_id) AS total_products,
            COUNTIF(eligible_product = TRUE) AS eligible_products,
            COUNTIF(used_product = TRUE) AS used_products,
            SAFE_DIVIDE(
                SUM(IF(used_product, sale_PI * avg_daily_quantity, 0)),
                SUM(IF(used_product, avg_daily_quantity, 0))
            ) AS avg_blended_pi,
            COUNTIF(
                eligible_product = TRUE
                AND NOT (has_PI = TRUE AND updated = TRUE)
            ) AS needs_action
        FROM `dbt_gohary.pricing_index_analysis`
        """
        df = self._query_with_cache(query, "kpi_summary")
        row = df.iloc[0]

        return {
            "total_products": int(row["total_products"]),
            "eligible_products": int(row["eligible_products"]),
            "used_products": int(row["used_products"]),
            "avg_blended_pi": round(float(row["avg_blended_pi"]), 4) if pd.notna(row["avg_blended_pi"]) else None,
            "needs_action": int(row["needs_action"]),
        }

    # ─── Executive Metrics ────────────────────────────────────────

    def get_executive_summary(self) -> dict:
        """
        Get executive-level summary metrics.

        Returns:
            dict with overall PI, top/bottom subcategories, coverage stats
        """
        kpis = self.get_kpi_summary()
        blended = self.get_blended_pi_by_subcategory()

        top_5_cheapest = blended.nlargest(5, "blended_pi")[
            ["sub_category_name", "blended_pi", "used_product_count"]
        ].to_dict("records")

        top_5_expensive = blended.nsmallest(5, "blended_pi")[
            ["sub_category_name", "blended_pi", "used_product_count"]
        ].to_dict("records")

        coverage_pct = round(
            kpis["used_products"] / kpis["total_products"] * 100, 1
        ) if kpis["total_products"] > 0 else 0

        return {
            "overall_blended_pi": kpis["avg_blended_pi"],
            "coverage_pct": coverage_pct,
            "total_products": kpis["total_products"],
            "used_products": kpis["used_products"],
            "needs_action": kpis["needs_action"],
            "top_5_cheapest": top_5_cheapest,
            "top_5_most_expensive": top_5_expensive,
            "subcategory_count": len(blended),
        }
```

### FastAPI Backend Structure

```
backend/
├── main.py                     # FastAPI app entry point
├── requirements.txt
├── config.py                   # Settings (BQ project, cache TTL, etc.)
├── services/
│   ├── __init__.py
│   ├── bigquery_service.py     # PricingDataService (above)
│   └── cache_service.py        # Redis or in-memory TTL cache
├── routers/
│   ├── __init__.py
│   ├── commercial.py           # /api/commercial/* endpoints
│   ├── master_data.py          # /api/master-data/* endpoints
│   └── executive.py            # /api/executive/* endpoints
├── models/
│   ├── __init__.py
│   ├── product.py              # Pydantic models for product data
│   ├── metrics.py              # Pydantic models for KPIs, funnel, etc.
│   └── filters.py              # Pydantic models for filter params
└── utils/
    ├── __init__.py
    ├── calculations.py         # Blended PI, action type, tier logic
    └── formatters.py           # Symbol formatting, number formatting
```

### API Endpoints

```python
# ─── Commercial View ──────────────────────────────────────
GET  /api/commercial/kpis                       # KPI summary bar (5 metrics)
GET  /api/commercial/treemap                    # Subcategory treemap data
GET  /api/commercial/blended-pi                 # Blended PI ranking table
GET  /api/commercial/products?subcat=X&tier=Y   # Product detail table (filterable)
GET  /api/commercial/funnel?category=X          # Coverage funnel

# ─── Master Data View ─────────────────────────────────────
GET  /api/master-data/action-summary            # Action type KPI cards (4 counts)
GET  /api/master-data/action-breakdown          # Actions by category (stacked bar)
GET  /api/master-data/worklist?action=X&tier=Y  # Priority worklist table
GET  /api/master-data/ai-matches                # AI match review panel
GET  /api/master-data/staleness-heatmap         # Staleness by subcat × days
POST /api/master-data/ai-match/{id}/accept      # Accept AI match (future)
POST /api/master-data/ai-match/{id}/reject      # Reject AI match (future)

# ─── Executive View ───────────────────────────────────────
GET  /api/executive/summary                     # Overall PI, coverage, top/bottom 5
GET  /api/executive/pi-trend                    # Blended PI over time (30d)
GET  /api/executive/coverage-trend              # Coverage % over time (30d)
GET  /api/executive/category-performance        # PI by main category (bar chart)
GET  /api/executive/week-over-week              # WoW delta for key metrics

# ─── Shared ───────────────────────────────────────────────
GET  /api/filters/categories                    # Distinct main categories
GET  /api/filters/subcategories?main=X          # Subcategories for a main category
GET  /api/filters/tiers                         # Available tier values
GET  /api/health                                # Health check
```

### Vue.js Frontend Structure

```
frontend/
├── src/
│   ├── main.js
│   ├── App.vue
│   ├── router/
│   │   └── index.js                # Routes: /commercial, /master-data, /executive
│   ├── stores/
│   │   ├── commercial.js           # Pinia store for commercial view state
│   │   ├── masterData.js           # Pinia store for master data view state
│   │   ├── executive.js            # Pinia store for executive view state
│   │   └── filters.js              # Shared filter state
│   ├── api/
│   │   └── client.js               # Axios instance + endpoint wrappers
│   ├── composables/
│   │   ├── useBlendedPI.js         # Blended PI formatting logic
│   │   ├── useActionType.js        # Action badge symbol/color mapping
│   │   └── useTierRating.js        # Star rating rendering
│   ├── views/
│   │   ├── CommercialView.vue      # Commercial team dashboard
│   │   ├── MasterDataView.vue      # Master data team dashboard
│   │   └── ExecutiveView.vue       # Executive summary dashboard
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppHeader.vue       # Top bar with nav tabs + logo
│   │   │   ├── FilterBar.vue       # Shared filter chips row
│   │   │   └── KpiCard.vue         # Reusable KPI card with icon
│   │   ├── commercial/
│   │   │   ├── SubcategoryTreemap.vue
│   │   │   ├── BlendedPITable.vue
│   │   │   ├── ProductDetailTable.vue
│   │   │   └── CoverageFunnel.vue
│   │   ├── master-data/
│   │   │   ├── ActionSummary.vue
│   │   │   ├── ActionBreakdown.vue
│   │   │   ├── PriorityWorklist.vue
│   │   │   ├── AIMatchPanel.vue
│   │   │   └── StalenessHeatmap.vue
│   │   └── executive/
│   │       ├── PIGauge.vue
│   │       ├── TopBottomSubcats.vue
│   │       ├── CoverageTrend.vue
│   │       ├── PITrend.vue
│   │       └── CategoryPerformance.vue
│   └── assets/
│       ├── icons/                  # SVG icons (from Breadfast_Tableau_Icons)
│       └── styles/
│           └── breadfast.css       # Brand design tokens
├── tailwind.config.js
├── vite.config.js
└── package.json
```

---

## View Specifications

### VIEW 1: Commercial Team — Pricing Intelligence

**Purpose:** Enable commercial managers to understand competitive pricing position by subcategory and take informed pricing decisions.

**Key Questions This View Answers:**
- Which subcategories are we priced competitively vs. Talabat?
- Which subcategories are we losing on price?
- Within a subcategory, which high-tier products are overpriced vs. competitor?
- What is our overall price position weighted by actual sales volume?
- How complete is our price coverage?

**Layout (1200px fixed width):**
```
┌──────────────────────────────────────────────────────────┐
│  Product Tiering & Price Index    [Commercial] [MD] [Exec]  [B] │
├──────────────────────────────────────────────────────────┤
│  🔽 Filters: Category | Subcat | Global Tier | Subcat Tier | Action | Date │
├────────┬────────┬────────┬────────┬──────────────────────┤
│ 📦     │ ★      │ ✓      │ 📊     │ ⚠                   │
│ 12,480 │ 8,216  │ 5,934  │ 1.07   │ 2,282               │
│ Total  │Eligible│ Used   │Blended │ Needs Action         │
├────────┴────────┴──┬─────┴────────┴──────────────────────┤
│                    │ Blended PI by Subcategory     [1B]  │
│  Subcategory       │ Subcat | PI ████ | Tier | # | Dir   │
│  Treemap    [1A]   │ Dairy  | 1.12    | Top+ |842| ▲+.12 │
│                    │ Clean  | 1.15    | Top  |318| ▲+.15 │
│  Size = Revenue    │ ...scrollable...                    │
│  Color = PI        ├─────────────────────────────────────┤
│                    │ Product Detail — Action List  [1C]  │
│  Click to filter → │ Name|Brand|BF|Tal|PI|Tier|Action|AI │
│                    │ Juhayna|32.5|35.0|1.08|Top+|✓|—     │
│                    │ Pepsi|18.0|—|—|Med|⊘ Map|—           │
│                    │ ...sortable, filterable...           │
├────────────────────┴─────────────────────────────────────┤
│  Coverage Funnel                                  [1D]   │
│  📦 12,480  → ★ 8,216  → 🔗 6,745  → ⏱ 6,210  → ✔ 5,934 │
│   100%       65.8%       54.0%       49.8%       47.5%   │
└──────────────────────────────────────────────────────────┘
```

**Components:**

1. **KPI Summary Bar** — Five headline metrics with icons
2. **Subcategory Treemap** — 180 subcats, size=revenue, color=blended PI (ECharts treemap)
3. **Blended PI Ranking Table** — Sortable subcat list with inline bars (AG Grid)
4. **Product Detail Table** — Row-level data, filterable by treemap click (AG Grid)
5. **Coverage Funnel** — Five-stage horizontal funnel with progressive brand shading

**Interactivity:**
- Treemap click → filters PI table + product table + funnel
- All filters cross-linked
- Product table columns sortable
- Export to CSV from any table

---

### VIEW 2: Master Data Team — Action Queue

**Purpose:** Give the master data team a prioritized, actionable worklist of products that need attention to improve pricing coverage.

**Key Questions This View Answers:**
- How many products need mapping, AI review, or price updates today?
- Which high-tier products are unmapped (biggest revenue impact)?
- Which AI match candidates should I review next?
- Which mapped products have stale prices?
- Is our team reducing the action backlog over time?

**Layout:**
```
┌──────────────────────────────────────────────────────────┐
│  Product Tiering & Price Index    [Comm] [Master Data] [Exec]  [B] │
├──────────────────────────────────────────────────────────┤
│  🔽 Filters: Category | Subcat | Action Type | Tier | Staleness    │
├──────────┬──────────┬──────────┬─────────────────────────┤
│ ⚠ 2,282  │ ⊘ 1,140  │ ⚡ 485   │ ⟳ 657                  │
│ Total    │ Needs    │ Review   │ Needs Price             │
│ Actions  │ Mapping  │ AI Match │ Update                  │
├──────────┴──────────┴──────────┴─────────────────────────┤
│  Action Breakdown by Category                     [2A]   │
│  ████████████████░░░░░░ Dairy (342 actions)              │
│  ████████████░░░░░░░░░ Beverages (278 actions)           │
│  ██████░░░░░░░░░░░░░░ Snacks (189 actions)               │
│  ...stacked bar: ⊘ dark | ⚡ brand | ⟳ light...          │
├──────────────────────────────────────────────────────────┤
│  Priority Worklist                                [2B]   │
│  Name | Brand | Subcat | Tier | Action | AI | Price | Updated │
│  ★★★★★ Juhayna Milk  | Dairy | Top+ | ⊘ Needs Map | — | 32.5 │
│  ★★★★★ Persil Gel    | Clean | Top+ | ⟳ Update    | — | 149  │
│  ★★★★☆ Dettol 120g   | Pers  | Top  | ⚡ AI Match | 0.91    │
│  ...sorted by tier desc → revenue desc...                │
├───────────────────────┬──────────────────────────────────┤
│  AI Match Review [2C] │  Staleness Heatmap        [2D]   │
│  BF Product ↔ Talabat │  Subcat | 7-14d | 14-21d | 21d+ │
│  Dettol 120g          │  Dairy  |  ██   |  ██    | ████ │
│  → Dettol 125g (0.91) │  Bev    |  █    |  ███   | ██   │
│  [✓ Accept] [✗ Reject]│  ...heatmap intensity...         │
└───────────────────────┴──────────────────────────────────┘
```

**Components:**

1. **Action Summary KPIs** — Four cards with symbol badges
2. **Action Breakdown by Category** — Stacked horizontal bar (ECharts)
3. **Priority Worklist Table** — Core table sorted by impact (AG Grid)
4. **AI Match Review Panel** — Side-by-side BF↔Talabat with accept/reject
5. **Staleness Heatmap** — Subcategory × days-since-update (ECharts heatmap)
6. **Coverage Progress Over Time** — Trend line toward 90% target (optional)

---

### VIEW 3: Executive Summary

**Purpose:** High-level overview for leadership — are we competitively priced, is our data coverage improving, and where should we focus?

**Key Questions This View Answers:**
- What is our overall price position vs. Talabat right now?
- Is our competitive position improving or declining over time?
- Which categories are our biggest wins and biggest risks?
- How complete is our pricing data, and is coverage getting better?
- What is the week-over-week change in key metrics?

**Layout:**
```
┌──────────────────────────────────────────────────────────┐
│  Product Tiering & Price Index    [Comm] [MD] [Executive]  [B] │
├──────────────────────────────────────────────────────────┤
│                                                          │
│        ┌─────────────┐     Overall Blended PI            │
│        │             │     ──────────────────            │
│        │    1.07     │     BF is 7% cheaper than         │
│        │   ◉ gauge   │     Talabat on average            │
│        │             │     (qty-weighted, used products)  │
│        └─────────────┘     WoW: ▲ +0.02 vs last week     │
│                                                          │
├──────────────┬──────────────┬────────────────────────────┤
│  Coverage %  │  Products    │  Actions Remaining          │
│  ◉ 47.5%    │  5,934 used  │  2,282 need action          │
│  Target: 90% │  of 12,480  │  WoW: ▼ -134 (improving)    │
├──────────────┴──────────────┴────────────────────────────┤
│                                                          │
│  Blended PI Trend (Last 30 Days)                  [3A]   │
│  ──────────────────────────────────                      │
│       1.10 ┤          ╱──╲                               │
│       1.05 ┤    ╱────╱    ╲───                           │
│       1.00 ┤───╱ ─ ─ ─ ─ ─ ─ ─ parity line              │
│       0.95 ┤                                             │
│            └──────────────────────── dates                │
│                                                          │
├──────────────────────────┬───────────────────────────────┤
│                          │                               │
│  🏆 Top 5 BF Cheaper     │  ⚠ Top 5 BF More Expensive   │
│  ─────────────────────   │  ─────────────────────        │
│  1. Cleaning     PI 1.15 │  1. Frozen Foods  PI 0.91     │
│  2. Dairy        PI 1.12 │  2. Fruits        PI 0.94     │
│  3. Personal     PI 1.09 │  3. Beverages     PI 0.97     │
│  4. Bakery       PI 1.08 │  4. Canned        PI 0.98     │
│  5. Snacks       PI 1.04 │  5. Pasta         PI 0.99     │
│                          │                               │
├──────────────────────────┴───────────────────────────────┤
│                                                          │
│  PI by Main Category                              [3B]   │
│  ─────────────────────────                               │
│  Food & Bev  ████████████████████░░░░ 1.06               │
│  Home Care   ██████████████████████████ 1.12              │
│  Personal    ████████████████████████░░ 1.09              │
│  Baby        █████████████████████░░░░ 1.02               │
│              ← BF expensive | parity | BF cheaper →      │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Coverage Progress (Last 30 Days)                 [3C]   │
│  ──────────────────────────────                          │
│   50% ┤                    ╱───── 47.5%                  │
│   40% ┤             ╱─────╱                              │
│   30% ┤      ╱─────╱                                     │
│   20% ┤─────╱                                            │
│       └──────────────────────── dates                    │
│       ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ 90% target               │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Components:**

1. **Overall Blended PI Gauge** — Large center metric with interpretation text and WoW delta
2. **Three Mini KPI Cards** — Coverage %, Products Used, Actions Remaining (all with WoW change)
3. **Blended PI Trend Line** — 30-day trend with parity reference line at 1.0 (ECharts line)
4. **Top 5 / Bottom 5 Subcategories** — Side-by-side ranked lists (cheapest vs. most expensive)
5. **PI by Main Category** — Horizontal diverging bar chart centered on parity (ECharts bar)
6. **Coverage Progress Trend** — 30-day line chart with 90% target goal line (ECharts line)

---

## Design System (Breadfast Brand Standards)

### Color Tokens

```css
:root {
  /* Brand palette */
  --brand-primary: #AB0184;
  --brand-dark: #7A015E;
  --brand-darkest: #4A0038;
  --brand-light: #D4A1C7;
  --brand-lightest: #F3E4EF;

  /* Sequential palette (for continuous data: PI magnitude, heatmaps) */
  --seq-1: #F3E4EF;  /* lightest */
  --seq-2: #E8CCE0;
  --seq-3: #D4A1C7;
  --seq-4: #C24DA5;
  --seq-5: #AB0184;  /* mid = brand primary */
  --seq-6: #8B0170;
  --seq-7: #7A015E;
  --seq-8: #6A0060;
  --seq-9: #4A0038;  /* darkest */

  /* Neutral palette */
  --grey-900: #333333;
  --grey-700: #555555;
  --grey-500: #999999;
  --grey-300: #CCCCCC;
  --grey-100: #F0F0F0;
  --white: #FFFFFF;

  /* Action type colors */
  --action-needs-mapping: #4A0038;
  --action-review-ai: #AB0184;
  --action-needs-update: #D4A1C7;
  --action-complete: #F3E4EF;

  /* Banned: NO blue, NO orange, NO red/green grading, NO pink fonts */
}
```

### Typography

```css
/* Font: Lato (load from Google Fonts) */
--font-primary: 'Lato', sans-serif;
--font-mono: 'Consolas', 'Monaco', monospace;

/* Sizes */
--text-title: 18px;     /* Dashboard title */
--text-heading: 14px;   /* Section headers */
--text-subheading: 11px; /* Panel headers, table headers */
--text-body: 10px;      /* Table cells, labels */
--text-caption: 9px;    /* Footnotes, annotations */
--text-micro: 8px;      /* Tags, badges */
```

### Layout Rules

- Dashboard width: **1200px fixed**
- Containers: **Tiled** (no floating), sharp edges (no rounded corners)
- Logo: **Breadfast 32×32px** top-right corner
- Spacing: 0px gap between panels (borders separate sections)

### Symbol Conventions

```
Direction:  ▲ (PI > 1, BF cheaper)  ▼ (PI < 1, BF expensive)  — (parity)
Actions:    ⊘ Needs Mapping  ⚡ Review AI Match  ⟳ Needs Update  ✓ Complete
Tiers:      ★★★★★ Top+  ★★★★☆ Top  ★★★☆☆ Medium  ★★☆☆☆ Low  ★☆☆☆☆ Very Low
Funnel:     📦 All  ★ Eligible  🔗 Mapped  ⏱ Updated  ✔ Used
Separators: · (middle dot)  │ (pipe)  — (dash)
```

---

## Dependencies

### Backend (requirements.txt)

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
google-cloud-bigquery>=3.13.0
pandas>=2.1.0
numpy>=1.25.0
pydantic>=2.5.0
python-dotenv>=1.0.0
redis>=5.0.0              # Optional: for distributed caching
```

### Frontend (package.json)

```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.0",
    "pinia": "^2.1.0",
    "axios": "^1.6.0",
    "echarts": "^5.4.0",
    "vue-echarts": "^6.6.0",
    "ag-grid-vue3": "^31.0.0",
    "ag-grid-community": "^31.0.0",
    "@vueuse/core": "^10.7.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
```

---

## Deliverables

1. **FastAPI backend** — All endpoints, BigQuery service, Pydantic models, caching
2. **Vue.js frontend** — Three views with all components, routing, state management
3. **Database queries** — Optimized BigQuery queries for each endpoint
4. **Design system** — TailwindCSS config with Breadfast tokens, component library
5. **API documentation** — Auto-generated FastAPI /docs (Swagger)
6. **Docker setup** — Dockerfile for backend + frontend, docker-compose for local dev
7. **Deployment config** — Cloud Run or GKE manifests for Breadfast infrastructure
8. **Testing** — API tests (pytest) + frontend tests (Vitest)

---

## Success Criteria

- Commercial team can identify overpriced subcategories within 30 seconds
- Master data team has a prioritized daily worklist sorted by business impact
- Executive leadership can assess competitive position in a single glance
- Coverage % is trackable over time with a clear 90% target
- All visuals comply with Breadfast brand standards (no banned colors)
- API response time < 2 seconds for all endpoints (with caching)
- Frontend loads and renders in < 3 seconds
- Supports 50 concurrent users without degradation
