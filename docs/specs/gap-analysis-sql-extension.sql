-- =============================================================================
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
-- a matched copy wins, otherwise the most recently seen one. Applied here, at
-- the single definition of the competitor catalogue, so it carries into
-- everything downstream (brand universe, category bridge, recommendation
-- flags, catalogue-health counts, competitor-only branch).
--
-- REVISED 2026-08-03: the previous `OR is_matched_any = 1` short-circuit kept
-- EVERY matched copy rather than one, leaking 6,159 duplicate rows (8.5% of
-- the catalogue) into the gap tab.
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
    -- An empty name is not evidence of duplication.
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
-- The two branches below replace the final `SELECT * FROM final_product_data`.
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
  AND pk.competitor_product_key IS NULL
