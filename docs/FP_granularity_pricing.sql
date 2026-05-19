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
-- FP scope: active FPs matching "<Area> FP #<number>" and not in SLEEP.
-- (product, fp) pairs are only emitted when:
--   • Breadfast has a price record for the SKU in that FP, AND
--   • the SKU was live in the app in that FP in the last 7 days.
--
-- Default output: one row per (product, fp, competitor) from final_product_data.
-- Alternative: (fp, subcategory, competitor) roll-up via subcategory_summary.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE TABLE dbt_gohary.competitor_price_monitoring_fps AS (
WITH
-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 0a ▸ COMPETITOR REGISTRY
-- Competitors we benchmark against (everyone except Breadfast). Used both
-- to filter source data AND as one spine of the output grid in STEP 11.
-- ─────────────────────────────────────────────────────────────────────────────
competitor_registry AS (
    SELECT
        competitor_id,
        competitor_name
    FROM `followbreadfast.l03_marts.dim_competitors`
    WHERE competitor_name != 'Breadfast'
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 0b ▸ FP REGISTRY
-- Active FPs whose name ends with "FP #<number>" (e.g. "New Cairo FP #1",
-- "Maadi FP #10") and are not currently sleeping.
-- ─────────────────────────────────────────────────────────────────────────────
fp_registry AS (
    SELECT
        fp_id,
        fp_name
    FROM `followbreadfast.l03_marts.dim_fps`
    WHERE REGEXP_CONTAINS(fp_name, r'FP #\d+$')
        AND current_fp_now_status != 'SLEEP'
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 0c ▸ FP × SKU AVAILABILITY
-- (product, fp) pairs where the SKU was live in the app at least once in
-- the last 7 days. Used as an INNER JOIN gate in STEP 7 to restrict the
-- (product, fp) grain to genuinely active assortment combinations — every
-- row downstream is therefore active by construction (no flag needed).
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
-- STEPS 1–5 ▸ BREADFAST-INTERNAL METRICS (PRODUCT GRAIN, GLOBAL)
-- Competitor- and FP-agnostic. Global scores remain product-level and are
-- simply broadcast across fp rows downstream.
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
-- Pre-computes a few revenue/quantity weight blends so downstream consumers
-- can pick the mix that fits their decision. COALESCE handles single-product
-- subcategories where normalization → NULL.
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
-- STEPS 6–7 ▸ BREADFAST PRICE ENRICHMENT (PER FP) + ACTIVITY GATE
-- The SCD is at (product_key, fp_id) grain. We keep that grain instead of
-- collapsing it. STEP 7 also enforces the activity gate — every (product, fp)
-- row downstream is guaranteed to have BF pricing AND active assortment.
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 6 ▸ BREADFAST PRICES — LATEST SCD ROW PER (PRODUCT, FP)
-- INNER JOIN to fp_registry enforces FP scope, and INNER JOIN to the SCD
-- enforces the "BF must have a price" rule.
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
-- If multiple SCD rows tie for "latest" within an (product, fp) cell, take
-- the mode of each price column. INNER JOIN to fps_available_products
-- restricts the grain to (product, fp) pairs where the SKU was live in the
-- app in the last 7 days — this is the universal activity gate for the
-- rest of the pipeline.
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
-- STEPS 8–10 ▸ COMPETITOR PRICE PIPELINE (PER FP, MULTI-COMPETITOR)
--   Step 8  — latest crawl per (competitor, BF product, fp), preferring v2.
--   Step 9  — collapse multi-location observations within an fp into modal
--             prices and within-fp spread.
--   Step 9b — product-level mapping (collapses across FPs).
--   Step 10 — sale_PI = BF sale price ÷ competitor sale price (per fp).
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 8 ▸ COMPETITOR PRICES — RAW LATEST OBSERVATION (PER FP)
-- For each (competitor, mapped BF product, fp) take the row with the newest
-- valid_to_ltz, breaking ties by latest crawl date and preferring v2.
-- bf_sale_price falls back to bf_regular_price when sale price is missing/zero.
-- ─────────────────────────────────────────────────────────────────────────────
competitor_raw AS (
    SELECT
        cr.competitor_id,
        cr.competitor_name,
        fr.fp_id,
        fr.fp_name,
        h.competitor_product_id,
        h.competitor_product_key,
        h.comp_sale_price AS sale_price,
        h.bf_regular_price,
        COALESCE(NULLIF(h.bf_sale_price, 0), h.bf_regular_price) AS bf_sale_price,
        h.comp_regular_price AS regular_price,
        h.mapped_bf_product_id AS bf_product_id,
        COALESCE(DATE(h.last_crawled_at_ltz), '1970-01-01') AS date_day,
        h.location_id,
        CASE
            WHEN h.valid_to_ltz >= CURRENT_DATE() THEN CURRENT_DATE()
            ELSE DATE(h.valid_to_ltz)
        END AS breadfast_last_updated_day
    FROM `followbreadfast.l03_marts.fct_competitor_price_monitoring` h
    INNER JOIN competitor_registry cr
        ON h.competitor_id = cr.competitor_id
    INNER JOIN fp_registry fr
        ON h.fp_id = fr.fp_id
    WHERE h.mapped_bf_product_id IS NOT NULL
    QUALIFY RANK() OVER (
        PARTITION BY h.competitor_id, h.mapped_bf_product_id, h.fp_id
        ORDER BY
            h.pricing_tool_version DESC,   -- Prefer v2 over v1
            h.valid_to_ltz DESC,
            DATE(h.last_crawled_at_ltz) DESC
    ) = 1
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 9 ▸ COMPETITOR PRICES — COLLAPSE LOCATIONS WITHIN AN FP
-- Modal price across the fp's locations via APPROX_TOP_COUNT; MIN/MAX gives
-- within-fp spread. is_recent_* flags freshness (≤ 7 days).
-- ─────────────────────────────────────────────────────────────────────────────
competitor_clean AS (
    SELECT
        cr.competitor_id,
        cr.competitor_name,
        cr.fp_id,
        cr.fp_name,
        cr.competitor_product_id,
        cp.product_name_en AS competitor_product_name,
        cr.competitor_product_key,
        cr.bf_product_id,

        -- Freshness
        MAX(cr.date_day) >= CURRENT_DATE() - 7 AS is_recent_competitor,
        MAX(cr.breadfast_last_updated_day) >= CURRENT_DATE() - 7 AS is_recent_breadfast,
        MAX(cr.breadfast_last_updated_day) AS breadfast_last_updated_day,
        MAX(cr.date_day) AS date_day,

        -- Modal prices within the fp
        APPROX_TOP_COUNT(cr.regular_price, 1)[OFFSET(0)].value AS competitor_regular_price,
        APPROX_TOP_COUNT(cr.sale_price, 1)[OFFSET(0)].value AS competitor_sale_price,
        APPROX_TOP_COUNT(cr.bf_regular_price, 1)[OFFSET(0)].value AS breadfast_regular_price,
        APPROX_TOP_COUNT(cr.bf_sale_price, 1)[OFFSET(0)].value AS breadfast_sale_price,

        -- Within-fp spread across locations
        MIN(cr.sale_price) AS min_competitor_sale_price,
        MAX(cr.sale_price) AS max_competitor_sale_price,
        MIN(cr.bf_sale_price) AS min_bf_sale_price,
        MAX(cr.bf_sale_price) AS max_bf_sale_price
    FROM competitor_raw cr
    LEFT JOIN `followbreadfast.l03_marts.dim_competitor_products` cp
        ON cr.competitor_product_key = cp.competitor_product_key
        AND cp.competitor_id = cr.competitor_id
    GROUP BY ALL
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 9b ▸ COMPETITOR MAPPING (PRODUCT-LEVEL, FP-AGNOSTIC)
-- A BF product is "mapped" to a competitor if *any* FP has an observation
-- linking them. This CTE collapses competitor_clean across FPs to give the
-- canonical link per (bf_product, competitor), broadcast to every FP in
-- STEP 11 — even FPs where this competitor has no price observation.
-- The "most recent observation" wins for the link details, handling
-- competitor product re-mappings gracefully.
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
-- One row per (BF product, competitor, fp) where a price match exists.
--   sale_PI = Breadfast sale price / Competitor sale price
--     PI > 1 → BF more expensive   |   PI < 1 → BF cheaper
-- ─────────────────────────────────────────────────────────────────────────────
price_index AS (
    SELECT
        c.bf_product_id AS product_id,
        c.competitor_id,
        c.competitor_name,
        c.fp_id,
        c.fp_name,
        c.is_recent_competitor,
        c.is_recent_breadfast,
        c.breadfast_sale_price,
        c.competitor_sale_price,
        c.min_competitor_sale_price,
        c.max_competitor_sale_price,
        c.breadfast_last_updated_day,
        c.date_day AS competitor_last_updated_day,
        SAFE_DIVIDE(c.breadfast_sale_price, c.competitor_sale_price) AS sale_PI
    FROM competitor_clean c
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 11–13 ▸ ASSEMBLY, AI CANDIDATES, FLAGS & CLASSIFICATION
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 11 ▸ JOIN SCORES + MAPPING + PRICE INDEX
-- Driver: products_enriched_prices_2 (already gated on activity + BF pricing).
-- CROSS JOIN competitors, then two LEFT JOINs:
--   • competitor_mapping → product-level link (carries across all FPs)
--   • price_index        → fp-level price (NULL where this FP has no obs)
-- This decouples "is the product mapped?" from "is there a price here?".
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

        -- BF price: competitor-side wins where present; else SCD-derived
        COALESCE(pi.breadfast_sale_price, s.bf_sale_price) AS breadfast_sale_price,
        COALESCE(pi.is_recent_breadfast, s.is_recent_breadfast) AS is_recent_breadfast,
        pi.is_recent_competitor,
        COALESCE(pi.breadfast_last_updated_day, s.breadfast_last_updated_day) AS breadfast_last_updated_day,
        pi.competitor_last_updated_day,

        -- Both sides fresh (≤ 7 days)
        (COALESCE(pi.is_recent_breadfast, s.is_recent_breadfast)
            AND pi.is_recent_competitor) AS prices_recently_updated,

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
-- STEP 12 ▸ AI MATCH CANDIDATES (PRODUCT-LEVEL, REPLICATED ACROSS FPS)
-- The recommendation table is product-level. The same candidate applies to
-- every FP in which the product is priced — that's intentional.
-- ─────────────────────────────────────────────────────────────────────────────
ai_match_candidates AS (
    SELECT
        CAST(rcp.bf_product_id AS INT64) AS recommended_bf_product_id,
        rcp.competitor_id,
        rcp.similarity_score,
        cp.product_name_en AS match_potential_product_name
    FROM `bf-data-dev-qz06.dbt_salma.dim_recommended_bf_competitor_products` rcp
    INNER JOIN competitor_registry cr
        ON rcp.competitor_id = cr.competitor_id
    LEFT JOIN `followbreadfast.l03_marts.dim_competitor_products` cp
        ON rcp.competitor_product_id = cp.competitor_product_id
        AND cp.competitor_id = rcp.competitor_id
    QUALIFY ROW_NUMBER() OVER (PARTITION BY rcp.bf_product_id, rcp.competitor_id
  ORDER BY rcp.similarity_score DESC) = 1 
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 13 ▸ FINAL PRODUCT DATA + ELIGIBILITY / ACTION FLAGS
-- One row per (product, fp, competitor). Every row is for an active SKU in
-- that FP with a BF price (gate enforced in STEP 7).
--
-- Flag semantics:
--   eligible_product → top 80% of subcategory revenue (product-level, global)
--   is_mapped        → product is linked to this competitor in any FP
--   has_PI           → THIS FP has a competitor price observation (FP-level)
--   updated          → both BF and competitor prices are ≤ 7 days fresh
--   used_product     → eligible AND has_PI AND updated (counts toward PI)
--   match_potential  → AI similarity ≥ 0.85 for this competitor
--
-- action_type (per product, fp, competitor):
--   Needs Mapping       — no link anywhere AND no AI candidate
--   Review AI Match     — no link anywhere BUT AI suggests one
--   Needs Price for FP  — linked, but this FP has no competitor price
--   Needs Price Update  — linked AND priced here, but stale
--   Complete            — linked, priced here, and fresh
--
-- classification (Mapped is product-level):
--   Mapped - PL                           /  Mapped - Not PL
--   Not Mapped - PL - Potential Match     /  - No Potential Match
--   Not Mapped - Not PL - Potential Match /  - No Potential Match
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
            -- Branch 1: MAPPED (product-level)
            WHEN w.is_mapped AND w.brand_name != 'Breadfast'
                THEN 'Mapped - Not PL'
            WHEN w.is_mapped AND w.brand_name = 'Breadfast'
                THEN 'Mapped - PL'

            -- Branch 2a: NOT MAPPED — PL
            WHEN NOT w.is_mapped
                 AND w.brand_name = 'Breadfast'
                 AND amc.similarity_score >= 0.85
                THEN 'Not Mapped - PL - Potential Match'
            WHEN NOT w.is_mapped
                 AND w.brand_name = 'Breadfast'
                 AND (amc.similarity_score IS NULL OR amc.similarity_score < 0.85)
                THEN 'Not Mapped - PL - No Potential Match'

            -- Branch 2b: NOT MAPPED — Not PL
            WHEN NOT w.is_mapped
                 AND w.brand_name != 'Breadfast'
                 AND amc.similarity_score >= 0.85
                THEN 'Not Mapped - Not PL - Potential Match'
            WHEN NOT w.is_mapped
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
-- STEP 14 ▸ (FP × SUBCATEGORY × COMPETITOR) ROLL-UP (optional output)
-- mapped_products          → linked (product-level)
-- priced_products          → has a price in THIS FP
-- mapped_no_price_products → linked but no price in this FP (action backlog)
-- blended_PI               → quantity-weighted mean PI over "used" products
-- coverage_pct             → share of eligible set we cover in that FP
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
)


-- =============================================================================
-- OUTPUT
-- Option A (default): product × fp × competitor detail
-- Option B (commented): fp × subcategory × competitor roll-up
-- =============================================================================
SELECT p.*
FROM final_product_data p
-- WHERE product_id = 10900814 and competitor_id = 1
ORDER BY p.combined_score_global DESC, p.fp_id, p.competitor_id

-- SELECT * FROM subcategory_summary
-- ORDER BY fp_name, competitor_name, blended_PI DESC
)
