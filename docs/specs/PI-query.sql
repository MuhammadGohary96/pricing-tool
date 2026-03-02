-- =============================================================================
-- PRODUCT TIERING & PRICE INDEX ANALYSIS
-- =============================================================================
--
-- Purpose : Rank products by revenue/quantity, assign performance tiers,
-- calculate weighted Price Index (PI) vs Talabat competitor.
--
-- Scope : Egypt (EG) market | Grocery vertical | Single products only
-- Window : Rolling 3-month lookback
-- Filter : Products with >= 70% in-stock availability
-- Excludes: Coffee, Pharmacy, Vitamins, Beauty, Hot Food, Bundles, AFCON Bites
--
-- PI Interpretation:
-- PI > 1.0 → Breadfast is CHEAPER than Talabat (competitive advantage)
-- PI = 1.0 → Price parity
-- PI < 1.0 → Breadfast is MORE EXPENSIVE (needs attention)
--
-- Output : Product-level data with tiers, scores, PI, and eligibility flags
-- filtered to mapped non-Breadfast-brand products
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 1 ▸ BASE DATA
-- Aggregate average daily revenue & quantity per product over the last 3 months.
-- Only include products that were in-stock at least 70% of ideal available time.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE dbt_gohary.pricing_index_analysis AS (
WITH product_base AS (
SELECT
p.product_id,
p.sub_category_name,
COALESCE(AVG(COALESCE(subtotal_revenue, 0)), 0) AS avg_daily_revenue,
COALESCE(AVG(COALESCE(sold_quantity, 0)), 0) AS avg_daily_quantity
FROM `followbreadfast.l04_views.agg_daily_supply_demand_scorecard` s
LEFT JOIN `followbreadfast.l03_marts.dim_products` p USING (product_key)
WHERE TRUE
AND p.country_code = 'EG'
AND p.vertical = 'grocery'
AND product_type = 'single'
-- Availability: at least 70% in-stock
AND (1 - SAFE_DIVIDE(minutes_out_of_stock, ideal_available_minutes)) >= 0.7
-- Rolling 3-month window
AND date_day BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 3 MONTH)
AND CURRENT_DATE() - 1
-- Exclude non-grocery verticals
AND main_category_id NOT IN (
1084, -- Coffee
2092, -- Pharmacy
3018, -- Vitamins
2055, -- Beauty
1858 -- Hot Food
)
AND LOWER(p.sub_category_name) NOT LIKE '%bundle%'
AND p.sub_category_name NOT IN ('AFCON Bites')
GROUP BY ALL
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 2 ▸ PERCENTILE THRESHOLDS
-- Calculate global and subcategory-level percentile breakpoints for tiering.
--
-- Tier Definitions:
-- Top+ ≥ 90th percentile (elite performers)
-- Top ≥ 80th percentile (strong performers)
-- Medium ≥ 50th percentile (above median)
-- Low ≥ 25th percentile (below median)
-- Very Low < 25th percentile (bottom quartile)
-- ─────────────────────────────────────────────────────────────────────────────

-- 2a. Global percentiles (across ALL products)
global_percentiles AS (
SELECT
APPROX_QUANTILES(avg_daily_revenue, 100)[OFFSET(90)] AS p90_revenue,
APPROX_QUANTILES(avg_daily_revenue, 100)[OFFSET(80)] AS p80_revenue,
APPROX_QUANTILES(avg_daily_revenue, 100)[OFFSET(50)] AS p50_revenue,
APPROX_QUANTILES(avg_daily_revenue, 100)[OFFSET(25)] AS p25_revenue,
APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(90)] AS p90_quantity,
APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(80)] AS p80_quantity,
APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(50)] AS p50_quantity,
APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(25)] AS p25_quantity
FROM product_base
),

-- 2b. Subcategory-level percentiles (within each subcategory)
subcat_percentiles AS (
SELECT
sub_category_name,
APPROX_QUANTILES(avg_daily_revenue, 100)[OFFSET(90)] AS p90_revenue,
APPROX_QUANTILES(avg_daily_revenue, 100)[OFFSET(80)] AS p80_revenue,
APPROX_QUANTILES(avg_daily_revenue, 100)[OFFSET(50)] AS p50_revenue,
APPROX_QUANTILES(avg_daily_revenue, 100)[OFFSET(25)] AS p25_revenue,
APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(90)] AS p90_quantity,
APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(80)] AS p80_quantity,
APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(50)] AS p50_quantity,
APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(25)] AS p25_quantity
FROM product_base
GROUP BY ALL
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 3 ▸ PRODUCT RANKINGS
-- Dense rank every product globally by revenue and by quantity (desc).
-- ─────────────────────────────────────────────────────────────────────────────
product_rankings AS (
SELECT
product_id,
DENSE_RANK() OVER (ORDER BY avg_daily_revenue DESC) AS rank_by_revenue,
DENSE_RANK() OVER (ORDER BY avg_daily_quantity DESC) AS rank_by_quantity
FROM product_base
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 4 ▸ TIER ASSIGNMENT & CUMULATIVE REVENUE SHARE
-- Combine base metrics + dimension attributes + percentile thresholds.
-- Assign each product a tier at both global and subcategory level.
-- Compute running cumulative revenue share within each subcategory.
-- ─────────────────────────────────────────────────────────────────────────────
tiered_products AS (
SELECT
-- Product identifiers
b.product_id,
dp.product_key,
dp.product_name_en,
dp.commercial_category_name,
dp.main_category_name,
dp.sub_category_name,
dp.brand_name,

-- Rankings
r.rank_by_revenue,
r.rank_by_quantity,

-- Raw performance metrics
b.avg_daily_revenue,
b.avg_daily_quantity,

-- Global percentile thresholds (for reference)
gp.p25_revenue,
gp.p50_revenue,
gp.p80_revenue,
gp.p90_revenue,
gp.p25_quantity,
gp.p50_quantity,
gp.p80_quantity,
gp.p90_quantity,

-- ── Global tier ──
-- A product qualifies if it exceeds the threshold in EITHER revenue OR quantity
CASE
WHEN b.avg_daily_revenue >= gp.p90_revenue
OR b.avg_daily_quantity >= gp.p90_quantity THEN 'Top+'
WHEN b.avg_daily_revenue >= gp.p80_revenue
OR b.avg_daily_quantity >= gp.p80_quantity THEN 'Top'
WHEN b.avg_daily_revenue >= gp.p50_revenue
OR b.avg_daily_quantity >= gp.p50_quantity THEN 'Medium'
WHEN b.avg_daily_revenue >= gp.p25_revenue
OR b.avg_daily_quantity >= gp.p25_quantity THEN 'Low'
ELSE 'Very Low'
END AS global_tier,

-- ── Subcategory tier ──
CASE
WHEN b.avg_daily_revenue >= sp.p90_revenue
OR b.avg_daily_quantity >= sp.p90_quantity THEN 'Top+'
WHEN b.avg_daily_revenue >= sp.p80_revenue
OR b.avg_daily_quantity >= sp.p80_quantity THEN 'Top'
WHEN b.avg_daily_revenue >= sp.p50_revenue
OR b.avg_daily_quantity >= sp.p50_quantity THEN 'Medium'
WHEN b.avg_daily_revenue >= sp.p25_revenue
OR b.avg_daily_quantity >= sp.p25_quantity THEN 'Low'
ELSE 'Very Low'
END AS subcat_tier,

-- Cumulative revenue share within subcategory (ordered by revenue rank)
-- Products contributing to the top 80% are considered "eligible"
SAFE_DIVIDE(
SUM(avg_daily_revenue) OVER (
PARTITION BY dp.sub_category_name
ORDER BY r.rank_by_revenue
),
SUM(avg_daily_revenue) OVER (
PARTITION BY dp.sub_category_name
)
) AS cumulative_revenue_share

FROM product_base b
CROSS JOIN global_percentiles gp
LEFT JOIN product_rankings r ON b.product_id = r.product_id
LEFT JOIN `followbreadfast.l03_marts.dim_products` dp
ON dp.product_id = b.product_id
AND dp.country_code = 'EG'
LEFT JOIN subcat_percentiles sp ON dp.sub_category_name = sp.sub_category_name
ORDER BY r.rank_by_revenue
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 5 ▸ MIN-MAX NORMALIZATION
-- Scale revenue & quantity to 0–1 range, both globally and per subcategory.
-- This enables apples-to-apples weighting across different magnitude metrics.
--
-- Formula: normalized = (value - min) / (max - min)
-- ─────────────────────────────────────────────────────────────────────────────
normalized_products AS (
SELECT
*,

-- Global normalization
SAFE_DIVIDE(
avg_daily_revenue - MIN(avg_daily_revenue) OVER (),
MAX(avg_daily_revenue) OVER () - MIN(avg_daily_revenue) OVER ()
) AS norm_revenue_global,

SAFE_DIVIDE(
avg_daily_quantity - MIN(avg_daily_quantity) OVER (),
MAX(avg_daily_quantity) OVER () - MIN(avg_daily_quantity) OVER ()
) AS norm_quantity_global,

-- Subcategory normalization
SAFE_DIVIDE(
avg_daily_revenue - MIN(avg_daily_revenue) OVER (PARTITION BY sub_category_name),
MAX(avg_daily_revenue) OVER (PARTITION BY sub_category_name)
- MIN(avg_daily_revenue) OVER (PARTITION BY sub_category_name)
) AS norm_revenue_subcat,

SAFE_DIVIDE(
avg_daily_quantity - MIN(avg_daily_quantity) OVER (PARTITION BY sub_category_name),
MAX(avg_daily_quantity) OVER (PARTITION BY sub_category_name)
- MIN(avg_daily_quantity) OVER (PARTITION BY sub_category_name)
) AS norm_quantity_subcat

FROM tiered_products
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 6 ▸ WEIGHTED COMBINED SCORES
-- Blend normalized revenue & quantity using different weight schemes.
-- The "combined_score" is the global weight; subcat variants allow sensitivity
-- analysis on how much to weight revenue vs volume at the category level.
--
-- Weight Schemes:
-- 100rev → Pure revenue focus (current default)
-- 70rev → Revenue-dominant with volume consideration
-- 50rev → Balanced revenue and volume
-- 30rev → Volume-dominant with revenue consideration
-- ─────────────────────────────────────────────────────────────────────────────
scored_products AS (
SELECT
product_id,
product_key,
product_name_en,
commercial_category_name,
main_category_name,
sub_category_name,
brand_name,
rank_by_revenue,
rank_by_quantity,
avg_daily_revenue,
avg_daily_quantity,
global_tier,
subcat_tier,
cumulative_revenue_share,

-- Global normalized scores
norm_revenue_global,
norm_quantity_global,

-- Global combined score (100% revenue, default)
(1.0 * norm_revenue_global) + (0.0 * norm_quantity_global) AS combined_score_global,

-- Subcategory normalized scores (null-safe)
COALESCE(norm_revenue_subcat, 0) AS norm_revenue_subcat,
COALESCE(norm_quantity_subcat, 0) AS norm_quantity_subcat,

-- Subcategory combined scores (sensitivity analysis variants)
COALESCE(1.0 * norm_revenue_subcat + 0.0 * norm_quantity_subcat, 0) AS score_subcat_100rev,
COALESCE(0.7 * norm_revenue_subcat + 0.3 * norm_quantity_subcat, 0) AS score_subcat_70rev,
COALESCE(0.5 * norm_revenue_subcat + 0.5 * norm_quantity_subcat, 0) AS score_subcat_50rev,
COALESCE(0.3 * norm_revenue_subcat + 0.7 * norm_quantity_subcat, 0) AS score_subcat_30rev

FROM normalized_products
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 7 ▸ PRICE INDEX CALCULATION
-- Compare Breadfast prices against Talabat (competitor_id = 4).
--
-- For each matched product pair:
-- sale_PI = Talabat Sale Price / Breadfast Sale Price
--
-- Uses the most recent price observation per product per competitor.
-- Median price across locations handles multi-location variance.
-- ─────────────────────────────────────────────────────────────────────────────
price_index AS (

-- 7a. Talabat prices (most recent observation per competitor product)
WITH talabat_raw AS (
SELECT
h.competitor_product_id,
sale_price,
regular_price,
bf_product_id,
date_day,
location_id,
(DATE_TRUNC(date_day, DAY) >= CURRENT_DATE() - 7) AS is_recent_talabat
FROM `followbreadfast.l02_intermediate.int_pricing_tool_daily_price_history` h
INNER JOIN `followbreadfast.l02_intermediate.int_pricing_tool_product_competitor_category` pc
USING (competitor_product_key)
WHERE h.competitor_id = 4 -- Talabat
AND bf_product_id IS NOT NULL -- Must have a Breadfast match
GROUP BY ALL
QUALIFY RANK() OVER (
PARTITION BY competitor_product_id
ORDER BY date_day DESC
) = 1
),

-- Median sale price across locations for Talabat
talabat_clean AS (
SELECT
competitor_product_id,
bf_product_id,
is_recent_talabat,
APPROX_QUANTILES(regular_price, 2)[OFFSET(1)] AS talabat_regular_price,
APPROX_QUANTILES(sale_price, 2)[OFFSET(1)] AS talabat_sale_price,
date_day
FROM talabat_raw
GROUP BY ALL
),

-- 7b. Breadfast prices (most recent from price logs)
breadfast_raw AS (
WITH product_prices AS (
SELECT
date_day,
product_id,
fp_id,
MAX(CASE WHEN price_type_name = 'Sale' THEN applied_fp_product_price END) AS sale_price,
MAX(CASE WHEN price_type_name = 'Original' THEN applied_fp_product_price END) AS original_price
FROM `bf-data-dev-qz06.dbt_salma.int_mysql_fp_product_price_logs`
WHERE price_type_name IN ('Sale', 'Original')
GROUP BY ALL
)
SELECT
date_day,
pp.product_id,
fp_id,
(DATE_TRUNC(date_day, DAY) >= CURRENT_DATE() - 7) AS is_recent_breadfast,
COALESCE(sale_price, original_price) AS effective_sale_price,
original_price
FROM product_prices pp
QUALIFY RANK() OVER (
PARTITION BY pp.product_id
ORDER BY date_day DESC
) = 1
),

-- Median sale price across FPs for Breadfast
breadfast_clean AS (
SELECT
date_day,
product_id,
APPROX_QUANTILES(effective_sale_price, 2)[OFFSET(1)] AS breadfast_sale_price,
date_day AS breadfast_price_date,
is_recent_breadfast
FROM breadfast_raw
GROUP BY ALL
)

-- Final PI: Talabat / Breadfast
SELECT
b.product_id AS product_id,
t.is_recent_talabat,
b.is_recent_breadfast,
b.breadfast_sale_price,
t.talabat_sale_price,
b.date_day AS breadfast_last_updated_day,
t.date_day AS talabat_last_updated_day,
SAFE_DIVIDE(t.talabat_sale_price, b.breadfast_sale_price) AS sale_PI
FROM talabat_clean t
RIGHT JOIN breadfast_clean b
ON t.bf_product_id = b.product_id
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 8 ▸ JOIN SCORES + PRICE INDEX
-- Merge product scores with PI data.
-- Flag "newly" = TRUE when BOTH sides have prices updated in last 7 days.
-- ─────────────────────────────────────────────────────────────────────────────
products_with_pi AS (
SELECT
s.*,
pi.sale_PI,
pi.talabat_sale_price,
pi.breadfast_sale_price,
pi.is_recent_breadfast,
pi.is_recent_talabat,
pi.breadfast_last_updated_day,
pi.talabat_last_updated_day,
(pi.is_recent_breadfast AND pi.is_recent_talabat) AS prices_recently_updated
FROM scored_products s
LEFT JOIN price_index pi ON s.product_id = pi.product_id
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 9 ▸ AI MATCH CANDIDATES
-- Pull recommended competitor product matches (similarity_score from ML model).
-- These are potential Talabat mappings for currently unmapped Breadfast products.
-- ─────────────────────────────────────────────────────────────────────────────
ai_match_candidates AS (
SELECT
rcp.* EXCEPT (recommended_bf_product_id),
CAST(recommended_bf_product_id AS INT64) AS recommended_bf_product_id
FROM `followbreadfast.l03_marts.dim_recommended_bf_competitor_products` rcp
WHERE competitor_id = 4 -- Talabat matches only
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 10 ▸ FINAL PRODUCT DATA + ELIGIBILITY FLAGS
-- Apply availability filter (product must be visible on app in last 7 days).
-- Assign eligibility & action flags:
--
-- eligible_product → Within top 80% cumulative subcategory revenue
-- used_product → Eligible + has PI + prices recently updated
-- has_PI → A competitor price match exists
-- updated → Both prices updated in last 7 days
-- match_potential → AI similarity score >= 0.85 (mapping candidate)
-- ─────────────────────────────────────────────────────────────────────────────
final_product_data AS (
SELECT
w.*,

-- Eligibility: product contributes to top 80% of subcategory revenue
(cumulative_revenue_share <= 0.8) AS eligible_product,

-- Used in PI calculation: eligible + mapped + recent prices
(cumulative_revenue_share <= 0.8 AND sale_PI IS NOT NULL AND prices_recently_updated) AS used_product,

-- Has any price mapping
(sale_PI IS NOT NULL) AS has_PI,

-- Both Breadfast & Talabat prices updated in last 7 days
COALESCE(prices_recently_updated, FALSE) AS updated,

-- AI model found a high-confidence match candidate
(similarity_score >= 0.85) AS match_potential,

similarity_score

FROM products_with_pi w

-- Only include products available on the app in the last 7 days
INNER JOIN `followbreadfast.l03_marts.dim_fps_products_daily_availability` av
ON w.product_id = av.product_id
AND av.country_code = 'EG'
AND av.date_day >= CURRENT_DATE() - 7

-- Join AI match scores
LEFT JOIN ai_match_candidates amc
ON w.product_id = amc.recommended_bf_product_id

-- Filter to core FPs only
INNER JOIN `followbreadfast.l03_marts.dim_fps` fp
ON av.fp_id = fp.fp_id
AND fp.fp_name LIKE '%FP #%'


GROUP BY ALL

-- Product must be visible (either at open or close)
HAVING LOGICAL_OR(opening_available_on_app_state) = TRUE
OR LOGICAL_OR(closing_available_on_app_state) = TRUE

ORDER BY combined_score_global DESC
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 11 ▸ SUBCATEGORY AGGREGATION (Blended PI Summary)
-- Roll up product-level data into subcategory-level weighted PI metrics.
--
-- Blended PI = Σ(PI × quantity) / Σ(quantity) for used products
-- This gives higher-volume products more influence on the subcategory PI.
-- ─────────────────────────────────────────────────────────────────────────────
subcategory_summary AS (
SELECT
'sale' AS pi_type,
main_category_name,
sub_category_name,
'Blended' AS pi_status,

-- Product counts
COUNT(DISTINCT product_id) AS total_products,
COUNT(DISTINCT CASE WHEN has_PI THEN product_id END) AS mapped_products,
COUNT(DISTINCT CASE WHEN eligible_product THEN product_id END) AS eligible_products,
COUNT(DISTINCT CASE WHEN updated THEN product_id END) AS recently_updated_products,
COUNT(DISTINCT CASE WHEN used_product THEN product_id END) AS used_products,

-- Products requiring master data team action
COUNT(DISTINCT CASE
WHEN eligible_product AND (NOT has_PI OR NOT updated)
THEN product_id
END) AS needs_action_products,

-- Revenue & quantity totals
ROUND(SUM(avg_daily_revenue), 2) AS total_avg_daily_revenue,
ROUND(SUM(avg_daily_quantity), 2) AS total_avg_daily_quantity,

-- PRIMARY METRIC: Quantity-weighted blended PI
ROUND(
SAFE_DIVIDE(
SUM(CASE WHEN used_product THEN sale_PI * avg_daily_quantity END),
SUM(CASE WHEN used_product THEN avg_daily_quantity END)
), 3
) AS blended_PI,

-- Simple average PI (unweighted, for reference)
ROUND(AVG(sale_PI), 3) AS avg_PI_unweighted

FROM final_product_data
GROUP BY ALL
)


-- =============================================================================
-- OUTPUT
-- =============================================================================
-- Option A: Subcategory summary (uncomment to use)
-- SELECT * FROM subcategory_summary ORDER BY main_category_name, sub_category_name

-- Option B: Product-level detail — currently active
-- Filtered to: products WITH price mapping, excluding Breadfast-branded products
SELECT
p.*
FROM final_product_data p
ORDER BY combined_score_global DESC)