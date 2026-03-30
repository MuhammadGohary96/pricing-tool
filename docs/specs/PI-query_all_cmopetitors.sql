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
WITH competitor_registry AS (
    SELECT competitor_id, competitor_name
    FROM followbreadfast.l03_marts.dim_competitors
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 1–6: BREADFAST-INTERNAL METRICS (UNCHANGED)
-- These steps are competitor-agnostic — they compute product base metrics,
-- percentile thresholds, rankings, tiers, normalization, and scores using
-- only Breadfast data. No modifications needed for multi-competitor support.
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 0 ▸ AVAILABLE PRODUCTS
-- Products currently live on the app (available in the last 7 days).
-- ─────────────────────────────────────────────────────────────────────────────
available_products AS (
    SELECT DISTINCT
        av.product_id
    FROM `followbreadfast.l03_marts.dim_fps_products_daily_availability` av
    INNER JOIN `followbreadfast.l03_marts.dim_fps` fp
        ON av.fp_id = fp.fp_id
        AND fp.fp_name LIKE '%FP #%'
    WHERE av.country_code = 'EG'
        AND av.date_day >= CURRENT_DATE() - 7
        AND (
            av.opening_available_on_app_state = TRUE
            OR av.closing_available_on_app_state = TRUE
        )
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 1 ▸ PRODUCT BASE METRICS + DIMENSIONS
-- Average daily revenue & quantity over a rolling 3-month window.
-- Filters: Egypt · grocery vertical · single products · ≥70% in-stock
-- ─────────────────────────────────────────────────────────────────────────────
product_base AS (
    SELECT
        p.product_id,
        p.product_key,
        p.product_name_en,
        p.commercial_category_name,
        p.main_category_name,
        p.sub_category_name,
        p.brand_name,
        COALESCE(AVG(COALESCE(s.subtotal_revenue, 0)), 0) AS avg_daily_revenue,
        COALESCE(AVG(COALESCE(s.sold_quantity,     0)), 0) AS avg_daily_quantity
    FROM `followbreadfast.l04_views.agg_daily_supply_demand_scorecard` s
    LEFT JOIN `followbreadfast.l03_marts.dim_products` p
        USING (product_key)
    INNER JOIN available_products ap
        ON p.product_id = ap.product_id
    WHERE TRUE
        AND p.country_code      = 'EG'
        AND p.vertical           = 'grocery'
        AND p.product_type       = 'single'
        AND (1 - SAFE_DIVIDE(s.minutes_out_of_stock, s.ideal_available_minutes)) >= 0.7
        AND s.date_day BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 3 MONTH)
                           AND CURRENT_DATE() - 1
        AND p.main_category_id NOT IN (
            1084,  -- Coffee
            2092,  -- Pharmacy
            3018,  -- Vitamins
            -- 2055,  -- Beauty
            1858   -- Hot Food 
        )
        AND LOWER(p.sub_category_name) NOT LIKE '%bundle%'
        AND p.sub_category_name NOT IN ('AFCON Bites')
    GROUP BY
        p.product_id,
        p.product_key,
        p.product_name_en,
        p.commercial_category_name,
        p.main_category_name,
        p.sub_category_name,
        p.brand_name
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 2 ▸ PERCENTILE THRESHOLDS
-- ─────────────────────────────────────────────────────────────────────────────

-- 2a. Global percentiles
global_percentiles AS (
    SELECT
        APPROX_QUANTILES(avg_daily_revenue,  100)[OFFSET(90)] AS p90_revenue,
        APPROX_QUANTILES(avg_daily_revenue,  100)[OFFSET(80)] AS p80_revenue,
        APPROX_QUANTILES(avg_daily_revenue,  100)[OFFSET(50)] AS p50_revenue,
        APPROX_QUANTILES(avg_daily_revenue,  100)[OFFSET(25)] AS p25_revenue,
        APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(90)] AS p90_quantity,
        APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(80)] AS p80_quantity,
        APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(50)] AS p50_quantity,
        APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(25)] AS p25_quantity
    FROM product_base
),

-- 2b. Subcategory-level percentiles
subcat_percentiles AS (
    SELECT
        sub_category_name,
        APPROX_QUANTILES(avg_daily_revenue,  100)[OFFSET(90)] AS p90_revenue,
        APPROX_QUANTILES(avg_daily_revenue,  100)[OFFSET(80)] AS p80_revenue,
        APPROX_QUANTILES(avg_daily_revenue,  100)[OFFSET(50)] AS p50_revenue,
        APPROX_QUANTILES(avg_daily_revenue,  100)[OFFSET(25)] AS p25_revenue,
        APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(90)] AS p90_quantity,
        APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(80)] AS p80_quantity,
        APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(50)] AS p50_quantity,
        APPROX_QUANTILES(avg_daily_quantity, 100)[OFFSET(25)] AS p25_quantity
    FROM product_base
    GROUP BY sub_category_name
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 3 ▸ PRODUCT RANKINGS
-- ─────────────────────────────────────────────────────────────────────────────
product_rankings AS (
    SELECT
        product_id,
        DENSE_RANK() OVER (ORDER BY avg_daily_revenue  DESC) AS rank_by_revenue,
        DENSE_RANK() OVER (ORDER BY avg_daily_quantity DESC) AS rank_by_quantity
    FROM product_base
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 4 ▸ TIER ASSIGNMENT & CUMULATIVE REVENUE SHARE
-- ─────────────────────────────────────────────────────────────────────────────
tiered_products AS (
    SELECT
        b.product_id,
        b.product_key,
        b.product_name_en,
        b.commercial_category_name,
        b.main_category_name,
        b.sub_category_name,
        b.brand_name,
        r.rank_by_revenue,
        r.rank_by_quantity,
        b.avg_daily_revenue,
        b.avg_daily_quantity,
        gp.p25_revenue,
        gp.p50_revenue,
        gp.p80_revenue,
        gp.p90_revenue,
        gp.p25_quantity,
        gp.p50_quantity,
        gp.p80_quantity,
        gp.p90_quantity,

        CASE
            WHEN b.avg_daily_revenue  >= gp.p90_revenue
              OR b.avg_daily_quantity >= gp.p90_quantity THEN 'Top+'
            WHEN b.avg_daily_revenue  >= gp.p80_revenue
              OR b.avg_daily_quantity >= gp.p80_quantity THEN 'Top'
            WHEN b.avg_daily_revenue  >= gp.p50_revenue
              OR b.avg_daily_quantity >= gp.p50_quantity THEN 'Medium'
            WHEN b.avg_daily_revenue  >= gp.p25_revenue
              OR b.avg_daily_quantity >= gp.p25_quantity THEN 'Low'
            ELSE 'Very Low'
        END AS global_tier,

        CASE
            WHEN b.avg_daily_revenue  >= sp.p90_revenue
              OR b.avg_daily_quantity >= sp.p90_quantity THEN 'Top+'
            WHEN b.avg_daily_revenue  >= sp.p80_revenue
              OR b.avg_daily_quantity >= sp.p80_quantity THEN 'Top'
            WHEN b.avg_daily_revenue  >= sp.p50_revenue
              OR b.avg_daily_quantity >= sp.p50_quantity THEN 'Medium'
            WHEN b.avg_daily_revenue  >= sp.p25_revenue
              OR b.avg_daily_quantity >= sp.p25_quantity THEN 'Low'
            ELSE 'Very Low'
        END AS subcat_tier,

        SAFE_DIVIDE(
            SUM(b.avg_daily_revenue) OVER (
                PARTITION BY b.sub_category_name
                ORDER BY r.rank_by_revenue
            ),
            SUM(b.avg_daily_revenue) OVER (
                PARTITION BY b.sub_category_name
            )
        ) AS cumulative_revenue_share

    FROM product_base b
    CROSS JOIN global_percentiles gp
    LEFT JOIN product_rankings r
        ON b.product_id = r.product_id
    LEFT JOIN subcat_percentiles sp
        ON b.sub_category_name = sp.sub_category_name
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 5 ▸ MIN-MAX NORMALIZATION
-- ─────────────────────────────────────────────────────────────────────────────
normalized_products AS (
    SELECT
        *,
        SAFE_DIVIDE(
            avg_daily_revenue - MIN(avg_daily_revenue) OVER (),
            MAX(avg_daily_revenue) OVER () - MIN(avg_daily_revenue) OVER ()
        ) AS norm_revenue_global,

        SAFE_DIVIDE(
            avg_daily_quantity - MIN(avg_daily_quantity) OVER (),
            MAX(avg_daily_quantity) OVER () - MIN(avg_daily_quantity) OVER ()
        ) AS norm_quantity_global,

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
        norm_revenue_global,
        norm_quantity_global,
        (1.0 * norm_revenue_global) + (0.0 * norm_quantity_global) AS combined_score_global,
        COALESCE(norm_revenue_subcat,  0) AS norm_revenue_subcat,
        COALESCE(norm_quantity_subcat, 0) AS norm_quantity_subcat,
        COALESCE(1.0 * norm_revenue_subcat + 0.0 * norm_quantity_subcat, 0) AS score_subcat_100rev,
        COALESCE(0.7 * norm_revenue_subcat + 0.3 * norm_quantity_subcat, 0) AS score_subcat_70rev,
        COALESCE(0.5 * norm_revenue_subcat + 0.5 * norm_quantity_subcat, 0) AS score_subcat_50rev,
        COALESCE(0.3 * norm_revenue_subcat + 0.7 * norm_quantity_subcat, 0) AS score_subcat_30rev
    FROM normalized_products
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 7–8: COMPETITOR PRICE PIPELINE (REFACTORED)
-- Previously: 5 Talabat-specific CTEs with hardcoded competitor_id = 4
-- Now:        2 generic CTEs that handle ALL competitors from the registry
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 7 ▸ COMPETITOR PRICES (ALL COMPETITORS, GENERIC)
-- For each competitor in the registry:
--   1. Get the most recent price observation per competitor product
--   2. Compute median sale price across locations
--   3. Carry competitor_id and competitor_name through
--
-- The QUALIFY clause picks the latest date per competitor product.
-- The GROUP BY with APPROX_QUANTILES handles multi-location median.
-- ─────────────────────────────────────────────────────────────────────────────

-- 7a. Raw competitor prices — most recent observation per competitor product
competitor_raw AS (
    SELECT
        cr.competitor_id,
        cr.competitor_name,
        h.competitor_product_id,
        h.competitor_product_key,
        h.sale_price,
        h.regular_price,
        pc.bf_product_id,
        h.date_day,
        h.location_id,
        (DATE_TRUNC(h.date_day, DAY) >= CURRENT_DATE() - 7) AS is_recent_competitor
    FROM `followbreadfast.l02_intermediate.int_pricing_tool_daily_price_history` h
    -- Only pull competitors that are in our registry
    INNER JOIN competitor_registry cr
        ON h.competitor_id = cr.competitor_id
    INNER JOIN `followbreadfast.l02_intermediate.int_pricing_tool_product_competitor_category` pc
        USING (competitor_product_key)
    WHERE pc.bf_product_id IS NOT NULL  -- Must have a Breadfast match
    QUALIFY RANK() OVER (
        PARTITION BY h.competitor_id,pc.bf_product_id
        ORDER BY h.date_day DESC
    ) = 1
),

-- 7b. Competitor prices — median sale price across locations
competitor_clean AS (
    SELECT
        cr.competitor_id,
        cr.competitor_name,
        cr.competitor_product_id,
        cp.product_name_en                                      AS competitor_product_name,
        cr.competitor_product_key,
        cr.bf_product_id,
        cr.is_recent_competitor,
        APPROX_TOP_COUNT(cr.regular_price, 1)[OFFSET(0)].value      AS competitor_regular_price,
        APPROX_TOP_COUNT(cr.sale_price, 1)[OFFSET(0)].value       AS competitor_sale_price,
        MIN(cr.sale_price) AS min_competitor_sale_price,
        MAX(cr.sale_price) AS max_competitor_sale_price,
        cr.date_day
    FROM competitor_raw cr
    LEFT JOIN `followbreadfast.l03_marts.dim_competitor_products` cp
        ON  cr.competitor_product_key = cp.competitor_product_key
        AND cp.competitor_id = cr.competitor_id
    GROUP BY
        cr.competitor_id,
        cr.competitor_name,
        cr.competitor_product_id,
        cp.product_name_en,
        cr.competitor_product_key,
        cr.bf_product_id,
        cr.is_recent_competitor,
        cr.date_day
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 8 ▸ BREADFAST PRICES (UNCHANGED)
-- Breadfast-side prices are competitor-agnostic — computed once, joined many.
-- ─────────────────────────────────────────────────────────────────────────────

-- 8a. Breadfast prices — pivot sale/original then pick most recent
breadfast_product_prices AS (
    SELECT
        date_day,
        product_id,
        fp_id,
        MAX(CASE WHEN price_type_name = 'Sale'     THEN applied_fp_product_price END) AS sale_price,
        MAX(CASE WHEN price_type_name = 'Original'  THEN applied_fp_product_price END) AS original_price
    FROM `bf-data-dev-qz06.dbt_salma.int_mysql_fp_product_price_logs`
    WHERE price_type_name IN ('Sale', 'Original')
    GROUP BY
        date_day,
        product_id,
        fp_id
),

breadfast_raw AS (
    SELECT
        date_day,
        product_id,
        fp_id,
        (DATE_TRUNC(date_day, DAY) >= CURRENT_DATE() - 7) AS is_recent_breadfast,
        COALESCE(sale_price, original_price)               AS effective_sale_price,
        original_price
    FROM breadfast_product_prices
    QUALIFY RANK() OVER (
        PARTITION BY product_id
        ORDER BY date_day DESC
    ) = 1
),

-- 8b. Breadfast — median sale price across FPs
breadfast_clean AS (
    SELECT
        date_day,
        product_id,
        APPROX_TOP_COUNT(effective_sale_price, 1)[OFFSET(0)].value AS breadfast_sale_price,
        date_day                                              AS breadfast_price_date,
        is_recent_breadfast
    FROM breadfast_raw
    GROUP BY
        date_day,
        product_id,
        is_recent_breadfast
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 9 ▸ PRICE INDEX CALCULATION (MULTI-COMPETITOR)
-- Previously: Single PI per product (Talabat only)
-- Now:        One PI row per product × competitor pair
--
-- The RIGHT JOIN on breadfast_clean ensures every BF product appears even
-- if it has no competitor match. Unmatched products get NULL competitor cols.
--
-- sale_PI = Breadfast Sale Price / Competitor Sale Price
--   PI > 1 → BF is cheaper | PI < 1 → BF is more expensive
-- ─────────────────────────────────────────────────────────────────────────────
price_index AS (
    SELECT
        b.product_id,
        c.competitor_id,
        c.competitor_name,
        c.competitor_product_name,
        c.is_recent_competitor,
        b.is_recent_breadfast,
        b.breadfast_sale_price,
        c.competitor_sale_price,
        c.min_competitor_sale_price,
        c.max_competitor_sale_price,
        b.date_day                                             AS breadfast_last_updated_day,
        c.date_day                                             AS competitor_last_updated_day,
        SAFE_DIVIDE(b.breadfast_sale_price,c.competitor_sale_price) AS sale_PI
    FROM competitor_clean c
    INNER JOIN breadfast_clean b
        ON c.bf_product_id = b.product_id
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 10–11: JOIN + FLAGS (COMPETITOR-AWARE)
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 10 ▸ JOIN SCORES + PRICE INDEX (MULTI-COMPETITOR)
-- Each scored product is joined to ALL its competitor PI rows.
-- A product mapped to 3 competitors produces 3 output rows.
-- A product with NO competitor mapping produces 1 row with NULL competitor cols.
--
-- The Breadfast-side columns (tiers, scores, revenue, quantity) repeat
-- across rows — BigQuery columnar compression handles this efficiently.
-- ─────────────────────────────────────────────────────────────────────────────
products_with_pi AS (
    SELECT
        s.*,
        cr.competitor_id,
        cr.competitor_name,
        pi.competitor_product_name,
        pi.sale_PI,
        pi.competitor_sale_price,
        pi.min_competitor_sale_price,
        pi.max_competitor_sale_price,
        b.breadfast_sale_price,
        b.is_recent_breadfast,
        pi.is_recent_competitor,
        b.date_day  breadfast_last_updated_day,
        pi.competitor_last_updated_day,
        (pi.is_recent_breadfast AND pi.is_recent_competitor) AS prices_recently_updated
    FROM scored_products s
    CROSS JOIN competitor_registry cr
    LEFT JOIN price_index pi
        ON s.product_id = pi.product_id
        AND cr.competitor_id = pi.competitor_id
    LEFT JOIN breadfast_clean b on 
    s.product_id = b.product_id
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 11 ▸ AI MATCH CANDIDATES (MULTI-COMPETITOR)
-- Previously: Hardcoded to competitor_id = 4
-- Now:        Pulls matches for ALL competitors in the registry.
-- The competitor_id is carried so we can join precisely per competitor.
-- ─────────────────────────────────────────────────────────────────────────────
ai_match_candidates AS (
    SELECT
        CAST(rcp.recommended_bf_product_id AS INT64) AS recommended_bf_product_id,
        rcp.competitor_id,
        rcp.similarity_score,
        cp.product_name_en                           AS match_potential_product_name
    FROM `followbreadfast.l03_marts.dim_recommended_bf_competitor_products` rcp
    -- Only competitors in our registry
    INNER JOIN competitor_registry cr
        ON rcp.competitor_id = cr.competitor_id
    LEFT JOIN `followbreadfast.l03_marts.dim_competitor_products` cp
        ON  rcp.competitor_product_id = cp.competitor_product_id
        AND cp.competitor_id = rcp.competitor_id
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 12 ▸ FINAL PRODUCT DATA + ELIGIBILITY FLAGS (MULTI-COMPETITOR)
-- Each row = one product × one competitor.
-- Flags are now PER-COMPETITOR:
--   has_PI       → This specific competitor has a price match
--   updated      → Both BF and THIS competitor prices updated in last 7 days
--   used_product → Eligible + has_PI for THIS competitor + updated
--   match_potential → AI model suggests a match for THIS competitor
--
-- action_type is computed per product × competitor pair:
--   Needs Mapping   → No PI for this competitor, no AI match candidate
--   Review AI Match → No PI, but AI found a candidate (score ≥ 0.85)
--   Needs Update    → Has PI, but prices are stale (>7 days)
--   Complete        → Has PI and prices are fresh
-- ─────────────────────────────────────────────────────────────────────────────
final_product_data AS (
    SELECT
        w.*,

        -- Eligibility: product contributes to top 80% of subcategory revenue
        -- (this is competitor-agnostic — same value across all competitor rows)
        (w.cumulative_revenue_share <= 0.8)                     AS eligible_product,

        -- Per-competitor: used in PI calculation
        (w.cumulative_revenue_share <= 0.8
            AND w.sale_PI IS NOT NULL
            AND w.prices_recently_updated)                      AS used_product,

        -- Per-competitor: has any price mapping
        (w.sale_PI IS NOT NULL)                                 AS has_PI,

        -- Per-competitor: both prices updated in last 7 days
        COALESCE(w.prices_recently_updated, FALSE)              AS updated,

        -- Per-competitor: AI model found a high-confidence match
        (amc.similarity_score >= 0.85)                          AS match_potential,
        amc.similarity_score,
        amc.match_potential_product_name,

        -- Per-competitor: action type for master data team
        CASE
            WHEN w.sale_PI IS NULL AND (amc.similarity_score IS NULL OR amc.similarity_score < 0.85)
                THEN 'Needs Mapping'
            WHEN w.sale_PI IS NULL AND amc.similarity_score >= 0.85
                THEN 'Review AI Match'
            WHEN w.sale_PI IS NOT NULL AND NOT COALESCE(w.prices_recently_updated, FALSE)
                THEN 'Needs Price Update'
            ELSE 'Complete'
        END                                                     AS action_type,
        -- ─────────────────────────────────────────────────────────────
        -- CLASSIFICATION (per sketch)
        -- Mapped     = has_PI (sale_PI IS NOT NULL)
        -- PL         = brand_name = 'Breadfast'
        -- Pot        = match_potential (similarity_score >= 0.85)
        -- Eligible   = cumulative_revenue_share <= 0.8
        -- ─────────────────────────────────────────────────────────────
        CASE
            -- ── Branch 1: MAPPED ─────────────────────────────────────
            -- Eligible PL is crossed out in the sketch (excluded/ignored)
            -- Only "Not Eligible / Not PL" is a valid leaf
            WHEN w.sale_PI IS NOT NULL
                AND NOT (w.brand_name = 'Breadfast')            -- Not PL
                THEN 'Mapped - Not PL'

            WHEN w.sale_PI IS NOT NULL
                AND w.brand_name = 'Breadfast'                  -- PL 
                THEN 'Mapped - PL'

            -- ── Branch 2: NOT MAPPED ─────────────────────────────────
            -- Sub-branch: PL (brand = Breadfast)
            WHEN w.sale_PI IS NULL
                AND w.brand_name = 'Breadfast'
                AND (amc.similarity_score >= 0.85)              -- Pot
                THEN 'Not Mapped - PL - Potential Match'

            WHEN w.sale_PI IS NULL
                AND w.brand_name = 'Breadfast'
                AND (amc.similarity_score IS NULL OR amc.similarity_score < 0.85) -- Not Pot
                THEN 'Not Mapped - PL - No Potential Match'

            -- Sub-branch: Not PL
            WHEN w.sale_PI IS NULL
                AND w.brand_name != 'Breadfast'
                AND (amc.similarity_score >= 0.85)         -- Pot
                THEN 'Not Mapped - Not PL - Potential Match'

            WHEN w.sale_PI IS NULL
                AND w.brand_name != 'Breadfast'
                AND (amc.similarity_score IS NULL OR amc.similarity_score < 0.85) -- Not Pot
                THEN 'Not Mapped - Not PL - No Potential Match'

            ELSE 'Unclassified'
        END                                                     AS classification


    FROM products_with_pi w
    LEFT JOIN ai_match_candidates amc
        ON  w.product_id = amc.recommended_bf_product_id
        AND w.competitor_id = amc.competitor_id
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 13 ▸ SUBCATEGORY AGGREGATION PER COMPETITOR
-- Roll up product-level data into subcategory × competitor summaries.
--
-- Blended PI = Σ(PI × quantity) / Σ(quantity) for used products
-- Each subcategory now has one row per competitor.
-- ─────────────────────────────────────────────────────────────────────────────
subcategory_summary AS (
    SELECT
        competitor_id,
        competitor_name,
        main_category_name,
        sub_category_name,

        -- Product counts
        COUNT(DISTINCT product_id)                                                      AS total_products,
        COUNT(DISTINCT CASE WHEN has_PI           THEN product_id END)                  AS mapped_products,
        COUNT(DISTINCT CASE WHEN eligible_product THEN product_id END)                  AS eligible_products,
        COUNT(DISTINCT CASE WHEN updated          THEN product_id END)                  AS recently_updated_products,
        COUNT(DISTINCT CASE WHEN used_product     THEN product_id END)                  AS used_products,

        -- Products requiring master data team action for this competitor
        COUNT(DISTINCT CASE
            WHEN eligible_product AND action_type != 'Complete'
            THEN product_id
        END)                                                                            AS needs_action_products,

        -- Revenue & quantity totals
        ROUND(SUM(avg_daily_revenue),  2)                                               AS total_avg_daily_revenue,
        ROUND(SUM(avg_daily_quantity), 2)                                               AS total_avg_daily_quantity,

        -- PRIMARY METRIC: quantity-weighted blended PI for this competitor
        ROUND(
            SAFE_DIVIDE(
                SUM(CASE WHEN used_product THEN sale_PI * avg_daily_quantity END),
                SUM(CASE WHEN used_product THEN avg_daily_quantity           END)
            ), 3
        )                                                                               AS blended_PI,

        -- Simple average PI (unweighted, for reference)
        ROUND(AVG(CASE WHEN sale_PI IS NOT NULL THEN sale_PI END), 3)                   AS avg_PI_unweighted,

        -- Coverage: percentage of eligible products that are "used"
        ROUND(
            SAFE_DIVIDE(
                COUNT(DISTINCT CASE WHEN used_product     THEN product_id END),
                COUNT(DISTINCT CASE WHEN eligible_product THEN product_id END)
            ) * 100, 1
        )                                                                               AS coverage_pct

    FROM final_product_data
    WHERE competitor_id IS NOT NULL  -- Exclude unmapped-product ghost rows
    GROUP BY
        competitor_id,
        competitor_name,
        main_category_name,
        sub_category_name
)
-- =============================================================================
-- OUTPUT OPTIONS
-- =============================================================================
-- Uncomment the query you need:

-- ── Option A: Product × Competitor detail (main output) ──
SELECT p.* FROM final_product_data p 
ORDER BY p.combined_score_global DESC

-- ── Option B: Subcategory summary per competitor ──
-- SELECT * FROM subcategory_summary ORDER BY competitor_name, main_category_name, sub_category_name

-- ── Option C: Cross-competitor product summary (executive view) ──
-- SELECT * FROM cross_competitor_summary ORDER BY avg_daily_revenue DESC

-- ── Option D: Subcategory summary for a SINGLE competitor (legacy mode) ──
-- SELECT * FROM subcategory_summary WHERE competitor_name = 'Talabat' ORDER BY main_category_name, sub_category_name
)