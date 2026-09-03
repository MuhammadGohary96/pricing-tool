-- ═══════════════════════════════════════════════════════════════════════════
-- COMPETITIVE PRICING INTELLIGENCE — MULTI-COMPETITOR × MULTI-FP PRICE INDEX
-- ═══════════════════════════════════════════════════════════════════════════
-- Produces a product × fp × competitor grid with sale price index (sale_PI),
-- mapping completeness flags, action_type for the master-data workflow, and
-- a classification tree (Mapped × PL × Potential Match).
--
-- Mapping vs Pricing separation:
--   is_mapped → product-level, from dim_competitor_products.mapped_bf_product_id
--               (v2 rows; the master-data truth — NULL means not mapped NOW).
--               Never derived from price observations: mapped-with-no-price is
--               still mapped; an unassigned pair stops being mapped that day.
--   has_PI    → fp-level: this FP has a price observation, so sale_PI exists.
--
-- Scope: 7 competitors (Amazon, Amazon Now, Seoudi, Talabat, Noon Minutes,
-- Rabbit, Carrefour); active FPs ("<Area> FP #<n>" or *Sahel*, not SLEEP);
-- (product, fp) pairs need a BF price AND app availability in the last 7 days.
--
-- Output: two row types under `row_type` —
--   'breadfast'  → one row per (product, fp, competitor) + gap columns.
--   'competitor' → national competitor-only catalogue (fp/product NULL); must
--                  NOT flow through the app's _BASE_CTE.
--
-- PIPELINE (one CTE per step)
--   STEP 0a  competitor_registry        the 7 benchmarked competitors
--   STEP 0a2 current_mapping            THE mapping truth (dim, v2, non-NULL)
--   STEP 0b  fp_registry                active fulfillment points
--   STEP 0c  fps_available_products     (product, fp) live in app ≤7d
--   STEPS 1–5  scored_products          revenue/quantity metrics, tiers, scores
--   STEPS 6–7  products_enriched_prices BF price per (product, fp) + gate
--   STEP 8   competitor_clean           freshest fact row per pair×fp, gated
--                                       to current mapping; per-FP sale_PI
--   STEP 9   competitor_mapping         one counterpart per (product, comp)
--   STEP 11  products_with_pi           assembly: products × competitors × fps
--   STEP 12  rec_base → ai_match_candidates  matcher output, read once
--   STEP 13  final_product_data         eligibility, action_type, classification
--   STEPS 15–20 (NEW 1–7)               gap layer: brand overlap, category
--                                       bridge, catalogue partition
--   OUTPUT   breadfast rows UNION ALL competitor-only rows
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
-- STEP 0a2 ▸ CURRENT MAPPING — THE ONE SOURCE OF "IS THIS PAIR MAPPED NOW"
-- mapped_bf_product_id (NULL = not mapped today) is the master-data truth;
-- the daily fact is history and spells "unmapped" as a hash-of-NULL key.
-- Every mapping decision flows from HERE.
-- ─────────────────────────────────────────────────────────────────────────────
current_mapping AS (
    SELECT
        cp.competitor_id,
        cp.competitor_product_key,
        SAFE_CAST(cp.mapped_bf_product_id AS INT64) AS bf_product_id,
        cp.competitor_product_id,
        cp.product_name_en AS competitor_product_name
    FROM `followbreadfast.l03_marts.dim_competitor_products` cp
    INNER JOIN competitor_registry cr
        ON cr.competitor_id = cp.competitor_id
    WHERE cp.mapped_bf_product_id IS NOT NULL
      -- v2 only: a mapping onto an uncrawled v1 row can never price — it
      -- reads as unmapped and surfaces as re-mapping work.
      AND cp.pricing_tool_version = 'v2'
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
-- STEPS 6–7 ▸ BREADFAST PRICES (PER FP) + ACTIVITY GATE — ONE PASS
-- The driver grid: (product, fp) pairs with a BF price AND active assortment,
-- so unmapped products still appear. Latest SCD row per pair (ROW_NUMBER, so
-- one-row-per-pair is a guarantee, not luck).
-- ═══════════════════════════════════════════════════════════════════════════
products_enriched_prices AS (
    SELECT
        s.*,
        p.fp_id,
        fr.fp_name,
        p.applied_regular_price AS bf_regular_price,
        COALESCE(NULLIF(p.applied_sale_price, 0), p.applied_regular_price) AS bf_sale_price,
        CASE
            WHEN p.valid_to_ltz >= CURRENT_DATE() THEN CURRENT_DATE()
            ELSE DATE(p.valid_to_ltz)
        END AS breadfast_last_updated_day,
        CASE
            WHEN p.valid_to_ltz >= CURRENT_DATE() THEN CURRENT_DATE()
            ELSE DATE(p.valid_to_ltz)
        END >= CURRENT_DATE() - 7 AS is_recent_breadfast
    FROM scored_products s
    INNER JOIN `followbreadfast.l03_marts.dim_fp_product_price_logs_scd` p
        ON s.product_key = p.product_key
    INNER JOIN fp_registry fr
        ON p.fp_id = fr.fp_id
    INNER JOIN fps_available_products av
        ON s.product_id = av.product_id
        AND p.fp_id = av.fp_id
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY p.product_key, p.fp_id
        ORDER BY p.valid_to_ltz DESC
    ) = 1
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 8–9 ▸ COMPETITOR PRICE PIPELINE — RE-SOURCED ONTO THE DAILY FACT
--   Step 8 — latest daily-comparison row per (competitor, BF product, fp),
--            gated to the current mapping, with per-FP sale_PI computed in
--            place (= the fp_sale_price_index metric's row-level sale_pi).
--   Step 9 — product-level mapping from current_mapping (FP-agnostic).
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 8 ▸ COMPETITOR PRICES — LATEST DAILY OBSERVATION (PER FP)
-- Freshest comparison day per (competitor, mapped BF product, fp), gated to
-- the CURRENT mapping. Counterpart id/name come from current_mapping (the
-- same dim rows the gate reads). MIN/MAX are point values — the daily fact
-- carries no within-fp location spread.
-- ─────────────────────────────────────────────────────────────────────────────
competitor_clean AS (
    SELECT
        cr.competitor_id,
        cr.competitor_name,
        fr.fp_id,
        fr.fp_name,
        cm.competitor_product_id,
        cm.competitor_product_name,
        h.competitor_product_key,
        dp.product_id AS bf_product_id,

        -- Prices straight from the metric's source table
        NULLIF(h.last_seen_sale_price, 0)    AS competitor_sale_price,   -- carry-forward, >0
        NULLIF(h.last_seen_regular_price, 0) AS competitor_regular_price,
        NULLIF(h.bf_eod_sale_price, 0)       AS breadfast_sale_price,    -- BF end-of-day
        NULLIF(h.bf_eod_regular_price, 0)    AS breadfast_regular_price,
        -- No location spread in the daily fact → point value
        NULLIF(h.last_seen_sale_price, 0)    AS min_competitor_sale_price,
        NULLIF(h.last_seen_sale_price, 0)    AS max_competitor_sale_price,

        -- sale_PI = bf_eod_sale_price / last_seen_sale_price → identical to the
        -- fp_sale_price_index metric's row-level sale_pi.
        SAFE_DIVIDE(NULLIF(h.bf_eod_sale_price, 0),
                    NULLIF(h.last_seen_sale_price, 0)) AS sale_PI,

        -- Freshness anchored to the BUILD date, not the row's own day — a pair
        -- the fact stops emitting decays to stale instead of freezing "fresh".
        (DATE_SUB(h.date_day, INTERVAL h.days_since_crawl DAY)
            >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)) AS is_recent_competitor,

        -- Actual last crawl date (date_day is the comparison day)
        DATE_SUB(h.date_day, INTERVAL h.days_since_crawl DAY) AS date_day
    FROM `followbreadfast.l03_marts.fct_daily_competitor_price_comparison` h
    INNER JOIN competitor_registry cr
        ON h.competitor_key = cr.competitor_key
    INNER JOIN fp_registry fr
        ON h.fp_id = fr.fp_id
    LEFT JOIN `followbreadfast.l03_marts.dim_products` dp
        ON h.mapped_product_key = dp.product_key
    -- The current-mapping gate: keep a price row only when the fact's pair IS
    -- today's mapping. History rows for since-unassigned pairs (and the
    -- hash-of-NULL rows) die here.
    INNER JOIN current_mapping cm
        ON  cm.competitor_id = cr.competitor_id
        AND cm.competitor_product_key = h.competitor_product_key
        AND cm.bf_product_id = dp.product_id
    -- The fact is LOCATION grain; this ORDER BY is the location collapse:
    -- freshest crawl wins, equal freshness → LOWEST real price (house tie
    -- rule; guards one-off promos and bad scrapes).
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY cr.competitor_id, h.mapped_product_key, h.fp_id
        ORDER BY
            h.date_day DESC,                              -- freshest comparison day
            h.days_since_crawl ASC,                       -- freshest crawl
            NULLIF(h.last_seen_sale_price, 0) ASC NULLS LAST,  -- ties → lowest real price
            h.competitor_product_key                      -- final determinism
    ) = 1
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 9 ▸ COMPETITOR MAPPING (PRODUCT-LEVEL, FP-AGNOSTIC) — DIM-ANCHORED
-- The mapping IS current_mapping. Several of theirs → one of ours: the
-- displayed counterpart is the most recently priced one.
-- ─────────────────────────────────────────────────────────────────────────────
competitor_mapping AS (
    SELECT
        cm.bf_product_id,
        cm.competitor_id,
        cr.competitor_name,
        cm.competitor_product_id,
        cm.competitor_product_key,
        cm.competitor_product_name
    FROM current_mapping cm
    INNER JOIN competitor_registry cr
        ON cr.competitor_id = cm.competitor_id
    LEFT JOIN (
        SELECT competitor_id, competitor_product_key, MAX(date_day) AS last_obs
        FROM competitor_clean
        GROUP BY 1, 2
    ) obs
        ON  obs.competitor_id = cm.competitor_id
        AND obs.competitor_product_key = cm.competitor_product_key
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY cm.bf_product_id, cm.competitor_id
        ORDER BY obs.last_obs DESC NULLS LAST, cm.competitor_product_key
    ) = 1
),


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 11–13 ▸ ASSEMBLY, AI CANDIDATES, FLAGS & CLASSIFICATION
-- ═══════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 11 ▸ JOIN SCORES + MAPPING + PRICE INDEX
-- Driver: products_enriched_prices (gated on activity + BF SCD pricing).
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
        pi.date_day AS competitor_last_updated_day,

        -- Both sides fresh (≤ 7 days)
        (s.is_recent_breadfast AND pi.is_recent_competitor) AS prices_recently_updated,

        -- Product-level mapping flag (carries across FPs)
        (cm.competitor_product_id IS NOT NULL) AS is_mapped
    FROM products_enriched_prices s
    CROSS JOIN competitor_registry cr
    LEFT JOIN competitor_mapping cm
        ON s.product_id = cm.bf_product_id
        AND cr.competitor_id = cm.competitor_id
    LEFT JOIN competitor_clean pi
        ON s.product_id = pi.bf_product_id
        AND s.fp_id = pi.fp_id
        AND cr.competitor_id = pi.competitor_id
),


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 12 ▸ AI MATCH CANDIDATES (PRODUCT-LEVEL, REPLICATED ACROSS FPS) — UNCHANGED
-- ─────────────────────────────────────────────────────────────────────────────
-- The matcher's output, read ONCE: v2 only (v1 never records a rejection, so
-- it would block the 'not match' branches); country_code pins the read.
-- recommended_product_status ∈ 'mapped' (accepted) · 'ambiguous mapping'
-- (competing accepted targets) · 'not match' (explicitly rejected) ·
-- 'pending action' (awaiting review).
rec_base AS (
    SELECT
        r.competitor_id,
        CAST(r.bf_product_id AS INT64) AS bf_product_id,
        r.competitor_product_id,
        r.competitor_product_key,
        r.similarity_score,
        r.recommended_product_status
    FROM `followbreadfast.l03_marts.dim_recommended_bf_competitor_products` r
    INNER JOIN competitor_registry cr
        ON r.competitor_id = cr.competitor_id
    WHERE r.pricing_tool_version = 'v2'
      AND r.country_code = 'EG'
),

ai_match_candidates AS (
    SELECT
        rb.bf_product_id AS recommended_bf_product_id,
        rb.competitor_id,
        rb.similarity_score,
        cp.product_name_en AS match_potential_product_name,
        rb.recommended_product_status
    FROM rec_base rb
    LEFT JOIN `followbreadfast.l03_marts.dim_competitor_products` cp
        ON rb.competitor_product_id = cp.competitor_product_id
        AND cp.competitor_id = rb.competitor_id
    QUALIFY ROW_NUMBER() OVER (PARTITION BY rb.bf_product_id, rb.competitor_id
        ORDER BY rb.similarity_score DESC) = 1
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

        -- ─── Classification tree ─────────────────────────────────────────────
        -- Keys on is_mapped (Mapped = LINKED, same definition as Mapped %
        -- everywhere), never on sale_PI.
        CASE
            -- Branch 1: MAPPED
            WHEN w.is_mapped AND w.brand_name != 'Breadfast'
                THEN 'Mapped - Not PL'
            WHEN w.is_mapped AND w.brand_name = 'Breadfast'
                THEN 'Mapped - PL'

            -- Branch 2a: NOT MAPPED — PL
            WHEN NOT w.is_mapped
                 AND w.brand_name = 'Breadfast'
                 AND recommended_product_status = 'not match'
                THEN 'Not Mapped - PL - No Match'
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
                 AND recommended_product_status = 'not match'
                THEN 'Not Mapped - Not PL - No Match'
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


-- ═══════════════════════════════════════════════════════════════════════════
-- STEPS 15-20 ▸ GAP-ANALYSIS LAYER (added 2026-08-03)
-- Adds the assortment-gap columns (brand overlap, category bridge, catalogue
-- partition) to the same output rows. Section labels NEW 1-7 are stable
-- identifiers referenced from docs/DDD.md and the app specs — do not renumber.
--
-- SOURCE CONTRACT: match determination = current_mapping (dim, v2); the fact
-- supplies price history for currently-mapped pairs and the crawl clock;
-- dim_competitor_products is also the CATALOGUE (only source of never-matched
-- products). Comp-only rows are NATIONAL (fp NULL); PL/Beauty kept but
-- flagged; similarity 0.85 everywhere.
--
-- DOWNSTREAM WARNING: competitor-only rows (product_id NULL) MUST NOT flow
-- through the app's _BASE_CTE (it collapses on product_id, competitor_id).
-- =============================================================================

-- ── NEW 1 ▸ ANY CURRENT MATCH (unrestricted to our universe) ────────────────
-- Mapped-out-of-scope must stay distinguishable from never-matched. A bare
-- projection of current_mapping, named only for the join sites.
comp_matched_any AS (
    SELECT competitor_id, competitor_product_key FROM current_mapping
),

-- ── NEW 2 ▸ BREADFAST UNIVERSE AT PRODUCT GRAIN ─────────────────────────────
-- products_enriched_prices is per (product, fp). Gap metrics are national, so
-- collapse to product grain and attach brand_key + scope flags.
bf_universe_enriched AS (
    SELECT
        s.product_id,
        ANY_VALUE(s.product_key)        AS product_key,
        ANY_VALUE(s.sub_category_name)  AS sub_category_name,
        ANY_VALUE(s.main_category_name) AS main_category_name,
        ANY_VALUE(s.brand_name)         AS brand_name,
        COALESCE(ANY_VALUE(dp.brand_slug), LOWER(ANY_VALUE(s.brand_name)))  AS brand_key,
        (ANY_VALUE(s.main_category_name) = 'Fragrances & Beauty')           AS is_beauty,
        -- is_private_label is deliberately WIDER than STEP 13's
        -- brand_name != 'Breadfast': brand grain makes 'Breadfast Bakery' a
        -- first-class row.
        (LOWER(ANY_VALUE(s.brand_name)) LIKE '%breadfast%')                 AS is_private_label
    FROM products_enriched_prices s
    LEFT JOIN `followbreadfast.l03_marts.dim_products` AS dp
        ON dp.product_key = s.product_key
    GROUP BY s.product_id
),
bf_brands AS (
    SELECT DISTINCT brand_key FROM bf_universe_enriched WHERE brand_key IS NOT NULL
),

-- ── NEW 6 ▸ PAIRED KEYS (reachability-gated) ────────────────────────────────
-- Competitor products represented on a Breadfast row. Gated on
-- final_product_data so a match to an out-of-universe BF product falls to the
-- comp-only side, not out of the table — this keeps paired + unpaired an
-- exact PARTITION of the active catalogue.
paired_comp_keys AS (
    SELECT DISTINCT cm.competitor_id, cm.competitor_product_key
    FROM competitor_mapping AS cm
    INNER JOIN (
        SELECT DISTINCT product_id, competitor_id FROM final_product_data
    ) AS reachable
        ON  reachable.competitor_id = cm.competitor_id
        AND reachable.product_id    = cm.bf_product_id
    WHERE cm.competitor_product_key IS NOT NULL
),

-- ── NEW 3a ▸ FACT CRAWL CLOCK (per competitor product) ──────────────────────
-- The ONLY activity clock: latest true crawl date per product; MAX over its
-- rows (one per location per day) = fresh if ANY location crawled recently.
-- The dim's updated_at_ltz is NOT consulted — it lags the crawl (Seoudi:
-- 2,403) and covers no product the fact lacks (measured zero). 8-day window
-- guarantees anything crawled within 7 days is present; absent 8+ = inactive.
fact_crawl_clock AS (
    SELECT
        cr.competitor_id,
        h.competitor_product_key,
        MAX(DATE_SUB(DATE(h.date_day), INTERVAL h.days_since_crawl DAY)) AS last_crawl
    FROM `followbreadfast.l03_marts.fct_daily_competitor_price_comparison` h
    INNER JOIN competitor_registry cr
        ON h.competitor_key = cr.competitor_key
    WHERE DATE(h.date_day) >= DATE_SUB(CURRENT_DATE(), INTERVAL 8 DAY)
      AND h.competitor_product_key IS NOT NULL
    GROUP BY 1, 2
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
        -- Activity from the FACT's crawl clock only. A product with no clock
        -- row was not crawled in 8 days: inactive, comp_last_seen NULL.
        MAX(IF(fc.last_crawl >= CURRENT_DATE() - 7, 1, 0))                  AS is_active_7d,
        MAX(fc.last_crawl)                                                  AS comp_last_seen
    FROM `followbreadfast.l03_marts.dim_competitor_products` AS cp
    INNER JOIN competitor_registry AS cr ON cr.competitor_id = cp.competitor_id
    LEFT JOIN fact_crawl_clock AS fc
        ON  fc.competitor_id          = cp.competitor_id
        AND fc.competitor_product_key = cp.competitor_product_key
    WHERE cp.pricing_tool_version = 'v2'
    GROUP BY cp.competitor_id, cr.competitor_name, cp.competitor_product_key
),
-- Dedup identical names within (competitor, brand) to ONE row (paired copy
-- wins, else matched, else freshest); unmatched ' + ' bundle names dropped.
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
            IF(ma.competitor_product_key IS NOT NULL, 1, 0) AS is_matched_any,
            IF(pk.competitor_product_key IS NOT NULL, 1, 0) AS is_paired
        FROM comp_products_raw AS r
        LEFT JOIN comp_matched_any AS ma
            ON  ma.competitor_id          = r.competitor_id
            AND ma.competitor_product_key = r.competitor_product_key
        LEFT JOIN paired_comp_keys AS pk
            ON  pk.competitor_id          = r.competitor_id
            AND pk.competitor_product_key = r.competitor_product_key
    )
    -- Paired bundles KEPT (dropping one strands our product as unmatched);
    -- spaced ' + ' only ("Vitamin B+" is no bundle).
    WHERE ( is_paired = 1
            OR NOT REGEXP_CONTAINS(COALESCE(comp_product_name, ''), r'\s\+\s') )
    -- Empty names are never collapsed into each other.
    QUALIFY name_norm = ''
         OR ROW_NUMBER() OVER (
                PARTITION BY competitor_id, name_norm, brand_norm
                -- is_paired FIRST: the matched copy must survive, or the
                -- product reads "they only" while its matched twin vanishes.
                ORDER BY is_paired DESC,             -- the copy we actually matched
                         is_matched_any DESC,        -- else any matched copy
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
        -- Same count restricted to brands we also carry — not derivable in the
        -- app (comp_catalogue downstream holds only UNPAIRED products).
        -- bf_brands is DISTINCT brand_key, so the join cannot fan the count.
        COUNTIF(cp.is_active_7d = 1 AND bb.brand_key IS NOT NULL)
                                         AS comp_active_products_shared,
        COUNTIF(cp.is_active_7d = 1) > 0 AS competitor_has_v2_catalogue
    FROM competitor_registry AS cr
    LEFT JOIN comp_products AS cp ON cp.competitor_id = cr.competitor_id
    LEFT JOIN bf_brands     AS bb ON bb.brand_key     = cp.brand_key
    GROUP BY cr.competitor_id
),

-- ── NEW 4 ▸ CATEGORY BRIDGE (competitor category path -> BF subcategory) ────
-- Evidence = the query's own competitor_mapping (STEP 9, i.e. the current
-- dim mapping). Keyed on the full path incl. level_4 (only Amazon
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
-- Same single read of the matcher's output as STEP 12 (rec_base), so
-- confirmed-no-match and match-potential can never come from two different
-- generations of the matcher.
rec_flags AS (
    SELECT
        rb.competitor_id,
        rb.bf_product_id,
        -- accepted evidence = an accepted mapping, incl. a competing one;
        -- rejected = EXPLICIT rejection only — 'pending action' is neither
        -- (previously pending counted as rejected via NOT is_matched).
        LOGICAL_OR(rb.recommended_product_status IN ('mapped', 'ambiguous mapping')) AS has_true_rec,
        LOGICAL_OR(rb.recommended_product_status = 'not match')                      AS has_false_rec,
        -- best similarity among candidates still present in the portfolio
        MAX(IF(cp.competitor_product_key IS NOT NULL, rb.similarity_score, NULL)) AS best_similarity_in_portfolio
    FROM rec_base AS rb
    LEFT JOIN comp_products AS cp
        ON  cp.competitor_id          = rb.competitor_id
        AND cp.competitor_product_key = rb.competitor_product_key
    GROUP BY 1, 2
),

-- ── NEW 6 ▸ PAIR FRESHNESS ────────────────────────────────────────────────
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
),

-- ── NEW 7 ▸ BRAND OVERLAP FROM MATCH EVIDENCE ──────────────────────────────
-- Name equality misses manufacturer-vs-consumer labels (our Froneri = their
-- Nestle), so a brand also counts as shared when ≥50% of its products are
-- matched there — computed over the WHOLE range, never inside app filters
-- (Shared-only would feed on itself).
bf_brand_pair AS (          -- is_mapped is FP-agnostic; collapse the FP grain away
    SELECT product_id, competitor_id, LOGICAL_OR(is_mapped) AS is_mapped
    FROM final_product_data
    GROUP BY product_id, competitor_id
),
bf_brand_evidence AS (
    SELECT
        p.competitor_id,
        bu.brand_key,
        COUNT(DISTINCT p.product_id)                            AS brand_products,
        COUNT(DISTINCT IF(p.is_mapped, p.product_id, NULL))     AS brand_mapped
    FROM bf_brand_pair AS p
    JOIN bf_universe_enriched AS bu USING (product_id)
    WHERE bu.brand_key IS NOT NULL
    GROUP BY 1, 2
),
bf_brand_shared_by_match AS (
    SELECT competitor_id, brand_key
    FROM bf_brand_evidence
    WHERE brand_products > 0 AND brand_mapped / brand_products >= 0.5
),
-- The mirror, from their end; paired_comp_keys is range-gated, so "matched"
-- means matched to something we actually sell.
comp_brand_evidence AS (
    SELECT
        cp.competitor_id,
        cp.brand_key,
        COUNT(DISTINCT cp.competitor_product_key)               AS products,
        COUNT(DISTINCT IF(pk.competitor_product_key IS NOT NULL,
                          cp.competitor_product_key, NULL))     AS matched
    FROM comp_products AS cp
    LEFT JOIN paired_comp_keys AS pk
        ON  pk.competitor_id          = cp.competitor_id
        AND pk.competitor_product_key = cp.competitor_product_key
    WHERE cp.is_active_7d = 1 AND cp.brand_key IS NOT NULL
    GROUP BY 1, 2
),
comp_brand_shared_by_match AS (
    SELECT competitor_id, brand_key
    FROM comp_brand_evidence
    WHERE products > 0 AND matched / products >= 0.5
),
-- The audit trail for promoted brands: every distinct spelling the matches
-- landed on, grouped by DISPLAY name (so 7Up/7UP/7up stay visible), encoded
-- "brand:count|brand:count", ranked, capped at 10. Blank names dropped.
brand_variants AS (
    SELECT
        competitor_id,
        bf_brand_key,
        STRING_AGG(CONCAT(comp_brand, ':', CAST(n AS STRING)), '|'
                   ORDER BY n DESC, comp_brand) AS comp_brand_variants
    FROM (
        SELECT competitor_id, bf_brand_key, comp_brand,
               COUNT(DISTINCT competitor_product_key) AS n
        FROM (
            SELECT
                f.competitor_id,
                bu.brand_key AS bf_brand_key,
                -- DISPLAY name, not key (the key collapses the variants this
                -- column exists to show); '(unbranded)' so a matched brand
                -- never reads blank.
                COALESCE(NULLIF(TRIM(cpx.comp_brand_name), ''),
                         NULLIF(TRIM(cpx.brand_key), ''),
                         '(unbranded)') AS comp_brand,
                cpx.competitor_product_key
            FROM (SELECT DISTINCT product_id, competitor_id FROM final_product_data) AS f
            JOIN bf_universe_enriched AS bu ON bu.product_id = f.product_id
            JOIN competitor_mapping   AS cm
                 ON cm.competitor_id = f.competitor_id AND cm.bf_product_id = f.product_id
            -- comp_products_RAW, not the deduped table: a key the mapping
            -- points at may have been collapsed away there, silently blanking
            -- the variants of mapped brands.
            JOIN comp_products_raw    AS cpx
                 ON  cpx.competitor_id          = cm.competitor_id
                 AND cpx.competitor_product_key = cm.competitor_product_key
            WHERE bu.brand_key IS NOT NULL
              -- Same-key brands stay in: their shelf can still spell the name
              -- several ways, and showing that is the point.
        )
        GROUP BY 1, 2, 3
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY competitor_id, bf_brand_key ORDER BY n DESC, comp_brand) <= 10
    )
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
    -- Brand overlap: names agree, OR the matches prove they stock it anyway.
    (cb.brand_key IS NOT NULL OR sbm.brand_key IS NOT NULL) AS is_shared_brand,
    -- Which of the two it was, so the UI can show provenance instead of asking
    -- anyone to take a promoted brand on faith.
    (cb.brand_key IS NULL AND sbm.brand_key IS NOT NULL)    AS shared_brand_by_match,
    bv.comp_brand_variants,
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
    -- The matched competitor product's key: lets the app count the PAIRED half
    -- of their catalogue (DISTINCT — one of theirs can answer several of ours),
    -- so paired + unpaired partition the active catalogue under any filter.
    cmk.competitor_product_key AS competitor_product_key,
    -- Is that matched product in the live deduped catalogue? Uses the exact
    -- predicate behind comp_active_products, so the partition sums to it.
    (COALESCE(mcp.is_active_7d, 0) = 1) AS matched_comp_in_catalogue,
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
    cc.competitor_has_v2_catalogue,
    -- Catalogue totals: not derivable downstream (comp rows are unpaired only).
    cc.comp_active_products,
    cc.comp_active_products_shared
FROM final_product_data AS f
LEFT JOIN bf_universe_enriched AS bu ON bu.product_id = f.product_id
LEFT JOIN comp_brand           AS cb ON cb.competitor_id = f.competitor_id AND cb.brand_key = bu.brand_key
LEFT JOIN bf_pair_freshness    AS fr ON fr.competitor_id = f.competitor_id AND fr.bf_product_id = f.product_id
LEFT JOIN rec_flags            AS rf ON rf.competitor_id = f.competitor_id AND rf.bf_product_id = f.product_id
LEFT JOIN competitor_catalogue AS cc ON cc.competitor_id = f.competitor_id
-- Every joined CTE is one row per its join key — nothing fans the grain out.
LEFT JOIN bf_brand_shared_by_match AS sbm
       ON sbm.competitor_id = f.competitor_id AND sbm.brand_key = bu.brand_key
LEFT JOIN brand_variants       AS bv
       ON bv.competitor_id = f.competitor_id AND bv.bf_brand_key = bu.brand_key
LEFT JOIN competitor_mapping   AS cmk ON cmk.competitor_id = f.competitor_id
                                     AND cmk.bf_product_id = f.product_id
LEFT JOIN comp_products        AS mcp ON mcp.competitor_id = f.competitor_id
                                     AND mcp.competitor_product_key = cmk.competitor_product_key

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
    -- Does BREADFAST carry this brand -- by name, or on the evidence that half
    -- its products here are matched to ours under a different label.
    (bb.brand_key IS NOT NULL OR csbm.brand_key IS NOT NULL) AS is_shared_brand,
    (bb.brand_key IS NULL AND csbm.brand_key IS NOT NULL)    AS shared_brand_by_match,
    -- Same ordinal slot as the Breadfast branch. Their brand IS the variant, so
    -- there is nothing to list back at them.
    CAST(NULL AS STRING)  AS comp_brand_variants,
    CAST(NULL AS INT64)   AS matched_comp_active_7d,
    CAST(NULL AS BOOL)    AS is_confirmed_no_match,
    CAST(NULL AS BOOL)    AS is_potential_match,
    CAST(NULL AS NUMERIC) AS best_similarity_in_portfolio,
    -- competitor-side detail
    cp.competitor_product_key,
    -- FALSE, not NULL: these rows ARE the unpaired half; counting the flag
    -- here would double-count the partition.
    FALSE                 AS matched_comp_in_catalogue,
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
    cc.competitor_has_v2_catalogue,
    cc.comp_active_products,
    -- Same position as the breadfast branch: UNION ALL matches by ordinal.
    cc.comp_active_products_shared
FROM comp_products AS cp
LEFT JOIN paired_comp_keys AS pk
    ON  pk.competitor_id          = cp.competitor_id
    AND pk.competitor_product_key = cp.competitor_product_key
LEFT JOIN bf_brands AS bb ON bb.brand_key = cp.brand_key
LEFT JOIN comp_brand_shared_by_match AS csbm
       ON csbm.competitor_id = cp.competitor_id AND csbm.brand_key = cp.brand_key
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
