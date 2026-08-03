-- ═══════════════════════════════════════════════════════════════════════════
-- COMPETITIVE PRICING INTELLIGENCE — MULTI-COMPETITOR × MULTI-FP PRICE INDEX
-- ═══════════════════════════════════════════════════════════════════════════
-- Produces a product × fp × competitor grid with sale price index (sale_PI),
-- mapping completeness flags, action_type for the master-data workflow, and
-- a classification tree (Mapped × PL × Potential Match).
--
-- Mapping vs Pricing separation:
--   is_mapped → product-level: this BF product is linked to a competitor
--               product in at least one FP. Carries to every FP.
--   has_PI    → fp-level: this FP has an actual price observation for the
--               (product, competitor) pair, so sale_PI is computable.
--
-- Competitor scope: the seven benchmarked competitors (Amazon, Amazon Now,
-- Seoudi, Talabat, Noon Minutes, Rabbit, Carrefour).
-- FP scope: active FPs matching "<Area> FP #<number>" or named "*Sahel*",
-- and not in SLEEP.
-- (product, fp) pairs are only emitted when:
--   • Breadfast has a price record for the SKU in that FP, AND
--   • the SKU was live in the app in that FP in the last 7 days.
--
-- Output is a UNION of two row types, discriminated by `row_type`:
--   'breadfast'  → one row per (product, fp, competitor) from final_product_data,
--                  plus the gap-analysis columns (STEPS 15-20).
--   'competitor' → the national competitor-only catalogue: competitor products
--                  we do not carry. fp_id / fp_name are NULL and product_id is
--                  NULL, so these rows MUST NOT flow through the app's
--                  _BASE_CTE (which collapses on (product_id, competitor_id)).
-- Alternative roll-up: (fp, subcategory, competitor) via subcategory_summary.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE TABLE dbt_gohary.competitor_price_monitoring_fps AS (
WITH
-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 0a ▸ COMPETITOR REGISTRY
-- The seven competitors we benchmark against. competitor_key is carried so we
-- can join the daily comparison fact (which keys on competitor_key, not
-- competitor_id).
-- ─────────────────────────────────────────────────────────────────────────────
competitor_registry AS (
    SELECT
        competitor_id,
        competitor_key,
        competitor_name
    FROM `followbreadfast.l03_marts.dim_competitors`
    WHERE competitor_name IN ('Amazon', 'Amazon Now', 'Seoudi', 'Talabat', 'Noon Minutes', 'Rabbit', 'Carrefour')
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 0b ▸ FP REGISTRY
-- Active FPs whose name ends with "FP #<number>", plus the Sahel FPs (which do
-- not follow that naming convention), and are not currently sleeping.
-- ─────────────────────────────────────────────────────────────────────────────
fp_registry AS (
    SELECT
        fp_id,
        fp_name
    FROM `followbreadfast.l03_marts.dim_fps`
    WHERE (REGEXP_CONTAINS(fp_name, r'FP #\d+$') OR lower(fp_name) LIKE '%sahel%')
        AND current_fp_now_status != 'SLEEP'
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 0c ▸ FP × SKU AVAILABILITY  (retained — not a price-index source, but
-- kept per the requested scope to preserve the active-assortment universe)
-- (product, fp) pairs where the SKU was live in the app at least once in the
-- last 7 days. INNER-JOIN gate in STEP 7.
-- ─────────────────────────────────────────────────────────────────────────────
fps_available_products AS (
    SELECT DISTINCT
        av.fp_id,
        av.product_id
    FROM `followbreadfast.l03_marts.dim_fps_products_daily_availability` av
    INNER JOIN fp_registry fp
        ON av.fp_id = fp.fp_id
    WHERE av.country_code = 'EG'
        AND av.date_day >= CURRENT_DATE() - 7
        AND (
            av.opening_available_on_app_state = TRUE
            OR av.closing_available_on_app_state = TRUE
        )
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 1–5 ▸ BREADFAST-INTERNAL METRICS (PRODUCT GRAIN, GLOBAL)  — UNCHANGED
-- Sourced from dim_product_commercial_profile + dim_products (already the
-- metric's product-side sources).
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 1 ▸ AVAILABLE PRODUCTS
-- ─────────────────────────────────────────────────────────────────────────────
available_products AS (
    SELECT *
    FROM `followbreadfast.l03_marts.dim_product_commercial_profile`
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 2 ▸ PRODUCT BASE METRICS + DIMENSIONS
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
        s.avg_daily_revenue_last3_months AS avg_daily_revenue,
        s.avg_daily_quantity_last3_months AS avg_daily_quantity,
        s.global_tier_last3_months AS global_tier,
        s.subcat_tier_last3_months AS subcat_tier,
        s.cumulative_sum_revenue_per_product,
        s.cumulative_revenue_share
    FROM available_products s
    LEFT JOIN `followbreadfast.l03_marts.dim_products` p
        USING (product_key)
    WHERE TRUE
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 3 ▸ PRODUCT RANKINGS
-- ─────────────────────────────────────────────────────────────────────────────
product_rankings AS (
    SELECT
        *,
        DENSE_RANK() OVER (ORDER BY avg_daily_revenue DESC) AS rank_by_revenue,
        DENSE_RANK() OVER (ORDER BY avg_daily_quantity DESC) AS rank_by_quantity
    FROM product_base
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 4 ▸ MIN-MAX NORMALIZATION (GLOBAL + SUBCATEGORY)
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
    FROM product_rankings
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 5 ▸ WEIGHTED COMBINED SCORES
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

        -- Global score (revenue-only blend)
        norm_revenue_global,
        norm_quantity_global,
        (1.0 * norm_revenue_global) + (0.0 * norm_quantity_global) AS combined_score_global,

        -- Subcategory scores with multiple revenue/quantity weight blends
        COALESCE(norm_revenue_subcat, 0) AS norm_revenue_subcat,
        COALESCE(norm_quantity_subcat, 0) AS norm_quantity_subcat,
        COALESCE(1.0 * norm_revenue_subcat + 0.0 * norm_quantity_subcat, 0) AS score_subcat_100rev,
        COALESCE(0.7 * norm_revenue_subcat + 0.3 * norm_quantity_subcat, 0) AS score_subcat_70rev,
        COALESCE(0.5 * norm_revenue_subcat + 0.5 * norm_quantity_subcat, 0) AS score_subcat_50rev,
        COALESCE(0.3 * norm_revenue_subcat + 0.7 * norm_quantity_subcat, 0) AS score_subcat_30rev
    FROM normalized_products
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 6–7 ▸ BREADFAST PRICE ENRICHMENT (PER FP) + ACTIVITY GATE  — UNCHANGED
-- Retained as the driver grid: establishes the (product, fp) universe that has
-- a BF price AND active assortment, so unmapped products still appear.
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 6 ▸ BREADFAST PRICES — LATEST SCD ROW PER (PRODUCT, FP)
-- ─────────────────────────────────────────────────────────────────────────────
products_enriched_prices_1 AS (
    SELECT
        s.*,
        p.fp_id,
        fr.fp_name,
        p.applied_regular_price,
        COALESCE(NULLIF(p.applied_sale_price, 0), p.applied_regular_price) AS applied_sale_price,
        CASE
            WHEN p.valid_to_ltz >= CURRENT_DATE() THEN CURRENT_DATE()
            ELSE DATE(p.valid_to_ltz)
        END AS breadfast_last_updated_day
    FROM scored_products s
    INNER JOIN `followbreadfast.l03_marts.dim_fp_product_price_logs_scd` p
        ON s.product_key = p.product_key
    INNER JOIN fp_registry fr
        ON p.fp_id = fr.fp_id
    QUALIFY RANK() OVER (
        PARTITION BY p.product_key, p.fp_id
        ORDER BY p.valid_to_ltz DESC
    ) = 1
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 7 ▸ BREADFAST PRICES — COLLAPSE TIES + GATE ON SKU ACTIVITY
-- ─────────────────────────────────────────────────────────────────────────────
products_enriched_prices_2 AS (
    SELECT
        s.* EXCEPT (applied_regular_price, applied_sale_price, breadfast_last_updated_day),
        APPROX_TOP_COUNT(applied_regular_price, 1)[OFFSET(0)].value AS bf_regular_price,
        APPROX_TOP_COUNT(applied_sale_price, 1)[OFFSET(0)].value AS bf_sale_price,
        MAX(breadfast_last_updated_day) AS breadfast_last_updated_day,
        MAX(breadfast_last_updated_day) >= CURRENT_DATE() - 7 AS is_recent_breadfast
    FROM products_enriched_prices_1 s
    INNER JOIN fps_available_products av
        ON s.product_id = av.product_id
        AND s.fp_id = av.fp_id
    GROUP BY ALL
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 8–10 ▸ COMPETITOR PRICE PIPELINE — RE-SOURCED ONTO THE DAILY FACT
--   Step 8  — latest daily-comparison row per (competitor, BF product, fp).
--   Step 9  — thin enrichment (names, freshness); no location collapse needed.
--   Step 9b — product-level mapping (collapses across FPs).
--   Step 10 — sale_PI = bf_eod_sale_price ÷ last_seen_sale_price (matches metric).
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 8 ▸ COMPETITOR PRICES — LATEST DAILY OBSERVATION (PER FP)
-- One row per (competitor, mapped BF product, fp): the most recent comparison
-- day. The marts table already prefers the cleaned/latest crawl and is
-- location-collapsed, so the v2/valid_to/location logic is gone. Keys are
-- bridged to ids via the dims (competitor_key→id, product_key→id).
-- ─────────────────────────────────────────────────────────────────────────────
competitor_raw AS (
    SELECT
        cr.competitor_id,
        cr.competitor_name,
        fr.fp_id,
        fr.fp_name,
        dcp.competitor_product_id,
        dcp.product_name_en AS competitor_product_name,
        h.competitor_product_key,
        dp.product_id AS bf_product_id,

        -- Prices straight from the metric's source table
        NULLIF(h.last_seen_sale_price, 0)    AS sale_price,        -- competitor sale (carry-forward, >0)
        NULLIF(h.last_seen_regular_price, 0) AS regular_price,
        NULLIF(h.bf_eod_sale_price, 0)       AS bf_sale_price,     -- Breadfast end-of-day sale
        NULLIF(h.bf_eod_regular_price, 0)    AS bf_regular_price,

        -- Freshness == the metric's recently_crawled gate
        h.days_since_crawl,
        (h.days_since_crawl <= 7) AS is_recent_competitor,

        -- Actual last crawl date (date_day is the comparison day)
        DATE_SUB(h.date_day, INTERVAL h.days_since_crawl DAY) AS date_day
    FROM `followbreadfast.l03_marts.fct_daily_competitor_price_comparison` h
    INNER JOIN competitor_registry cr
        ON h.competitor_key = cr.competitor_key
    INNER JOIN fp_registry fr
        ON h.fp_id = fr.fp_id
    LEFT JOIN `followbreadfast.l03_marts.dim_products` dp
        ON h.mapped_product_key = dp.product_key
    LEFT JOIN `followbreadfast.l03_marts.dim_competitor_products` dcp
        ON h.competitor_product_key = dcp.competitor_product_key
        AND dcp.competitor_id = cr.competitor_id
    WHERE h.mapped_product_key IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY cr.competitor_id, h.mapped_product_key, h.fp_id
        ORDER BY
            h.date_day DESC,            -- freshest comparison day
            h.days_since_crawl ASC,     -- freshest crawl
            h.competitor_product_key    -- deterministic tiebreak
    ) = 1
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 9 ▸ COMPETITOR PRICES — ENRICH (no location collapse; table is already
-- one price per fp). MIN/MAX retained as the point value for schema parity —
-- within-fp location spread is not available from the daily comparison table.
-- ─────────────────────────────────────────────────────────────────────────────
competitor_clean AS (
    SELECT
        competitor_id,
        competitor_name,
        fp_id,
        fp_name,
        competitor_product_id,
        competitor_product_name,
        competitor_product_key,
        bf_product_id,

        is_recent_competitor,
        date_day,

        regular_price AS competitor_regular_price,
        sale_price    AS competitor_sale_price,
        bf_regular_price AS breadfast_regular_price,
        bf_sale_price    AS breadfast_sale_price,

        -- No location spread in the daily fact → point value
        sale_price AS min_competitor_sale_price,
        sale_price AS max_competitor_sale_price
    FROM competitor_raw
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 9b ▸ COMPETITOR MAPPING (PRODUCT-LEVEL, FP-AGNOSTIC)  — UNCHANGED LOGIC
-- A BF product is "mapped" to a competitor if any FP has an observation linking
-- them. Most recent observation wins for link details.
-- ─────────────────────────────────────────────────────────────────────────────
competitor_mapping AS (
    SELECT
        bf_product_id,
        competitor_id,
        competitor_name,
        ANY_VALUE(competitor_product_id HAVING MAX date_day) AS competitor_product_id,
        ANY_VALUE(competitor_product_key HAVING MAX date_day) AS competitor_product_key,
        ANY_VALUE(competitor_product_name HAVING MAX date_day) AS competitor_product_name
    FROM competitor_clean
    GROUP BY bf_product_id, competitor_id, competitor_name
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 10 ▸ PRICE INDEX CALCULATION (PER FP)
--   sale_PI = bf_eod_sale_price / last_seen_sale_price  →  identical to the
--   fp_sale_price_index metric's row-level sale_pi.
-- ─────────────────────────────────────────────────────────────────────────────
price_index AS (
    SELECT
        c.bf_product_id AS product_id,
        c.competitor_id,
        c.competitor_name,
        c.fp_id,
        c.fp_name,
        c.is_recent_competitor,
        c.breadfast_sale_price,
        c.competitor_sale_price,
        c.min_competitor_sale_price,
        c.max_competitor_sale_price,
        c.date_day AS competitor_last_updated_day,
        SAFE_DIVIDE(c.breadfast_sale_price, c.competitor_sale_price) AS sale_PI
    FROM competitor_clean c
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 11–13 ▸ ASSEMBLY, AI CANDIDATES, FLAGS & CLASSIFICATION
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 11 ▸ JOIN SCORES + MAPPING + PRICE INDEX
-- Driver: products_enriched_prices_2 (gated on activity + BF SCD pricing).
-- BF price for PI rows comes from the comparison fact (bf_eod); SCD is the
-- fallback + the source of BF freshness (the daily fact has no BF-price age).
-- ─────────────────────────────────────────────────────────────────────────────
products_with_pi AS (
    SELECT
        s.* EXCEPT (is_recent_breadfast, bf_sale_price, breadfast_last_updated_day),

        cr.competitor_id,
        cr.competitor_name,

        -- Link details (broadcast to every FP for this product × competitor)
        cm.competitor_product_id,
        cm.competitor_product_name,

        -- Price details (NULL where this FP has no observation)
        pi.sale_PI,
        pi.competitor_sale_price,
        pi.min_competitor_sale_price,
        pi.max_competitor_sale_price,

        -- BF price: competitor-side (bf_eod) wins where present; else SCD-derived
        COALESCE(pi.breadfast_sale_price, s.bf_sale_price) AS breadfast_sale_price,

        -- BF freshness always from the SCD (daily fact carries no BF-price age)
        s.is_recent_breadfast,
        pi.is_recent_competitor,
        s.breadfast_last_updated_day,
        pi.competitor_last_updated_day,

        -- Both sides fresh (≤ 7 days)
        (s.is_recent_breadfast AND pi.is_recent_competitor) AS prices_recently_updated,

        -- Product-level mapping flag (carries across FPs)
        (cm.competitor_product_id IS NOT NULL) AS is_mapped
    FROM products_enriched_prices_2 s
    CROSS JOIN competitor_registry cr
    LEFT JOIN competitor_mapping cm
        ON s.product_id = cm.bf_product_id
        AND cr.competitor_id = cm.competitor_id
    LEFT JOIN price_index pi
        ON s.product_id = pi.product_id
        AND s.fp_id = pi.fp_id
        AND cr.competitor_id = pi.competitor_id
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 12 ▸ AI MATCH CANDIDATES (PRODUCT-LEVEL, REPLICATED ACROSS FPS) — UNCHANGED
-- ─────────────────────────────────────────────────────────────────────────────
ai_match_candidates AS (
    SELECT
        CAST(rcp.bf_product_id AS INT64) AS recommended_bf_product_id,
        rcp.competitor_id,
        rcp.similarity_score,
        cp.product_name_en AS match_potential_product_name,
        rcp.is_matched
    FROM `followbreadfast.l03_marts.dim_recommended_bf_competitor_products` rcp
    INNER JOIN competitor_registry cr
        ON rcp.competitor_id = cr.competitor_id
    LEFT JOIN `followbreadfast.l03_marts.dim_competitor_products` cp
        ON rcp.competitor_product_id = cp.competitor_product_id
        AND cp.competitor_id = rcp.competitor_id
    QUALIFY ROW_NUMBER() OVER (PARTITION BY rcp.bf_product_id, rcp.competitor_id
  ORDER BY rcp.similarity_score DESC) = 1
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 13 ▸ FINAL PRODUCT DATA + ELIGIBILITY / ACTION FLAGS  — UNCHANGED LOGIC
-- (has_PI now reflects a carried-forward price; stale-but-priced rows route to
--  'Needs Price Update' rather than 'Needs Price for FP'.)
-- ─────────────────────────────────────────────────────────────────────────────
final_product_data AS (
    SELECT
        w.*,

        -- Eligibility (product-level, global)
        (w.cumulative_revenue_share <= 0.8) AS eligible_product,

        -- has_PI = price exists in THIS FP
        (w.competitor_sale_price IS NOT NULL) AS has_PI,

        -- used_product = eligible + priced in this FP + fresh (activity already gated)
        (w.cumulative_revenue_share <= 0.8
            AND w.competitor_sale_price IS NOT NULL
            AND w.prices_recently_updated) AS used_product,

        COALESCE(w.prices_recently_updated, FALSE) AS updated,
        (amc.similarity_score >= 0.85) AS match_potential,
        amc.similarity_score,
        amc.match_potential_product_name,

        -- Master-data workflow status per (product, fp, competitor)
        CASE
            WHEN NOT w.is_mapped
                 AND (amc.similarity_score IS NULL OR amc.similarity_score < 0.85)
                THEN 'Needs Mapping'
            WHEN NOT w.is_mapped
                 AND amc.similarity_score >= 0.85
                THEN 'Review AI Match'
            WHEN w.is_mapped
                 AND w.competitor_sale_price IS NULL
                THEN 'Needs Price for FP'
            WHEN w.competitor_sale_price IS NOT NULL
                 AND NOT COALESCE(w.prices_recently_updated, FALSE)
                THEN 'Needs Price Update'
            ELSE 'Complete'
        END AS action_type,

        -- ─── Classification tree (Mapped is product-level) ──────────────────
        CASE
            -- Branch 1: MAPPED
            WHEN w.sale_PI IS NOT NULL AND w.brand_name != 'Breadfast'
                THEN 'Mapped - Not PL'
            WHEN w.sale_PI IS NOT NULL AND w.brand_name = 'Breadfast'
                THEN 'Mapped - PL'

            -- Branch 2a: NOT MAPPED — PL
            WHEN w.sale_PI IS NULL
                 AND w.brand_name = 'Breadfast'
                 AND NOT is_matched
                THEN 'Not Mapped - PL - No Match'
            WHEN w.sale_PI IS NULL
                 AND w.brand_name = 'Breadfast'
                 AND amc.similarity_score >= 0.85
                THEN 'Not Mapped - PL - Potential Match'
            WHEN w.sale_PI IS NULL
                 AND w.brand_name = 'Breadfast'
                 AND (amc.similarity_score IS NULL OR amc.similarity_score < 0.85)
                THEN 'Not Mapped - PL - No Potential Match'

            -- Branch 2b: NOT MAPPED — Not PL
            WHEN w.sale_PI IS NULL
                 AND w.brand_name != 'Breadfast'
                 AND NOT is_matched
                THEN 'Not Mapped - Not PL - No Match'
            WHEN w.sale_PI IS NULL
                 AND w.brand_name != 'Breadfast'
                 AND amc.similarity_score >= 0.85
                THEN 'Not Mapped - Not PL - Potential Match'
            WHEN w.sale_PI IS NULL
                 AND w.brand_name != 'Breadfast'
                 AND (amc.similarity_score IS NULL OR amc.similarity_score < 0.85)
                THEN 'Not Mapped - Not PL - No Potential Match'

            ELSE 'Unclassified'
        END AS classification

    FROM products_with_pi w
    LEFT JOIN ai_match_candidates amc
        ON w.product_id = amc.recommended_bf_product_id
        AND w.competitor_id = amc.competitor_id
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 14 ▸ (FP × SUBCATEGORY × COMPETITOR) ROLL-UP (optional output) — UNCHANGED
-- ─────────────────────────────────────────────────────────────────────────────
subcategory_summary AS (
    SELECT
        competitor_id,
        competitor_name,
        fp_id,
        fp_name,
        main_category_name,
        sub_category_name,

        -- Product counts
        COUNT(DISTINCT product_id) AS total_products,
        COUNT(DISTINCT CASE WHEN is_mapped THEN product_id END) AS mapped_products,
        COUNT(DISTINCT CASE WHEN has_PI    THEN product_id END) AS priced_products,
        COUNT(DISTINCT CASE WHEN is_mapped AND NOT has_PI THEN product_id END) AS mapped_no_price_products,
        COUNT(DISTINCT CASE WHEN eligible_product THEN product_id END) AS eligible_products,
        COUNT(DISTINCT CASE WHEN updated THEN product_id END) AS recently_updated_products,
        COUNT(DISTINCT CASE WHEN used_product THEN product_id END) AS used_products,

        -- Action backlog for the master-data team
        COUNT(DISTINCT CASE
            WHEN eligible_product AND action_type != 'Complete'
            THEN product_id
        END) AS needs_action_products,

        -- Revenue & quantity totals
        ROUND(SUM(avg_daily_revenue), 2) AS total_avg_daily_revenue,
        ROUND(SUM(avg_daily_quantity), 2) AS total_avg_daily_quantity,

        -- PRIMARY METRIC — quantity-weighted blended PI within (fp, subcategory)
        ROUND(
            SAFE_DIVIDE(
                SUM(CASE WHEN used_product THEN sale_PI * avg_daily_quantity END),
                SUM(CASE WHEN used_product THEN avg_daily_quantity END)
            ), 3
        ) AS blended_PI,

        -- Reference — unweighted average PI
        ROUND(AVG(CASE WHEN sale_PI IS NOT NULL THEN sale_PI END), 3) AS avg_PI_unweighted,

        -- Coverage of the eligible set within (fp, subcategory)
        ROUND(
            SAFE_DIVIDE(
                COUNT(DISTINCT CASE WHEN used_product THEN product_id END),
                COUNT(DISTINCT CASE WHEN eligible_product THEN product_id END)
            ) * 100, 1
        ) AS coverage_pct
    FROM final_product_data
    WHERE competitor_id IS NOT NULL
    GROUP BY
        competitor_id,
        competitor_name,
        fp_id,
        fp_name,
        main_category_name,
        sub_category_name
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 15-20 ▸ GAP-ANALYSIS LAYER (added 2026-08-03)
-- ADDITIVE GAP-ANALYSIS LAYER for competitor_price_monitoring_fps
-- =============================================================================
-- Splice into docs/FP_granularity_pricing.sql (CREATE OR REPLACE TABLE
-- dbt_gohary.competitor_price_monitoring_fps) after STEP 12
-- (ai_match_candidates) / STEP 13 (final_product_data).
--
-- SOURCE CONTRACT (revised 2026-08-03)
--   ALL match determination comes from
--     `followbreadfast.l03_marts.fct_daily_competitor_price_comparison`
--   through the query's OWN STEP 8/9/9b CTEs (competitor_raw / competitor_clean
--   / competitor_mapping). fct_competitor_price_monitoring is deliberately NOT
--   used, so the new gap metrics can never disagree with the existing
--   is_mapped / sale_PI columns.
--
--   `dim_competitor_products` is still read, but ONLY as the competitor
--   CATALOGUE (the list of products that exist). It has to be: the daily
--   comparison fact contains matched pairs only, so competitor products that
--   were never matched -- precisely the "competitor-only" population this
--   feature is about -- appear nowhere else.
--
-- Decisions encoded here:
--   * comp-only rows are NATIONAL: fp_id/fp_name NULL, row_type='competitor'
--   * PL kept, flagged is_private_label (app toggles it)
--   * Beauty kept, flagged is_beauty / beauty_path_share (app toggles it)
--   * category bridge computed in BQ at product grain
--   * similarity threshold aligned on 0.85 everywhere
--   * all 7 competitors; competitor_has_v2_catalogue flags the Carrefour gap
--
-- DOWNSTREAM WARNING
--   duckdb_service.py `_BASE_CTE` collapses to ONE ROW PER (product_id,
--   competitor_id). Competitor-only rows carry product_id = NULL and MUST NOT
--   flow through it -- they would all collapse into a single row per
--   competitor. See docs/plans/brand-subcategory-gap-tab-plan.md section 5.
-- =============================================================================

-- ── NEW 1 ▸ COMPETITOR PRODUCTS THAT HAVE ANY MATCH (daily fact) ────────────
-- Deliberately NOT restricted to our product universe: a competitor product
-- matched to a Breadfast product that falls outside scope must remain
-- distinguishable from one that was never matched at all.
comp_matched_any AS (
    SELECT DISTINCT
        cr.competitor_id,
        h.competitor_product_key
    FROM `followbreadfast.l03_marts.fct_daily_competitor_price_comparison` AS h
    INNER JOIN competitor_registry AS cr ON cr.competitor_key = h.competitor_key
    WHERE h.mapped_product_key IS NOT NULL
      AND h.competitor_product_key IS NOT NULL
),

-- ── NEW 2 ▸ BREADFAST UNIVERSE AT PRODUCT GRAIN ─────────────────────────────
-- products_enriched_prices_2 is per (product, fp). Gap metrics are national, so
-- collapse to product grain and attach brand_key + scope flags.
bf_universe AS (
    SELECT
        s.product_id,
        ANY_VALUE(s.product_key)        AS product_key,
        ANY_VALUE(s.sub_category_name)  AS sub_category_name,
        ANY_VALUE(s.main_category_name) AS main_category_name,
        ANY_VALUE(s.brand_name)         AS brand_name
    FROM products_enriched_prices_2 s
    GROUP BY s.product_id
),
bf_universe_enriched AS (
    SELECT
        u.*,
        COALESCE(dp.brand_slug, LOWER(u.brand_name))   AS brand_key,
        (u.main_category_name = 'Fragrances & Beauty') AS is_beauty,
        -- NOTE: matches the pandas convention (contains 'breadfast'), which is
        -- WIDER than the SQL convention brand_name != 'Breadfast' used in
        -- STEP 13's classification tree. Deliberate: brand grain makes
        -- 'Breadfast Bakery' a first-class row. See plan section 9.
        (LOWER(u.brand_name) LIKE '%breadfast%')       AS is_private_label
    FROM bf_universe AS u
    LEFT JOIN `followbreadfast.l03_marts.dim_products` AS dp
        ON dp.product_key = u.product_key
),
bf_brands AS (
    SELECT DISTINCT brand_key FROM bf_universe_enriched WHERE brand_key IS NOT NULL
),

-- ── NEW 3 ▸ COMPETITOR CATALOGUE + DEDUP + BUNDLE EXCLUSION ─────────────────
-- The only source of competitor products that were never matched.
comp_products_raw AS (
    SELECT
        cp.competitor_id,
        cr.competitor_name,
        cp.competitor_product_key,
        ANY_VALUE(cp.competitor_product_id) AS competitor_product_id,
        ANY_VALUE(cp.product_name_en)       AS comp_product_name,
        ANY_VALUE(cp.brand_name)            AS comp_brand_name,
        COALESCE(ANY_VALUE(cp.brand_slug), LOWER(ANY_VALUE(cp.brand_name))) AS brand_key,
        ANY_VALUE(cp.category_level_1)      AS category_level_1,
        ANY_VALUE(cp.category_level_2)      AS category_level_2,
        ANY_VALUE(cp.category_level_3)      AS category_level_3,
        ANY_VALUE(cp.category_level_4)      AS category_level_4,
        MAX(IF(COALESCE(DATE(cp.updated_at_ltz), DATE(cp.created_at_ltz)) >= CURRENT_DATE() - 7, 1, 0)) AS is_active_7d,
        MAX(COALESCE(DATE(cp.updated_at_ltz), DATE(cp.created_at_ltz)))     AS comp_last_seen
    FROM `followbreadfast.l03_marts.dim_competitor_products` AS cp
    INNER JOIN competitor_registry AS cr ON cr.competitor_id = cp.competitor_id
    WHERE cp.pricing_tool_version = 'v2'
    GROUP BY cp.competitor_id, cr.competitor_name, cp.competitor_product_key
),
-- Dedup identical names within (competitor, brand) down to EXACTLY ONE row:
-- a matched copy wins, otherwise the most recently seen one. The dedup is
-- applied here, at the single definition of the competitor catalogue, so it
-- carries into everything downstream — the brand universe, the category
-- bridge, the recommendation flags, the catalogue-health counts and the
-- competitor-only output branch.
--
-- The earlier `OR is_matched_any = 1` short-circuit kept EVERY matched copy,
-- not one. That leaked 6,159 duplicate rows (8.5% of the competitor
-- catalogue) into the gap tab — 19 identical "Flower Hair Clip" rows for
-- Amazon, 18 "Ice Cream" for Amazon Now. All of them were 'Matched Out Of
-- Scope', which is the tell: comp_matched_any has no fp_registry gate, so it
-- marks a product matched that paired_comp_keys (which is FP-gated, via
-- competitor_mapping) does not exclude — so every copy fell through to the
-- comp-only branch.
--
-- Bundle exclusion: unmatched products whose name joins two items with ' + '
-- are dropped, because Breadfast bundles are out of scope on our side.
comp_products AS (
    SELECT
        competitor_id, competitor_name, competitor_product_key, competitor_product_id,
        comp_product_name, comp_brand_name, brand_key,
        category_level_1, category_level_2, category_level_3, category_level_4,
        is_active_7d, comp_last_seen, is_matched_any
    FROM (
        SELECT
            r.*,
            COALESCE(TRIM(LOWER(r.comp_product_name)), '')  AS name_norm,
            COALESCE(r.brand_key, '')                       AS brand_norm,
            IF(ma.competitor_product_key IS NOT NULL, 1, 0) AS is_matched_any
        FROM comp_products_raw AS r
        LEFT JOIN comp_matched_any AS ma
            ON  ma.competitor_id          = r.competitor_id
            AND ma.competitor_product_key = r.competitor_product_key
    )
    WHERE ( is_matched_any = 1
            OR NOT REGEXP_CONTAINS(COALESCE(comp_product_name, ''), r'\s\+\s') )
    -- An empty name is not evidence of duplication, so those rows are never
    -- collapsed into each other.
    QUALIFY name_norm = ''
         OR ROW_NUMBER() OVER (
                PARTITION BY competitor_id, name_norm, brand_norm
                ORDER BY is_matched_any DESC,        -- a matched copy wins
                         comp_last_seen DESC,        -- else the freshest
                         competitor_product_key      -- deterministic tiebreak
            ) = 1
),
-- Brand universe per competitor: products on the list (active or matched)
comp_brand AS (
    SELECT DISTINCT competitor_id, brand_key
    FROM comp_products
    WHERE (is_active_7d = 1 OR is_matched_any = 1) AND brand_key IS NOT NULL
),
-- Carrefour-style data-quality flag: does this competitor have a live catalogue?
competitor_catalogue AS (
    SELECT
        cr.competitor_id,
        COUNTIF(cp.is_active_7d = 1)     AS comp_active_products,
        COUNTIF(cp.is_active_7d = 1) > 0 AS competitor_has_v2_catalogue
    FROM competitor_registry AS cr
    LEFT JOIN comp_products AS cp ON cp.competitor_id = cr.competitor_id
    GROUP BY cr.competitor_id
),

-- ── NEW 4 ▸ CATEGORY BRIDGE (competitor category path -> BF subcategory) ────
-- Evidence = the query's own competitor_mapping (STEP 9b, i.e. the daily
-- comparison fact). Keyed on the full path incl. level_4 (only Amazon
-- populates L4), with a parent-L3 fallback for thin L4 nodes.
bridge_pairs AS (
    SELECT
        cp.competitor_id,
        IFNULL(cp.category_level_1, '(none)') AS l1,
        IFNULL(cp.category_level_2, '(none)') AS l2,
        IFNULL(cp.category_level_3, '(none)') AS l3,
        IFNULL(cp.category_level_4, '(none)') AS l4,
        b.sub_category_name                   AS bf_sub_category,
        b.is_beauty,
        b.product_id
    FROM competitor_mapping AS cm
    JOIN bf_universe_enriched AS b
        ON b.product_id = cm.bf_product_id
    JOIN comp_products AS cp
        ON  cp.competitor_id          = cm.competitor_id
        AND cp.competitor_product_key = cm.competitor_product_key
    WHERE cm.bf_product_id IS NOT NULL
),
bridge_exact AS (
    SELECT competitor_id, l1, l2, l3, l4, bf_sub_category, pair_count,
           pair_count / SUM(pair_count) OVER (PARTITION BY competitor_id, l1, l2, l3, l4) AS pct_of_comp_category
    FROM (
        SELECT competitor_id, l1, l2, l3, l4, bf_sub_category, COUNT(DISTINCT product_id) AS pair_count
        FROM bridge_pairs GROUP BY 1,2,3,4,5,6
    )
    QUALIFY pair_count >= 3
         OR pair_count / SUM(pair_count) OVER (PARTITION BY competitor_id, bf_sub_category) >= 0.10
),
bridge_l3 AS (
    SELECT competitor_id, l1, l2, l3, bf_sub_category, pair_count,
           pair_count / SUM(pair_count) OVER (PARTITION BY competitor_id, l1, l2, l3) AS pct_of_comp_category
    FROM (
        SELECT competitor_id, l1, l2, l3, bf_sub_category, COUNT(DISTINCT product_id) AS pair_count
        FROM bridge_pairs GROUP BY 1,2,3,4,5
    )
    QUALIFY pair_count >= 3
         OR pair_count / SUM(pair_count) OVER (PARTITION BY competitor_id, bf_sub_category) >= 0.10
),
path_map_exact AS (
    SELECT competitor_id, l1, l2, l3, l4,
           ARRAY_AGG(STRUCT(bf_sub_category, pct_of_comp_category)
                     ORDER BY pct_of_comp_category DESC, pair_count DESC LIMIT 1)[OFFSET(0)] AS primary_map,
           STRING_AGG(bf_sub_category, ' | ' ORDER BY pct_of_comp_category DESC, pair_count DESC) AS all_subs
    FROM bridge_exact GROUP BY 1,2,3,4,5
),
path_map_l3 AS (
    SELECT competitor_id, l1, l2, l3,
           ARRAY_AGG(STRUCT(bf_sub_category, pct_of_comp_category)
                     ORDER BY pct_of_comp_category DESC, pair_count DESC LIMIT 1)[OFFSET(0)] AS primary_map,
           STRING_AGG(bf_sub_category, ' | ' ORDER BY pct_of_comp_category DESC, pair_count DESC) AS all_subs
    FROM bridge_l3 GROUP BY 1,2,3,4
),
-- Beauty share of a competitor category's mapping evidence. The app excludes
-- competitor beauty rows with: beauty_path_share > 0.90 (i.e. <10% in-scope).
path_beauty AS (
    SELECT competitor_id, l1, l2, l3,
           COUNT(DISTINCT product_id)                      AS all_pairs,
           COUNT(DISTINCT IF(is_beauty, product_id, NULL)) AS beauty_pairs,
           SAFE_DIVIDE(COUNT(DISTINCT IF(is_beauty, product_id, NULL)),
                       COUNT(DISTINCT product_id))         AS beauty_path_share
    FROM bridge_pairs GROUP BY 1,2,3,4
),

-- ── NEW 5 ▸ RECOMMENDATION FLAGS (confirmed no-match + best similarity) ─────
-- NOTE: filtered to v2 + EG. Intentionally STRICTER than STEP 12's
-- ai_match_candidates (which reads the table unfiltered). Confirmed-no-match
-- must not be driven by a v1-era or non-EG rejection. Both reads coexist.
rec_flags AS (
    SELECT
        r.competitor_id,
        CAST(r.bf_product_id AS INT64) AS bf_product_id,
        LOGICAL_OR(r.is_matched)       AS has_true_rec,
        LOGICAL_OR(NOT r.is_matched)   AS has_false_rec,
        -- best similarity among candidates still present in the portfolio
        MAX(IF(cp.competitor_product_key IS NOT NULL, r.similarity_score, NULL)) AS best_similarity_in_portfolio
    FROM `followbreadfast.l03_marts.dim_recommended_bf_competitor_products` AS r
    INNER JOIN competitor_registry AS cr ON cr.competitor_id = r.competitor_id
    LEFT JOIN comp_products AS cp
        ON  cp.competitor_id          = r.competitor_id
        AND cp.competitor_product_key = r.competitor_product_key
    WHERE r.pricing_tool_version = 'v2' AND r.country_code = 'EG'
    GROUP BY 1, 2
),

-- ── NEW 6 ▸ PAIRED KEYS + PAIR FRESHNESS (both from the daily fact) ─────────
-- Competitor products already represented on a Breadfast row, so comp-only
-- counts are never inflated.
paired_comp_keys AS (
    SELECT DISTINCT competitor_id, competitor_product_key
    FROM competitor_mapping
    WHERE competitor_product_key IS NOT NULL
),
-- Was the matched competitor product seen recently? Uses the daily fact's own
-- days_since_crawl gate (competitor_clean.is_recent_competitor), so freshness
-- means exactly what it means everywhere else in the tool.
bf_pair_freshness AS (
    SELECT
        competitor_id,
        bf_product_id,
        MAX(IF(is_recent_competitor, 1, 0)) AS matched_comp_active_7d
    FROM competitor_clean
    WHERE bf_product_id IS NOT NULL
    GROUP BY 1, 2
)


-- =============================================================================
-- OUTPUT ▸ product x fp x competitor (row_type='breadfast')
--        UNION national competitor-only catalogue (row_type='competitor')
-- =============================================================================
SELECT
    'breadfast'                                    AS row_type,
    f.*,
    -- scope flags (app toggles)
    bu.is_beauty,
    bu.is_private_label,
    bu.brand_key,
    -- brand overlap
    (cb.brand_key IS NOT NULL)                     AS is_shared_brand,
    -- gap family. f.is_mapped (STEP 13, daily fact) is the single match truth.
    fr.matched_comp_active_7d,
    ( NOT f.is_mapped
      AND NOT COALESCE(rf.has_true_rec, FALSE)
      AND COALESCE(rf.has_false_rec, FALSE) )      AS is_confirmed_no_match,
    ( NOT f.is_mapped
      AND NOT ( NOT COALESCE(rf.has_true_rec, FALSE)
                AND COALESCE(rf.has_false_rec, FALSE) )
      AND rf.best_similarity_in_portfolio >= 0.85 ) AS is_potential_match,
    rf.best_similarity_in_portfolio,
    -- competitor-side columns are null on Breadfast rows
    CAST(NULL AS STRING)  AS competitor_product_key,
    CAST(NULL AS STRING)  AS comp_brand_name,
    CAST(NULL AS STRING)  AS category_level_1,
    CAST(NULL AS STRING)  AS category_level_2,
    CAST(NULL AS STRING)  AS category_level_3,
    CAST(NULL AS STRING)  AS category_level_4,
    f.sub_category_name   AS mapped_bf_sub_category,
    f.sub_category_name   AS mapped_bf_sub_categories_all,
    CAST(NULL AS FLOAT64) AS mapped_pct_of_comp_category,
    'bf_own'              AS bridge_level,
    CAST(NULL AS FLOAT64) AS beauty_path_share,
    cc.competitor_has_v2_catalogue
FROM final_product_data AS f
LEFT JOIN bf_universe_enriched AS bu ON bu.product_id = f.product_id
LEFT JOIN comp_brand           AS cb ON cb.competitor_id = f.competitor_id AND cb.brand_key = bu.brand_key
LEFT JOIN bf_pair_freshness    AS fr ON fr.competitor_id = f.competitor_id AND fr.bf_product_id = f.product_id
LEFT JOIN rec_flags            AS rf ON rf.competitor_id = f.competitor_id AND rf.bf_product_id = f.product_id
LEFT JOIN competitor_catalogue AS cc ON cc.competitor_id = f.competitor_id

UNION ALL

-- ── COMPETITOR-ONLY ROWS (national: fp_id / fp_name NULL) ───────────────────
SELECT
    'competitor'          AS row_type,
    CAST(NULL AS INT64)   AS product_id,
    CAST(NULL AS STRING)  AS product_key,
    cp.comp_product_name  AS product_name_en,
    CAST(NULL AS STRING)  AS commercial_category_name,
    CAST(NULL AS STRING)  AS main_category_name,
    CAST(NULL AS STRING)  AS sub_category_name,
    cp.comp_brand_name    AS brand_name,
    CAST(NULL AS INT64)   AS rank_by_revenue,
    CAST(NULL AS INT64)   AS rank_by_quantity,
    CAST(NULL AS FLOAT64) AS avg_daily_revenue,
    CAST(NULL AS FLOAT64) AS avg_daily_quantity,
    CAST(NULL AS STRING)  AS global_tier,
    CAST(NULL AS STRING)  AS subcat_tier,
    CAST(NULL AS FLOAT64) AS cumulative_revenue_share,
    CAST(NULL AS FLOAT64) AS norm_revenue_global,
    CAST(NULL AS FLOAT64) AS norm_quantity_global,
    CAST(NULL AS FLOAT64) AS combined_score_global,
    CAST(NULL AS FLOAT64) AS norm_revenue_subcat,
    CAST(NULL AS FLOAT64) AS norm_quantity_subcat,
    CAST(NULL AS FLOAT64) AS score_subcat_100rev,
    CAST(NULL AS FLOAT64) AS score_subcat_70rev,
    CAST(NULL AS FLOAT64) AS score_subcat_50rev,
    CAST(NULL AS FLOAT64) AS score_subcat_30rev,
    CAST(NULL AS STRING)  AS fp_id,                     -- NATIONAL
    CAST(NULL AS STRING)  AS fp_name,
    CAST(NULL AS NUMERIC) AS bf_regular_price,
    cp.competitor_id,
    cp.competitor_name,
    cp.competitor_product_id,
    cp.comp_product_name  AS competitor_product_name,
    CAST(NULL AS NUMERIC) AS sale_PI,
    CAST(NULL AS NUMERIC) AS competitor_sale_price,
    CAST(NULL AS NUMERIC) AS min_competitor_sale_price,
    CAST(NULL AS NUMERIC) AS max_competitor_sale_price,
    CAST(NULL AS NUMERIC) AS breadfast_sale_price,
    CAST(NULL AS BOOL)    AS is_recent_breadfast,
    (cp.is_active_7d = 1) AS is_recent_competitor,
    CAST(NULL AS DATE)    AS breadfast_last_updated_day,
    cp.comp_last_seen     AS competitor_last_updated_day,
    CAST(NULL AS BOOL)    AS prices_recently_updated,
    FALSE                 AS is_mapped,
    CAST(NULL AS BOOL)    AS eligible_product,
    FALSE                 AS has_PI,
    FALSE                 AS used_product,
    FALSE                 AS updated,
    CAST(NULL AS BOOL)    AS match_potential,
    CAST(NULL AS NUMERIC) AS similarity_score,
    CAST(NULL AS STRING)  AS match_potential_product_name,
    IF(cp.is_matched_any = 1,
       'Competitor Matched Out Of Scope', 'Competitor Unmatched')      AS action_type,
    IF(cp.is_matched_any = 1,
       'Competitor Only - Matched Out Of Scope',
       'Competitor Only - Unmatched')                                  AS classification,
    -- scope flags
    CAST(NULL AS BOOL)    AS is_beauty,
    FALSE                 AS is_private_label,
    cp.brand_key,
    (bb.brand_key IS NOT NULL) AS is_shared_brand,   -- does BREADFAST carry this brand
    CAST(NULL AS INT64)   AS matched_comp_active_7d,
    CAST(NULL AS BOOL)    AS is_confirmed_no_match,
    CAST(NULL AS BOOL)    AS is_potential_match,
    CAST(NULL AS NUMERIC) AS best_similarity_in_portfolio,
    -- competitor-side detail
    cp.competitor_product_key,
    cp.comp_brand_name,
    cp.category_level_1,
    cp.category_level_2,
    cp.category_level_3,
    cp.category_level_4,
    COALESCE(pme.primary_map.bf_sub_category, pml.primary_map.bf_sub_category)   AS mapped_bf_sub_category,
    COALESCE(pme.all_subs, pml.all_subs)                                        AS mapped_bf_sub_categories_all,
    COALESCE(pme.primary_map.pct_of_comp_category,
             pml.primary_map.pct_of_comp_category)                              AS mapped_pct_of_comp_category,
    CASE WHEN pme.competitor_id IS NOT NULL THEN 'exact_path'
         WHEN pml.competitor_id IS NOT NULL THEN 'parent_l3_fallback' END       AS bridge_level,
    pb.beauty_path_share,
    cc.competitor_has_v2_catalogue
FROM comp_products AS cp
LEFT JOIN paired_comp_keys AS pk
    ON  pk.competitor_id          = cp.competitor_id
    AND pk.competitor_product_key = cp.competitor_product_key
LEFT JOIN bf_brands AS bb ON bb.brand_key = cp.brand_key
LEFT JOIN path_map_exact AS pme
    ON  pme.competitor_id = cp.competitor_id
    AND pme.l1 = IFNULL(cp.category_level_1, '(none)')
    AND pme.l2 = IFNULL(cp.category_level_2, '(none)')
    AND pme.l3 = IFNULL(cp.category_level_3, '(none)')
    AND pme.l4 = IFNULL(cp.category_level_4, '(none)')
LEFT JOIN path_map_l3 AS pml
    ON  pml.competitor_id = cp.competitor_id
    AND pml.l1 = IFNULL(cp.category_level_1, '(none)')
    AND pml.l2 = IFNULL(cp.category_level_2, '(none)')
    AND pml.l3 = IFNULL(cp.category_level_3, '(none)')
LEFT JOIN path_beauty AS pb
    ON  pb.competitor_id = cp.competitor_id
    AND pb.l1 = IFNULL(cp.category_level_1, '(none)')
    AND pb.l2 = IFNULL(cp.category_level_2, '(none)')
    AND pb.l3 = IFNULL(cp.category_level_3, '(none)')
LEFT JOIN competitor_catalogue AS cc ON cc.competitor_id = cp.competitor_id
WHERE cp.is_active_7d = 1
  AND pk.competitor_product_key IS NULL)
