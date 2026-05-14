-- =============================================================================
-- PRICE INDEX — MULTI-COMPETITOR
-- Outputs one row per Breadfast product × competitor pair.
-- Products with no competitor mapping still appear (NULLs in competitor cols).
-- =============================================================================
CREATE OR REPLACE TABLE dbt_gohary.competitor_products_analysis as (
WITH competitor_registry AS (
-- Active competitors to include in this run. Uncomment the WHERE clause to
-- scope the analysis to a single competitor during development.
    SELECT
        competitor_id,
        competitor_name
    FROM followbreadfast.l03_marts.dim_competitors
    WHERE competitor_name != 'Breadfast'
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 1  PRODUCT UNIVERSE
-- Egypt · grocery · single products · exclude bundles & AFCON sub-category.
-- ─────────────────────────────────────────────────────────────────────────────
product_base AS (
    SELECT
        p.product_id,
        p.product_key,
        p.product_name_en,
        p.commercial_category_name,
        p.main_category_name,
        p.sub_category_name,
        p.brand_name
    FROM `followbreadfast.l03_marts.dim_products` p
    WHERE TRUE
        AND p.country_code    = 'EG'
        AND p.vertical        = 'grocery'
        AND p.product_type    = 'single'
        AND LOWER(p.sub_category_name) NOT LIKE '%bundle%'
        AND p.sub_category_name NOT IN ('AFCON Bites')
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEPS 2–3  BREADFAST PRICES
-- Attach the most-recent price record per product (RANK = 1 on valid_to_ltz).
-- sale_price falls back to regular_price when the sale price is 0 / NULL.
-- Step 3 then collapses multiple FP rows into a single modal price per product.
-- ─────────────────────────────────────────────────────────────────────────────
products_enriched_prices_1 AS (
    SELECT
        s.*,
        fp_id,
        p.applied_regular_price,
        COALESCE(NULLIF(p.applied_sale_price, 0), p.applied_regular_price) AS applied_sale_price,
        CASE
            WHEN p.valid_to_ltz >= CURRENT_DATE() THEN CURRENT_DATE()
            ELSE DATE(p.valid_to_ltz)
        END                                                                 AS breadfast_last_updated_day
    FROM product_base s
    LEFT JOIN `followbreadfast.l03_marts.dim_fp_product_price_logs_scd` p
        ON s.product_key = p.product_key
    -- WHERE s.product_id = 331030
    QUALIFY RANK() OVER (PARTITION BY p.product_key ORDER BY valid_to_ltz DESC) = 1
),

products_enriched_prices_2 AS (
-- Modal (most-frequent) price across all facility-point records.
-- is_recent_breadfast = TRUE when at least one FP updated within the last 7 days.
    SELECT
        s.* EXCEPT (fp_id, applied_regular_price, applied_sale_price, breadfast_last_updated_day),
        APPROX_TOP_COUNT(applied_regular_price, 1)[OFFSET(0)].value AS bf_regular_price,
        APPROX_TOP_COUNT(applied_sale_price,   1)[OFFSET(0)].value AS bf_sale_price,
        MAX(breadfast_last_updated_day)                              AS breadfast_last_updated_day,
        MAX(breadfast_last_updated_day) >= CURRENT_DATE() - 7       AS is_recent_breadfast
    FROM products_enriched_prices_1 s
    GROUP BY ALL
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEPS 4–6  COMPETITOR PRICES
-- Step 4: Keep only the latest price record per competitor × BF product pair
--         (latest valid_to_ltz, then latest crawl date as a tie-breaker).
-- Step 5: Pull all mapped competitor products and left-join their latest price.
-- Step 6: Collapse to one row per competitor product using modal price across
--         all locations; derive freshness flags and min/max price range.
-- ─────────────────────────────────────────────────────────────────────────────
competitor_ranked AS (
    SELECT
        h.competitor_id,
        h.competitor_product_key,
        h.comp_sale_price                                                  AS sale_price,
        h.bf_regular_price,
        h.bf_sale_price,
        h.comp_regular_price                                               AS regular_price,
        h.mapped_bf_product_id                                             AS bf_product_id,
        COALESCE(DATE(h.last_crawled_at_ltz), '1970-1-1')                  AS date_day,
        h.location_id,
        CASE
            WHEN valid_to_ltz >= CURRENT_DATE() THEN CURRENT_DATE()
            ELSE DATE(valid_to_ltz)
        END                                                                AS breadfast_last_updated_day,
        RANK() OVER (
            PARTITION BY h.competitor_id, h.mapped_bf_product_id,h.competitor_product_key
            ORDER BY h.valid_to_ltz DESC, DATE(h.last_crawled_at_ltz) DESC
        )                                                                  AS price_rank
    FROM `followbreadfast.l03_marts.fct_competitor_price_monitoring` h
    INNER JOIN competitor_registry cr
        ON h.competitor_id = cr.competitor_id
    QUALIFY RANK() OVER (
        PARTITION BY h.competitor_id, h.mapped_bf_product_id, h.competitor_product_key
        ORDER BY h.valid_to_ltz DESC, DATE(h.last_crawled_at_ltz) DESC
    ) = 1
),

competitor_raw AS (
    SELECT
        cp.competitor_id,
        cp.competitor_name,
        cp.competitor_product_id,
        cp.competitor_product_key,
        cp.product_name_en,
        cp.category_level_1,
        cp.category_level_2,
        cp.category_level_3,
        r.bf_regular_price,
        r.bf_sale_price,
        r.regular_price,
        r.sale_price,
        r.bf_product_id,
        COALESCE(r.date_day, DATE(cp.updated_at_ltz), DATE(cp.created_at_ltz)) AS date_day,
        r.location_id,
        r.breadfast_last_updated_day
    FROM `followbreadfast.l03_marts.dim_competitor_products` cp
    INNER JOIN competitor_registry cr
        ON cr.competitor_id = cp.competitor_id
    LEFT JOIN competitor_ranked r
        ON cp.competitor_product_key = r.competitor_product_key
),

competitor_clean AS (
-- Modal price and freshness flags per competitor product.
-- is_recent_competitor = TRUE when the latest crawl is within 7 days.
-- min/max sale prices capture the spread across locations.
    SELECT
        cr.competitor_id,
        cr.competitor_name,
        cr.competitor_product_id,
        cr.product_name_en                                              AS competitor_product_name,
        cr.competitor_product_key,
        cr.category_level_1,
        cr.category_level_2,
        cr.category_level_3,
        cr.bf_product_id,
        MAX(cr.date_day) >= CURRENT_DATE() - 7                         AS is_recent_competitor,
        MAX(cr.breadfast_last_updated_day) >= CURRENT_DATE() - 7       AS is_recent_breadfast,
        MAX(cr.breadfast_last_updated_day)                              AS breadfast_last_updated_day,
        APPROX_TOP_COUNT(cr.regular_price,    1)[OFFSET(0)].value      AS competitor_regular_price,
        APPROX_TOP_COUNT(cr.sale_price,       1)[OFFSET(0)].value      AS competitor_sale_price,
        APPROX_TOP_COUNT(cr.bf_regular_price, 1)[OFFSET(0)].value      AS breadfast_regular_price,
        APPROX_TOP_COUNT(cr.bf_sale_price,    1)[OFFSET(0)].value      AS breadfast_sale_price,
        MIN(cr.sale_price)                                             AS min_competitor_sale_price,
        MAX(cr.sale_price)                                             AS max_competitor_sale_price,
        MIN(cr.bf_sale_price)                                          AS min_bf_sale_price,
        MAX(cr.bf_sale_price)                                          AS max_bf_sale_price,
        MAX(cr.date_day)                                               AS date_day
    FROM competitor_raw cr
    GROUP BY ALL
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 7  PRICE INDEX
-- One PI row per BF product × competitor pair.
-- sale_PI = BF sale price ÷ competitor sale price.
--   PI > 1  →  BF is more expensive than the competitor.
--   PI < 1  →  BF is cheaper.
--   NULL    →  no competitor price available (unmatched product).
-- ─────────────────────────────────────────────────────────────────────────────
price_index AS (
    SELECT
        c.bf_product_id                                                    AS product_id,
        c.competitor_id,
        c.competitor_name,
        c.competitor_product_id,
        c.competitor_product_name,
        c.category_level_1,
        c.category_level_2,
        c.category_level_3,
        c.is_recent_competitor,
        c.is_recent_breadfast,
        c.breadfast_sale_price,
        c.competitor_sale_price,
        c.min_competitor_sale_price,
        c.max_competitor_sale_price,
        c.breadfast_last_updated_day,
        COALESCE(c.date_day, '1970-1-1')                                   AS competitor_last_updated_day,
        SAFE_DIVIDE(c.breadfast_sale_price, c.competitor_sale_price)       AS sale_PI
    FROM competitor_clean c
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 8  PRODUCTS × PRICE INDEX
-- Each BF product fans out to N rows — one per competitor.
-- Products with no competitor mapping produce 1 row with NULL competitor cols.
-- BF price / freshness columns fall back to the products_enriched_prices_2
-- value when the price index row carries no override.
-- ─────────────────────────────────────────────────────────────────────────────
products_with_pi AS (
    SELECT
        s.* EXCEPT (is_recent_breadfast, bf_sale_price, breadfast_last_updated_day),
        pi.competitor_id,
        pi.competitor_name,
        pi.competitor_product_id,
        pi.competitor_product_name,
        pi.sale_PI,
        pi.competitor_sale_price,
        pi.min_competitor_sale_price,
        pi.max_competitor_sale_price,
        pi.category_level_1,
        pi.category_level_2,
        pi.category_level_3,
        COALESCE(pi.breadfast_sale_price,       s.bf_sale_price)           AS breadfast_sale_price,
        COALESCE(pi.is_recent_breadfast,        s.is_recent_breadfast)     AS is_recent_breadfast,
        pi.is_recent_competitor,
        COALESCE(pi.breadfast_last_updated_day, s.breadfast_last_updated_day) AS breadfast_last_updated_day,
        pi.competitor_last_updated_day,
        (COALESCE(pi.is_recent_breadfast, s.is_recent_breadfast) AND pi.is_recent_competitor)
                                                                           AS prices_recently_updated
    FROM price_index pi
    LEFT JOIN products_enriched_prices_2 s
        ON s.product_id = pi.product_id
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 9  AI MATCH CANDIDATES
-- High-confidence AI-suggested mappings (similarity_score ≥ 0.85) scoped to
-- the active competitor registry. Used in Step 10 to flag unmapped products
-- that have a ready-to-review match candidate.
-- ─────────────────────────────────────────────────────────────────────────────
ai_match_candidates AS (
    SELECT
        CAST(rcp.bf_product_id AS INT64)    AS recommended_bf_product_id,
        rcp.competitor_id,
        rcp.similarity_score,
        cp.competitor_product_id,
        p.product_name_en                  AS match_potential_product_name
    FROM `bf-data-dev-qz06.dbt_salma.dim_recommended_bf_competitor_products` rcp
    INNER JOIN competitor_registry cr
        ON rcp.competitor_id = cr.competitor_id
    LEFT JOIN `followbreadfast.l03_marts.dim_competitor_products` cp
        ON  rcp.competitor_product_id = cp.competitor_product_id
        AND cp.competitor_id           = rcp.competitor_id
    LEFT JOIN `followbreadfast.l03_marts.dim_products` p on CAST(rcp.bf_product_id AS INT64) = p.product_id AND p.country_code = 'EG'
    WHERE similarity_score >= 0.85
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 10  FINAL PRODUCT DATA + CLASSIFICATION
-- Flags and classification are computed per product × competitor pair.
--
-- Flags:
--   has_PI             → competitor price mapping exists for this pair
--   updated            → both BF and competitor prices refreshed within 7 days
--   match_potential    → AI model found a candidate with score ≥ 0.85
--
-- Classification tree:
--   Mapped
--     ├── Mapped - Not PL          (has PI, third-party brand)
--     └── Mapped - PL              (has PI, Breadfast private label)
--   Not Mapped
--     ├── PL - Potential Match     (no PI, PL, AI candidate found)
--     ├── PL - No Potential Match  (no PI, PL, no AI candidate)
--     ├── Not PL - Potential Match (no PI, third-party, AI candidate found)
--     └── Not PL - No Potential Match (no PI, third-party, no AI candidate)
-- ─────────────────────────────────────────────────────────────────────────────
final_product_data AS (
    SELECT
        w.*,

        -- Per-competitor mapping & freshness flags
        (w.sale_PI IS NOT NULL)                    AS has_PI,
        COALESCE(w.prices_recently_updated, FALSE) AS updated,

        -- AI match candidate flags
        (amc.similarity_score >= 0.85)             AS match_potential,
        amc.similarity_score,
        amc.match_potential_product_name,

        CASE
            -- ── Mapped ───────────────────────────────────────────────────────
            WHEN w.sale_PI IS NOT NULL AND w.brand_name != 'Breadfast'
                THEN 'Mapped - Not PL'

            WHEN w.sale_PI IS NOT NULL AND w.brand_name = 'Breadfast'
                THEN 'Mapped - PL'

            -- ── Not Mapped · Private Label ────────────────────────────────
            WHEN w.sale_PI IS NULL AND w.brand_name = 'Breadfast'
                AND  amc.similarity_score >= 0.85
                THEN 'Not Mapped - PL - Potential Match'

            WHEN w.sale_PI IS NULL AND w.brand_name = 'Breadfast'
                AND (amc.similarity_score IS NULL OR amc.similarity_score < 0.85)
                THEN 'Not Mapped - PL - No Potential Match'

            -- ── Not Mapped · Third-Party ──────────────────────────────────
            WHEN w.sale_PI IS NULL AND w.brand_name != 'Breadfast'
                AND  amc.similarity_score >= 0.85
                THEN 'Not Mapped - Not PL - Potential Match'

            WHEN w.sale_PI IS NULL AND w.brand_name != 'Breadfast'
                AND (amc.similarity_score IS NULL OR amc.similarity_score < 0.85)
                THEN 'Not Mapped - Not PL - No Potential Match'

            ELSE 'Unclassified'
        END AS classification

    FROM products_with_pi w
    LEFT JOIN ai_match_candidates amc
        ON  w.competitor_product_id    = amc.competitor_product_id
        AND w.competitor_id = amc.competitor_id
)


-- =============================================================================
-- OUTPUT  (uncomment the desired option)
-- =============================================================================

-- Option A — Product × competitor detail (default)
SELECT p.*
FROM final_product_data p
WHERE competitor_last_updated_day != '1970-1-1'
-- AND product_id IS NULL


-- Option B — Subcategory summary per competitor
-- SELECT * FROM subcategory_summary
-- ORDER BY competitor_name, main_category_name, sub_category_name

-- Option C — Cross-competitor product summary (executive view)
-- SELECT * FROM cross_competitor_summary
-- ORDER BY avg_daily_revenue DESC

-- Option D — Subcategory summary for a single competitor (legacy mode)
-- SELECT * FROM subcategory_summary
-- WHERE competitor_name = 'Talabat'
-- ORDER BY main_category_name, sub_category_name
)