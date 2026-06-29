# FP Aggregation Logic - Complete Reference

**Document Version:** 1.1  
**Last Updated:** 2026-05-19  
**Applies to:** Commercial View & Executive View

---

## Changelog

### Version 1.1 (2026-05-19)
- **Fixed**: Mapping coverage calculation in "Blended PI by Competitor" table
  - Changed from `has_PI` (FP-specific) to `is_mapped` (product-level)
  - Fixed total active count to be SAME across all competitors (subcategory total)
  - Mapped count is now DIFFERENT per competitor (correctly shows per-competitor mapping)
  - Now correctly shows per-competitor mapping status with proper denominator
  - Added detailed documentation in section "Competitor PI Table"

### Version 1.0 (2026-05-18)
- Initial comprehensive documentation of FP aggregation logic

---

## Table of Contents
1. [Overview](#overview)
2. [Data Sources](#data-sources)
3. [FP Filter Modes](#fp-filter-modes)
4. [Aggregation Rules by Field](#aggregation-rules-by-field)
5. [Blended PI Calculation](#blended-pi-calculation)
6. [KPI Formulas](#kpi-formulas)
7. [View-Specific Behavior](#view-specific-behavior)

---

## Overview

The Pricing Intelligence Tool operates on data at **FP (Fulfillment Point) grain**, meaning each product can have different prices and availability across different FPs. When viewing data in Commercial and Executive views, the system aggregates this FP-level data based on the selected FP filter.

### Key Concepts

- **Source Table**: `competitor_price_monitoring_fps` (4.5M rows)
- **Grain**: `product_id × fp_name × competitor_id`
- **Total FPs**: 59 fulfillment points across Egypt
- **Total Products**: ~12,683 unique products
- **Total Rows**: 4,570,404 (product × FP × competitor combinations)

---

## Data Sources

The system maintains two DataFrames for performance:

### 1. Raw FP-grain DataFrame (`_df`)
- **Rows**: 4,570,404
- **Grain**: `(product_id, fp_name, competitor_id)`
- **Usage**: FP-scoped queries (one or more FPs selected)
- **Contains**: All product × FP × competitor combinations

### 2. Pre-aggregated GLOBAL DataFrame (`_global_df`)
- **Rows**: 152,196
- **Grain**: `(product_id, competitor_id)`
- **Usage**: GLOBAL mode (no FP filter)
- **Contains**: Aggregated data across all FPs using modal prices
- **Performance**: 30x smaller than raw data, zero-latency switching

---

## FP Filter Modes

### Mode 1: GLOBAL (No FP Filter Selected)

**Data Source**: `_global_df` (pre-aggregated)

**When Used**:
- User opens Commercial or Executive view
- No FP selected in filter dropdown
- Default state

**Aggregation Logic**:
1. **Breadfast Prices**: Modal (most frequent) price from rows where `is_recent_breadfast = TRUE`
2. **Competitor Prices**: Modal (most frequent) price from rows where `is_recent_competitor = TRUE`, grouped by competitor
3. **Used Products**: Logical OR across all FPs from rows where `is_recent_breadfast = TRUE` AND `is_recent_competitor = TRUE`
4. **Other Fields**: First value per (product, competitor) pair

**SQL Equivalent**:
```sql
SELECT 
    product_id,
    competitor_id,
    -- Modal BF price from recent rows
    MODE(bf_sale_price) OVER (
        PARTITION BY product_id 
        WHERE is_recent_breadfast = TRUE
    ) AS bf_sale_price,
    -- Modal competitor price from recent rows
    MODE(competitor_sale_price) OVER (
        PARTITION BY product_id, competitor_id 
        WHERE is_recent_competitor = TRUE
    ) AS competitor_sale_price,
    -- ANY used across all FPs (from recent rows)
    LOGICAL_OR(used_product) OVER (
        PARTITION BY product_id, competitor_id
        WHERE is_recent_breadfast = TRUE 
          AND is_recent_competitor = TRUE
    ) AS used_product
FROM competitor_price_monitoring_fps
GROUP BY product_id, competitor_id
```

**Example Result**:
- Total Products: 12,683
- **Used Products: 3,343** (products with `used_product = TRUE` in ANY FP with recent prices)
  - ⚠️ **Critical**: Only these 3,343 products are included in Blended PI calculation
  - This is 77% more than single FP (3,343 vs 1,607) because it includes products used in ANY FP
- Eligible Products: 4,941
- Data represents: Network-wide view with modal pricing

---

### Mode 2: Single FP Selected

**Data Source**: `_df` filtered to selected FP, then aggregated on-demand

**When Used**:
- User selects exactly one FP (e.g., "New Cairo FP #1")
- Filter parameter: `fp_names=New Cairo FP #1`

**Aggregation Logic**:
1. **Filter**: `_df[_df["fp_name"] == "New Cairo FP #1"]`
2. **Aggregate**: Apply same modal aggregation rules as GLOBAL mode, but only from this FP's rows
3. **Result**: Grain becomes `(product_id, competitor_id)` for this specific FP

**Python Code**:
```python
# Filter to selected FP
scoped = self._df[self._df["fp_name"] == "New Cairo FP #1"]

# Aggregate using same logic as GLOBAL
result = self._aggregate_to_global(scoped)
```

**Example Result**:
- Total Products: 7,310 (subset of products available at this FP)
- **Used Products: 1,607** (products with `used_product = TRUE` at this FP)
  - ⚠️ **Critical**: Only these 1,607 products are included in Blended PI calculation
  - Products with `used_product = FALSE` are excluded from PI aggregation
- Eligible Products: 3,607
- Data represents: Single FP view with that FP's pricing

**Key Difference from GLOBAL**:
- Fewer products (only those available at this FP)
- Prices specific to this FP (not modal across all FPs)
- Used products only from this FP

---

### Mode 3: Multiple FPs Selected

**Data Source**: `_df` filtered to selected FPs, then aggregated on-demand

**When Used**:
- User selects 2+ FPs (e.g., "New Cairo FP #1, Maadi FP #1, Heliopolis FP #1")
- Filter parameter: `fp_names=New Cairo FP #1,Maadi FP #1,Heliopolis FP #1`

**Aggregation Logic**:
1. **Filter**: `_df[_df["fp_name"].isin(["New Cairo FP #1", "Maadi FP #1", "Heliopolis FP #1"])]`
2. **Aggregate**: 
   - **BF Prices**: Modal price across the 3 selected FPs (from `is_recent_breadfast = TRUE` rows)
   - **Competitor Prices**: Modal price across the 3 selected FPs (from `is_recent_competitor = TRUE` rows)
   - **Used Products**: Logical OR - TRUE if used in ANY of the 3 FPs (from recent rows)
3. **Result**: Grain becomes `(product_id, competitor_id)` aggregated across these 3 FPs

**Python Code**:
```python
# Filter to selected FPs
fp_list = ["New Cairo FP #1", "Maadi FP #1", "Heliopolis FP #1"]
scoped = self._df[self._df["fp_name"].isin(fp_list)]

# Aggregate using same logic as GLOBAL
result = self._aggregate_to_global(scoped)
```

**Example Result**:
- Total Products: 9,500 (products available in ANY of the 3 FPs)
- **Used Products: 2,100** (products with `used_product = TRUE` in ANY of the 3 FPs)
  - ⚠️ **Critical**: Only these 2,100 products are included in Blended PI calculation
  - Between single FP (1,607) and GLOBAL (3,343)
- Eligible Products: 4,200
- Data represents: Multi-FP regional view with modal pricing across selected FPs

**Key Difference from Single FP**:
- More products (union of products from all selected FPs)
- Prices are modal across the selected FPs (not just one FP)
- Used products if used in ANY of the selected FPs

---

## Aggregation Rules by Field

### Product-Level Fields
These fields are **identical across all FPs** (copied from first row):

| Field | Aggregation | Notes |
|-------|-------------|-------|
| `product_id` | Identity | Unique identifier |
| `product_name` | First value | Same across all FPs |
| `brand_name` | First value | Same across all FPs |
| `main_category_name` | First value | Same across all FPs |
| `commercial_category_name` | First value | Same across all FPs |
| `sub_category_name` | First value | Same across all FPs |
| `global_tier` | First value | Same across all FPs |
| `subcat_tier` | First value | Same across all FPs |
| `total_revenue` | First value | Aggregated at product level |
| `avg_daily_quantity` | First value | Aggregated at product level |
| `weighted_score` | First value | Product-level score |
| `norm_revenue` | First value | Normalized revenue |
| `norm_quantity` | First value | Normalized quantity |
| `cumulative_revenue_share` | First value | Product-level metric |
| `eligible_product` | First value | Boolean flag |
| `bf_regular_price` | First value | Standard price |

---

### Price Fields (Modal Aggregation from Recent Rows)

#### Breadfast Sale Price
```python
# Filter to recent Breadfast rows only
bf_recent = df[df["is_recent_breadfast"] == True]

# Modal aggregation per product
bf_modal = (
    bf_recent.groupby("product_id")["bf_sale_price"]
    .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
)
```

**Logic**:
- Only consider rows where `is_recent_breadfast = TRUE`
- Take the **most frequently occurring price** across selected FPs
- If tie (multiple modes), take first
- Result: Representative price for this product across selected FP(s)

#### Competitor Sale Price
```python
# Filter to recent competitor rows only
comp_recent = df[df["is_recent_competitor"] == True]

# Modal aggregation per (product, competitor)
comp_modal = (
    comp_recent.groupby(["product_id", "competitor_id"])["competitor_sale_price"]
    .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
)
```

**Logic**:
- Only consider rows where `is_recent_competitor = TRUE`
- Take the **most frequently occurring price** per competitor across selected FPs
- Separate modal calculation for each competitor
- Result: Representative competitor price across selected FP(s)

#### Min/Max Competitor Prices
```python
# First value per (product, competitor)
# These represent the range across ALL competitors at source FP grain
min_competitor_sale_price = first_value
max_competitor_sale_price = first_value
```

---

### Boolean Flags

#### Used Product (Logical OR from Recent Rows)
```python
# Filter to rows where BOTH prices are recent
recent_rows = df[
    (df["is_recent_breadfast"] == True) & 
    (df["is_recent_competitor"] == True)
]

# Logical OR per (product, competitor)
used_agg = recent_rows.groupby(["product_id", "competitor_id"])["used_product"].any()
```

**Logic**:
- Only consider rows where **both** `is_recent_breadfast = TRUE` AND `is_recent_competitor = TRUE`
- Take **logical OR** (ANY) across selected FPs
- If used in **any** FP (with recent data), mark as used
- Result: TRUE if product is actively sold in any of the selected FP(s)

**Examples**:
- Product A used in New Cairo FP #1 but not Maadi FP #1
  - GLOBAL: TRUE (used in at least one FP)
  - New Cairo FP #1 only: TRUE
  - Maadi FP #1 only: FALSE
  - Both FPs selected: TRUE (used in at least one of the two)

#### Other Boolean Flags
```python
# First value per (product, competitor)
has_PI = first_value          # Has price index calculated
is_mapped = first_value        # Product is mapped to competitor
match_potential = first_value  # Has potential match
updated = first_value          # Price was updated
```

---

### Competitor Matching Fields

| Field | Aggregation | Notes |
|-------|-------------|-------|
| `competitor_id` | Identity | Unique competitor identifier |
| `competitor_name` | First value | Competitor name |
| `competitor_product_id` | First value | Matched competitor product ID |
| `competitor_product_name` | First value | Matched competitor product name |
| `similarity_score` | First value | ML similarity score (0-1) |
| `match_potential_product_name` | First value | Suggested match |
| `action_type` | First value | Action needed (Needs Mapping, Review Match, etc.) |
| `classification` | First value | Product classification |

---

### Calculated Fields

#### Price Index (PI)
```python
sale_PI = bf_sale_price / competitor_sale_price
```

**Recalculated After Aggregation**:
- Uses modal `bf_sale_price` and modal `competitor_sale_price`
- Division gives relative price ratio
- Example: PI = 1.15 means Breadfast is 15% more expensive

#### PI Deviation
```python
pi_deviation = sale_PI - 1.0
```

**Interpretation**:
- `pi_deviation = 0.15` → BF is 15% more expensive
- `pi_deviation = -0.10` → BF is 10% cheaper
- `pi_deviation = 0.0` → BF matches competitor price

---

## Blended PI Calculation

Blended PI represents the **weighted average price index** for a category or group of products.

### Formula

```python
def compute_blended_pi(products_df):
    """
    Compute blended (weighted-average) PI for a group of products.
    
    ⚠️ CRITICAL FILTER: Only products with used_product = TRUE are included!
    
    Weight = product's revenue share within the group
    Only includes products where:
      - has_PI = TRUE (has valid competitor match with price)
      - used_product = TRUE (actively sold in selected FP(s) with recent prices)
    
    Products with used_product = FALSE are EXCLUDED from blended PI.
    """
    # Filter to products with PI that are USED
    valid = products_df[
        (products_df["has_PI"] == True) & 
        (products_df["used_product"] == True)  # ← THIS IS THE KEY FILTER
    ]
    
    # Calculate weights based on revenue
    total_revenue = valid["total_revenue"].sum()
    if total_revenue == 0:
        return None
    
    valid["weight"] = valid["total_revenue"] / total_revenue
    
    # Weighted average of PI
    blended_pi = (valid["sale_PI"] * valid["weight"]).sum()
    
    return blended_pi
```

### Key Points

1. **⚠️ Only Used Products**: Products must be `used_product = TRUE` (actively sold in selected FP(s))
   - **This is the most important filter!**
   - Products with `used_product = FALSE` are completely excluded
   - The FP filter directly impacts which products are "used"
   - GLOBAL mode: 3,343 used products (ANY FP)
   - Single FP mode: 1,607 used products (specific FP only)
   - **Result**: Blended PI can differ significantly between FP filter modes
   
2. **Only Valid PIs**: Products must have `has_PI = TRUE` (valid competitor match)
   - Secondary filter after used_product check
   - Ensures product has competitor price for comparison
   
3. **Revenue-Weighted**: Higher revenue products have more influence
   - Each product's weight = its revenue / total revenue of used products
   
4. **Per Subcategory**: Usually calculated at subcategory level
   - Blended PI computed separately for each subcategory
   - Then aggregated to category or overall level

### Example Calculation

**Subcategory: Fresh Milk (3 products)**

| Product | Revenue | sale_PI | Used | has_PI | Weight | Weighted PI |
|---------|---------|---------|------|--------|--------|-------------|
| Product A | 10,000 | 1.20 | TRUE | TRUE | 0.50 | 0.60 |
| Product B | 8,000 | 1.10 | TRUE | TRUE | 0.40 | 0.44 |
| Product C | 2,000 | 0.95 | TRUE | TRUE | 0.10 | 0.095 |
| **Total** | **20,000** | - | - | - | **1.0** | **1.135** |

**Blended PI = 1.135** → On average, Breadfast is 13.5% more expensive than competitors in Fresh Milk category.

### Critical Relationship: used_product → Blended PI

**The `used_product` flag is the gatekeeper for Blended PI calculations.**

```
Total Products (12,683)
    ↓
Filter by FP selection
    ↓
FP-filtered Products (varies by FP filter)
    ↓
Filter to used_product = TRUE  ← KEY FILTER
    ↓
Products Included in Blended PI (varies significantly)
    ↓
Filter to has_PI = TRUE
    ↓
Revenue-weighted average → Blended PI
```

**Impact Examples:**

| FP Filter | Total Products | used_product = TRUE | % Used | Included in Blended PI |
|-----------|----------------|---------------------|--------|------------------------|
| **GLOBAL** | 12,683 | **3,343** | 26.4% | ✅ 3,343 products |
| **New Cairo FP #1** | 7,310 | **1,607** | 22.0% | ✅ 1,607 products |
| **3 FPs selected** | 9,500 | **2,100** | 22.1% | ✅ 2,100 products |

**Why Different Blended PIs?**
1. Different products included (used in different FPs)
2. Different prices (modal across different FP sets)
3. Different revenue weights (based on included products)

**Example**: 
- A product used in Maadi but not New Cairo:
  - GLOBAL Blended PI: ✅ Included (used in ANY FP)
  - New Cairo FP #1 Blended PI: ❌ Excluded (not used there)
  - Result: **Different Blended PI values**

---

### FP Filter Impact on Blended PI

#### GLOBAL Mode (All FPs)
```python
# Uses products where used_product = TRUE in ANY FP
# Prices are modal across all FPs
# Result: Network-wide blended PI
```

**Example**: 
- Total products in subcategory: 50
- Used products (any FP): 30
- Blended PI calculated from 30 products

#### Single FP Mode
```python
# Uses products where used_product = TRUE in this specific FP
# Prices are from this FP only
# Result: FP-specific blended PI
```

**Example**: 
- Total products in subcategory: 50
- Used products (New Cairo FP #1 only): 18
- Blended PI calculated from 18 products
- **Different result** than GLOBAL (different products, different prices)

#### Multiple FPs Mode
```python
# Uses products where used_product = TRUE in ANY of selected FPs
# Prices are modal across selected FPs
# Result: Regional blended PI
```

**Example**: 
- Total products in subcategory: 50
- Used products (3 selected FPs): 25
- Blended PI calculated from 25 products
- **Between single FP and GLOBAL** (subset of network)

---

## KPI Formulas

### Commercial View KPIs

#### Total Products
```python
total_products = df["product_id"].nunique()
```
- **GLOBAL**: All unique products in database (12,683)
- **Single FP**: Products available at that FP (e.g., 7,310)
- **Multiple FPs**: Products available in ANY selected FP

#### Used Products
```python
used_products = df[df["used_product"] == True]["product_id"].nunique()
```
- **GLOBAL**: Products used in ANY FP with recent prices (3,343)
- **Single FP**: Products used at that specific FP (1,607)
- **Multiple FPs**: Products used in ANY of selected FPs (2,100)

**Aggregation Note**: Uses logical OR logic described in "Used Product" section above

#### Eligible Products
```python
eligible_products = df[df["eligible_product"] == True]["product_id"].nunique()
```
- Products that meet eligibility criteria for PI tracking
- Same product-level field across all FPs
- Count varies by FP filter based on product availability

#### Needs Action
```python
needs_action = df[
    (df["eligible_product"] == True) & 
    (df["action_type"] != "Complete")
]["product_id"].nunique()
```
- Eligible products requiring action (Needs Mapping, Review Match, Needs Price Update)
- Excludes products with `action_type = "Complete"`

#### Average Blended PI
```python
avg_blended_pi = compute_blended_pi(df)  # See formula above
```
- Revenue-weighted average PI across all used products
- Varies by FP filter (different products/prices)

---

### Executive View KPIs

#### Coverage Rate
```python
coverage_rate = (used_products / eligible_products) * 100
```
- **Example**: 3,343 / 4,941 = 67.7%
- Percentage of eligible products actively tracked
- Higher is better

#### Action Rate
```python
action_rate = (needs_action / eligible_products) * 100
```
- **Example**: 4,941 / 4,941 = 100%
- Percentage of eligible products needing action
- Lower is better (indicates more products are "Complete")

#### PI Trend
```python
# Historical blended PI over time
# Calculated same as blended PI, but for each time period
```
- Shows how pricing competitiveness changes over time
- FP filter affects which products are included

#### Category Performance
```python
# Per category:
{
    "category": category_name,
    "blended_pi": compute_blended_pi(category_df),
    "used_products": used_count,
    "eligible_products": eligible_count,
    "needs_action": action_count,
    "revenue": total_revenue
}
```
- Aggregated to category level
- Each metric follows same FP filter rules

---

## View-Specific Behavior

### Commercial View

#### Blended PI Table (by Subcategory)
```python
# Group by subcategory
for subcategory in subcategories:
    subcat_df = filtered_df[filtered_df["sub_category_name"] == subcategory]
    
    row = {
        "sub_category_name": subcategory,
        "blended_pi": compute_blended_pi(subcat_df),
        "used_product_count": subcat_df[subcat_df["used_product"] == True].shape[0],
        "total_product_count": len(subcat_df),
        "eligible_product_count": subcat_df[subcat_df["eligible_product"] == True].shape[0],
        "needs_action_count": subcat_df[
            (subcat_df["eligible_product"] == True) & 
            (subcat_df["action_type"] != "Complete")
        ].shape[0],
        "total_revenue": subcat_df["total_revenue"].sum(),
        "direction": "increase" if blended_pi > 1.0 else "decrease"
    }
```

**FP Filter Impact**:
- **GLOBAL**: Shows all subcategories with network-wide metrics
- **Single FP**: Only subcategories available at that FP, with FP-specific metrics
- **Multiple FPs**: Union of subcategories from selected FPs, with aggregated metrics

#### Product Detail Table
```python
# One row per product (deduplicated by product_id)
# Shows modal prices and aggregated flags based on FP filter
```

**Columns Include**:
- Product info (name, brand, category, tier)
- Breadfast prices (modal based on FP filter)
- Competitor prices (modal based on FP filter)
- Price index (recalculated from modal prices)
- Action type
- Revenue metrics
- Match potential

---

### Executive View

#### Dashboard Summary
```python
{
    "total_products": total_products,
    "used_products": used_products,
    "eligible_products": eligible_products,
    "coverage_rate": (used_products / eligible_products) * 100,
    "avg_blended_pi": compute_blended_pi(all_products_df),
    "needs_action": needs_action_count,
    "total_revenue": total_revenue
}
```

**FP Filter Impact**:
- All metrics respect FP filter
- Coverage and action rates calculated from FP-filtered data
- Blended PI uses FP-filtered products and prices

#### Competitor PI Table
```python
# Per competitor:
for competitor in competitors:
    comp_df = filtered_df[filtered_df["competitor_name"] == competitor]
    
    row = {
        "competitor_name": competitor,
        "blended_pi": compute_blended_pi(comp_df),
        "used_products": comp_df[comp_df["used_product"] == True].shape[0],
        "coverage": (used_products / eligible_products) * 100
    }
```

**FP Filter Impact**:
- **GLOBAL**: All competitors across all FPs
- **Single FP**: Only competitors available at that FP
- **Multiple FPs**: Competitors available in selected FPs

**⚠️ IMPORTANT: Mapping Coverage Calculation (Per-Competitor)**

Mapping coverage in the "Blended PI by Competitor" table shows **per-competitor** mapped/active ratio:

```python
# Per subcategory:
total_active_products = df["product_id"].nunique()  # SAME for all competitors

# Per competitor in subcategory:
mapped_to_competitor = df[df["is_mapped"] == True]["product_id"].nunique()  # DIFFERENT per competitor

# Mapping coverage per competitor
mapping_coverage = (mapped_to_competitor / total_active_products) * 100
```

**Key Points:**
- **Total Active Products** (`comp_eligible_count`): **SAME for all competitors** in a subcategory
  - Total unique products in the subcategory (not filtered by competitor)
  - Example: Fresh Milk has 150 products
- **Mapped Products** (`comp_mapped_count`): **DIFFERENT per competitor**
  - Count of products where `is_mapped = TRUE` for THIS specific competitor
  - Example: 95 products mapped to Amazon, 78 to Carrefour, 102 to Noon
- **`is_mapped` Definition**: Product-level flag from SQL query
  ```sql
  -- Product-level mapping flag (carries across FPs)
  (cm.competitor_product_id IS NOT NULL) AS is_mapped
  ```
- **NOT `has_PI`**: `has_PI` is FP-specific (has price in THIS FP), `is_mapped` is product-level (linked in ANY FP)

**Example (Fresh Milk Subcategory):**
| Competitor | Total Active | Mapped | Coverage |
|------------|--------------|--------|----------|
| Amazon | 150 | 95 | 63.3% |
| Carrefour | 150 | 78 | 52.0% |
| Noon Minutes | 150 | 102 | 68.0% |
| Seoudi | 150 | 45 | 30.0% |

→ All competitors show 150 total active products (same denominator)
→ Mapped count varies by competitor (different numerator)

**Fixed Issue (2026-05-19):**
- Previously incorrectly used `has_PI` (has price in FP) instead of `is_mapped`
- Now correctly shows product-level mapping status per competitor
- Total active count is now the SAME across all competitors (correct)

#### Classification Breakdown
```python
# Group by classification (Parity, Premium, Value)
for classification in ["Parity", "Premium", "Value"]:
    class_df = filtered_df[filtered_df["classification"] == classification]
    
    count = len(class_df)
    percentage = (count / total_products) * 100
```

**FP Filter Impact**:
- Distribution changes based on FP-filtered products
- Percentages recalculated from filtered subset

---

## Performance Considerations

### Why Two DataFrames?

1. **GLOBAL Mode** (`_global_df`):
   - **Pre-aggregated** at startup (one-time cost)
   - **Zero latency** for GLOBAL queries
   - **30x smaller** (152K vs 4.5M rows)
   - **Cached in memory** for instant access

2. **FP-scoped Mode** (`_df`):
   - **On-demand aggregation** when FP filter applied
   - **Flexible** - supports any FP combination
   - **Higher latency** (aggregation needed)
   - **Full fidelity** - no data loss

### Latency Comparison

| Filter Mode | Data Source | Aggregation | Typical Latency |
|-------------|-------------|-------------|-----------------|
| GLOBAL (no FP) | `_global_df` | Pre-computed | <50ms |
| Single FP | `_df` filtered → aggregate | On-demand | ~500-800ms |
| Multiple FPs | `_df` filtered → aggregate | On-demand | ~800-1500ms |

### Memory Usage

- **Raw DataFrame** (`_df`): ~1.8 GB (4.5M rows × 50 columns)
- **GLOBAL DataFrame** (`_global_df`): ~60 MB (152K rows × 50 columns)
- **Total**: ~2 GB for entire pricing dataset

---

## Data Freshness Flags

### is_recent_breadfast
- **Definition**: Breadfast price was updated within last 7 days
- **Usage**: Filter for modal BF price aggregation
- **Ensures**: Prices used in PI calculations are current

### is_recent_competitor
- **Definition**: Competitor price was updated within last 7 days
- **Usage**: Filter for modal competitor price aggregation
- **Ensures**: Competitor prices used in PI calculations are current

### prices_recently_updated
- **Definition**: Both BF and competitor prices updated recently
- **Usage**: Filter for used_product aggregation (requires both prices to be fresh)
- **Ensures**: "Used" products have up-to-date price comparisons

### Why Both Flags Required for used_product?
```python
# We need BOTH prices to be recent to consider a product "used"
recent_rows = df[
    (df["is_recent_breadfast"] == True) & 
    (df["is_recent_competitor"] == True)
]
```

**Rationale**:
- A product with only BF price updated (no recent competitor data) → incomplete comparison
- A product with only competitor price updated (no recent BF data) → incomplete comparison
- Both prices recent → valid, actionable comparison

---

## Edge Cases & Special Scenarios

### No Products Match Filter
```python
if len(filtered_df) == 0:
    return {
        "total_products": 0,
        "used_products": 0,
        "avg_blended_pi": None,
        # ... all metrics zero or null
    }
```

### No Used Products
```python
if used_products == 0:
    # Blended PI returns None (no valid PI to calculate)
    avg_blended_pi = None
```

### Missing Competitor Prices
```python
# If competitor_sale_price is null/NaN:
sale_PI = None  # Cannot calculate PI
has_PI = False  # Flag as no PI available
```

### Tie in Modal Aggregation
```python
# Multiple prices with same frequency (tie)
# Take first mode value
bf_modal = x.mode().iloc[0]
```

### Product Available in Some FPs but Not Others
```python
# GLOBAL mode: Product included (modal price across FPs where available)
# Single FP (not available): Product excluded
# Multiple FPs (available in at least one): Product included
```

---

## Testing & Validation

### Validation Queries

#### Test 1: GLOBAL vs Single FP Used Products
```python
global_used = get_kpis()["used_products"]  # Should be highest (any FP)
single_fp_used = get_kpis(fp_names="New Cairo FP #1")["used_products"]  # Subset

assert global_used >= single_fp_used
```

#### Test 2: Multiple FPs Between Single and GLOBAL
```python
single_used = get_kpis(fp_names="New Cairo FP #1")["used_products"]
multi_used = get_kpis(fp_names="New Cairo FP #1,Maadi FP #1")["used_products"]
global_used = get_kpis()["used_products"]

assert single_used <= multi_used <= global_used
```

#### Test 3: Product Count Consistency
```python
# Total products should be consistent (product-level field)
global_total = get_kpis()["total_products"]
assert global_total == 12683  # Fixed number from database
```

#### Test 4: Blended PI Calculation
```python
# Manual calculation should match computed value
manual_blended_pi = (df["sale_PI"] * df["weight"]).sum()
computed_blended_pi = compute_blended_pi(df)

assert abs(manual_blended_pi - computed_blended_pi) < 0.0001
```

---

## Summary Table

| Scenario | Data Source | Products | Prices | Used Products (used_product = TRUE) | Products in Blended PI |
|----------|-------------|----------|--------|-------------------------------------|------------------------|
| **No FP filter (GLOBAL)** | `_global_df` | All 12,683 | Modal across all FPs | ANY FP: **3,343** ✅ | **3,343** products (26.4% of total) |
| **Single FP** | `_df` → aggregate | FP subset (7,310) | From this FP only | This FP only: **1,607** ✅ | **1,607** products (22.0% of total) |
| **Multiple FPs** | `_df` → aggregate | Union of FPs (9,500) | Modal across selected | ANY selected FP: **2,100** ✅ | **2,100** products (22.1% of total) |

### ⚠️ Critical Insight

**The `used_product` flag determines Blended PI calculations:**

- ✅ **used_product = TRUE**: Product IS included in Blended PI (actively sold with recent prices)
- ❌ **used_product = FALSE**: Product IS NOT included in Blended PI (not actively sold or stale prices)

**Impact of FP Filter on Blended PI:**
- GLOBAL: Uses 3,343 products (maximum - any FP with recent data)
- Single FP: Uses 1,607 products (subset - only this specific FP)
- Multiple FPs: Uses 2,100 products (middle - any of selected FPs)

**Why This Matters:**
1. Different products included → Different Blended PI value
2. More used products (GLOBAL) → More representative network-wide PI
3. Fewer used products (Single FP) → More FP-specific PI
4. FP selection directly impacts pricing competitiveness metrics

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-05-18 | Initial document created |
|  |  | Documented ALL FPs, single FP, and multiple FPs logic |
|  |  | Added used_product aggregation with recent rows filter |
|  |  | Included all formulas and KPI calculations |

---

## References

- **Source Code**: `backend/services/bigquery_service.py::_aggregate_to_global()`
- **SQL Query**: `docs/competitors_products_analysis.sql`
- **Implementation Plan**: `docs/plans/fp-filter-implementation-plan.md`
- **BigQuery Table**: `bf-data-dev-qz06.dbt_gohary.competitor_price_monitoring_fps`
