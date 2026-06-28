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
        self._materialize_global_base()
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
            top_fp_result = self._duckdb_conn.execute(
                "SELECT fp_name FROM fp_grain GROUP BY fp_name "
                "ORDER BY COUNT(*) DESC LIMIT 1"
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
            self._materialize_global_base()
            logger.info("[DuckDB] Refreshed Parquet + reopened view + rebuilt global_base")

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
            if filters.get("exclude_private_label"):
                filtered = filtered[~filtered["brand_name"].str.lower().str.contains("breadfast", na=False)]
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
                "SELECT * FROM fp_grain WHERE CAST(product_id AS VARCHAR) = ?",
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
        add_in_filter("main_category_name", "main_category")
        add_in_filter("sub_category_name", "sub_category")
        add_in_filter("global_tier", "global_tier")
        add_in_filter("brand_name", "brand")
        add_in_filter("competitor_name", "competitor")
        add_in_filter("action_type", "action_type")

        # Private-label exclusion (matches pandas behavior)
        if filters.get("exclude_private_label"):
            clauses.append("brand_name != 'Breadfast'")

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
        {where}
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
            MAX(competitor_price_updated_at) FILTER (WHERE competitor_sale_price > 0) AS competitor_price_updated_at
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

    def _base_cte(self, where: str) -> str:
        """_BASE_CTE with the WHERE clause injected. The product-level gate
        (`used_product`) is fixed to the observed definition — the competitor
        price fallback is a purely FP-grain effect and never touches this path."""
        return self._BASE_CTE.format(where=where)

    # ------------------------------------------------------------------
    # OVERRIDDEN ENDPOINT 1/5 — get_blended_pi_by_subcategory
    # ------------------------------------------------------------------
    def get_blended_pi_by_subcategory(self, filters: dict | None = None) -> pd.DataFrame:
        """DuckDB implementation: 300× faster than pandas on single-FP filter.

        Returns one row per subcategory with:
          - blended_pi (quantity-weighted Σ(sale_PI × qty) / Σ(qty) over used)
          - per-competitor dicts: blended_pis, product_pis, used_counts,
            eligible_counts, mapped_counts, needs_action_counts
          - total revenue, total/eligible/needs_action product counts
        Product-level: unaffected by the competitor price fallback (FP-grain only).
        """
        where, params = self._build_where_clause(filters)
        base_cte = self._base_cte(where)

        # Materialize `base` into a temp table once per request so both
        # downstream aggregations share the (expensive) modal-price + JOIN work.
        # Lock serializes against concurrent requests on the single connection.
        materialize_sql = base_cte + " SELECT * FROM base"

        sql_subcat = """
        WITH used_agg AS (
            SELECT
                sub_category_name,
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
            GROUP BY sub_category_name
            HAVING COUNT(DISTINCT product_id) FILTER (WHERE used_product) > 0
        ),
        -- Revenue summed over DISTINCT used products (total_revenue is product-
        -- level, constant across competitor rows). Matches pandas
        -- drop_duplicates("product_id")["total_revenue"].sum(). NB: a plain
        -- SUM(DISTINCT total_revenue) is WRONG — it collapses two different
        -- products that happen to share an identical revenue value.
        used_rev AS (
            SELECT sub_category_name, ROUND(SUM(rev), 2) AS total_revenue
            FROM (
                SELECT sub_category_name, product_id, ANY_VALUE(total_revenue) AS rev
                FROM base_tmp
                WHERE used_product
                GROUP BY sub_category_name, product_id
            )
            GROUP BY sub_category_name
        ),
        full_counts AS (
            SELECT
                sub_category_name,
                COUNT(DISTINCT product_id) AS total_product_count,
                COUNT(DISTINCT product_id) FILTER (WHERE eligible_product) AS eligible_product_count,
                COUNT(DISTINCT product_id) FILTER (
                    WHERE eligible_product AND action_type != 'Complete'
                ) AS needs_action_count
            FROM base_tmp
            GROUP BY sub_category_name
        )
        SELECT
            ua.sub_category_name,
            ua.blended_pi,
            CAST(ua.used_product_count AS INTEGER) AS used_product_count,
            COALESCE(ur.total_revenue, 0)::DOUBLE AS total_revenue,
            ua.product_pis,
            CAST(COALESCE(fc.total_product_count, 0)    AS INTEGER) AS total_product_count,
            CAST(COALESCE(fc.eligible_product_count, 0) AS INTEGER) AS eligible_product_count,
            CAST(COALESCE(fc.needs_action_count, 0)     AS INTEGER) AS needs_action_count
        FROM used_agg ua
        LEFT JOIN used_rev ur USING (sub_category_name)
        LEFT JOIN full_counts fc USING (sub_category_name)
        ORDER BY ua.blended_pi DESC NULLS LAST
        """

        sql_comp = """
        WITH comp_agg AS (
            SELECT
                sub_category_name,
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
                LIST({
                    'product_name': product_name,
                    'sale_PI': sale_PI,
                    'weight': avg_daily_quantity
                }) FILTER (WHERE used_product AND sale_PI IS NOT NULL) AS comp_product_pis
            FROM base_tmp
            WHERE competitor_name IS NOT NULL
            GROUP BY sub_category_name, competitor_name
        ),
        subcat_total_active AS (
            SELECT sub_category_name,
                   CAST(COUNT(DISTINCT product_id) AS INTEGER) AS total_active
            FROM base_tmp
            GROUP BY sub_category_name
        )
        SELECT
            ca.sub_category_name,
            ca.competitor_name,
            ca.comp_blended_pi,
            ca.comp_used_count,
            ca.comp_mapped_count,
            ca.comp_needs_action,
            ca.comp_product_pis,
            sta.total_active AS comp_eligible_count
        FROM comp_agg ca
        LEFT JOIN subcat_total_active sta USING (sub_category_name)
        """

        with self._duckdb_lock:
            self._duckdb_conn.execute(
                "CREATE OR REPLACE TEMPORARY TABLE base_tmp AS " + materialize_sql,
                params,
            )
            df = self._duckdb_conn.execute(sql_subcat).df()
            comp_df = self._duckdb_conn.execute(sql_comp).df()

        if df.empty:
            return pd.DataFrame(columns=[
                "sub_category_name", "blended_pi", "used_product_count",
                "total_revenue", "pi_deviation", "direction",
                "total_product_count", "eligible_product_count", "needs_action_count",
                "product_pis",
                "competitor_blended_pis", "competitor_product_pis",
                "competitor_used_counts", "competitor_needs_action_counts",
                "competitor_eligible_counts", "competitor_mapped_counts",
            ])

        # Derived columns
        df["pi_deviation"] = df["blended_pi"].apply(
            lambda x: round(x - 1, 4) if pd.notna(x) else None
        )
        df["direction"] = df["pi_deviation"].apply(pi_direction)
        df["product_pis"] = df["product_pis"].apply(
            lambda x: list(x) if x is not None else []
        )

        # Build per-competitor dicts keyed by sub_category_name
        comp_blended: dict[str, dict] = {}
        comp_product_pis: dict[str, dict] = {}
        comp_used: dict[str, dict] = {}
        comp_action: dict[str, dict] = {}
        comp_eligible: dict[str, dict] = {}
        comp_mapped: dict[str, dict] = {}

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
            sub = row.sub_category_name
            comp = row.competitor_name
            comp_blended.setdefault(sub, {})[comp] = _safe_float(row.comp_blended_pi)
            comp_product_pis.setdefault(sub, {})[comp] = _safe_list(row.comp_product_pis)
            comp_used.setdefault(sub, {})[comp] = _safe_int(row.comp_used_count)
            comp_action.setdefault(sub, {})[comp] = _safe_int(row.comp_needs_action)
            comp_eligible.setdefault(sub, {})[comp] = _safe_int(row.comp_eligible_count)
            comp_mapped.setdefault(sub, {})[comp] = _safe_int(row.comp_mapped_count)

        df["competitor_blended_pis"] = df["sub_category_name"].map(comp_blended).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        df["competitor_product_pis"] = df["sub_category_name"].map(comp_product_pis).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        df["competitor_used_counts"] = df["sub_category_name"].map(comp_used).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        df["competitor_needs_action_counts"] = df["sub_category_name"].map(comp_action).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        df["competitor_eligible_counts"] = df["sub_category_name"].map(comp_eligible).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        df["competitor_mapped_counts"] = df["sub_category_name"].map(comp_mapped).apply(
            lambda x: x if isinstance(x, dict) else {}
        )

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
            # Observed-only — unchanged from the original (the regression guard:
            # price_fallback=False must stay byte-identical to pre-feature output).
            sql = """
            WITH scoped AS (SELECT * FROM fp_grain {where})
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
            FROM scoped
            WHERE competitor_name IS NOT NULL AND fp_name IS NOT NULL
            GROUP BY fp_name, competitor_name
            HAVING COUNT(DISTINCT product_id) FILTER (WHERE eligible_product) > 0
            ORDER BY fp_name, competitor_name
            """.format(where=where)
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
            sql = """
            WITH scoped AS (SELECT * FROM fp_grain {where}),
            modal AS (
                SELECT product_id, competitor_name, competitor_sale_price AS modal_price FROM (
                    SELECT product_id, competitor_name, competitor_sale_price,
                           ROW_NUMBER() OVER (PARTITION BY product_id, competitor_name
                               ORDER BY COUNT(*) DESC, competitor_sale_price ASC) AS rn
                    FROM fp_grain
                    WHERE competitor_sale_price > 0 AND is_recent_competitor = TRUE
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
                FROM scoped s
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
            """.format(where=where)
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
            SELECT DISTINCT product_id, competitor_name, classification, is_mapped
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
            CAST(COUNT(*) AS INTEGER) AS total
        FROM product_class
        GROUP BY competitor_name
        """

        # Overall classification breakdown (raw row counts, matches pandas value_counts)
        sql_class_overall = """
        SELECT
            classification,
            CAST(COUNT(*) AS INTEGER) AS cnt
        FROM base_tmp
        WHERE classification IS NOT NULL
        GROUP BY classification
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
                "total": total,
                # is_mapped count (matches Blended PI by competitor); mapped_pct now
                # uses it over total so the classification donut and that table agree.
                "mapped_products": mapped_products,
                "mapped_pct": round(mapped_products / total * 100, 1) if total > 0 else 0.0,
                "potential_reach_pct": round((mapped_total + potential_total) / reachable * 100, 1) if reachable > 0 else 0.0,
            })
        mapping_progress.sort(key=lambda x: x["mapped_pct"], reverse=True)

        # ── classification_breakdown ─────────────────────────────────
        classification_counts = dict(zip(class_df["classification"], class_df["cnt"]))
        classification_breakdown = {
            "mapped_not_pl": int(classification_counts.get("Mapped - Not PL", 0)),
            "mapped_pl": int(classification_counts.get("Mapped - PL", 0)),
            "not_mapped_not_pl_potential": int(classification_counts.get("Not Mapped - Not PL - Potential Match", 0)),
            "not_mapped_not_pl_no_potential": int(classification_counts.get("Not Mapped - Not PL - No Potential Match", 0)),
            "not_mapped_pl_potential": int(classification_counts.get("Not Mapped - PL - Potential Match", 0)),
            "not_mapped_pl_no_potential": int(classification_counts.get("Not Mapped - PL - No Potential Match", 0)),
            "not_mapped_not_pl_no_match": int(classification_counts.get("Not Mapped - Not PL - No Match", 0)),
            "not_mapped_pl_no_match": int(classification_counts.get("Not Mapped - PL - No Match", 0)),
        }

        return {
            "kpis": kpis,
            "competitor_pi": competitor_pi,
            "mapping_progress": mapping_progress,
            "classification_breakdown": classification_breakdown,
        }
