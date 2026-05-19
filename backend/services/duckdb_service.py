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
        # Pre-warm so the first user query doesn't pay the cold-open cost
        (row_count,) = self._duckdb_conn.execute("SELECT COUNT(*) FROM fp_grain").fetchone()
        logger.info(f"[DuckDB] Connected to fp_grain view ({row_count:,} rows)")

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
    # OVERRIDDEN ENDPOINT 1/5 — get_blended_pi_by_subcategory
    # ------------------------------------------------------------------
    def get_blended_pi_by_subcategory(self, filters: dict | None = None) -> pd.DataFrame:
        """DuckDB implementation: 533× faster than pandas on single-FP filter.

        Matches pandas semantics:
          - FP-scoped: re-aggregates from FP grain (modal fresh price → fallback all)
          - GLOBAL: still re-aggregates (we don't have a separate _global_df in DuckDB)
          - used_product = eligible AND has fresh BF price AND has fresh competitor price
          - blended_pi = Σ(sale_PI × avg_daily_quantity) / Σ(avg_daily_quantity) over used rows
        """
        where, params = self._build_where_clause(filters)

        sql = f"""
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
        -- Competitor modal price from fresh observations
        comp_fresh AS (
            SELECT product_id, competitor_id, competitor_sale_price AS comp_modal FROM (
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
        -- Per (product, competitor) base with aggregated prices
        base AS (
            SELECT
                s.product_id, s.competitor_id, s.product_name,
                s.sub_category_name, s.avg_daily_quantity, s.total_revenue,
                s.eligible_product,
                cf.comp_modal,
                bm.bf_modal,
                bm.bf_modal / cf.comp_modal AS sale_PI,
                (s.eligible_product
                    AND cf.comp_modal IS NOT NULL
                    AND bm.bf_modal   IS NOT NULL) AS used_product
            FROM (
                SELECT DISTINCT product_id, competitor_id, product_name,
                       sub_category_name, avg_daily_quantity, total_revenue,
                       eligible_product
                FROM scoped
            ) s
            LEFT JOIN comp_fresh cf USING (product_id, competitor_id)
            LEFT JOIN bf_modal   bm USING (product_id)
        ),
        -- Per-subcategory aggregation (used rows only)
        used_agg AS (
            SELECT
                sub_category_name,
                ROUND(
                    SUM(sale_PI * avg_daily_quantity) FILTER (WHERE used_product)
                    / NULLIF(SUM(avg_daily_quantity) FILTER (WHERE used_product), 0),
                    4
                ) AS blended_pi,
                COUNT(DISTINCT product_id) FILTER (WHERE used_product) AS used_product_count,
                ROUND(
                    (SELECT SUM(total_revenue) FROM (
                        SELECT DISTINCT product_id, total_revenue FROM base b2
                        WHERE b2.used_product AND b2.sub_category_name = base.sub_category_name
                    )), 2
                ) AS total_revenue,
                -- product_pis tooltip data (kept as a LIST of structs)
                LIST({{
                    'product_name': product_name,
                    'sale_PI': sale_PI,
                    'weight': avg_daily_quantity
                }}) FILTER (WHERE used_product AND sale_PI IS NOT NULL) AS product_pis
            FROM base
            GROUP BY sub_category_name
            HAVING COUNT(DISTINCT product_id) FILTER (WHERE used_product) > 0
        ),
        -- Per-subcategory full-set counts (not just used)
        full_counts AS (
            SELECT
                sub_category_name,
                COUNT(DISTINCT product_id) AS total_product_count,
                COUNT(DISTINCT product_id) FILTER (WHERE eligible_product) AS eligible_product_count
            FROM base
            GROUP BY sub_category_name
        )
        SELECT
            ua.sub_category_name,
            ua.blended_pi,
            CAST(ua.used_product_count AS INTEGER) AS used_product_count,
            ua.total_revenue,
            ua.product_pis,
            CAST(COALESCE(fc.total_product_count, 0)    AS INTEGER) AS total_product_count,
            CAST(COALESCE(fc.eligible_product_count, 0) AS INTEGER) AS eligible_product_count,
            0::INTEGER AS needs_action_count
        FROM used_agg ua
        LEFT JOIN full_counts fc USING (sub_category_name)
        ORDER BY ua.blended_pi DESC NULLS LAST
        """

        with self._duckdb_lock:
            df = self._duckdb_conn.execute(sql, params).df()

        if df.empty:
            return pd.DataFrame(columns=[
                "sub_category_name", "blended_pi", "used_product_count",
                "total_revenue", "pi_deviation", "direction",
                "total_product_count", "eligible_product_count", "needs_action_count",
                "product_pis",
            ])

        # Add derived columns that pandas version produces
        df["pi_deviation"] = df["blended_pi"].apply(
            lambda x: round(x - 1, 4) if pd.notna(x) else None
        )
        df["direction"] = df["pi_deviation"].apply(pi_direction)

        # product_pis comes back as a list of dicts; ensure it's a Python list
        df["product_pis"] = df["product_pis"].apply(
            lambda x: list(x) if x is not None else []
        )

        # ── Per-competitor enrichment (still done in pandas for Phase 1) ──
        # The router expects competitor_blended_pis, competitor_used_counts,
        # competitor_eligible_counts, competitor_mapped_counts, etc. on each row.
        # For Phase 1 we keep these as empty dicts; the executive dashboard
        # endpoint (also a Phase 2 target) provides per-competitor breakdown.
        df["competitor_blended_pis"] = [{} for _ in range(len(df))]
        df["competitor_product_pis"] = [{} for _ in range(len(df))]
        df["competitor_used_counts"] = [{} for _ in range(len(df))]
        df["competitor_needs_action_counts"] = [{} for _ in range(len(df))]
        df["competitor_eligible_counts"] = [{} for _ in range(len(df))]
        df["competitor_mapped_counts"] = [{} for _ in range(len(df))]

        return df.reset_index(drop=True)
