"""
DuckDB-backed pricing data service.

Inherits from BigQueryPricingDataService and overrides the slow filter-heavy
methods to use DuckDB queries against a Parquet file. All other methods fall
through to the pandas implementation.

This is intentionally minimal in Phase 1 — only the highest-impact endpoint
(get_blended_pi_by_subcategory) is overridden. Phase 2 will add the other
4 priority endpoints.

Modal price aggregation matches pandas exactly: pick smallest value among the
most-frequent (tie-breaker on value ascending), validated in Phase 0 spike.
"""

import logging
import threading
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from backend.services.bigquery_service import BigQueryPricingDataService
from backend.services.parquet_cache import exists as parquet_exists, is_fresh, write_parquet
from backend.utils.calculations import pi_direction

logger = logging.getLogger(__name__)


class DuckDBPricingDataService(BigQueryPricingDataService):
    """BigQuery service + DuckDB acceleration for hot-path queries.

    The pandas DataFrames `_df`, `_global_df`, `_competitor_df` are still loaded
    (and used by non-overridden methods), but the slow filter+aggregate methods
    push down to DuckDB.
    """

    def __init__(
        self,
        parquet_path: str = "cache/pricing_data/fp_grain.parquet",
        max_parquet_age_hours: int = 24,
        **bq_kwargs,
    ):
        super().__init__(**bq_kwargs)
        self._parquet_path = Path(parquet_path)
        self._max_parquet_age_hours = max_parquet_age_hours
        self._duckdb_conn: Optional[duckdb.DuckDBPyConnection] = None
        self._duckdb_lock = threading.Lock()
        self._init_duckdb()

    def _init_duckdb(self) -> None:
        """Open a DuckDB view over the fp-grain Parquet.

        Writes the Parquet from the in-memory `_df` UNLESS the Parquet is the
        authoritative source of `_df` (set via `_parquet_from_source`). Writing
        is otherwise required so the Parquet matches the freshly-loaded `_df`
        (cold BigQuery load or legacy pickle load). We deliberately do NOT write
        based on file age — that would reset the mtime and defeat the
        background-refresh staleness check in main.py.
        """
        parquet_from_source = getattr(self, "_parquet_from_source", False)
        if not parquet_exists(self._parquet_path) or not parquet_from_source:
            logger.info("[DuckDB] Writing fp-grain Parquet from in-memory _df")
            write_parquet(self._df, self._parquet_path)

        self._duckdb_conn = duckdb.connect(":memory:", read_only=False)
        self._duckdb_conn.execute("PRAGMA threads=4")
        self._duckdb_conn.execute(
            f"CREATE OR REPLACE VIEW fp_grain AS "
            f"SELECT * FROM read_parquet('{self._parquet_path}')"
        )
        self._assert_gap_schema()
        self._materialize_global_base()
        self._materialize_comp_catalogue()
        # Pre-warm in three stages:
        # 1. Page the entire Parquet file into OS cache (one large sequential read)
        # 2. Run a GLOBAL blended-pi query — warms DuckDB internals + tests SQL
        # 3. Run a single-FP blended-pi query — warms the per-FP code path
        import time
        t0 = time.time()
        try:
            # Stage 1: force the OS to cache the Parquet file
            with open(self._parquet_path, "rb") as fh:
                while fh.read(8 * 1024 * 1024):  # 8 MB chunks
                    pass
            logger.info(f"[DuckDB] Parquet paged into OS cache in {time.time() - t0:.1f}s")

            # Stage 2 + 3: warm DuckDB's internal caches
            t1 = time.time()
            self.get_blended_pi_by_subcategory(filters=None)
            logger.info(f"[DuckDB] GLOBAL pre-warm query: {time.time() - t1:.1f}s")

            # Find an FP with the most data and pre-warm against it
            t1 = time.time()
            # row_type guard matters here: the competitor-only rows share a
            # single NULL fp_name group that is larger than any real FP, so
            # without it this picks NULL and the FP pre-warm silently degrades
            # into a second GLOBAL query.
            top_fp_result = self._duckdb_conn.execute(
                "SELECT fp_name FROM fp_grain WHERE row_type = 'breadfast' "
                "GROUP BY fp_name ORDER BY COUNT(*) DESC LIMIT 1"
            ).fetchone()
            if top_fp_result:
                self.get_blended_pi_by_subcategory(filters={"fp_names": top_fp_result[0]})
                logger.info(f"[DuckDB] FP pre-warm query: {time.time() - t1:.1f}s")
        except Exception as e:
            logger.warning(f"[DuckDB] Pre-warm failed (continuing): {e}")

        (row_count,) = self._duckdb_conn.execute("SELECT COUNT(*) FROM fp_grain").fetchone()
        logger.info(
            f"[DuckDB] Ready — {row_count:,} rows, total pre-warm {time.time() - t0:.1f}s"
        )

    def _assert_gap_schema(self) -> None:
        """Fail loudly, and early, if the Parquet predates the gap-analysis layer.

        Every aggregation path now gates on `row_type`. Without this check a
        stale Parquet surfaces as a DuckDB binder error from deep inside a
        query — or worse, only on the endpoints that happen to be hit first.
        A restart alone does NOT pick up new columns (`_load_data` rehydrates
        the existing Parquet), so the fix is always a forced refresh.
        """
        cols = {
            r[0] for r in self._duckdb_conn.execute(
                "SELECT column_name FROM (DESCRIBE SELECT * FROM fp_grain)"
            ).fetchall()
        }
        missing = {"row_type", "brand_key", "is_shared_brand", "mapped_bf_sub_category"} - cols
        if missing:
            raise RuntimeError(
                f"Parquet cache is missing the gap-analysis columns {sorted(missing)}. "
                f"It predates the BigQuery gap layer. Delete {self._parquet_path} "
                "(or POST /api/admin/refresh) to force a rebuild — a restart alone "
                "rehydrates the same stale file."
            )

    def _materialize_comp_catalogue(self) -> None:
        """Materialize the national competitor-only catalogue.

        Deliberately NOT routed through `_BASE_CTE`: these rows carry
        product_id = NULL, so its GROUP BY (product_id, competitor_id) would
        collapse the whole catalogue into one row per competitor. They also need
        no collapsing — the BigQuery layer already emits exactly one row per
        (competitor, competitor product), national.
        """
        import time
        t0 = time.time()
        self._duckdb_conn.execute(
            "CREATE OR REPLACE TABLE comp_catalogue AS "
            "SELECT * FROM fp_grain WHERE row_type = 'competitor'"
        )
        (n,) = self._duckdb_conn.execute("SELECT COUNT(*) FROM comp_catalogue").fetchone()
        logger.info(f"[DuckDB] Materialized comp_catalogue: {n:,} rows in {time.time() - t0:.1f}s")

    def _materialize_global_base(self) -> None:
        """Materialize the GLOBAL (unfiltered) aggregated base into a DuckDB
        table so GLOBAL queries hit a ~150K-row table instead of re-aggregating
        4.9M rows on every request — the DuckDB equivalent of the old pandas
        `_global_df` precompute, but using the single `_BASE_CTE` definition.
        """
        import time
        t0 = time.time()
        self._duckdb_conn.execute(
            "CREATE OR REPLACE TABLE global_base AS "
            + self._base_cte("")
            + " SELECT * FROM base"
        )
        (n,) = self._duckdb_conn.execute("SELECT COUNT(*) FROM global_base").fetchone()
        logger.info(f"[DuckDB] Materialized global_base: {n:,} rows in {time.time() - t0:.1f}s")

    def refresh_parquet(self) -> None:
        """Re-export `_df` to Parquet and reload the DuckDB view (called after BG refresh)."""
        with self._duckdb_lock:
            write_parquet(self._df, self._parquet_path)
            self._duckdb_conn.execute(
                f"CREATE OR REPLACE VIEW fp_grain AS "
                f"SELECT * FROM read_parquet('{self._parquet_path}')"
            )
            self._assert_gap_schema()
            self._materialize_global_base()
            self._materialize_comp_catalogue()
            logger.info(
                "[DuckDB] Refreshed Parquet + reopened view + rebuilt global_base + comp_catalogue"
            )

    # ------------------------------------------------------------------
    # OVERRIDDEN — _apply_filters: the single aggregation path for EVERY
    # filter-heavy method. Both GLOBAL and FP-scoped now go through DuckDB
    # `_BASE_CTE` (the pandas `_global_df` path is retired):
    #   - GLOBAL    → read the pre-materialized `global_base` table (fast)
    #   - FP-scoped → run `_BASE_CTE` with a WHERE on fp_name
    # then merge catalog prices + apply the remaining filters in pandas.
    # ------------------------------------------------------------------
    def _apply_filters(self, df: pd.DataFrame, filters: dict | None = None) -> pd.DataFrame:
        fp_names = filters.get("fp_names") if filters else None
        with self._duckdb_lock:
            if fp_names:
                where, params = self._build_where_clause({"fp_names": fp_names})
                sql = self._base_cte(where) + " SELECT * FROM base"
                aggregated = self._duckdb_conn.execute(sql, params).df()
            else:
                # GLOBAL: pre-materialized aggregation (~150K rows, fast)
                aggregated = self._duckdb_conn.execute("SELECT * FROM global_base").df()

        # now_price / now_sale_price come from BQ in the base query
        # (bf_regular_price / modal sale). Read-only — price editing was removed.

        # Apply remaining filters in pandas (now operating on the small
        # aggregated frame — ~150K rows max, much faster than scanning 4.5M)
        filtered = aggregated
        if filters:
            if filters.get("main_category"):
                filtered = self._multi_match(filtered, "commercial_category_name", filters["main_category"])
            if filters.get("sub_category"):
                filtered = self._multi_match(filtered, "sub_category_name", filters["sub_category"])
            if filters.get("global_tier"):
                filtered = self._multi_match(filtered, "global_tier", filters["global_tier"])
            if filters.get("subcat_tier"):
                filtered = self._multi_match(filtered, "subcat_tier", filters["subcat_tier"])
            if filters.get("action_type"):
                filtered = self._multi_match(filtered, "action_type", filters["action_type"])
            if filters.get("brand"):
                filtered = self._multi_match(filtered, "brand_name", filters["brand"])
            if filters.get("competitor"):
                filtered = self._multi_match(filtered, "competitor_name", filters["competitor"])
            if filters.get("vertical"):
                v = str(filters["vertical"]).strip().lower()
                mc = filtered["main_category_name"].fillna("").str.lower()
                if v == "beauty":
                    filtered = filtered[mc == "fragrances & beauty"]
                elif v == "supermarket":
                    filtered = filtered[mc != "fragrances & beauty"]
            if filters.get("exclude_private_label"):
                filtered = filtered[~filtered["brand_name"].str.lower().str.contains("breadfast", na=False)]
            # Brand scope. Applied here as well as in _build_where_clause because
            # the GLOBAL path reads the pre-built global_base and narrows it in
            # pandas; same filter-after caveat that already applies to
            # `competitor` on this path.
            scope = str(filters.get("brand_scope") or "").strip().lower()
            if scope in ("shared", "shared_name") and "is_shared_brand" in filtered.columns:
                filtered = filtered[filtered["is_shared_brand"] == True]
                if scope == "shared_name" and "shared_brand_by_match" in filtered.columns:
                    filtered = filtered[filtered["shared_brand_by_match"] != True]
        return filtered

    # ------------------------------------------------------------------
    # OVERRIDDEN — filter/fp option lists, sourced from DuckDB instead of the
    # pandas `_df` (which is no longer loaded on the serving path).
    # ------------------------------------------------------------------
    def _load_product_rows(self, product_id):
        """Fetch one product's fp-grain rows from the Parquet view (the pandas
        `_df` isn't loaded on the DuckDB serving path)."""
        with self._duckdb_lock:
            return self._duckdb_conn.execute(
                "SELECT * FROM fp_grain "
                "WHERE row_type = 'breadfast' AND CAST(product_id AS VARCHAR) = ?",
                [str(product_id)],
            ).df()

    def get_fp_options(self) -> list[str]:
        with self._duckdb_lock:
            rows = self._duckdb_conn.execute(
                "SELECT DISTINCT fp_name FROM fp_grain WHERE fp_name IS NOT NULL ORDER BY fp_name"
            ).fetchall()
        return [r[0] for r in rows]

    def get_filter_options(self, main_category: Optional[str] = None) -> dict:
        con = self._duckdb_conn
        with self._duckdb_lock:
            mains = [r[0] for r in con.execute(
                "SELECT DISTINCT commercial_category_name FROM global_base "
                "WHERE commercial_category_name IS NOT NULL ORDER BY 1"
            ).fetchall()]
            if main_category:
                subs = [r[0] for r in con.execute(
                    "SELECT DISTINCT sub_category_name FROM global_base "
                    "WHERE sub_category_name IS NOT NULL AND commercial_category_name = ? ORDER BY 1",
                    [main_category],
                ).fetchall()]
            else:
                subs = [r[0] for r in con.execute(
                    "SELECT DISTINCT sub_category_name FROM global_base "
                    "WHERE sub_category_name IS NOT NULL ORDER BY 1"
                ).fetchall()]
            brands = [r[0] for r in con.execute(
                "SELECT DISTINCT brand_name FROM global_base WHERE brand_name IS NOT NULL ORDER BY 1"
            ).fetchall()]
            comps = [r[0] for r in con.execute(
                "SELECT DISTINCT competitor_name FROM global_base WHERE competitor_name IS NOT NULL ORDER BY 1"
            ).fetchall()]
        return {
            "main_categories": mains,
            "sub_categories": subs,
            "global_tiers": ["Top+", "Top", "Medium", "Low", "Very Low"],
            "subcat_tiers": ["Top+", "Top", "Medium", "Low", "Very Low"],
            "action_types": ["Needs Mapping", "Review Match", "Needs Price Update", "Complete"],
            "brands": brands,
            "competitors": comps,
        }

    # ------------------------------------------------------------------
    # Filter parsing helpers — translate the dict-of-filters into SQL
    # ------------------------------------------------------------------
    def _build_where_clause(self, filters: dict | None) -> tuple[str, list]:
        """Build a SQL WHERE fragment + parameter list from the filters dict.

        Returns ("WHERE col IN (?, ?) AND ...", [val1, val2, ...]).
        Returns ("", []) when there are no filters.
        """
        if not filters:
            return "", []

        clauses = []
        params: list = []

        def add_in_filter(column: str, key: str):
            raw = filters.get(key)
            if not raw:
                return
            values = [v.strip() for v in str(raw).split(",") if v.strip()]
            if not values:
                return
            placeholders = ", ".join(["?"] * len(values))
            clauses.append(f"{column} IN ({placeholders})")
            params.extend(values)

        add_in_filter("fp_name", "fp_names")
        # NOTE: the app's "Categories" filter (`main_category`) carries
        # commercial_category_name values (that's what get_filter_options serves
        # and what the category roll-up groups on), so it must filter that column
        # — not main_category_name — to match the dropdown and the category drill.
        add_in_filter("commercial_category_name", "main_category")
        add_in_filter("sub_category_name", "sub_category")
        add_in_filter("global_tier", "global_tier")
        add_in_filter("brand_name", "brand")
        add_in_filter("competitor_name", "competitor")
        add_in_filter("action_type", "action_type")

        # Vertical — derived from main_category_name: Beauty = 'Fragrances & Beauty',
        # Supermarket = everything else. A single-select toggle ('' / All = no filter).
        vertical = str(filters.get("vertical") or "").strip().lower()
        if vertical == "beauty":
            clauses.append("LOWER(main_category_name) = 'fragrances & beauty'")
        elif vertical == "supermarket":
            clauses.append("(main_category_name IS NULL OR LOWER(main_category_name) <> 'fragrances & beauty')")

        # Private-label exclusion (matches pandas behavior)
        if filters.get("exclude_private_label"):
            clauses.append("brand_name != 'Breadfast'")

        # Brand scope — 'shared' keeps only (product, competitor) pairs whose brand
        # the competitor also carries. A brand they do not stock can never be
        # matched, so this turns every mapping rate on the screen into the
        # realistic ceiling rather than a target nobody can hit.
        # Three states, widening left to right:
        #   ''            every brand
        #   'shared_name' brands whose NAME matches on both sides -- the original,
        #                 strict reading of "they stock this brand"
        #   'shared'      the above PLUS brands proved shared by matching, where
        #                 the two names disagree (Froneri / Nestle). This is what
        #                 'shared' has meant since the 50% rule landed, so the
        #                 value is unchanged and no saved URL shifts meaning.
        scope = str(filters.get("brand_scope") or "").strip().lower()
        if scope == "shared":
            clauses.append("COALESCE(is_shared_brand, FALSE)")
        elif scope == "shared_name":
            clauses.append("COALESCE(is_shared_brand, FALSE) "
                           "AND NOT COALESCE(shared_brand_by_match, FALSE)")

        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        return where, params

    # ------------------------------------------------------------------
    # Core CTE template — used by multiple endpoints.
    # Builds the per-(product, competitor) aggregated state from FP-grain.
    # Recomputes is_recent_competitor, has_PI, used_product, action_type
    # to match the pandas _aggregate_to_global implementation.
    # ------------------------------------------------------------------
    _BASE_CTE = """
    WITH scoped AS (
        SELECT * FROM fp_grain
        WHERE row_type = 'breadfast'
        {and_where}
    ),
    -- BF modal price from fresh rows (smallest value among the most-frequent)
    bf_modal AS (
        SELECT product_id, bf_sale_price AS bf_modal FROM (
            SELECT product_id, bf_sale_price,
                   ROW_NUMBER() OVER (
                       PARTITION BY product_id
                       ORDER BY COUNT(*) DESC, bf_sale_price ASC
                   ) AS rn
            FROM scoped
            WHERE is_recent_breadfast = TRUE AND bf_sale_price IS NOT NULL
            GROUP BY product_id, bf_sale_price
        ) WHERE rn = 1
    ),
    -- Competitor modal price from FRESH observations
    comp_fresh AS (
        SELECT product_id, competitor_id, competitor_sale_price AS comp_fresh_modal FROM (
            SELECT product_id, competitor_id, competitor_sale_price,
                   ROW_NUMBER() OVER (
                       PARTITION BY product_id, competitor_id
                       ORDER BY COUNT(*) DESC, competitor_sale_price ASC
                   ) AS rn
            FROM scoped
            WHERE competitor_sale_price > 0 AND is_recent_competitor = TRUE
            GROUP BY product_id, competitor_id, competitor_sale_price
        ) WHERE rn = 1
    ),
    -- Competitor modal price from ALL observations (fallback when no fresh)
    comp_all AS (
        SELECT product_id, competitor_id, competitor_sale_price AS comp_all_modal FROM (
            SELECT product_id, competitor_id, competitor_sale_price,
                   ROW_NUMBER() OVER (
                       PARTITION BY product_id, competitor_id
                       ORDER BY COUNT(*) DESC, competitor_sale_price ASC
                   ) AS rn
            FROM scoped
            WHERE competitor_sale_price > 0
            GROUP BY product_id, competitor_id, competitor_sale_price
        ) WHERE rn = 1
    ),
    -- Per-(product, competitor) carry-through. ANY_VALUE for fields that are
    -- product- or pair-level (constant across the FP rows); reductions where
    -- a real aggregation is needed.
    pair_meta AS (
        SELECT
            product_id, competitor_id,
            ANY_VALUE(competitor_name)             AS competitor_name,
            ANY_VALUE(product_name)                AS product_name,
            ANY_VALUE(main_category_name)          AS main_category_name,
            ANY_VALUE(commercial_category_name)    AS commercial_category_name,
            ANY_VALUE(sub_category_name)           AS sub_category_name,
            ANY_VALUE(brand_name)                  AS brand_name,
            ANY_VALUE(avg_daily_quantity)          AS avg_daily_quantity,
            ANY_VALUE(total_revenue)               AS total_revenue,
            ANY_VALUE(eligible_product)            AS eligible_product,
            BOOL_OR(is_mapped)                     AS is_mapped,
            MAX(similarity_score)                  AS similarity_score,
            -- MIN (not ANY_VALUE) so the pick is DETERMINISTIC *and* correct:
            -- 12.5% of pairs have classification that varies across FP rows, and
            -- for all of them is_mapped=BOOL_OR is True. "Mapped …" sorts before
            -- "Not Mapped …", so MIN picks the Mapped label — matching is_mapped.
            -- (ANY_VALUE picked arbitrarily → wobbling counts; MAX would have
            --  wrongly labeled every varying-but-mapped pair "Not Mapped".)
            MIN(classification)                    AS classification,
            ANY_VALUE(weighted_score)              AS weighted_score,
            ANY_VALUE(norm_revenue)                AS norm_revenue,
            ANY_VALUE(norm_quantity)               AS norm_quantity,
            ANY_VALUE(cumulative_revenue_share)    AS cumulative_revenue_share,
            ANY_VALUE(global_tier)                 AS global_tier,
            ANY_VALUE(subcat_tier)                 AS subcat_tier,
            ANY_VALUE(bf_regular_price)            AS bf_regular_price,
            ANY_VALUE(competitor_product_id)       AS competitor_product_id,
            ANY_VALUE(competitor_product_name)     AS competitor_product_name,
            ANY_VALUE(match_potential)             AS match_potential,
            ANY_VALUE(match_potential_product_name) AS match_potential_product_name,
            MIN(days_since_update) FILTER (WHERE competitor_sale_price > 0)        AS days_since_update,
            MIN(competitor_sale_price) FILTER (WHERE competitor_sale_price > 0)    AS min_competitor_sale_price,
            MAX(competitor_sale_price) FILTER (WHERE competitor_sale_price > 0)    AS max_competitor_sale_price,
            MAX(bf_price_updated_at) FILTER (WHERE competitor_sale_price > 0)      AS bf_price_updated_at,
            MAX(competitor_price_updated_at) FILTER (WHERE competitor_sale_price > 0) AS competitor_price_updated_at,

            -- ── Gap-analysis columns ────────────────────────────────────────
            -- Carried so the Executive and Commercial roll-ups can answer "how
            -- much CAN be matched", not just "how much is". Anything absent
            -- from this list is invisible to them: `base` is `pm.*`.
            --
            -- BOOL_OR / MAX, never ANY_VALUE, for the flags that can vary
            -- across a pair's FP rows — ANY_VALUE would reproduce exactly the
            -- nondeterminism the MIN(classification) note above warns about,
            -- and Executive would then disagree with the Gap tab run to run.
            ANY_VALUE(is_beauty)                    AS is_beauty,
            ANY_VALUE(is_private_label)             AS is_private_label,
            -- Blank brand_key means unbranded, not a brand named "" — matching
            -- the normalization in _gap_ctes.
            NULLIF(TRIM(ANY_VALUE(brand_key)), '')  AS brand_key,
            BOOL_OR(is_shared_brand)                AS is_shared_brand,
            -- How the overlap was established, and the evidence behind it. Both
            -- are constants of (brand, competitor), so BOOL_OR/ANY_VALUE only
            -- carry the value through the collapse.
            BOOL_OR(shared_brand_by_match)          AS shared_brand_by_match,
            ANY_VALUE(comp_brand_variants)          AS comp_brand_variants,
            BOOL_OR(matched_comp_active_7d)         AS matched_comp_active_7d,
            BOOL_OR(is_confirmed_no_match)          AS is_confirmed_no_match,
            BOOL_OR(is_potential_match)             AS is_potential_match,
            MAX(best_similarity_in_portfolio)       AS best_similarity_in_portfolio,
            BOOL_OR(competitor_has_v2_catalogue)    AS competitor_has_v2_catalogue,
            -- Competitor-level constants: the size of their live catalogue, and
            -- the same restricted to brands we also carry. Both are per-competitor
            -- scalars, so MAX is just "carry the value through" — but the second
            -- is what lets the Shared-only scope narrow the catalogue column
            -- instead of leaving it as the one figure no filter touches.
            MAX(comp_active_products)               AS comp_active_products,
            MAX(comp_active_products_shared)        AS comp_active_products_shared,
            -- The matched competitor product, so their catalogue can be COUNTed
            -- under the current filters rather than only read off the two totals
            -- above. Constant within (product_id, competitor_id), hence ANY_VALUE.
            -- This is the one VARCHAR added to global_base; kept because the count
            -- has to be DISTINCT (one of their products can match several of ours)
            -- and it must sit at the collapsed grain, where action_type is the
            -- recomputed one.
            ANY_VALUE(competitor_product_key)       AS competitor_product_key,
            BOOL_OR(matched_comp_in_catalogue)      AS matched_comp_in_catalogue
            -- Deliberately NOT carried: mapped_bf_sub_category. On
            -- row_type='breadfast' rows it only echoes sub_category_name, so it
            -- adds no information, and _apply_filters materializes every
            -- global_base column into pandas on each GLOBAL request.
        FROM scoped
        GROUP BY product_id, competitor_id
    ),
    -- Final aggregated base: one row per (product, competitor) with recomputed flags
    base AS (
        SELECT
            pm.*,
            COALESCE(cf.comp_fresh_modal, ca.comp_all_modal) AS competitor_sale_price,
            bm.bf_modal AS bf_sale_price,
            -- "now" prices sourced from BQ (no live Catalog-API fetch):
            -- now_price = regular price, now_sale_price = modal sale price.
            pm.bf_regular_price AS now_price,
            bm.bf_modal         AS now_sale_price,
            bm.bf_modal / COALESCE(cf.comp_fresh_modal, ca.comp_all_modal) AS sale_PI,
            -- Recomputed flags (match pandas _aggregate_to_global)
            (cf.comp_fresh_modal IS NOT NULL)             AS is_recent_competitor,
            (ca.comp_all_modal   IS NOT NULL)             AS has_PI,
            (bm.bf_modal         IS NOT NULL)             AS is_recent_breadfast,
            -- prices_recently_updated/updated = BF fresh AND competitor fresh
            -- (matches pandas _aggregate_to_global lines 623-626)
            (bm.bf_modal IS NOT NULL AND cf.comp_fresh_modal IS NOT NULL) AS prices_recently_updated,
            (bm.bf_modal IS NOT NULL AND cf.comp_fresh_modal IS NOT NULL) AS updated,
            -- Usable gate: eligible pair with a BF modal AND a FRESH competitor
            -- modal. The competitor-price fallback is a purely FP-grain effect
            -- (it fills non-fresh FPs of a pair that IS fresh somewhere), so it
            -- never changes this product-level gate — a pair with a fresh price
            -- is already counted, and a stale-only pair correctly stays out.
            (pm.eligible_product
                AND ca.comp_all_modal IS NOT NULL
                AND bm.bf_modal IS NOT NULL
                AND cf.comp_fresh_modal IS NOT NULL)      AS used_product,
            -- Recomputed action_type (match pandas semantics)
            CASE
                WHEN NOT pm.is_mapped
                     AND (pm.similarity_score IS NULL OR pm.similarity_score < 0.85)
                    THEN 'Needs Mapping'
                WHEN NOT pm.is_mapped AND pm.similarity_score >= 0.85
                    THEN 'Review AI Match'
                WHEN pm.is_mapped AND ca.comp_all_modal IS NULL
                    THEN 'Needs Price for FP'
                WHEN pm.is_mapped AND cf.comp_fresh_modal IS NOT NULL
                    THEN 'Complete'
                ELSE 'Needs Price Update'
            END AS action_type
        FROM pair_meta pm
        LEFT JOIN bf_modal   bm USING (product_id)
        LEFT JOIN comp_fresh cf USING (product_id, competitor_id)
        LEFT JOIN comp_all   ca USING (product_id, competitor_id)
    )
    """

    @staticmethod
    def _as_and(where: str) -> str:
        """Turn a "WHERE a AND b" fragment into "AND a AND b" so it can be
        appended to a clause that already opened with WHERE. Empty stays empty."""
        w = (where or "").strip()
        if not w:
            return ""
        if w.upper().startswith("WHERE "):
            return "AND " + w[6:]
        return "AND " + w

    # ------------------------------------------------------------------
    # FP-grain twin of _BASE_CTE. Identical method — collapse the filtered rows
    # to one row per key, recompute modal prices, then derive sale_PI and
    # used_product from those — but with fp_id in the key, so the result stays a
    # per-FP grid. Used by get_fp_competitor_pi, whose whole axis IS the FP and
    # which therefore cannot use the national collapse.
    #
    # Why not just read fp_grain's own sale_PI / used_product, as this used to:
    # those come straight from BigQuery and are computed on a different basis
    # (bf_eod ÷ last_seen, BigQuery's freshness gate) than every other number in
    # the app. Recomputing here puts the geographic grid on the same price basis
    # as Commercial and Executive. Measured effect: 402 of 441 cells identical,
    # mean |delta| 0.0015, worst cell 1.0023 -> 1.0234.
    # ------------------------------------------------------------------
    _FP_BASE_CTE = """
    WITH scoped AS (
        SELECT * FROM fp_grain
        WHERE row_type = 'breadfast'
        {and_where}
    ),
    fp_bf_modal AS (
        SELECT product_id, fp_id, bf_sale_price AS bf_modal FROM (
            SELECT product_id, fp_id, bf_sale_price,
                   ROW_NUMBER() OVER (
                       PARTITION BY product_id, fp_id
                       ORDER BY COUNT(*) DESC, bf_sale_price ASC
                   ) AS rn
            FROM scoped
            WHERE is_recent_breadfast = TRUE AND bf_sale_price IS NOT NULL
            GROUP BY product_id, fp_id, bf_sale_price
        ) WHERE rn = 1
    ),
    fp_comp_fresh AS (
        SELECT product_id, competitor_id, fp_id, competitor_sale_price AS comp_fresh_modal FROM (
            SELECT product_id, competitor_id, fp_id, competitor_sale_price,
                   ROW_NUMBER() OVER (
                       PARTITION BY product_id, competitor_id, fp_id
                       ORDER BY COUNT(*) DESC, competitor_sale_price ASC
                   ) AS rn
            FROM scoped
            WHERE competitor_sale_price > 0 AND is_recent_competitor = TRUE
            GROUP BY product_id, competitor_id, fp_id, competitor_sale_price
        ) WHERE rn = 1
    ),
    fp_comp_all AS (
        SELECT product_id, competitor_id, fp_id, competitor_sale_price AS comp_all_modal FROM (
            SELECT product_id, competitor_id, fp_id, competitor_sale_price,
                   ROW_NUMBER() OVER (
                       PARTITION BY product_id, competitor_id, fp_id
                       ORDER BY COUNT(*) DESC, competitor_sale_price ASC
                   ) AS rn
            FROM scoped
            WHERE competitor_sale_price > 0
            GROUP BY product_id, competitor_id, fp_id, competitor_sale_price
        ) WHERE rn = 1
    ),
    fp_pair AS (
        SELECT
            product_id, competitor_id, fp_id,
            ANY_VALUE(fp_name)              AS fp_name,
            ANY_VALUE(competitor_name)      AS competitor_name,
            ANY_VALUE(avg_daily_quantity)   AS avg_daily_quantity,
            ANY_VALUE(eligible_product)     AS eligible_product,
            BOOL_OR(is_mapped)              AS is_mapped
        FROM scoped
        GROUP BY product_id, competitor_id, fp_id
    ),
    fp_base AS (
        SELECT
            p.*,
            bm.bf_modal                                       AS bf_sale_price,
            COALESCE(cf.comp_fresh_modal, ca.comp_all_modal)  AS competitor_sale_price,
            bm.bf_modal / COALESCE(cf.comp_fresh_modal, ca.comp_all_modal) AS sale_PI,
            (p.eligible_product
                AND ca.comp_all_modal   IS NOT NULL
                AND bm.bf_modal         IS NOT NULL
                AND cf.comp_fresh_modal IS NOT NULL)          AS used_product
        FROM fp_pair p
        LEFT JOIN fp_bf_modal   bm USING (product_id, fp_id)
        LEFT JOIN fp_comp_fresh cf USING (product_id, competitor_id, fp_id)
        LEFT JOIN fp_comp_all   ca USING (product_id, competitor_id, fp_id)
    )
    """

    def _fp_base_cte(self, where: str) -> str:
        return self._FP_BASE_CTE.format(and_where=self._as_and(where))

    def _base_cte(self, where: str) -> str:
        """_BASE_CTE with the WHERE clause injected. The product-level gate
        (`used_product`) is fixed to the observed definition — the competitor
        price fallback is a purely FP-grain effect and never touches this path.

        `scoped` is hard-gated to row_type='breadfast'. The competitor-only rows
        added by the gap layer carry product_id = NULL, so without the gate they
        would ALL collapse into a single row per competitor here and silently
        corrupt every Executive / Commercial / Master-Data number. They are
        served instead from the `comp_catalogue` table (_materialize_comp_catalogue).
        """
        return self._BASE_CTE.format(and_where=self._as_and(where))

    # ------------------------------------------------------------------
    # OVERRIDDEN ENDPOINT 1/5 — get_blended_pi_by_subcategory
    # ------------------------------------------------------------------
    def get_blended_pi_by_subcategory(self, filters: dict | None = None, group_by: str = "sub_category") -> pd.DataFrame:
        """DuckDB implementation: 300× faster than pandas on single-FP filter.

        group_by:
          - 'sub_category' (default): one row per subcategory (commercial category
            carried as a column).
          - 'commercial_category': rolled up to one row per commercial category —
            a true quantity-weighted recompute at that grain (not an average of
            subcategory PIs).

        Each row carries: group_key (the grouped value), blended_pi, per-competitor
        dicts (blended_pis, product_pis, used/eligible/mapped/needs_action counts),
        total revenue, and total/eligible/mapped/needs_action product counts.
        Product-level: unaffected by the competitor price fallback (FP-grain only).
        """
        grp = "commercial_category_name" if group_by == "commercial_category" else "sub_category_name"

        where, params = self._build_where_clause(filters)
        base_cte = self._base_cte(where)

        # Materialize `base` into a temp table once per request so both
        # downstream aggregations share the (expensive) modal-price + JOIN work.
        # Lock serializes against concurrent requests on the single connection.
        materialize_sql = base_cte + " SELECT * FROM base"

        # Competitor-only products, bridged into our taxonomy. Only meaningful at
        # subcategory grain: the BigQuery bridge maps a competitor category onto
        # one of OUR subcategories, never onto a commercial category. In category
        # grain the CTE is present but empty so the join below stays uniform.
        comp_where, comp_params = self._comp_side_where(filters)
        if grp == "sub_category_name":
            comp_side_sql = f"""
        comp_side AS (
            SELECT mapped_bf_sub_category AS group_key, COUNT(*) AS comp_only_products
            FROM comp_catalogue
            WHERE mapped_bf_sub_category IS NOT NULL{comp_where}
            GROUP BY 1
        ),"""
        else:
            comp_side_sql = """
        comp_side AS (
            SELECT CAST(NULL AS VARCHAR) AS group_key, 0 AS comp_only_products WHERE FALSE
        ),"""
            comp_params = []

        # The same count, split BY competitor, so the table's "They only" column
        # follows the selected competitor header instead of staying pooled.
        if grp == "sub_category_name":
            comp_only_join = f"""
        LEFT JOIN (
            SELECT mapped_bf_sub_category AS group_key, competitor_name,
                   COUNT(*) AS comp_only_count
            FROM comp_catalogue
            WHERE mapped_bf_sub_category IS NOT NULL{comp_where}
            GROUP BY 1, 2
        ) cco ON cco.group_key = ca.group_key AND cco.competitor_name = ca.competitor_name"""
            comp_only_params = list(comp_params)
        else:
            comp_only_join = """
        LEFT JOIN (
            SELECT CAST(NULL AS VARCHAR) AS group_key, CAST(NULL AS VARCHAR) AS competitor_name,
                   0 AS comp_only_count WHERE FALSE
        ) cco ON FALSE"""
            comp_only_params = []

        # __GRP__ is substituted with the grouping column (avoids f-string/format
        # clashing with the DuckDB struct literals `{...}` below).
        sql_subcat = """
        WITH __COMP_SIDE__
        used_agg AS (
            SELECT
                __GRP__ AS group_key,
                ROUND(
                    SUM(sale_PI * avg_daily_quantity) FILTER (WHERE used_product)
                    / NULLIF(SUM(avg_daily_quantity) FILTER (WHERE used_product), 0),
                    4
                ) AS blended_pi,
                COUNT(DISTINCT product_id) FILTER (WHERE used_product) AS used_product_count,
                LIST({
                    'product_name': product_name,
                    'sale_PI': sale_PI,
                    'weight': avg_daily_quantity
                }) FILTER (WHERE used_product AND sale_PI IS NOT NULL) AS product_pis
            FROM base_tmp
            GROUP BY __GRP__
            -- No HAVING on used_product: a group where nothing is matched or
            -- priced is the single biggest gap there is, and filtering it out
            -- made it invisible rather than flagged. Such rows now come through
            -- with blended_pi NULL and their gap columns populated.
            -- (The treemap route filters total_revenue > 0 so it is unaffected.)
        ),
        -- Revenue summed over DISTINCT used products (total_revenue is product-
        -- level, constant across competitor rows). Matches pandas
        -- drop_duplicates("product_id")["total_revenue"].sum(). NB: a plain
        -- SUM(DISTINCT total_revenue) is WRONG — it collapses two different
        -- products that happen to share an identical revenue value.
        used_rev AS (
            SELECT group_key, ROUND(SUM(rev), 2) AS total_revenue
            FROM (
                SELECT __GRP__ AS group_key, product_id, ANY_VALUE(total_revenue) AS rev
                FROM base_tmp
                WHERE used_product
                GROUP BY __GRP__, product_id
            )
            GROUP BY group_key
        ),
        full_counts AS (
            SELECT
                __GRP__ AS group_key,
                ANY_VALUE(commercial_category_name) AS commercial_category_name,
                COUNT(DISTINCT product_id) AS total_product_count,
                COUNT(DISTINCT product_id) FILTER (WHERE eligible_product) AS eligible_product_count,
                COUNT(DISTINCT product_id) FILTER (WHERE is_mapped) AS mapped_product_count,
                COUNT(DISTINCT product_id) FILTER (
                    WHERE eligible_product AND action_type != 'Complete'
                ) AS needs_action_count
            FROM base_tmp
            GROUP BY __GRP__
        ),
        -- Matchability, computed PER PRODUCT first.
        --
        -- This row is pooled across every competitor in scope, so the flags have
        -- to be resolved to the product before they are counted. A product can
        -- be mapped to Talabat and confirmed-no-match for Amazon at the same
        -- time; counting both directly makes "matched" and "no-match" overlap,
        -- and (total - no_match) can then fall below matched — which produced an
        -- addressable rate of 1800%. Resolved at product grain, "no-match" means
        -- what a category manager reads it as: nobody has an equivalent.
        prod_flags AS (
            SELECT
                __GRP__ AS group_key,
                product_id,
                BOOL_OR(is_mapped)                              AS is_mapped,
                BOOL_OR(is_mapped AND matched_comp_active_7d)   AS matched_fresh,
                BOOL_OR(is_confirmed_no_match)                  AS any_no_match,
                BOOL_OR(is_potential_match)                     AS any_potential
            FROM base_tmp
            GROUP BY 1, 2
        ),
        gap_counts AS (
            SELECT
                group_key,
                COUNT(*) FILTER (WHERE matched_fresh)                        AS matched_fresh_count,
                COUNT(*) FILTER (WHERE NOT is_mapped AND any_no_match)       AS confirmed_no_match_count,
                COUNT(*) FILTER (WHERE NOT is_mapped AND any_potential)      AS potential_match_count,
                -- "Ours only": products matched at NO selected competitor, the
                -- mirror of comp_only_products. Counted off prod_flags rather
                -- than as (total - mapped) so the pooled row resolves per
                -- product first — the same reason addressable_pct is computed
                -- here instead of over the pair grain.
                COUNT(*) FILTER (WHERE NOT COALESCE(is_mapped, FALSE))       AS our_only_count,
                ROUND(100.0 * COUNT(*) FILTER (WHERE is_mapped)
                      / NULLIF(COUNT(*) - COUNT(*) FILTER (
                            WHERE NOT is_mapped AND any_no_match), 0), 1)     AS addressable_pct
            FROM prod_flags
            GROUP BY group_key
        )
        SELECT
            ua.group_key,
            fc.commercial_category_name,
            ua.blended_pi,
            CAST(ua.used_product_count AS INTEGER) AS used_product_count,
            COALESCE(ur.total_revenue, 0)::DOUBLE AS total_revenue,
            ua.product_pis,
            CAST(COALESCE(fc.total_product_count, 0)    AS INTEGER) AS total_product_count,
            CAST(COALESCE(fc.eligible_product_count, 0) AS INTEGER) AS eligible_product_count,
            CAST(COALESCE(fc.mapped_product_count, 0)   AS INTEGER) AS mapped_product_count,
            CAST(COALESCE(fc.needs_action_count, 0)     AS INTEGER) AS needs_action_count,
            CAST(COALESCE(gc.matched_fresh_count, 0)      AS INTEGER) AS matched_fresh_count,
            CAST(COALESCE(gc.confirmed_no_match_count, 0) AS INTEGER) AS confirmed_no_match_count,
            CAST(COALESCE(gc.potential_match_count, 0)    AS INTEGER) AS potential_match_count,
            gc.addressable_pct,
            CAST(COALESCE(gc.our_only_count, 0)          AS INTEGER) AS our_only_count,
            CAST(COALESCE(cs.comp_only_products, 0)      AS INTEGER) AS comp_only_products
        FROM used_agg ua
        LEFT JOIN used_rev ur USING (group_key)
        LEFT JOIN full_counts fc USING (group_key)
        LEFT JOIN gap_counts gc USING (group_key)
        LEFT JOIN comp_side cs USING (group_key)
        ORDER BY ua.blended_pi DESC NULLS LAST
        """.replace("__GRP__", grp).replace("__COMP_SIDE__", comp_side_sql)

        sql_comp = """
        WITH comp_agg AS (
            SELECT
                __GRP__ AS group_key,
                competitor_name,
                ROUND(
                    SUM(sale_PI * avg_daily_quantity) FILTER (WHERE used_product)
                    / NULLIF(SUM(avg_daily_quantity) FILTER (WHERE used_product), 0),
                    4
                ) AS comp_blended_pi,
                CAST(COUNT(DISTINCT product_id) FILTER (WHERE used_product) AS INTEGER) AS comp_used_count,
                CAST(COUNT(DISTINCT product_id) FILTER (WHERE is_mapped)    AS INTEGER) AS comp_mapped_count,
                CAST(COUNT(DISTINCT product_id) FILTER (
                    WHERE eligible_product AND action_type != 'Complete'
                ) AS INTEGER) AS comp_needs_action,
                -- Matchability per competitor, so the table's Addr % column
                -- follows the selected competitor like Used and Mapped do.
                -- No per-product pre-pass needed here, unlike the pooled row:
                -- within ONE competitor, is_mapped and is_confirmed_no_match are
                -- mutually exclusive by construction, so counting them directly
                -- cannot make matched exceed addressable.
                CAST(COUNT(DISTINCT product_id) FILTER (
                    WHERE is_confirmed_no_match) AS INTEGER)  AS comp_no_match_count,
                CAST(COUNT(DISTINCT product_id) FILTER (
                    WHERE is_mapped AND matched_comp_active_7d) AS INTEGER) AS comp_fresh_count,
                -- Per-competitor "Ours only", so the column follows the selected
                -- competitor like Used, Mapped and Addr % do.
                CAST(COUNT(DISTINCT product_id) FILTER (
                    WHERE NOT COALESCE(is_mapped, FALSE)) AS INTEGER) AS comp_our_only_count,
                ROUND(100.0 * COUNT(DISTINCT product_id) FILTER (WHERE is_mapped)
                      / NULLIF(COUNT(DISTINCT product_id)
                               - COUNT(DISTINCT product_id) FILTER (
                                     WHERE is_confirmed_no_match), 0), 1)
                                                              AS comp_addressable_pct,
                LIST({
                    'product_name': product_name,
                    'sale_PI': sale_PI,
                    'weight': avg_daily_quantity
                }) FILTER (WHERE used_product AND sale_PI IS NOT NULL) AS comp_product_pis
            FROM base_tmp
            WHERE competitor_name IS NOT NULL
            GROUP BY __GRP__, competitor_name
        ),
        subcat_total_active AS (
            SELECT __GRP__ AS group_key,
                   CAST(COUNT(DISTINCT product_id) AS INTEGER) AS total_active
            FROM base_tmp
            GROUP BY __GRP__
        )
        SELECT
            ca.group_key,
            ca.competitor_name,
            ca.comp_blended_pi,
            ca.comp_used_count,
            ca.comp_mapped_count,
            ca.comp_needs_action,
            ca.comp_no_match_count,
            ca.comp_fresh_count,
            ca.comp_our_only_count,
            ca.comp_addressable_pct,
            CAST(COALESCE(cco.comp_only_count, 0) AS INTEGER) AS comp_only_count,
            ca.comp_product_pis,
            sta.total_active AS comp_eligible_count
        FROM comp_agg ca
        LEFT JOIN subcat_total_active sta USING (group_key)
        __COMP_ONLY_JOIN__
        """.replace("__GRP__", grp).replace("__COMP_ONLY_JOIN__", comp_only_join)

        with self._duckdb_lock:
            self._duckdb_conn.execute(
                "CREATE OR REPLACE TEMPORARY TABLE base_tmp AS " + materialize_sql,
                params,
            )
            df = self._duckdb_conn.execute(sql_subcat, comp_params).df()
            comp_df = self._duckdb_conn.execute(sql_comp, comp_only_params).df()

        if df.empty:
            return pd.DataFrame(columns=[
                "group_key", "sub_category_name", "commercial_category_name",
                "blended_pi", "used_product_count",
                "total_revenue", "pi_deviation", "direction",
                "total_product_count", "eligible_product_count",
                "mapped_product_count", "needs_action_count",
                "matched_fresh_count", "confirmed_no_match_count",
                "potential_match_count", "addressable_pct", "comp_only_products",
                "our_only_count",
                "product_pis",
                "competitor_blended_pis", "competitor_product_pis",
                "competitor_used_counts", "competitor_needs_action_counts",
                "competitor_eligible_counts", "competitor_mapped_counts",
                "competitor_addressable_pcts", "competitor_comp_only_counts",
                "competitor_matched_fresh_counts", "competitor_no_match_counts",
                "competitor_our_only_counts",
            ])

        # Derived columns
        df["pi_deviation"] = df["blended_pi"].apply(
            lambda x: round(x - 1, 4) if pd.notna(x) else None
        )
        df["direction"] = df["pi_deviation"].apply(pi_direction)
        # A group with nothing used now reaches here (the HAVING is gone), and its
        # LIST(...) FILTER aggregate comes back as pandas NA rather than None —
        # list(pd.NA) raises, so test for missing rather than for None.
        def _as_list(x):
            if x is None:
                return []
            try:
                if pd.isna(x):
                    return []
            except (TypeError, ValueError):
                pass  # array-likes raise here; they are genuine lists
            return list(x)

        df["product_pis"] = df["product_pis"].apply(_as_list)

        # Build per-competitor dicts keyed by group_key
        comp_blended: dict[str, dict] = {}
        comp_product_pis: dict[str, dict] = {}
        comp_used: dict[str, dict] = {}
        comp_action: dict[str, dict] = {}
        comp_eligible: dict[str, dict] = {}
        comp_mapped: dict[str, dict] = {}
        comp_addr: dict[str, dict] = {}
        comp_only: dict[str, dict] = {}
        comp_fresh: dict[str, dict] = {}
        comp_nomatch: dict[str, dict] = {}
        comp_our_only: dict[str, dict] = {}

        def _safe_list(v):
            if v is None:
                return []
            try:
                if pd.isna(v):
                    return []
            except (TypeError, ValueError):
                pass
            return list(v)

        def _safe_int(v):
            if v is None or pd.isna(v):
                return 0
            return int(v)

        def _safe_float(v):
            if v is None or pd.isna(v):
                return None
            return float(v)

        for row in comp_df.itertuples(index=False):
            key = row.group_key
            comp = row.competitor_name
            comp_blended.setdefault(key, {})[comp] = _safe_float(row.comp_blended_pi)
            comp_product_pis.setdefault(key, {})[comp] = _safe_list(row.comp_product_pis)
            comp_used.setdefault(key, {})[comp] = _safe_int(row.comp_used_count)
            comp_action.setdefault(key, {})[comp] = _safe_int(row.comp_needs_action)
            comp_eligible.setdefault(key, {})[comp] = _safe_int(row.comp_eligible_count)
            comp_mapped.setdefault(key, {})[comp] = _safe_int(row.comp_mapped_count)
            comp_addr.setdefault(key, {})[comp] = _safe_float(row.comp_addressable_pct)
            comp_only.setdefault(key, {})[comp] = _safe_int(row.comp_only_count)
            comp_fresh.setdefault(key, {})[comp] = _safe_int(row.comp_fresh_count)
            comp_nomatch.setdefault(key, {})[comp] = _safe_int(row.comp_no_match_count)
            comp_our_only.setdefault(key, {})[comp] = _safe_int(row.comp_our_only_count)

        df["competitor_blended_pis"] = df["group_key"].map(comp_blended).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        df["competitor_product_pis"] = df["group_key"].map(comp_product_pis).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        df["competitor_used_counts"] = df["group_key"].map(comp_used).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        df["competitor_needs_action_counts"] = df["group_key"].map(comp_action).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        df["competitor_eligible_counts"] = df["group_key"].map(comp_eligible).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        df["competitor_mapped_counts"] = df["group_key"].map(comp_mapped).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        for col, src in (("competitor_addressable_pcts", comp_addr),
                         ("competitor_comp_only_counts", comp_only),
                         ("competitor_matched_fresh_counts", comp_fresh),
                         ("competitor_no_match_counts", comp_nomatch),
                         ("competitor_our_only_counts", comp_our_only)):
            df[col] = df["group_key"].map(src).apply(lambda x: x if isinstance(x, dict) else {})

        # Identity columns per grain: subcategory mode keeps the subcategory name
        # (commercial category is a carried column); category mode has no single
        # subcategory, so the group_key IS the commercial category.
        if group_by == "commercial_category":
            df["commercial_category_name"] = df["group_key"]
            df["sub_category_name"] = None
        else:
            df["sub_category_name"] = df["group_key"]

        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # OVERRIDDEN ENDPOINT 2/5 — get_executive_dashboard
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Blended PI per (fulfillment point × competitor) — Geographic exposure.
    # Same quantity-weighted blend as get_blended_pi_by_subcategory, grouped
    # by fp_name × competitor_name straight off the FP grain (no FP collapse).
    # ------------------------------------------------------------------
    def get_fp_competitor_pi(self, filters: dict | None = None, price_fallback: bool = False) -> dict:
        where, params = self._build_where_clause(filters)
        if not price_fallback:
            # Observed-only. Reads the recomputed FP-grain base, so each cell is
            # on the same price basis as Commercial and Executive rather than on
            # BigQuery's raw sale_PI / used_product columns.
            sql = self._fp_base_cte(where) + """
            SELECT
                fp_name,
                competitor_name,
                ROUND(
                    SUM(sale_PI * avg_daily_quantity) FILTER (WHERE used_product)
                    / NULLIF(SUM(avg_daily_quantity) FILTER (WHERE used_product), 0),
                    4
                ) AS blended_pi,
                CAST(COUNT(DISTINCT product_id) FILTER (WHERE used_product)     AS INTEGER) AS used_count,
                CAST(0 AS INTEGER) AS estimated_count,
                CAST(COUNT(DISTINCT product_id) FILTER (WHERE eligible_product) AS INTEGER) AS eligible_count
            FROM fp_base
            WHERE competitor_name IS NOT NULL AND fp_name IS NOT NULL
            GROUP BY fp_name, competitor_name
            HAVING COUNT(DISTINCT product_id) FILTER (WHERE eligible_product) > 0
            ORDER BY fp_name, competitor_name
            """
        else:
            # Fallback ON — fill mapped, non-fresh (product, fp, competitor) cells
            # with the per-(product, competitor) FRESH modal price computed over ALL
            # FPs, recompute the per-FP PI, and count them as estimated. The estimate
            # is drawn ONLY from fresh prices: a pair with no fresh price anywhere
            # (stale-only) has no fresh modal, so it is never estimated here (it stays
            # excluded — its stale price surfaces, flagged "outdated", in the product
            # FP-matrix, never in this blended aggregation). The modal CTE scans the
            # full grain (a price is a product-level property, independent of the FP
            # filter).
            # Layered on the same recomputed FP-grain base as the observed branch,
            # so an estimated cell and an observed cell are priced the same way.
            sql = self._fp_base_cte(where) + """
            , modal AS (
                SELECT product_id, competitor_name, competitor_sale_price AS modal_price FROM (
                    SELECT product_id, competitor_name, competitor_sale_price,
                           ROW_NUMBER() OVER (PARTITION BY product_id, competitor_name
                               ORDER BY COUNT(*) DESC, competitor_sale_price ASC) AS rn
                    FROM fp_grain
                    WHERE row_type = 'breadfast'
                      AND competitor_sale_price > 0 AND is_recent_competitor = TRUE
                    GROUP BY product_id, competitor_name, competitor_sale_price
                ) WHERE rn = 1
            ),
            enriched AS (
                SELECT s.*,
                    (s.used_product
                     OR (s.is_mapped AND s.eligible_product AND NOT s.used_product
                         AND m.modal_price IS NOT NULL AND s.bf_sale_price IS NOT NULL)) AS used_eff,
                    (NOT s.used_product AND s.is_mapped AND s.eligible_product
                     AND m.modal_price IS NOT NULL AND s.bf_sale_price IS NOT NULL) AS is_estimated,
                    CASE WHEN s.used_product THEN s.sale_PI
                         ELSE s.bf_sale_price / NULLIF(m.modal_price, 0) END AS pi_eff
                FROM fp_base s
                LEFT JOIN modal m USING (product_id, competitor_name)
            )
            SELECT
                fp_name,
                competitor_name,
                ROUND(
                    SUM(pi_eff * avg_daily_quantity) FILTER (WHERE used_eff)
                    / NULLIF(SUM(avg_daily_quantity) FILTER (WHERE used_eff), 0),
                    4
                ) AS blended_pi,
                CAST(COUNT(DISTINCT product_id) FILTER (WHERE used_eff)                    AS INTEGER) AS used_count,
                CAST(COUNT(DISTINCT product_id) FILTER (WHERE used_eff AND is_estimated)   AS INTEGER) AS estimated_count,
                CAST(COUNT(DISTINCT product_id) FILTER (WHERE eligible_product)            AS INTEGER) AS eligible_count
            FROM enriched
            WHERE competitor_name IS NOT NULL AND fp_name IS NOT NULL
            GROUP BY fp_name, competitor_name
            HAVING COUNT(DISTINCT product_id) FILTER (WHERE eligible_product) > 0
            ORDER BY fp_name, competitor_name
            """.format(and_where=self._as_and(where))
        with self._duckdb_lock:
            df = self._duckdb_conn.execute(sql, params).df()
        return self._shape_fp_competitor_pi(df)

    def get_executive_dashboard(self, filters: dict | None = None) -> dict:
        """Executive dashboard payload (KPIs + per-competitor PI + mapping
        progress + classification breakdown).

        Computed in a single materialization pass via the shared `base_tmp`
        temp table; ~100× faster than the pandas implementation on single-FP
        filters. Product-level: unaffected by the competitor price fallback.
        """
        where, params = self._build_where_clause(filters)
        base_cte = self._base_cte(where)
        materialize_sql = base_cte + " SELECT * FROM base"

        # KPIs: total / eligible / mapped / needs_action breakdown + blended PI.
        # Computes a "worst action" per product (across competitors) using a
        # priority ladder, matching pandas _worst_action_per_product.
        sql_kpis = """
        WITH product_worst AS (
            SELECT
                product_id,
                ANY_VALUE(eligible_product) AS eligible_product,
                CASE MAX(
                    CASE action_type
                        WHEN 'Needs Mapping'      THEN 3
                        WHEN 'Review AI Match'    THEN 2
                        WHEN 'Review Match'       THEN 2
                        WHEN 'Needs Price Update' THEN 1
                        ELSE 0
                    END
                )
                    WHEN 3 THEN 'Needs Mapping'
                    WHEN 2 THEN 'Review Match'
                    WHEN 1 THEN 'Needs Price Update'
                    ELSE 'Complete'
                END AS worst_action
            FROM base_tmp
            GROUP BY product_id
        ),
        pair_metrics AS (
            -- Per-(product, competitor) figures used for blended PI / mapped flag
            SELECT
                product_id, sale_PI, avg_daily_quantity, used_product,
                eligible_product
            FROM base_tmp
        )
        SELECT
            (SELECT COUNT(*) FROM product_worst)                                          AS total_products,
            (SELECT COUNT(*) FROM product_worst WHERE eligible_product)                   AS eligible_count,
            -- mapped count = eligible products that have a sale_PI for any competitor
            (SELECT COUNT(DISTINCT product_id) FROM pair_metrics
             WHERE eligible_product AND sale_PI IS NOT NULL)                              AS mapped_count,
            (SELECT COUNT(*) FROM product_worst
             WHERE eligible_product AND worst_action != 'Complete')                       AS needs_action,
            (SELECT COUNT(*) FROM product_worst
             WHERE eligible_product AND worst_action = 'Needs Mapping')                   AS nm,
            (SELECT COUNT(*) FROM product_worst
             WHERE eligible_product AND worst_action = 'Review Match')                    AS rm,
            (SELECT COUNT(*) FROM product_worst
             WHERE eligible_product AND worst_action = 'Needs Price Update')              AS npu,
            (SELECT ROUND(
                SUM(sale_PI * avg_daily_quantity) FILTER (WHERE used_product)
                / NULLIF(SUM(avg_daily_quantity) FILTER (WHERE used_product), 0),
                4
             ) FROM pair_metrics)                                                         AS blended_pi
        """

        # Per-competitor blended PI + mapped/used/eligible counts.
        # `eligible_products` = count of ELIGIBLE products (top-80% revenue head),
        # so Utilization = used / eligible. (Mapping Coverage uses total active,
        # which the frontend reads from mapping_progress.total.)
        sql_comp_pi = """
        WITH active_counts AS (
            SELECT
                COUNT(DISTINCT product_id) AS total_active,
                COUNT(DISTINCT product_id) FILTER (WHERE eligible_product) AS eligible_active
            FROM base_tmp
        ),
        per_comp AS (
            SELECT
                competitor_name,
                ROUND(
                    SUM(sale_PI * avg_daily_quantity) FILTER (WHERE used_product)
                    / NULLIF(SUM(avg_daily_quantity) FILTER (WHERE used_product), 0),
                    4
                ) AS blended_pi,
                COUNT(DISTINCT product_id) FILTER (WHERE is_mapped)    AS mapped_products,
                COUNT(DISTINCT product_id) FILTER (WHERE used_product) AS used_products
            FROM base_tmp
            WHERE competitor_name IS NOT NULL
            GROUP BY competitor_name
        )
        SELECT
            pc.competitor_name,
            pc.blended_pi,
            CASE WHEN pc.blended_pi IS NOT NULL THEN ROUND(pc.blended_pi - 1, 4) END AS pi_deviation,
            CAST(pc.mapped_products  AS INTEGER) AS mapped_products,
            CAST(ac.eligible_active  AS INTEGER) AS eligible_products,
            CAST(pc.used_products    AS INTEGER) AS used_products
        FROM per_comp pc CROSS JOIN active_counts ac
        ORDER BY pc.blended_pi DESC NULLS LAST
        """

        # Per-competitor mapping_progress at product grain.
        # The mapped/not-mapped split is driven by is_mapped (the SAME definition
        # the Blended-PI-by-competitor table uses), NOT by the classification
        # string — the two disagree in the source data, and is_mapped is the
        # source of truth. PL vs Not-PL still comes from the classification token
        # (always present, e.g. "… - PL - …" / "… - Not PL - …"), and the
        # not-mapped reason buckets are counted ONLY among is_mapped = FALSE. This
        # makes mapped_not_pl + mapped_pl = mapped_products and all buckets sum to
        # total, so the donut is internally consistent and matches that table.
        sql_mapping_progress = """
        WITH product_class AS (
            -- is_shared_brand rides along so the per-competitor donut can make the
            -- same distinction the overall one does: a dead end because THEY DO
            -- NOT STOCK THE BRAND is not a matching backlog. Without it the panel
            -- fell back to 0% the moment a competitor was selected, which is the
            -- default state.
            SELECT DISTINCT product_id, competitor_name, classification, is_mapped,
                   COALESCE(is_shared_brand, FALSE) AS is_shared_brand
            FROM base_tmp
            WHERE competitor_name IS NOT NULL AND classification IS NOT NULL
        )
        SELECT
            competitor_name,
            CAST(COUNT(*) FILTER (WHERE is_mapped AND classification LIKE '%Not PL%')     AS INTEGER) AS mapped_not_pl,
            CAST(COUNT(*) FILTER (WHERE is_mapped AND classification NOT LIKE '%Not PL%') AS INTEGER) AS mapped_pl,
            CAST(COUNT(*) FILTER (WHERE NOT is_mapped AND classification = 'Not Mapped - Not PL - Potential Match')    AS INTEGER) AS potential_not_pl,
            CAST(COUNT(*) FILTER (WHERE NOT is_mapped AND classification = 'Not Mapped - PL - Potential Match')        AS INTEGER) AS potential_pl,
            CAST(COUNT(*) FILTER (WHERE NOT is_mapped AND classification = 'Not Mapped - Not PL - No Potential Match') AS INTEGER) AS no_potential_not_pl,
            CAST(COUNT(*) FILTER (WHERE NOT is_mapped AND classification = 'Not Mapped - PL - No Potential Match')     AS INTEGER) AS no_potential_pl,
            -- "No Match" = master-data DECIDED there's no competitor equivalent (resolved)
            CAST(COUNT(*) FILTER (WHERE NOT is_mapped AND classification = 'Not Mapped - Not PL - No Match') AS INTEGER) AS no_match_not_pl,
            CAST(COUNT(*) FILTER (WHERE NOT is_mapped AND classification = 'Not Mapped - PL - No Match')     AS INTEGER) AS no_match_pl,
            -- Same two splits the overall breakdown carries, per competitor.
            CAST(COUNT(*) FILTER (WHERE NOT is_mapped AND NOT is_shared_brand
                  AND classification LIKE '%No Match')          AS INTEGER) AS no_match_not_shared_brand,
            CAST(COUNT(*) FILTER (WHERE NOT is_mapped AND NOT is_shared_brand
                  AND classification LIKE '%No Potential Match') AS INTEGER) AS no_potential_not_shared_brand,
            CAST(COUNT(*) AS INTEGER) AS total
        FROM product_class
        GROUP BY competitor_name
        """

        # Overall classification breakdown, at PRODUCT grain.
        #
        # It used to count base_tmp rows, which are (product x competitor) pairs:
        # the donut totalled 85,274 against a page that said 12,182 products
        # everywhere else, and its centre read 25% mapped while the scorecard
        # beside it read 16.6-48.9% per competitor. Both were right and no
        # arithmetic reconciled them. Collapsing to product grain first makes the
        # donut answer the same question as the rest of the page: of OUR
        # products, how many can we compare anywhere in scope.
        #
        # The four buckets must be disjoint to be a donut, and at product grain
        # the flags are not: a product can be confirmed-no-match at one
        # competitor and a potential match at another. Precedence is mapped >
        # potential > confirmed-no-match > no likely match -- potential outranks
        # confirmed because if ANY competitor shows a likely candidate the
        # product is still reachable, and the bucket exists to say what to work
        # on next.
        #
        # not_shared_brand splits the two dead-end buckets by whether the brand
        # is carried by any competitor in scope. A product nobody can match
        # because nobody stocks the brand is a different problem from one we
        # simply failed to match, and only the second is a matching backlog.
        sql_class_overall = """
        WITH prod AS (
            SELECT
                product_id,
                BOOL_OR(COALESCE(is_mapped, FALSE))              AS is_mapped,
                BOOL_OR(COALESCE(is_potential_match, FALSE))     AS any_potential,
                BOOL_OR(COALESCE(is_confirmed_no_match, FALSE))  AS any_no_match,
                BOOL_OR(COALESCE(is_shared_brand, FALSE))        AS any_shared_brand,
                ANY_VALUE(is_private_label)                      AS is_private_label
            FROM base_tmp
            GROUP BY product_id
        ),
        tagged AS (
            SELECT *,
                CASE WHEN is_mapped      THEN 'mapped'
                     WHEN any_potential  THEN 'potential'
                     WHEN any_no_match   THEN 'no_match'
                     ELSE 'no_potential' END AS bucket
            FROM prod
        )
        SELECT
            bucket,
            CAST(COUNT(*) AS INTEGER)                                        AS cnt,
            CAST(COUNT(*) FILTER (WHERE is_private_label) AS INTEGER)        AS pl,
            CAST(COUNT(*) FILTER (WHERE NOT any_shared_brand) AS INTEGER)    AS not_shared_brand
        FROM tagged
        GROUP BY bucket
        """

        with self._duckdb_lock:
            self._duckdb_conn.execute(
                "CREATE OR REPLACE TEMPORARY TABLE base_tmp AS " + materialize_sql,
                params,
            )
            kpi_row = self._duckdb_conn.execute(sql_kpis).fetchone()
            comp_df = self._duckdb_conn.execute(sql_comp_pi).df()
            map_df = self._duckdb_conn.execute(sql_mapping_progress).df()
            class_df = self._duckdb_conn.execute(sql_class_overall).df()

        # ── kpis ─────────────────────────────────────────────────────
        (
            total_products, eligible_count, mapped_count, needs_action,
            nm, rm, npu, blended_pi,
        ) = kpi_row
        total_products = int(total_products or 0)
        eligible_count = int(eligible_count or 0)
        mapped_count = int(mapped_count or 0)
        kpis = {
            "blended_pi": float(blended_pi) if blended_pi is not None else None,
            "total_products": total_products,
            "eligible_products": eligible_count,
            "eligible_pct": round(eligible_count / total_products * 100, 1) if total_products > 0 else 0.0,
            "mapped_products": mapped_count,
            "mapped_pct": round(mapped_count / eligible_count * 100, 1) if eligible_count > 0 else 0.0,
            "needs_action": int(needs_action or 0),
            "needs_mapping": int(nm or 0),
            "review_match": int(rm or 0),
            "needs_price_update": int(npu or 0),
        }

        # ── competitor_pi ────────────────────────────────────────────
        competitor_pi = []
        for r in comp_df.itertuples(index=False):
            competitor_pi.append({
                "competitor_name": str(r.competitor_name),
                "blended_pi": float(r.blended_pi) if pd.notna(r.blended_pi) else None,
                "pi_deviation": float(r.pi_deviation) if pd.notna(r.pi_deviation) else None,
                "mapped_products": int(r.mapped_products),
                "eligible_products": int(r.eligible_products),
                "used_products": int(r.used_products),
            })

        # ── mapping_progress ─────────────────────────────────────────
        # is_mapped count per competitor (same figure the Blended-PI-by-competitor
        # table uses for Mapping Coverage), so the Product-classification mapped %
        # is computed identically (mapped_products / total) instead of from the
        # classification buckets.
        mapped_products_by_comp = {
            str(r.competitor_name): int(r.mapped_products) for r in comp_df.itertuples(index=False)
        }
        mapping_progress = []
        for r in map_df.itertuples(index=False):
            mapped_total = int(r.mapped_not_pl) + int(r.mapped_pl)
            potential_total = int(r.potential_not_pl) + int(r.potential_pl)
            no_match_total = int(r.no_match_not_pl) + int(r.no_match_pl)
            total = int(r.total)
            mapped_products = mapped_products_by_comp.get(str(r.competitor_name), mapped_total)
            # No-Match products are a master-data decision (unmappable) → exclude
            # them from the reachable universe so reach % isn't dragged down.
            reachable = total - no_match_total
            mapping_progress.append({
                "competitor_name": str(r.competitor_name),
                "mapped_not_pl": int(r.mapped_not_pl),
                "mapped_pl": int(r.mapped_pl),
                "potential_not_pl": int(r.potential_not_pl),
                "potential_pl": int(r.potential_pl),
                "no_potential_not_pl": int(r.no_potential_not_pl),
                "no_potential_pl": int(r.no_potential_pl),
                "no_match_not_pl": int(r.no_match_not_pl),
                "no_match_pl": int(r.no_match_pl),
                "no_match_not_shared_brand": int(r.no_match_not_shared_brand),
                "no_potential_not_shared_brand": int(r.no_potential_not_shared_brand),
                "total": total,
                # is_mapped count (matches Blended PI by competitor); mapped_pct now
                # uses it over total so the classification donut and that table agree.
                "mapped_products": mapped_products,
                "mapped_pct": round(mapped_products / total * 100, 1) if total > 0 else 0.0,
                "potential_reach_pct": round((mapped_total + potential_total) / reachable * 100, 1) if reachable > 0 else 0.0,
            })
        mapping_progress.sort(key=lambda x: x["mapped_pct"], reverse=True)

        # ── classification_breakdown ─────────────────────────────────
        # Keys keep their old names so the component contract is unchanged; only
        # the GRAIN changed, plus the two *_not_shared_brand additions.
        by_bucket = {r.bucket: r for r in class_df.itertuples(index=False)}

        def _b(name, field):
            r = by_bucket.get(name)
            return int(getattr(r, field)) if r is not None else 0

        classification_breakdown = {
            "mapped_not_pl": _b("mapped", "cnt") - _b("mapped", "pl"),
            "mapped_pl": _b("mapped", "pl"),
            "not_mapped_not_pl_potential": _b("potential", "cnt") - _b("potential", "pl"),
            "not_mapped_pl_potential": _b("potential", "pl"),
            "not_mapped_not_pl_no_potential": _b("no_potential", "cnt") - _b("no_potential", "pl"),
            "not_mapped_pl_no_potential": _b("no_potential", "pl"),
            "not_mapped_not_pl_no_match": _b("no_match", "cnt") - _b("no_match", "pl"),
            "not_mapped_pl_no_match": _b("no_match", "pl"),
            # How much of each dead end is unreachable by brand rather than by
            # effort: nobody in scope carries the brand at all.
            "no_match_not_shared_brand": _b("no_match", "not_shared_brand"),
            "no_potential_not_shared_brand": _b("no_potential", "not_shared_brand"),
        }

        return {
            "kpis": kpis,
            "competitor_pi": competitor_pi,
            "mapping_progress": mapping_progress,
            "classification_breakdown": classification_breakdown,
        }

    # ==================================================================
    # BRAND & SUBCATEGORY GAP ANALYSIS
    # ------------------------------------------------------------------
    # A fourth analytical grain. Two populations, deliberately kept apart:
    #
    #   Breadfast side  — fp_grain WHERE row_type='breadfast', collapsed to
    #                     product grain (gap metrics are national, so the FP
    #                     replication must go first or every count is xN_fps).
    #   Competitor side — the `comp_catalogue` table: competitor products we do
    #                     NOT carry, placed into one of our subcategories by the
    #                     BigQuery category bridge. Never routed through
    #                     _BASE_CTE (product_id is NULL there).
    #
    # DIRECTION REMINDER: sale_PI = Breadfast ÷ competitor, so PI > 1 means
    # Breadfast is MORE EXPENSIVE. (The wireframes and the older PI-query.sql
    # use the inverted convention — do not copy numbers or labels from those.)
    # ==================================================================

    # Beauty is identified on our side by main_category_name; on the competitor
    # side there is no category of ours to read, so we use the bridge's
    # beauty_path_share — the share of a competitor category's mapping evidence
    # that landed in our beauty range. >0.90 means <10% of it is in scope.
    _BEAUTY_PATH_CUTOFF = 0.90

    def _collapsed_source(self, filters: dict | None) -> tuple[str, list, str | None]:
        """The Breadfast-side source for every national roll-up.

        One method for the whole app: collapse the filtered rows to one row per
        (product, competitor) with recomputed modal prices, then calculate. That
        is what `_BASE_CTE` does, and `global_base` is it pre-materialized for the
        unfiltered case.

        Returns (source_sql, params, materialize_sql). When materialize_sql is
        non-None the caller must execute it first; otherwise the source is a
        filtered read of the pre-built table.

        The CTE has to be re-run for any filter that can select rows *within* a
        product's modal partition, because `global_base` is built unfiltered and
        filtering it afterwards cannot change a modal that was already chosen:

          fp_names     — global_base has collapsed fp_name away entirely.
          competitor   — less obvious, and it bit us. `bf_sale_price` is NOT
                         competitor-invariant: BigQuery emits
                         COALESCE(bf_eod_sale_price, scd_price), so each
                         competitor contributes its own end-of-day Breadfast
                         price. For one real product the modal is 78.75 across
                         all competitors but 41.50 within Talabat, moving its PI
                         from 1.11 to 0.93.
          action_type  — varies per (fp, competitor), so it slices partitions too.
          brand_scope  — is_shared_brand is per (product, competitor), so keeping
                         shared-brand pairs only drops some of a product's
                         competitor rows, which is enough to move the Breadfast
                         modal for the same reason `competitor` does.

        Everything else (category, subcategory, tier, brand, vertical, private
        label) is a product-level attribute: it removes whole products and never
        rows inside a surviving product, so the pre-built table stays valid.
        """
        where, params = self._build_where_clause(filters)
        f = filters or {}
        if (f.get("fp_names") or f.get("competitor") or f.get("action_type")
                or str(f.get("brand_scope") or "").lower() in ("shared", "shared_name")):
            return (
                "base_tmp",
                params,
                "CREATE OR REPLACE TEMP TABLE base_tmp AS "
                + self._base_cte(where) + " SELECT * FROM base",
            )
        return f"(SELECT * FROM global_base {where})", params, None

    def _gap_where(self, filters: dict | None) -> tuple[str, str, list, list]:
        """WHERE fragments for the Breadfast and competitor sides.

        The two sides do not share a column vocabulary: a competitor-only row has
        no commercial category, tier or action type of ours, so replaying the
        Breadfast filter set against it would delete the entire catalogue. Only
        the filters that mean something on both sides cross over — competitor,
        and subcategory (which on the competitor side is the bridged
        `mapped_bf_sub_category`).
        """
        f = filters or {}
        bf_clauses, bf_params = [], []
        comp_clauses, comp_params = [], []

        def split(key):
            raw = f.get(key)
            return [v.strip() for v in str(raw).split(",") if v.strip()] if raw else []

        def add(clauses, params, column, values):
            if values:
                clauses.append(f"{column} IN ({', '.join(['?'] * len(values))})")
                params.extend(values)

        # Shared dimensions
        comps = split("competitor")
        add(bf_clauses, bf_params, "competitor_name", comps)
        add(comp_clauses, comp_params, "competitor_name", comps)

        subs = split("sub_category")
        add(bf_clauses, bf_params, "sub_category_name", subs)
        add(comp_clauses, comp_params, "mapped_bf_sub_category", subs)

        brands = split("brand")
        add(bf_clauses, bf_params, "brand_name", brands)
        # Their side matches on the normalized KEY, not the display name.
        # brand_name on a competitor row is THEIR spelling, and a competitor
        # routinely uses several: Talabat carries 7up as '7up', '7Up' and '7UP'.
        # Comparing our string to theirs case-sensitively kept 1 of their 6
        # unpaired 7up products and silently dropped the other 5, so filtering to
        # a brand made its own assortment gap look six times smaller than the
        # unfiltered table said. brand_key already collapses the spellings.
        if brands:
            ph = ", ".join(["?"] * len(brands))
            comp_clauses.append(
                f"brand_key IN (SELECT DISTINCT brand_key FROM global_base "
                f"WHERE brand_name IN ({ph}) AND brand_key IS NOT NULL)"
            )
            comp_params.extend(brands)

        # Breadfast-only dimensions
        add(bf_clauses, bf_params, "commercial_category_name", split("main_category"))
        add(bf_clauses, bf_params, "global_tier", split("global_tier"))
        add(bf_clauses, bf_params, "subcat_tier", split("subcat_tier"))

        # An FP filter narrows which of our products are in play; competitor
        # rows are national and simply keep their full catalogue.
        add(bf_clauses, bf_params, "fp_name", split("fp_names"))

        bf = (" AND " + " AND ".join(bf_clauses)) if bf_clauses else ""
        comp = (" AND " + " AND ".join(comp_clauses)) if comp_clauses else ""
        return bf, comp, bf_params, comp_params

    def _gap_ctes(self, filters: dict | None) -> tuple[str, list, list, str | None]:
        """Shared CTE prelude: `bf_prod` (our side, product grain) and
        `comp_prod` (theirs).

        Returns (sql, params_bf, params_comp, materialize_sql). The two param
        lists are kept apart because `materialize_sql` binds only the Breadfast
        ones; the query itself binds them in CTE order, bf then comp.
        materialize_sql is non-None only when an FP filter forces the base CTE
        to be re-run.

        The Breadfast side reads `_collapsed_source`, i.e. the same
        collapse-then-calculate base as Commercial and Executive, rather than
        `fp_grain` directly. It used to read the FP grain and collapse it here,
        which produced the right counts but the wrong price weighting — see the
        note on pi_side in get_gap_by_subcategory.
        """
        bf_source, params_bf, materialize = self._collapsed_source(filters)
        where_comp, params_comp = self._comp_side_where(filters)

        sql = f"""
        WITH bf_scoped AS (
            SELECT * FROM {bf_source}
        ),
        -- One row per product. The source is already one row per (product,
        -- competitor), so this collapses only across the competitors in scope.
        bf_prod AS (
            SELECT
                product_id,
                ANY_VALUE(product_name)             AS product_name,
                ANY_VALUE(sub_category_name)        AS sub_category_name,
                ANY_VALUE(commercial_category_name) AS commercial_category_name,
                -- blank brand_key means unbranded, not a brand called "";
                -- left as-is it becomes the single biggest 'comp-only brand'.
                NULLIF(TRIM(ANY_VALUE(brand_key)), '') AS brand_key,
                NULLIF(TRIM(ANY_VALUE(brand_name)), '') AS brand_name,
                ANY_VALUE(global_tier)              AS global_tier,
                -- MAX over competitors: "mapped" means mapped to at least one of
                -- the competitors currently in scope.
                MAX(is_mapped)                      AS is_mapped,
                MAX(is_shared_brand)                AS is_shared_brand,
                -- MAX over competitors like is_shared_brand above: promoted by
                -- evidence at any competitor in scope. The variants string is
                -- the longest one seen, so a brand scoped to one competitor
                -- shows that competitor's names rather than an arbitrary pick.
                MAX(shared_brand_by_match)          AS shared_by_match,
                ARG_MAX(comp_brand_variants, LENGTH(comp_brand_variants))
                                                    AS comp_brand_variants,
                MAX(is_confirmed_no_match)          AS no_match,
                MAX(is_potential_match)             AS potential,
                MAX(matched_comp_active_7d)         AS matched_active,
                MAX(best_similarity_in_portfolio)   AS best_similarity,
                ANY_VALUE(total_revenue)            AS rev,
                ANY_VALUE(avg_daily_quantity)       AS qty,
                -- Price, PI and action against the competitor in scope.
                --
                -- These are the only columns here that are NOT safe to pool. A
                -- product has a different price, PI and action against each
                -- competitor, so with several in scope ANY_VALUE would return an
                -- arbitrary one. The Gap tab selects exactly one competitor --
                -- every number on the screen is "against whom" -- so the guard
                -- is to emit them only when that is true, rather than to show a
                -- number whose meaning depends on which competitor DuckDB
                -- happened to reach first.
                CASE WHEN COUNT(DISTINCT competitor_name) = 1
                     THEN ANY_VALUE(bf_sale_price) END          AS bf_sale_price,
                CASE WHEN COUNT(DISTINCT competitor_name) = 1
                     THEN ANY_VALUE(competitor_sale_price) END  AS comp_sale_price,
                CASE WHEN COUNT(DISTINCT competitor_name) = 1
                     THEN ANY_VALUE(sale_PI) END                AS sale_PI,
                CASE WHEN COUNT(DISTINCT competitor_name) = 1
                     THEN ANY_VALUE(action_type) END            AS action_type,
                -- The competitor product this one is matched to. Guarded like
                -- the prices: it is per (product, competitor), and naming a
                -- counterpart from an unspecified competitor would be worse than
                -- naming none. Populated for exactly the mapped products.
                CASE WHEN COUNT(DISTINCT competitor_name) = 1
                     THEN ANY_VALUE(competitor_product_name) END AS competitor_product_name,
                -- The three flags Commercial counts, at product grain. They form
                -- a funnel and are most useful read as one: eligible (in the top
                -- 80% of revenue) -> updated (both sides priced recently) ->
                -- used (carries a PI). Whichever one first reads false is why a
                -- mapped product contributes nothing to the blended figure.
                MAX(eligible_product)               AS eligible_product,
                MAX(updated)                        AS updated,
                MAX(used_product)                   AS used_product
            FROM bf_scoped
            GROUP BY product_id
        ),
        comp_prod AS (
            SELECT
                competitor_name,
                competitor_product_key,
                product_name                 AS comp_product_name,
                NULLIF(TRIM(comp_brand_name), '') AS comp_brand_name,
                NULLIF(TRIM(brand_key), '')       AS brand_key,
                is_shared_brand,
                mapped_bf_sub_category       AS sub_category_name,
                mapped_bf_sub_categories_all,
                mapped_pct_of_comp_category,
                bridge_level,
                category_level_1, category_level_2, category_level_3,
                -- COLUMN_MAP renames competitor_last_updated_day on load
                competitor_price_updated_at AS comp_last_seen,
                classification,
                competitor_has_v2_catalogue
            FROM comp_catalogue
            WHERE TRUE{where_comp}
        )
        """
        return sql, params_bf, params_comp, materialize

    def _gap_execute(self, sql, params_bf, params_comp, materialize, extra=None):
        """Run a gap query, materializing the FP-scoped base first when needed.

        Param binding differs between the two paths. When the base is
        materialized, `bf_source` is the bare table name `base_tmp` and carries
        no placeholders — the Breadfast params belong to the CREATE statement.
        Otherwise `bf_source` is an inline filtered read of global_base and the
        placeholders are in the query itself.
        """
        with self._duckdb_lock:
            if materialize:
                self._duckdb_conn.execute(materialize, params_bf)
                # bf_source is the bare name `base_tmp`, which has no placeholders.
                bound = list(params_comp)
            else:
                bound = list(params_bf) + list(params_comp)
            return self._duckdb_conn.execute(sql, bound + list(extra or [])).df()

    def _comp_side_where(self, filters: dict | None) -> tuple[str, list]:
        """WHERE fragment for `comp_catalogue` when it is joined onto a
        Breadfast-side roll-up (the Executive overview, the Commercial
        blended-PI table).

        Only the crossover filters apply — a competitor-only row has no
        commercial category, tier or action type of ours. The vertical toggle is
        translated to the bridge's beauty evidence share, since there is no
        category of ours on that row to test directly.
        """
        _, where_comp, _, params_comp = self._gap_where(filters)
        f = filters or {}

        vertical = str(f.get("vertical") or "").strip().lower()
        if vertical == "supermarket":
            where_comp += f" AND COALESCE(beauty_path_share, 0) <= {self._BEAUTY_PATH_CUTOFF}"
        elif vertical == "beauty":
            where_comp += f" AND COALESCE(beauty_path_share, 0) > {self._BEAUTY_PATH_CUTOFF}"

        # Commercial category has no direct equivalent on a competitor-only row,
        # but it reaches them through the bridge: the bridge assigns each of their
        # products one of OUR subcategories, and our subcategories belong to our
        # commercial categories. Without this, picking a category narrowed our
        # side while leaving "they carry, we don't" at its full count — the same
        # half-applied trap that tier and FP are hidden for, except here it is
        # fixable rather than inherent.
        # Brand scope crosses over cleanly: on a competitor-only row
        # is_shared_brand means "Breadfast carries this brand", so 'shared' asks
        # "of the brands we both carry, what do they have that we don't" — the
        # actionable half of the assortment gap.
        comp_scope = str(f.get("brand_scope") or "").strip().lower()
        if comp_scope == "shared":
            where_comp += " AND COALESCE(is_shared_brand, FALSE)"
        elif comp_scope == "shared_name":
            where_comp += (" AND COALESCE(is_shared_brand, FALSE)"
                           " AND NOT COALESCE(shared_brand_by_match, FALSE)")

        cats = [v.strip() for v in str(f.get("main_category") or "").split(",") if v.strip()]
        if cats:
            ph = ", ".join(["?"] * len(cats))
            where_comp += (
                " AND mapped_bf_sub_category IN ("
                f"SELECT DISTINCT sub_category_name FROM global_base"
                f" WHERE commercial_category_name IN ({ph})"
                "   AND sub_category_name IS NOT NULL)"
            )
            params_comp = list(params_comp) + cats
        return where_comp, params_comp

    # ------------------------------------------------------------------
    # EXECUTIVE — competitor overview (one row per competitor)
    # ------------------------------------------------------------------
    def get_category_performance(self, filters: dict | None = None) -> list[dict]:
        """Blended PI per commercial category, on the same basis as Commercial.

        Overrides the inherited pandas implementation, which read the
        pre-materialized global_base and applied the filters AFTER the collapse.
        That is fine for product-level filters and wrong for the competitor one:
        `bf_sale_price` is COALESCE(bf_eod_sale_price, scd_price) per (product,
        fp, competitor) row, so the modal chosen across ALL competitors is not
        the modal within one of them, and filtering afterwards cannot re-choose
        it. Tomatoes (1Kg) is 35.00 across the board and 44.00 at Talabat, which
        alone moved "Private Label - Fresh & Frozen - Shaaban" from 1.1252 to
        0.9945 -- Executive and Commercial disagreeing about the same category,
        same competitor, same moment.

        _collapsed_source puts the filter INSIDE the collapse, which is what
        get_blended_pi_by_subcategory has always done. Same fix as the Gap tab.

        `product_count` was also renamed to `used_product_count`, because it
        counts products carrying a PI, not products in the category -- Beauty
        read 5 against 311 total. Nothing renders it; it is corrected at the
        source rather than left as a trap.
        """
        source, params, materialize = self._collapsed_source(filters)
        sql = f"""
        SELECT
            commercial_category_name AS category_name,
            ROUND(SUM(sale_PI * avg_daily_quantity) FILTER (WHERE used_product)
                  / NULLIF(SUM(avg_daily_quantity) FILTER (WHERE used_product), 0), 4)
                                                                     AS blended_pi,
            CAST(COUNT(DISTINCT product_id) FILTER (WHERE used_product) AS INTEGER)
                                                                     AS used_product_count
        FROM {source}
        WHERE commercial_category_name IS NOT NULL
        GROUP BY 1
        -- Matches the previous behaviour, which started from used rows only and
        -- so never emitted a category with nothing priced.
        HAVING COUNT(DISTINCT product_id) FILTER (WHERE used_product) > 0
        ORDER BY blended_pi DESC NULLS LAST
        """
        with self._duckdb_lock:
            if materialize:
                self._duckdb_conn.execute(materialize, params)
                df = self._duckdb_conn.execute(sql).df()
            else:
                df = self._duckdb_conn.execute(sql, params).df()

        out = []
        for r in df.itertuples(index=False):
            pi = None if pd.isna(r.blended_pi) else float(r.blended_pi)
            out.append({
                "category_name": r.category_name,
                "blended_pi": pi,
                "pi_deviation": None if pi is None else round(pi - 1, 4),
                "used_product_count": int(r.used_product_count),
            })
        return out

    def get_competitor_overview(self, filters: dict | None = None) -> list[dict]:
        """Matching + assortment coverage per competitor.

        This is the live equivalent of the hand-maintained workbook sheet
        `Brand_Portfolio_Consolidated_excl_Beauty.xlsx` -> "Competitor Overview".
        To reproduce that sheet, set Vertical = Supermarket (the workbook
        excludes beauty).

        Purely additive: it introduces no metric the Executive view already
        shows, and reuses the same Addressable formula as `get_gap_kpis` so the
        Executive panel and the Gap tab can never print different numbers for
        the same scope.

        The Breadfast side goes through `_base_cte`, so it honours the whole
        Executive filter bar exactly as `get_executive_dashboard` does. The
        competitor side reads `comp_catalogue` and can only honour the filters
        that mean something on that grain (see `_gap_where`).
        """
        where, params_bf = self._build_where_clause(filters)

        # Read the pre-materialized global_base whenever we can. It IS
        # _BASE_CTE("") built once at startup, and it carries every column the
        # filters touch, so re-running the CTE per request costs ~4s for nothing.
        # Only an FP filter forces the rebuild: global_base has no fp_name (the
        # FP grain is collapsed away), so an fp_names filter cannot be applied
        # to it. This is the same GLOBAL/FP-scoped split as _apply_filters.
        fp_scoped = bool((filters or {}).get("fp_names"))
        bf_source = "base_tmp" if fp_scoped else f"(SELECT * FROM global_base {where})"

        # Competitor side: only the crossover filters apply (see _gap_where).
        where_comp, params_comp = self._comp_side_where(filters)

        sql = f"""
        WITH bf_side AS (
            SELECT
                competitor_name,
                COUNT(DISTINCT product_id)                                        AS bf_products,
                COUNT(DISTINCT product_id) FILTER (WHERE is_mapped)               AS matched,
                -- Matched AND the competitor product was seen in the last 7 days:
                -- a match whose competitor side has gone quiet is a benchmark
                -- that is quietly rotting.
                COUNT(DISTINCT product_id) FILTER (
                    WHERE is_mapped AND matched_comp_active_7d)                   AS matched_fresh,
                COUNT(DISTINCT product_id) FILTER (WHERE is_confirmed_no_match)   AS confirmed_no_match,
                COUNT(DISTINCT product_id) FILTER (WHERE is_potential_match)      AS potential_match,
                -- "Ours only": our SKUs with no match at this competitor, the
                -- structural mirror of comp_only_products (their products with
                -- no link to ours). COALESCE, not a bare NOT: is_mapped is
                -- nullable, and `FILTER (WHERE NOT is_mapped)` would drop NULLs
                -- from BOTH sides, so matched + our_only would silently stop
                -- summing to bf_products.
                COUNT(DISTINCT product_id) FILTER (
                    WHERE NOT COALESCE(is_mapped, FALSE))                         AS our_only_products,
                COUNT(DISTINCT product_id) FILTER (WHERE is_shared_brand)         AS shared_brand_products,
                COUNT(DISTINCT product_id) FILTER (
                    WHERE is_mapped AND is_shared_brand)                          AS matched_shared_brand,
                COUNT(DISTINCT brand_key) FILTER (WHERE is_shared_brand)          AS shared_brands,
                -- A SUBSET of shared_brands, not a fourth bucket: brands whose
                -- overlap was proved by matches because the two names disagree.
                -- Froneri counts here and in shared_brands both.
                COUNT(DISTINCT brand_key) FILTER (
                    WHERE COALESCE(shared_brand_by_match, FALSE))                 AS shared_by_match_brands,
                COUNT(DISTINCT brand_key) FILTER (WHERE NOT is_shared_brand)      AS bf_only_brands,
                BOOL_OR(COALESCE(competitor_has_v2_catalogue, FALSE))             AS has_catalogue,
                MAX(comp_active_products)                                         AS comp_products,
                -- Their catalogue restricted to brands we also carry. Both are
                -- returned; the UI shows this one while Shared-only is active, so
                -- the column stops being the only figure the scope cannot narrow.
                MAX(comp_active_products_shared)                                  AS comp_products_shared,
                -- The PAIRED half of their live catalogue, inside the current
                -- scope. DISTINCT is load-bearing: the source is one row per
                -- (product, competitor), so a competitor product matched to three
                -- of our products appears three times. Added to the unpaired half
                -- from comp_catalogue, this is their catalogue under the filters.
                COUNT(DISTINCT competitor_product_key) FILTER (
                    WHERE matched_comp_in_catalogue)                              AS comp_paired_in_scope,
                -- Price position, so one table can carry both stories. Same
                -- quantity-weighted blend as get_executive_dashboard's
                -- competitor_pi and get_blended_pi_by_subcategory; verified equal
                -- to the dashboard's values, so consolidating moves no number.
                ROUND(SUM(sale_PI * avg_daily_quantity) FILTER (WHERE used_product)
                      / NULLIF(SUM(avg_daily_quantity) FILTER (WHERE used_product), 0), 4)
                                                                                  AS blended_pi,
                COUNT(DISTINCT product_id) FILTER (WHERE used_product)             AS used_products,
                COUNT(DISTINCT product_id) FILTER (WHERE eligible_product)         AS eligible_products
            FROM {bf_source} AS bf
            WHERE competitor_name IS NOT NULL
            GROUP BY competitor_name
        ),
        comp_side AS (
            SELECT
                competitor_name,
                COUNT(*)                                                     AS comp_only_products,
                -- NULLIF(TRIM(...)) is required, not cosmetic: comp_catalogue is
                -- read raw here (unlike the Breadfast side, which gets it from
                -- pair_meta already normalized), and a blank brand_key would
                -- otherwise count as one extra brand on every competitor.
                COUNT(DISTINCT NULLIF(TRIM(brand_key), ''))
                    FILTER (WHERE NOT is_shared_brand)                       AS comp_only_brands
            FROM comp_catalogue
            WHERE TRUE{where_comp}
            GROUP BY competitor_name
        )
        SELECT
            b.competitor_name,
            CAST(b.bf_products        AS INTEGER) AS bf_products,
            CAST(b.matched            AS INTEGER) AS matched,
            CAST(b.matched_fresh      AS INTEGER) AS matched_fresh,
            ROUND(100.0 * b.matched / NULLIF(b.bf_products, 0), 1)            AS mapping_pct,
            -- Restricted to brands the competitor also carries: the realistic
            -- ceiling, since a brand they do not stock can never be matched.
            ROUND(100.0 * b.matched_shared_brand
                  / NULLIF(b.shared_brand_products, 0), 1)                   AS mapping_pct_shared,
            CAST(b.confirmed_no_match AS INTEGER) AS confirmed_no_match,
            CAST(b.bf_products - b.confirmed_no_match AS INTEGER)            AS addressable,
            -- Products the matcher positively rejected leave the denominator.
            ROUND(100.0 * b.matched
                  / NULLIF(b.bf_products - b.confirmed_no_match, 0), 1)      AS addressable_pct,
            CAST(b.potential_match    AS INTEGER) AS potential_match,
            ROUND(100.0 * b.potential_match / NULLIF(b.bf_products, 0), 1)   AS potential_pct,
            CAST(COALESCE(b.comp_products, 0)        AS INTEGER) AS comp_products,
            CAST(COALESCE(b.comp_products_shared, 0) AS INTEGER) AS comp_products_shared,
            -- Their catalogue as narrowed by the current filters: the paired half
            -- from our side plus the unpaired half from theirs. The two partition
            -- the active catalogue, so with no filters applied this reproduces
            -- comp_products; with a category or subcategory filter it counts only
            -- what the bridge can attribute, which is why unbridged products drop
            -- out exactly when a category filter is on.
            CAST(COALESCE(b.comp_paired_in_scope, 0)
                 + COALESCE(c.comp_only_products, 0) AS INTEGER) AS comp_products_in_scope,
            CAST(COALESCE(c.comp_only_products, 0) AS INTEGER) AS comp_only_products,
            CAST(b.our_only_products  AS INTEGER) AS our_only_products,
            CAST(b.shared_brands      AS INTEGER) AS shared_brands,
            CAST(b.shared_by_match_brands AS INTEGER) AS shared_by_match_brands,
            CAST(b.bf_only_brands     AS INTEGER) AS bf_only_brands,
            CAST(COALESCE(c.comp_only_brands, 0)   AS INTEGER) AS comp_only_brands,
            b.has_catalogue,
            b.blended_pi,
            ROUND(b.blended_pi - 1, 4)             AS pi_deviation,
            CAST(b.used_products     AS INTEGER)   AS used_products,
            CAST(b.eligible_products AS INTEGER)   AS eligible_products,
            -- Share of the eligible basket we can actually price against this
            -- competitor. The denominator is the eligible set as a whole, which
            -- is the same for every competitor because BigQuery emits every
            -- (product, competitor) pair — so this reads as "how much of our
            -- priced-worthy range is benchmarked here", not as a per-competitor
            -- utilisation rate. Labelled accordingly in the UI.
            ROUND(100.0 * b.used_products / NULLIF(b.eligible_products, 0), 1) AS priced_pct
        FROM bf_side b
        LEFT JOIN comp_side c USING (competitor_name)
        ORDER BY b.blended_pi DESC NULLS LAST, b.matched DESC
        """

        with self._duckdb_lock:
            if fp_scoped:
                self._duckdb_conn.execute(
                    "CREATE OR REPLACE TEMP TABLE base_tmp AS "
                    + self._base_cte(where) + " SELECT * FROM base",
                    params_bf,
                )
                df = self._duckdb_conn.execute(sql, params_comp).df()
            else:
                # `where` is inlined into bf_source, so its params come first.
                df = self._duckdb_conn.execute(sql, params_bf + params_comp).df()
        return self._gap_records(df)

    def get_gap_kpis(self, filters: dict | None = None) -> dict:
        """Headline gap numbers for the scope currently selected."""
        cte, params_bf, params_comp, materialize = self._gap_ctes(filters)
        sql = cte + """
        SELECT
            (SELECT COUNT(*) FROM bf_prod)                                        AS bf_products,
            (SELECT COUNT(*) FILTER (WHERE is_mapped) FROM bf_prod)               AS matched,
            (SELECT COUNT(*) FILTER (WHERE no_match) FROM bf_prod)                AS confirmed_no_match,
            (SELECT COUNT(*) FILTER (WHERE potential) FROM bf_prod)               AS potential_match,
            (SELECT COUNT(*) FILTER (WHERE is_mapped AND NOT matched_active)
               FROM bf_prod)                                                      AS matched_but_stale,
            (SELECT ROUND(SUM(rev), 0) FROM bf_prod)                              AS daily_revenue,
            (SELECT ROUND(SUM(rev), 0) FROM bf_prod WHERE NOT is_mapped)          AS unmatched_revenue,
            (SELECT COUNT(*) FROM comp_prod)                                      AS comp_only_products,
            (SELECT COUNT(*) FROM comp_prod WHERE sub_category_name IS NOT NULL)  AS comp_only_bridged,
            (SELECT COUNT(DISTINCT brand_key) FROM bf_prod
              WHERE brand_key IS NOT NULL AND is_shared_brand)                    AS shared_brands,
            -- A SUBSET of shared_brands: overlap proved by matching, because
            -- the two names disagree. Every metric here is its own scalar
            -- subquery, so it needs its own FROM.
            (SELECT COUNT(DISTINCT brand_key) FROM bf_prod
              WHERE brand_key IS NOT NULL AND shared_by_match)               AS shared_by_match_brands,
            (SELECT COUNT(DISTINCT brand_key) FROM bf_prod
              WHERE brand_key IS NOT NULL AND NOT is_shared_brand)                AS bf_only_brands,
            (SELECT COUNT(DISTINCT brand_key) FROM comp_prod
              WHERE brand_key IS NOT NULL AND NOT is_shared_brand)                AS comp_only_brands
        """
        r = self._gap_execute(sql, params_bf, params_comp, materialize).iloc[0]

        def i(v):
            return int(v) if pd.notna(v) else 0

        bf_products, matched = i(r.bf_products), i(r.matched)
        no_match = i(r.confirmed_no_match)
        addressable = bf_products - no_match
        return {
            "bf_products": bf_products,
            "matched": matched,
            # Mapping % uses is_mapped (not has_PI): the question this tab asks is
            # "is this product linked to a competitor product", not "did we manage
            # to price it in this FP". Matches the BigQuery roll-up.
            "mapping_pct": round(matched / bf_products * 100, 1) if bf_products else 0.0,
            "confirmed_no_match": no_match,
            # Addressable % measures against what CAN be matched — products the
            # matcher has positively rejected are removed from the denominator.
            "addressable_pct": round(matched / addressable * 100, 1) if addressable else 0.0,
            "potential_match": i(r.potential_match),
            "matched_but_stale": i(r.matched_but_stale),
            "daily_revenue": float(r.daily_revenue) if pd.notna(r.daily_revenue) else 0.0,
            "unmatched_revenue": float(r.unmatched_revenue) if pd.notna(r.unmatched_revenue) else 0.0,
            "comp_only_products": i(r.comp_only_products),
            "comp_only_bridged": i(r.comp_only_bridged),
            "shared_brands": i(r.shared_brands),
            "shared_by_match_brands": i(r.shared_by_match_brands),
            "bf_only_brands": i(r.bf_only_brands),
            "comp_only_brands": i(r.comp_only_brands),
        }

    def get_gap_by_subcategory(self, filters: dict | None = None) -> list[dict]:
        """Per-subcategory gap roll-up: mapping, brand overlap, price position
        and commercial weight, with the competitor-only count bridged in.

        NOTE: never sum comp_only_products across rows — one competitor product
        can bridge to several of our subcategories (plan section 9.7).
        """
        cte, params_bf, params_comp, materialize = self._gap_ctes(filters)

        sql = cte + f"""
        , bf_side AS (
            SELECT
                sub_category_name,
                ANY_VALUE(commercial_category_name) AS commercial_category_name,
                COUNT(*)                                       AS bf_products,
                COUNT(*) FILTER (WHERE is_mapped)              AS matched,
                COUNT(*) FILTER (WHERE no_match)               AS confirmed_no_match,
                COUNT(*) FILTER (WHERE potential)              AS potential_match,
                COUNT(*) FILTER (WHERE is_mapped AND NOT matched_active) AS matched_but_stale,
                ROUND(100.0 * COUNT(*) FILTER (WHERE is_mapped)
                      / NULLIF(COUNT(*), 0), 1)                AS mapping_pct,
                -- Restricted to brands the competitor also carries: the honest
                -- ceiling, since a brand they do not stock can never be matched.
                ROUND(100.0 * COUNT(*) FILTER (WHERE is_mapped AND is_shared_brand)
                      / NULLIF(COUNT(*) FILTER (WHERE is_shared_brand), 0), 1)
                                                               AS mapping_pct_shared,
                ROUND(100.0 * COUNT(*) FILTER (WHERE is_mapped)
                      / NULLIF(COUNT(*) - COUNT(*) FILTER (WHERE no_match), 0), 1)
                                                               AS addressable_pct,
                COUNT(DISTINCT brand_key) FILTER (WHERE is_shared_brand)     AS shared_brands,
                -- A SUBSET of shared_brands, not a fourth bucket: brands whose
                -- overlap was proved by matching because the two names disagree.
                COUNT(DISTINCT brand_key) FILTER (WHERE shared_by_match)     AS shared_by_match_brands,
                COUNT(DISTINCT brand_key) FILTER (WHERE NOT is_shared_brand) AS bf_only_brands,
                ROUND(SUM(rev), 0)                             AS daily_revenue,
                ROUND(SUM(rev) FILTER (WHERE NOT is_mapped), 0) AS unmatched_revenue,
                list_sort(list_distinct(list(brand_name) FILTER (
                    WHERE is_shared_brand AND brand_name IS NOT NULL)))      AS shared_brand_list,
                list_sort(list_distinct(list(brand_name) FILTER (
                    WHERE NOT is_shared_brand AND brand_name IS NOT NULL)))  AS bf_only_brand_list
            FROM bf_prod
            WHERE sub_category_name IS NOT NULL
            GROUP BY sub_category_name
        ),
        -- Price position, on the same collapse-then-calculate basis as Commercial
        -- and Executive.
        --
        -- This used to read fp_grain directly and sum across FP rows. That was
        -- wrong, not merely different: avg_daily_quantity is a NATIONAL figure,
        -- so repeating it on every FP row and summing weights each product by
        -- demand x number of FPs it is stocked in. Hair Care / Talabat came out
        -- at 1.061 that way against 0.945 here, off the same 18 products, with a
        -- weight sum inflated 21x -- the two screens disagreed about which side
        -- of parity we were on, because of distribution breadth rather than
        -- price. docs/DDD.md requires weighting by real demand.
        pi_side AS (
            SELECT
                sub_category_name,
                -- 4dp, matching get_blended_pi_by_subcategory exactly, so the two
                -- screens cannot differ even at a rounding boundary.
                ROUND(SUM(CASE WHEN used_product THEN sale_PI * avg_daily_quantity END)
                      / NULLIF(SUM(CASE WHEN used_product THEN avg_daily_quantity END), 0), 4)
                                                                             AS blended_pi,
                ROUND(100.0 * COUNT(DISTINCT product_id) FILTER (WHERE used_product)
                      / NULLIF(COUNT(DISTINCT product_id) FILTER (WHERE eligible_product), 0), 1)
                                                                             AS coverage_pct
            FROM bf_scoped
            GROUP BY sub_category_name
        ),
        comp_side AS (
            SELECT
                sub_category_name,
                COUNT(*)                                                     AS comp_only_products,
                COUNT(DISTINCT brand_key) FILTER (WHERE NOT is_shared_brand) AS comp_only_brands,
                list_sort(list_distinct(list(comp_brand_name) FILTER (
                    WHERE NOT is_shared_brand AND comp_brand_name IS NOT NULL)))
                                                                             AS comp_only_brand_list
            FROM comp_prod
            WHERE sub_category_name IS NOT NULL
            GROUP BY sub_category_name
        )
        SELECT
            b.sub_category_name,
            b.commercial_category_name,
            CAST(b.bf_products         AS INTEGER) AS bf_products,
            CAST(b.matched             AS INTEGER) AS matched,
            b.mapping_pct,
            b.mapping_pct_shared,
            CAST(b.confirmed_no_match  AS INTEGER) AS confirmed_no_match,
            b.addressable_pct,
            CAST(b.potential_match     AS INTEGER) AS potential_match,
            CAST(b.matched_but_stale   AS INTEGER) AS matched_but_stale,
            p.blended_pi,
            p.coverage_pct,
            CAST(COALESCE(c.comp_only_products, 0) AS INTEGER) AS comp_only_products,
            CAST(b.shared_brands       AS INTEGER) AS shared_brands,
            CAST(b.shared_by_match_brands AS INTEGER) AS shared_by_match_brands,
            CAST(b.bf_only_brands      AS INTEGER) AS bf_only_brands,
            CAST(COALESCE(c.comp_only_brands, 0)   AS INTEGER) AS comp_only_brands,
            COALESCE(b.daily_revenue, 0)::DOUBLE      AS daily_revenue,
            COALESCE(b.unmatched_revenue, 0)::DOUBLE  AS unmatched_revenue,
            b.shared_brand_list,
            b.bf_only_brand_list,
            COALESCE(c.comp_only_brand_list, []::VARCHAR[]) AS comp_only_brand_list
        FROM bf_side b
        LEFT JOIN pi_side   p USING (sub_category_name)
        LEFT JOIN comp_side c USING (sub_category_name)
        ORDER BY b.daily_revenue DESC NULLS LAST
        """
        df = self._gap_execute(sql, params_bf, params_comp, materialize)
        return self._gap_records(df)

    def get_gap_by_brand(self, filters: dict | None = None) -> list[dict]:
        """Per-brand gap roll-up.

        A FULL OUTER JOIN, unlike the subcategory view: a brand can exist only on
        their shelf (comp_only), which is exactly the population this tab is for.

        Caveat (plan section 9.4): brand-name variants do not collapse —
        "L'Oreal", "L'Oréal Paris" and "Elvive" stay separate rows, so comp-only
        brand counts run high. Fuzzy brand resolution is its own piece of work.
        """
        cte, params_bf, params_comp, materialize = self._gap_ctes(filters)
        sql = cte + """
        , bf_side AS (
            SELECT
                brand_key,
                ANY_VALUE(brand_name)                          AS brand_name,
                COUNT(*)                                       AS bf_products,
                COUNT(*) FILTER (WHERE is_mapped)              AS matched,
                -- The mirror of comp_only_products on this table: our products
                -- of this brand with no match at the competitor. COALESCE rather
                -- than a bare NOT, so a NULL is_mapped cannot drop out of both
                -- sides and leave matched + our_only short of bf_products.
                COUNT(*) FILTER (WHERE NOT COALESCE(is_mapped, FALSE))
                                                               AS our_only_products,
                COUNT(*) FILTER (WHERE no_match)               AS confirmed_no_match,
                COUNT(*) FILTER (WHERE potential)              AS potential_match,
                ROUND(100.0 * COUNT(*) FILTER (WHERE is_mapped)
                      / NULLIF(COUNT(*), 0), 1)                AS mapping_pct,
                ROUND(100.0 * COUNT(*) FILTER (WHERE is_mapped)
                      / NULLIF(COUNT(*) - COUNT(*) FILTER (WHERE no_match), 0), 1)
                                                               AS addressable_pct,
                COUNT(DISTINCT sub_category_name)              AS bf_subcategories,
                ROUND(SUM(rev), 0)                             AS daily_revenue,
                ROUND(SUM(rev) FILTER (WHERE NOT is_mapped), 0) AS unmatched_revenue,
                BOOL_OR(is_shared_brand)                       AS is_shared_brand,
                BOOL_OR(shared_by_match)                       AS shared_by_match,
                ARG_MAX(comp_brand_variants, LENGTH(comp_brand_variants))
                                                               AS comp_brand_variants
            FROM bf_prod
            WHERE brand_key IS NOT NULL
            GROUP BY brand_key
        ),
        comp_side AS (
            SELECT
                brand_key,
                ANY_VALUE(comp_brand_name)        AS comp_brand_name,
                COUNT(*)                          AS comp_only_products,
                COUNT(DISTINCT sub_category_name) AS comp_subcategories,
                -- Carried so brand_type can see it. Without this a brand that
                -- exists only on THEIR shelf always fell through to 'comp_only',
                -- even after the mirror rule marked its rows shared — so Talabat's
                -- "Halwani Bros" read "Only theirs" in this column while the
                -- Executive comp-only-brand count excluded it and the Shared-only
                -- filter kept its products. Same brand, three answers.
                BOOL_OR(is_shared_brand)          AS is_shared_brand
            FROM comp_prod
            WHERE brand_key IS NOT NULL
            GROUP BY brand_key
        )
        SELECT
            COALESCE(b.brand_key, c.brand_key)                 AS brand_key,
            -- brand_key can come from brand_slug while the display name is
            -- missing, so fall back to the key rather than rendering a null row.
            COALESCE(b.brand_name, c.comp_brand_name,
                     COALESCE(b.brand_key, c.brand_key))       AS brand_name,
            CASE
                WHEN b.brand_key IS NOT NULL AND c.brand_key IS NOT NULL THEN 'shared'
                WHEN b.brand_key IS NOT NULL AND COALESCE(b.is_shared_brand, FALSE) THEN 'shared'
                WHEN b.brand_key IS NOT NULL THEN 'bf_only'
                -- Their-side-only brand that the mirror rule promoted: we DO
                -- carry it, under another name. Calling it 'comp_only' here
                -- contradicted both the Shared-only filter and the Executive
                -- brand counts, which read is_shared_brand directly.
                WHEN COALESCE(c.is_shared_brand, FALSE) THEN 'shared'
                ELSE 'comp_only'
            END                                                AS brand_type,
            -- Deliberately NOT a fourth brand_type: a brand promoted on match
            -- evidence IS shared, and the Shared filter has to keep returning it.
            -- This rides alongside so the UI can show how the overlap was
            -- established and filter to just those for auditing.
            -- Either side can be the one promoted by evidence: ours when they
            -- label our brand differently, theirs when we label theirs
            -- differently. Halwani Bros is the second kind.
            COALESCE(b.shared_by_match,
                     c.is_shared_brand AND b.brand_key IS NULL, FALSE)
                                                               AS shared_by_match,
            b.comp_brand_variants,
            CAST(COALESCE(b.bf_products, 0)        AS INTEGER) AS bf_products,
            CAST(COALESCE(b.matched, 0)            AS INTEGER) AS matched,
            b.mapping_pct,
            CAST(COALESCE(b.confirmed_no_match, 0) AS INTEGER) AS confirmed_no_match,
            b.addressable_pct,
            CAST(COALESCE(b.potential_match, 0)    AS INTEGER) AS potential_match,
            CAST(COALESCE(c.comp_only_products, 0) AS INTEGER) AS comp_only_products,
            CAST(COALESCE(b.our_only_products, 0) AS INTEGER) AS our_only_products,
            CAST(COALESCE(b.bf_subcategories, 0)   AS INTEGER) AS bf_subcategories,
            CAST(COALESCE(c.comp_subcategories, 0) AS INTEGER) AS comp_subcategories,
            COALESCE(b.daily_revenue, 0)::DOUBLE               AS daily_revenue,
            COALESCE(b.unmatched_revenue, 0)::DOUBLE           AS unmatched_revenue
        FROM bf_side b
        FULL OUTER JOIN comp_side c USING (brand_key)
        ORDER BY daily_revenue DESC, comp_only_products DESC, brand_name
        """
        df = self._gap_execute(sql, params_bf, params_comp, materialize)
        return self._gap_records(df)

    def get_gap_products(
        self,
        filters: dict | None = None,
        side: str = "breadfast",
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        sort_by: str | None = None,
        sort_dir: str = "desc",
    ) -> dict:
        """Product-level drill-down behind the roll-ups.

        side='breadfast'  → our products and their match state.
        side='competitor' → their products we do not carry, with the subcategory
                            the bridge assigned and how confident that call is.
        """
        cte, params_bf, params_comp, materialize = self._gap_ctes(filters)
        competitor_side = str(side).lower() == "competitor"

        if competitor_side:
            select = """
            SELECT
                competitor_name,
                competitor_product_key,
                comp_product_name                 AS product_name,
                comp_brand_name                   AS brand_name,
                is_shared_brand,
                sub_category_name,
                mapped_bf_sub_categories_all,
                mapped_pct_of_comp_category,
                bridge_level,
                category_level_1, category_level_2, category_level_3,
                comp_last_seen,
                classification
            FROM comp_prod
            """
            sortable = {
                "product_name": "comp_product_name", "brand_name": "comp_brand_name",
                "sub_category_name": "sub_category_name",
                "mapped_pct_of_comp_category": "mapped_pct_of_comp_category",
                "comp_last_seen": "comp_last_seen",
            }
            default_sort, search_cols = "comp_product_name", ["comp_product_name", "comp_brand_name"]
            source = "comp_prod"
        else:
            select = """
            SELECT
                product_id,
                product_name,
                brand_name,
                sub_category_name,
                commercial_category_name,
                global_tier,
                is_mapped,
                no_match      AS is_confirmed_no_match,
                potential     AS is_potential_match,
                matched_active AS matched_comp_active_7d,
                is_shared_brand,
                shared_by_match,
                comp_brand_variants,
                competitor_product_name,
                best_similarity,
                rev           AS total_revenue,
                qty           AS avg_daily_quantity,
                bf_sale_price,
                comp_sale_price,
                sale_PI,
                eligible_product,
                updated,
                used_product
            FROM bf_prod
            """
            sortable = {
                "product_name": "product_name", "brand_name": "brand_name",
                "sub_category_name": "sub_category_name", "total_revenue": "rev",
                "avg_daily_quantity": "qty", "best_similarity": "best_similarity",
                # The new price columns are sortable too: "which of our products
                # is this competitor beating us on" is the question the PI column
                # exists to answer, and it is useless unsorted.
                "sale_PI": "sale_PI", "bf_sale_price": "bf_sale_price",
                "comp_sale_price": "comp_sale_price",
            }
            # Searching by their product name matters: when chasing a match you
            # often know only what the competitor calls it.
            default_sort = "rev"
            search_cols = ["product_name", "brand_name", "competitor_product_name"]
            source = "bf_prod"

        where, extra = "", []
        if search:
            like = " OR ".join(f"LOWER({c}) LIKE ?" for c in search_cols)
            where = f" WHERE ({like})"
            extra = [f"%{search.lower()}%"] * len(search_cols)

        col = sortable.get(sort_by or "", default_sort)
        direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
        offset = max(0, (max(1, page) - 1) * page_size)

        # Both statements run under ONE lock acquisition. base_tmp is a temp table
        # on the single shared connection, so releasing the lock between the count
        # and the page would let a concurrent request replace it underneath us.
        with self._duckdb_lock:
            if materialize:
                self._duckdb_conn.execute(materialize, params_bf)
                bound = list(params_comp)      # bf_source is `base_tmp`, no placeholders
            else:
                bound = list(params_bf) + list(params_comp)
            (total,) = self._duckdb_conn.execute(
                cte + f" SELECT COUNT(*) FROM {source}{where}", bound + extra
            ).fetchone()
            df = self._duckdb_conn.execute(
                cte + select + where
                + f" ORDER BY {col} {direction} NULLS LAST LIMIT ? OFFSET ?",
                bound + extra + [page_size, offset],
            ).df()

        return {
            "items": self._gap_records(df),
            "total_count": int(total),
            "page": max(1, page),
            "page_size": page_size,
        }

    def get_gap_filter_options(self, filters: dict | None = None) -> dict:
        """Option lists for the tab's own controls. Competitors are annotated
        with their catalogue flag so the UI can explain a competitor that has no
        gap data at all (Carrefour) instead of just rendering zeros."""
        with self._duckdb_lock:
            comps = self._duckdb_conn.execute("""
                SELECT competitor_name,
                       BOOL_OR(COALESCE(competitor_has_v2_catalogue, FALSE)) AS has_catalogue,
                       COUNT(*) FILTER (WHERE row_type = 'competitor')       AS comp_only_rows,
                       -- Drives the tab's default competitor. Picking by
                       -- comp_only_rows instead would land on the competitor we
                       -- have matched *least*, which reads as a broken tab.
                       COUNT(DISTINCT product_id) FILTER (
                           WHERE row_type = 'breadfast' AND is_mapped)       AS matched_products
                FROM fp_grain
                WHERE competitor_name IS NOT NULL
                GROUP BY competitor_name
                ORDER BY competitor_name
            """).df()
            subs = [r[0] for r in self._duckdb_conn.execute(
                "SELECT DISTINCT sub_category_name FROM fp_grain "
                "WHERE row_type = 'breadfast' AND sub_category_name IS NOT NULL ORDER BY 1"
            ).fetchall()]
            cats = [r[0] for r in self._duckdb_conn.execute(
                "SELECT DISTINCT commercial_category_name FROM fp_grain "
                "WHERE row_type = 'breadfast' AND commercial_category_name IS NOT NULL ORDER BY 1"
            ).fetchall()]
        return {
            "competitors": [
                {
                    "name": r.competitor_name,
                    "has_catalogue": bool(r.has_catalogue),
                    "comp_only_rows": int(r.comp_only_rows),
                    "matched_products": int(r.matched_products),
                }
                for r in comps.itertuples()
            ],
            "sub_categories": subs,
            "main_categories": cats,
        }

    @staticmethod
    def _gap_records(df: pd.DataFrame) -> list[dict]:
        """DataFrame → JSON-safe records: NaN/NaT to None, numpy scalars to
        Python, DuckDB LIST columns (numpy arrays) to plain lists."""
        import numpy as np

        out = []
        for rec in df.to_dict(orient="records"):
            clean = {}
            for k, v in rec.items():
                if isinstance(v, np.ndarray):
                    clean[k] = [None if pd.isna(x) else x for x in v.tolist()]
                elif isinstance(v, (list, tuple)):
                    clean[k] = list(v)
                elif v is None or (not isinstance(v, (str, bool)) and pd.isna(v)):
                    clean[k] = None
                elif isinstance(v, (np.integer,)):
                    clean[k] = int(v)
                elif isinstance(v, (np.floating,)):
                    clean[k] = float(v)
                elif isinstance(v, (np.bool_,)):
                    clean[k] = bool(v)
                elif isinstance(v, pd.Timestamp):
                    clean[k] = v.date().isoformat()
                else:
                    clean[k] = v
            out.append(clean)
        return out
