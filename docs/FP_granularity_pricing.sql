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
-- Competitors we benchmark against (everyone except Breadfast). competitor_key
-- is carried so we can join the daily comparison fact (which keys on
-- competitor_key, not competitor_id).
-- ─────────────────────────────────────────────────────────────────────────────
competitor_registry AS (
    SELECT
        competitor_id,
        competitor_key,
        competitor_name
    FROM `followbreadfast.l03_marts.dim_competitors`
    WHERE competitor_name != 'Breadfast'
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 0b ▸ FP REGISTRY
-- Active FPs whose name ends with "FP #<number>" and are not currently sleeping.
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
)


-- =============================================================================
-- OUTPUT
-- Option A (default): product × fp × competitor detail
-- Option B (commented): fp × subcategory × competitor roll-up
-- =============================================================================
SELECT *
FROM final_product_data p
-- WHERE product_id = 10900814 and competitor_id = 1
ORDER BY p.combined_score_global DESC, p.fp_id, p.competitor_id)
