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
from backend.services.parquet_cache import is_fresh, write_parquet
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
        """Materialize Parquet from `_df` if stale/missing, then open a DuckDB view."""
        if not is_fresh(self._parquet_path, self._max_parquet_age_hours):
            logger.info(f"[DuckDB] Parquet missing/stale → writing from in-memory _df")
            write_parquet(self._df, self._parquet_path)

        self._duckdb_conn = duckdb.connect(":memory:", read_only=False)
        self._duckdb_conn.execute("PRAGMA threads=4")
        self._duckdb_conn.execute(
            f"CREATE OR REPLACE VIEW fp_grain AS "
            f"SELECT * FROM read_parquet('{self._parquet_path}')"
        )
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

    def refresh_parquet(self) -> None:
        """Re-export `_df` to Parquet and reload the DuckDB view (called after BG refresh)."""
        with self._duckdb_lock:
            write_parquet(self._df, self._parquet_path)
            self._duckdb_conn.execute(
                f"CREATE OR REPLACE VIEW fp_grain AS "
                f"SELECT * FROM read_parquet('{self._parquet_path}')"
            )
            logger.info("[DuckDB] Refreshed Parquet + reopened view")

    # ------------------------------------------------------------------
    # OVERRIDDEN — _apply_filters: speeds up EVERY method that goes through
    # this code path (which is all the filter-heavy ones). Routes the FP-filter
    # case through DuckDB; GLOBAL falls through to the pandas _global_df.
    # ------------------------------------------------------------------
    def _apply_filters(self, df: pd.DataFrame, filters: dict | None = None) -> pd.DataFrame:
        fp_names = filters.get("fp_names") if filters else None
        if not fp_names:
            # GLOBAL: parent uses pre-aggregated _global_df (already fast)
            return super()._apply_filters(df, filters)

        # FP-scoped: run DuckDB aggregation, return as pandas DataFrame, then
        # apply remaining filters in pandas (the small post-aggregation frame
        # makes pandas filtering trivially fast).
        where, params = self._build_where_clause({"fp_names": fp_names})
        base_cte = self._BASE_CTE.format(where=where)
        sql = base_cte + " SELECT * FROM base"
        with self._duckdb_lock:
            aggregated = self._duckdb_conn.execute(sql, params).df()

        # Merge in catalog-enriched prices (now_price, now_sale_price) from
        # the pandas `_df`. These are updated post-startup by the catalog
        # enrichment process and may not be in the Parquet snapshot.
        if "now_price" in self._df.columns or "now_sale_price" in self._df.columns:
            price_cols = [c for c in ("product_id", "now_price", "now_sale_price")
                          if c in self._df.columns]
            now_prices = self._df[price_cols].drop_duplicates("product_id")
            aggregated = aggregated.merge(now_prices, on="product_id", how="left")
        else:
            aggregated["now_price"] = None
            aggregated["now_sale_price"] = None

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
            WHERE competitor_sale_price IS NOT NULL AND is_recent_competitor = TRUE
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
            WHERE competitor_sale_price IS NOT NULL
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
            ANY_VALUE(classification)              AS classification,
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
            MIN(days_since_update) FILTER (WHERE competitor_sale_price IS NOT NULL)        AS days_since_update,
            MIN(competitor_sale_price) FILTER (WHERE competitor_sale_price IS NOT NULL)    AS min_competitor_sale_price,
            MAX(competitor_sale_price) FILTER (WHERE competitor_sale_price IS NOT NULL)    AS max_competitor_sale_price,
            MAX(bf_price_updated_at) FILTER (WHERE competitor_sale_price IS NOT NULL)      AS bf_price_updated_at,
            MAX(competitor_price_updated_at) FILTER (WHERE competitor_sale_price IS NOT NULL) AS competitor_price_updated_at
        FROM scoped
        GROUP BY product_id, competitor_id
    ),
    -- Final aggregated base: one row per (product, competitor) with recomputed flags
    base AS (
        SELECT
            pm.*,
            COALESCE(cf.comp_fresh_modal, ca.comp_all_modal) AS competitor_sale_price,
            bm.bf_modal AS bf_sale_price,
            bm.bf_modal / COALESCE(cf.comp_fresh_modal, ca.comp_all_modal) AS sale_PI,
            -- Recomputed flags (match pandas _aggregate_to_global)
            (cf.comp_fresh_modal IS NOT NULL)             AS is_recent_competitor,
            (ca.comp_all_modal   IS NOT NULL)             AS has_PI,
            (bm.bf_modal         IS NOT NULL)             AS is_recent_breadfast,
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
        """
        where, params = self._build_where_clause(filters)
        base_cte = self._BASE_CTE.format(where=where)

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
                }) FILTER (WHERE used_product AND sale_PI IS NOT NULL) AS product_pis,
                ROUND(SUM(DISTINCT total_revenue) FILTER (WHERE used_product), 2) AS total_revenue
            FROM base_tmp
            GROUP BY sub_category_name
            HAVING COUNT(DISTINCT product_id) FILTER (WHERE used_product) > 0
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
            COALESCE(ua.total_revenue, 0)::DOUBLE AS total_revenue,
            ua.product_pis,
            CAST(COALESCE(fc.total_product_count, 0)    AS INTEGER) AS total_product_count,
            CAST(COALESCE(fc.eligible_product_count, 0) AS INTEGER) AS eligible_product_count,
            CAST(COALESCE(fc.needs_action_count, 0)     AS INTEGER) AS needs_action_count
        FROM used_agg ua
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
    def get_executive_dashboard(self, filters: dict | None = None) -> dict:
        """Executive dashboard payload (KPIs + per-competitor PI + mapping
        progress + classification breakdown).

        Computed in a single materialization pass via the shared `base_tmp`
        temp table; ~100× faster than the pandas implementation on single-FP
        filters.
        """
        where, params = self._build_where_clause(filters)
        base_cte = self._BASE_CTE.format(where=where)
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

        # Per-competitor blended PI + mapped/used/eligible counts
        # `eligible_products` here means "total active products in the result set"
        # (same value for all competitors) — matches commercial.py expectation.
        sql_comp_pi = """
        WITH total_active AS (
            SELECT COUNT(DISTINCT product_id) AS total_active FROM base_tmp
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
            CAST(pc.mapped_products AS INTEGER) AS mapped_products,
            CAST(ta.total_active   AS INTEGER) AS eligible_products,
            CAST(pc.used_products  AS INTEGER) AS used_products
        FROM per_comp pc CROSS JOIN total_active ta
        ORDER BY pc.blended_pi DESC NULLS LAST
        """

        # Per-competitor mapping_progress: counts by classification at product grain
        sql_mapping_progress = """
        WITH product_class AS (
            SELECT DISTINCT product_id, competitor_name, classification
            FROM base_tmp
            WHERE competitor_name IS NOT NULL AND classification IS NOT NULL
        )
        SELECT
            competitor_name,
            CAST(COUNT(*) FILTER (WHERE classification = 'Mapped - Not PL') AS INTEGER) AS mapped_not_pl,
            CAST(COUNT(*) FILTER (WHERE classification = 'Mapped - PL')     AS INTEGER) AS mapped_pl,
            CAST(COUNT(*) FILTER (WHERE classification = 'Not Mapped - Not PL - Potential Match')    AS INTEGER) AS potential_not_pl,
            CAST(COUNT(*) FILTER (WHERE classification = 'Not Mapped - PL - Potential Match')        AS INTEGER) AS potential_pl,
            CAST(COUNT(*) FILTER (WHERE classification = 'Not Mapped - Not PL - No Potential Match') AS INTEGER) AS no_potential_not_pl,
            CAST(COUNT(*) FILTER (WHERE classification = 'Not Mapped - PL - No Potential Match')     AS INTEGER) AS no_potential_pl,
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
        mapping_progress = []
        for r in map_df.itertuples(index=False):
            mapped_total = int(r.mapped_not_pl) + int(r.mapped_pl)
            potential_total = int(r.potential_not_pl) + int(r.potential_pl)
            total = int(r.total)
            mapping_progress.append({
                "competitor_name": str(r.competitor_name),
                "mapped_not_pl": int(r.mapped_not_pl),
                "mapped_pl": int(r.mapped_pl),
                "potential_not_pl": int(r.potential_not_pl),
                "potential_pl": int(r.potential_pl),
                "no_potential_not_pl": int(r.no_potential_not_pl),
                "no_potential_pl": int(r.no_potential_pl),
                "total": total,
                "mapped_pct": round(mapped_total / total * 100, 1) if total > 0 else 0.0,
                "potential_reach_pct": round((mapped_total + potential_total) / total * 100, 1) if total > 0 else 0.0,
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
        }

        return {
            "kpis": kpis,
            "competitor_pi": competitor_pi,
            "mapping_progress": mapping_progress,
            "classification_breakdown": classification_breakdown,
        }
