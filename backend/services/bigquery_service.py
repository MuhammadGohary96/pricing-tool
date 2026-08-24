"""
BigQuery-backed pricing data service.

Reads from dbt_gohary.pricing_index_analysis (created by PI-query.sql)
and provides the same interface as MockPricingDataService.

Column mapping from BQ table → internal DataFrame:
  product_name_en              → product_name
  avg_daily_revenue            → total_revenue
  breadfast_sale_price         → bf_sale_price
  combined_score_global        → weighted_score
  norm_revenue_global          → norm_revenue
  norm_quantity_global         → norm_quantity
  breadfast_last_updated_day   → bf_price_updated_at
  competitor_last_updated_day  → competitor_price_updated_at

Derived fields (computed after load):
  pi_deviation      ← sale_PI - 1
  days_since_update ← days since competitor_price_updated_at

Multi-competitor: one row per product × competitor (from dim_competitors registry).
Use competitor filter or aggregate with nunique() for product counts.
"""

import math
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from backend.config import settings as app_settings
from backend.services.data_interface import PricingDataServiceInterface
from backend.utils.calculations import (
    compute_blended_pi,
    pi_direction,
    ACTION_SYMBOLS,
    TIER_ORDER,
)


# BQ column → internal column name
COLUMN_MAP = {
    "product_name_en": "product_name",
    "avg_daily_revenue": "total_revenue",
    "breadfast_sale_price": "bf_sale_price",
    "combined_score_global": "weighted_score",
    "norm_revenue_global": "norm_revenue",
    "norm_quantity_global": "norm_quantity",
    "breadfast_last_updated_day": "bf_price_updated_at",
    "competitor_last_updated_day": "competitor_price_updated_at",
}

FPS_QUERY = """
SELECT
    product_id,
    product_name_en,
    commercial_category_name,
    main_category_name,
    sub_category_name,
    brand_name,
    CAST(avg_daily_revenue          AS FLOAT64) AS avg_daily_revenue,
    CAST(avg_daily_quantity         AS FLOAT64) AS avg_daily_quantity,
    CAST(combined_score_global      AS FLOAT64) AS combined_score_global,
    CAST(norm_revenue_global        AS FLOAT64) AS norm_revenue_global,
    CAST(norm_quantity_global       AS FLOAT64) AS norm_quantity_global,
    global_tier,
    subcat_tier,
    CAST(cumulative_revenue_share   AS FLOAT64) AS cumulative_revenue_share,
    fp_id,
    fp_name,
    CAST(bf_regular_price           AS FLOAT64) AS bf_regular_price,
    competitor_id,
    competitor_name,
    competitor_product_id,
    competitor_product_name,
    CAST(sale_PI                    AS FLOAT64) AS sale_PI,
    CAST(competitor_sale_price      AS FLOAT64) AS competitor_sale_price,
    CAST(min_competitor_sale_price  AS FLOAT64) AS min_competitor_sale_price,
    CAST(max_competitor_sale_price  AS FLOAT64) AS max_competitor_sale_price,
    CAST(breadfast_sale_price       AS FLOAT64) AS breadfast_sale_price,
    is_recent_breadfast,
    is_recent_competitor,
    breadfast_last_updated_day,
    competitor_last_updated_day,
    prices_recently_updated,
    is_mapped,
    eligible_product,
    has_PI,
    used_product,
    updated,
    match_potential,
    CAST(similarity_score           AS FLOAT64) AS similarity_score,
    match_potential_product_name,
    action_type,
    classification,

    -- ── Gap-analysis layer (STEPS 15-20 of docs/FP_granularity_pricing.sql) ──
    -- row_type discriminates the two grains in this table:
    --   'breadfast'  → (product, fp, competitor); everything above is populated
    --   'competitor' → national competitor-only catalogue; product_id / fp_id
    --                  are NULL, so these rows MUST NOT reach _BASE_CTE (which
    --                  collapses on (product_id, competitor_id)). The guard
    --                  lives in duckdb_service._base_cte / get_fp_competitor_pi
    --                  and in _aggregate_to_global below.
    row_type,
    -- scope flags (the tab's beauty / private-label toggles)
    is_beauty,
    is_private_label,
    beauty_path_share,
    -- brand overlap
    brand_key,
    is_shared_brand,
    comp_brand_name,
    -- gap family. is_mapped (above) stays the single match truth.
    matched_comp_active_7d,
    is_confirmed_no_match,
    is_potential_match,
    CAST(best_similarity_in_portfolio AS FLOAT64) AS best_similarity_in_portfolio,
    -- competitor-side detail (NULL on 'breadfast' rows)
    competitor_product_key,
    category_level_1,
    category_level_2,
    category_level_3,
    category_level_4,
    -- competitor category → BF subcategory bridge. On 'breadfast' rows
    -- mapped_bf_sub_category echoes the product's own subcategory, so a single
    -- subcategory filter slices both sides of the gap analysis.
    mapped_bf_sub_category,
    mapped_bf_sub_categories_all,
    CAST(mapped_pct_of_comp_category AS FLOAT64) AS mapped_pct_of_comp_category,
    bridge_level,
    -- data-quality flag: FALSE for Carrefour (no live v2 catalogue)
    competitor_has_v2_catalogue,
    -- Size of the competitor's live catalogue. comp_catalogue downstream holds
    -- only the UNPAIRED products, so the total is not derivable from it.
    CAST(comp_active_products AS INT64) AS comp_active_products,
    -- The same total restricted to brands we also carry, so the Shared-only
    -- brand scope can narrow this column like it narrows every other one.
    CAST(comp_active_products_shared AS INT64) AS comp_active_products_shared,
    -- Marks Breadfast rows whose matched competitor product is in the live
    -- catalogue. With competitor_product_key now populated on those rows, the
    -- paired and unpaired halves partition the catalogue, so it can be counted
    -- under any filter instead of only read as a per-competitor total.
    matched_comp_in_catalogue,
    -- Brand overlap inferred from matches rather than from the brand string, so
    -- Froneri stops reading as ours-only at a competitor that stocks it as
    -- Nestle. The flag says which way it was established; the variants string is
    -- the evidence, "brand:count|brand:count", NULL when the names agree.
    shared_brand_by_match,
    comp_brand_variants
FROM `{project}.{dataset}.{table}`
"""

COMPETITOR_BQ_QUERY = """
SELECT
    product_id,
    product_name_en       AS bf_product_name,
    brand_name,
    main_category_name,
    sub_category_name,
    competitor_id,
    competitor_name,
    competitor_product_id,
    competitor_product_name,
    category_level_1,
    category_level_2,
    category_level_3,
    CAST(competitor_sale_price      AS FLOAT64) AS competitor_sale_price,
    CAST(min_competitor_sale_price  AS FLOAT64) AS min_competitor_sale_price,
    CAST(max_competitor_sale_price  AS FLOAT64) AS max_competitor_sale_price,
    CAST(breadfast_sale_price       AS FLOAT64) AS bf_sale_price,
    competitor_last_updated_day,
    breadfast_last_updated_day      AS bf_last_updated_day,
    is_recent_competitor,
    is_recent_breadfast,
    has_PI,
    CAST(sale_PI                    AS FLOAT64) AS sale_PI,
    classification,
    match_potential,
    CAST(similarity_score           AS FLOAT64) AS similarity_score,
    match_potential_product_name
FROM `{project}.{dataset}.{table}`
WHERE competitor_last_updated_day != '1970-01-01'
"""


class BigQueryPricingDataService(PricingDataServiceInterface):

    def __init__(
        self,
        project_id: str = "bf-data-dev-qz06",
        dataset: str = "dbt_gohary",
        table: str = "pricing_index_analysis",
        location: str = "EU",
        startup_status: dict = None,
    ):
        from google.cloud import bigquery

        self._startup_status = startup_status
        self._client = bigquery.Client(project=project_id, location=location)
        self._project = project_id
        self._dataset = dataset
        self._table = table
        self._location = location

        # Extract progress callback if provided
        progress_callback = None
        if self._startup_status and "progress_callback" in self._startup_status:
            progress_callback = self._startup_status["progress_callback"]

        # Helper to report progress
        def _report(stage: str, progress: int, total: int):
            if progress_callback:
                progress_callback(stage, progress, total)
            if self._startup_status:
                self._startup_status["stage"] = stage
                self._startup_status["progress"] = progress
                self._startup_status["total"] = total

        # Stage 1: Load from BigQuery (80% of work)
        _report("Loading products from BigQuery...", 0, 100)
        self._df = self._load_from_bigquery()
        print(
            f"[BigQuery] Loaded {len(self._df)} rows (FP grain) across "
            f"{self._df['sub_category_name'].nunique()} subcategories, "
            f"{self._df['fp_name'].nunique() if 'fp_name' in self._df.columns else 0} FPs"
        )

        # Stage 2: Pre-aggregate to GLOBAL view (15% of work)
        _report("Aggregating GLOBAL view...", 80, 100)
        self._global_df = self._aggregate_to_global(self._df)
        print(f"[BigQuery] Pre-aggregated GLOBAL view: {len(self._global_df)} rows")

        # Initialize price columns as null — enriched later via user token
        if "now_price" not in self._df.columns:
            self._df["now_price"] = None
        if "now_sale_price" not in self._df.columns:
            self._df["now_sale_price"] = None
        if "now_price" not in self._global_df.columns:
            self._global_df["now_price"] = None
        if "now_sale_price" not in self._global_df.columns:
            self._global_df["now_sale_price"] = None

        # Stage 3: Load competitor products analysis table (5% of work)
        _report("Loading competitor products...", 95, 100)
        self._competitor_df = self._load_competitor_products()

        _report("Ready", 100, 100)

    def _load_from_bigquery(self) -> pd.DataFrame:
        import time

        # Extract progress callback if provided
        progress_callback = None
        if self._startup_status and "progress_callback" in self._startup_status:
            progress_callback = self._startup_status["progress_callback"]

        query = FPS_QUERY.format(
            project=self._project,
            dataset=self._dataset,
            table=self._table,
        )
        print("[BigQuery] Submitting query...")
        t0 = time.time()
        job = self._client.query(query)
        print(f"[BigQuery] Job submitted ({job.job_id}), waiting for BQ execution...")

        # Report progress via callback or startup_status
        def _report_progress(stage: str, progress: int, total: int):
            if progress_callback:
                progress_callback(stage, progress, total)
            if self._startup_status:
                self._startup_status["total"] = total
                self._startup_status["progress"] = progress
                self._startup_status["stage"] = stage

        # Download via the BigQuery Storage Read API (multi-stream gRPC + Arrow
        # IPC). This replaces the old row-by-row dict() loop, which was the
        # dominant cold-load cost. Falls back to the REST iterator if the
        # Storage API is unavailable (e.g. missing bigquery.readsessions IAM).
        rows = job.result()  # Wait for query completion, returns RowIterator
        total_rows = rows.total_rows or 0
        t1 = time.time()

        print(f"[BigQuery] Query executed in {t1 - t0:.1f}s")
        print(f"[BigQuery] Downloading {total_rows:,} rows via Storage Read API (Arrow)...")
        _report_progress(f"Downloading {total_rows:,} rows via Storage API...", 0, total_rows)

        # Stream Arrow RecordBatches so progress ticks during the multi-minute
        # pull (a single to_arrow() call gives no feedback until it completes).
        # Uses the Storage Read API when the client is available; otherwise the
        # iterable transparently falls back to the REST pages (still batched).
        import pyarrow as pa

        bqs_client = None
        try:
            from google.cloud import bigquery_storage
            bqs_client = bigquery_storage.BigQueryReadClient()
        except Exception as exc:
            print(f"[BigQuery] Storage client unavailable ({exc}); using REST iterator")

        try:
            batches = []
            seen = 0
            for batch in rows.to_arrow_iterable(bqstorage_client=bqs_client):
                batches.append(batch)
                seen += batch.num_rows
                _report_progress(
                    f"Downloading {seen:,} / {total_rows:,} rows...", seen, total_rows or seen
                )
            # A RowIterator can only be consumed once — after the streaming
            # loop has started `rows`, any retry must ask the (already
            # completed) job for a fresh iterator, or it raises
            # "Iterator has already started".
            # create_bqstorage_client=False: to_arrow() defaults to True, and
            # the most likely reason we are here is that the Storage API just
            # failed (e.g. missing bigquery.readsessions.create) — the
            # fallback must be pure REST or it re-raises the same error.
            arrow_tbl = (
                pa.Table.from_batches(batches)
                if batches
                else job.result().to_arrow(create_bqstorage_client=False)
            )
            del batches
        except Exception as exc:
            print(f"[BigQuery] Streaming download failed ({exc}); falling back to bulk to_arrow()")
            _report_progress("Falling back to bulk download...", 0, total_rows)
            arrow_tbl = job.result().to_arrow(create_bqstorage_client=False)

        # date_as_object=False → DATE columns become datetime64[ns] (the
        # vectorized derivations below depend on this).
        df = arrow_tbl.to_pandas(date_as_object=False)
        del arrow_tbl
        print(
            f"[BigQuery] Downloaded {len(df):,} rows in {time.time() - t1:.1f}s "
            f"(total {time.time() - t0:.1f}s)"
        )

        _report_progress(f"Loaded {len(df):,} rows, processing...", len(df), max(len(df), 1))

        # A safety net, not a saving: FPS_QUERY does not select these, so they
        # never arrive. They stay IN the BigQuery table deliberately -- the subcat
        # scores pair with the global ones, and product_key/ranks are identifiers
        # other consumers may want -- so this guards a future `SELECT *`.
        DROP_COLS = [
            "norm_revenue_subcat", "norm_quantity_subcat",
            "score_subcat_100rev", "score_subcat_70rev",
            "score_subcat_50rev", "score_subcat_30rev",
            "rank_by_revenue", "rank_by_quantity", "product_key",
        ]
        df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])

        # Rename columns to match internal names
        df = df.rename(columns=COLUMN_MAP)

        # Safety-net numeric cast. The SQL already wraps these in CAST(... AS
        # FLOAT64), so they arrive as Arrow double → float64; this only catches
        # any column that slips through as object/decimal.
        numeric_cols = [
            "total_revenue", "avg_daily_quantity", "weighted_score",
            "norm_revenue", "norm_quantity", "sale_PI",
            "bf_sale_price", "bf_regular_price", "competitor_sale_price",
            "min_competitor_sale_price", "max_competitor_sale_price",
            "similarity_score", "cumulative_revenue_share",
            # gap layer
            "best_similarity_in_portfolio", "mapped_pct_of_comp_category",
            "beauty_path_share",
        ]
        for col in numeric_cols:
            if col in df.columns and df[col].dtype == object:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # matched_comp_active_7d arrives as INT64 (0/1, NULL when the pair has no
        # observation at all). Normalize to a plain bool: "no observation" and
        # "observation but stale" both mean "not active", which is what every
        # consumer asks of it.
        if "matched_comp_active_7d" in df.columns:
            df["matched_comp_active_7d"] = (
                pd.to_numeric(df["matched_comp_active_7d"], errors="coerce").fillna(0) == 1
            )

        # Cast booleans (BQ may return NaN for nullable bools).
        # Gap-layer flags are NULL on the row type they don't apply to
        # (e.g. is_confirmed_no_match on competitor rows); False is the correct
        # reading of "does not apply", and it matches the COALESCE(..., FALSE)
        # the roll-up SQL uses.
        for col in ["eligible_product", "has_PI", "updated", "match_potential", "used_product",
                    "is_recent_breadfast", "is_recent_competitor", "prices_recently_updated", "is_mapped",
                    # gap layer
                    "is_beauty", "is_private_label", "is_shared_brand",
                    "is_confirmed_no_match", "is_potential_match",
                    "competitor_has_v2_catalogue"]:
            if col in df.columns:
                df[col] = df[col].fillna(False).astype(bool)

        # Cast string columns (keep as plain strings to avoid categorical dtype bugs).
        # NULL-preserving: a bare .astype(str) turns missing values into the
        # literal strings "nan"/"None", which are not NULL to anything
        # downstream. That is harmless for 'breadfast' rows (never NULL here)
        # but the gap layer's competitor-only rows are NULL in all three, and a
        # stringified "None" fp_name would show up as an FP in the dropdown.
        # Integer ids need the nullable Int64 hop first: BQ INT64 + NULLs arrives
        # as float64, and str() on that yields "1180345.0".
        for col in ("product_id", "fp_id", "fp_name"):
            if col not in df.columns:
                continue
            s = df[col]
            if pd.api.types.is_float_dtype(s) or pd.api.types.is_integer_dtype(s):
                s = s.astype("Int64")
            df[col] = pd.Series(
                [None if pd.isna(v) else str(v) for v in s],
                index=df.index, dtype=object,
            )

        # Derive pi_deviation (vectorized; NaN stays NaN)
        df["pi_deviation"] = (df["sale_PI"] - 1).round(4)

        # Ensure date columns are datetime64 (Arrow date32 → datetime64[ns])
        for col in ["bf_price_updated_at", "competitor_price_updated_at"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # Derive days_since_update (vectorized)
        now_ts = pd.Timestamp(datetime.now().date())
        if "competitor_price_updated_at" in df.columns:
            days = (now_ts - df["competitor_price_updated_at"]).dt.days
            # Keep None (not NaN) for missing dates to match prior behavior
            df["days_since_update"] = days.astype("object").where(days.notna(), None)

        # Convert date columns to ISO strings for JSON serialization (vectorized)
        for col in ["bf_price_updated_at", "competitor_price_updated_at"]:
            if col in df.columns:
                iso = df[col].dt.strftime("%Y-%m-%d")
                df[col] = iso.where(df[col].notna(), None)

        # Fill bf_regular_price if missing (not in BQ table)
        if "bf_regular_price" not in df.columns:
            df["bf_regular_price"] = df["bf_sale_price"]

        return df.reset_index(drop=True)

    def get_products_pivoted(
        self, filters: dict = None, page: int = 1, page_size: int = 50,
        sort_by: str = None, sort_dir: str = "desc", search: str = None,
    ) -> dict:
        # Strip competitor + action_type filters: competitor because we always show all as columns,
        # action_type because we recompute it as the worst action across all competitors post-pivot.
        clean_filters = {k: v for k, v in (filters or {}).items() if k not in ("competitor", "action_type")}
        df = self._apply_filters(self._df, clean_filters)

        competitors = sorted(df["competitor_name"].dropna().unique().tolist())

        base_cols = [
            "product_id", "product_name", "brand_name", "sub_category_name",
            "global_tier", "bf_sale_price", "bf_regular_price",
            "now_price", "now_sale_price",
            "total_revenue", "eligible_product", "used_product", "weighted_score",
        ]
        product_df = df.drop_duplicates("product_id")[[c for c in base_cols if c in df.columns]].copy()

        for comp in competitors:
            comp_cols = ["product_id", "competitor_sale_price", "sale_PI", "action_type", "days_since_update"]
            if "classification" in df.columns:
                comp_cols.append("classification")
            comp_df = df[df["competitor_name"] == comp][comp_cols].drop_duplicates("product_id")
            product_df = product_df.merge(
                comp_df.rename(columns={
                    "competitor_sale_price": f"{comp}_price",
                    "sale_PI": f"{comp}_pi",
                    "action_type": f"{comp}_action",
                    "days_since_update": f"{comp}_days_stale",
                    "classification": f"{comp}_classification",
                }),
                on="product_id", how="left",
            )

        pi_cols = [f"{c}_pi" for c in competitors if f"{c}_pi" in product_df.columns]
        if pi_cols:
            product_df["worst_pi"] = product_df[pi_cols].max(axis=1)
        else:
            product_df["worst_pi"] = None

        # Compute product-level action as worst action across all competitors
        action_cols = [f"{c}_action" for c in competitors if f"{c}_action" in product_df.columns]
        _NORM = {"Review AI Match": "Review Match"}  # normalize legacy label
        if action_cols:
            _PRIO = {"Needs Mapping": 3, "Review Match": 2, "Review AI Match": 2, "Needs Price Update": 1, "Complete": 0}
            _REV  = {3: "Needs Mapping", 2: "Review Match", 1: "Needs Price Update", 0: "Complete"}
            product_df["action_type"] = product_df[action_cols].apply(
                lambda row: _REV[max(_PRIO.get(v, 0) for v in row if pd.notna(v) and v)],
                axis=1,
            )
        else:
            product_df["action_type"] = "Complete"

        # Compute action_counts per product (all actions including Complete, normalized)
        if action_cols:
            product_df["_action_counts"] = product_df[action_cols].apply(
                lambda row: {
                    a: sum(1 for v in row if _NORM.get(v, v) == a)
                    for a in ["Needs Mapping", "Review Match", "Needs Price Update", "Complete"]
                    if sum(1 for v in row if _NORM.get(v, v) == a) > 0
                },
                axis=1,
            )
        else:
            product_df["_action_counts"] = [{} for _ in range(len(product_df))]

        # Apply action_type filter post-pivot (using the computed worst action)
        if filters and filters.get("action_type"):
            allowed = {v.strip() for v in filters["action_type"].split(",")}
            product_df = product_df[product_df["action_type"].isin(allowed)]

        if search:
            q = search.lower()
            mask = product_df["product_name"].str.lower().str.contains(q, na=False)
            product_df = product_df[mask]

        SORTABLE = {"worst_pi", "total_revenue", "weighted_score", "product_name", "bf_sale_price", "global_tier", "action_type"}
        if sort_by and sort_by in SORTABLE and sort_by in product_df.columns:
            product_df = product_df.sort_values(sort_by, ascending=(sort_dir == "asc"), na_position="last")
        else:
            # Default: sort by combined_score_global (weighted_score) descending — most important products first
            product_df = product_df.sort_values("weighted_score", ascending=False, na_position="last")

        total = len(product_df)
        # Distinct subcategories in the same product scope as total_count — so the
        # "Subcategories" KPI counts ALL tracked subcats, not just those with a
        # blended PI (the blended-PI table drops subcats with no used products).
        subcategory_count = int(product_df["sub_category_name"].nunique()) if "sub_category_name" in product_df.columns else 0
        page_df = product_df.iloc[(page - 1) * page_size: page * page_size]

        def _s(val):
            if val is None:
                return None
            try:
                import math
                if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                    return None
            except Exception:
                pass
            return val

        items = []
        for _, row in page_df.iterrows():
            item = {
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "brand_name": row["brand_name"],
                "sub_category_name": row["sub_category_name"],
                "global_tier": row["global_tier"],
                "action_type": row["action_type"],
                "bf_sale_price": _s(float(row["bf_sale_price"])) if pd.notna(row.get("bf_sale_price")) else None,
                "bf_regular_price": _s(float(row["bf_regular_price"])) if pd.notna(row.get("bf_regular_price")) else None,
                "now_price": _s(float(row["now_price"])) if pd.notna(row.get("now_price")) else None,
                "now_sale_price": _s(float(row["now_sale_price"])) if pd.notna(row.get("now_sale_price")) else None,
                "total_revenue": _s(float(row["total_revenue"])) if pd.notna(row.get("total_revenue")) else None,
                "eligible_product": bool(row["eligible_product"]),
                "used_product": bool(row["used_product"]),
                "worst_pi": _s(float(row["worst_pi"])) if pd.notna(row.get("worst_pi")) else None,
                "weighted_score": _s(float(row["weighted_score"])) if pd.notna(row.get("weighted_score")) else None,
                "action_counts": row.get("_action_counts", {}),
            }
            for comp in competitors:
                price_key = f"{comp}_price"
                pi_key = f"{comp}_pi"
                action_key = f"{comp}_action"
                days_key = f"{comp}_days_stale"
                class_key = f"{comp}_classification"
                item[price_key] = _s(float(row[price_key])) if pd.notna(row.get(price_key)) else None
                item[pi_key] = _s(float(row[pi_key])) if pd.notna(row.get(pi_key)) else None
                item[action_key] = row.get(action_key)
                item[days_key] = int(row[days_key]) if pd.notna(row.get(days_key)) else None
                item[class_key] = row.get(class_key) if pd.notna(row.get(class_key)) else None
            items.append(item)

        return {"items": items, "total_count": total, "competitors": competitors,
                "subcategory_count": subcategory_count}

    def _load_product_rows(self, product_id) -> Optional[pd.DataFrame]:
        """All fp-grain rows for one product. pandas path reads `_df`; the
        DuckDB service overrides this to query the `fp_grain` Parquet view."""
        df = self._df
        if df is None:
            return None
        return df[df["product_id"].astype(str) == str(product_id)]

    def get_product_fp_matrix(self, product_id, filters: dict | None = None, price_fallback: bool = False) -> dict:
        """One product's full FP × competitor price matrix from the (product, fp,
        competitor)-grain frame. Each cell carries the competitor's modal price
        at that FP and its sale_PI (bf_fp / competitor_fp — same convention as
        the aggregated `sale_PI`, so cells stay consistent with the pivot table).

        Cell states: priced (fresh) · stale (>7d / not recent) · no_price
        (mapped, never observed at this FP) · not_mapped (no competitor link).

        Honors the dashboard's active filters (fp_names / competitor shape the
        rows & columns; category / brand / tier scope the product itself).

        The (product, fp, competitor)-grain rows are fetched via
        `_load_product_rows` so DuckDB-backed deployments (where `_df` is not
        loaded on the serving path) can override the source.
        """
        sub = self._load_product_rows(product_id)
        if sub is None or sub.empty:
            return {"found": False}

        # Apply the active dashboard filters to the product's rows. Each filter
        # maps to an fp-grain column; values are comma-separated (matches the
        # pivot/blended-PI filter semantics).
        if filters:
            _FILTER_COLS = {
                "fp_names": "fp_name",
                "competitor": "competitor_name",
                "brand": "brand_name",
                "main_category": "commercial_category_name",
                "sub_category": "sub_category_name",
                "global_tier": "global_tier",
                "subcat_tier": "subcat_tier",
            }
            for key, col in _FILTER_COLS.items():
                raw = filters.get(key)
                if not raw or col not in sub.columns:
                    continue
                values = [v.strip() for v in str(raw).split(",") if v.strip()]
                if values:
                    sub = sub[sub[col].isin(values)]
            if filters.get("exclude_private_label") and "brand_name" in sub.columns:
                sub = sub[~sub["brand_name"].str.lower().str.contains("breadfast", na=False)]
            if sub.empty:
                return {"found": False}

        def _modal(series):
            """Most-frequent positive value; tie-break on the smallest (matches
            the modal-price logic in `_aggregate_to_global` / the DuckDB CTE)."""
            s = series.dropna()
            s = s[s > 0]
            if s.empty:
                return None
            counts = s.value_counts()
            top = counts.max()
            return float(min(counts[counts == top].index))

        def _s(v):
            if v is None:
                return None
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
            return v

        first = sub.iloc[0]
        # Product-level BF prices (modal of fresh BF rows, fall back to all)
        bf_recent = sub[sub.get("is_recent_breadfast", False) == True]  # noqa: E712
        bf_sale = _modal(bf_recent["bf_sale_price"]) if not bf_recent.empty else None
        if bf_sale is None:
            bf_sale = _modal(sub["bf_sale_price"])

        competitors = sorted(c for c in sub["competitor_name"].dropna().unique())
        fp_names = sorted(f for f in sub["fp_name"].dropna().unique())

        _PRIO = {"Needs Mapping": 3, "Review Match": 2, "Needs Price Update": 1, "Complete": 0}
        _REV = {3: "Needs Mapping", 2: "Review Match", 1: "Needs Price Update", 0: "Complete"}

        # Per-competitor pair metadata + derived column action
        comp_meta = {}
        for comp in competitors:
            cdf = sub[sub["competitor_name"] == comp]
            is_mapped = bool(cdf.get("is_mapped", pd.Series([False])).any())
            sim_vals = cdf["similarity_score"].dropna() if "similarity_score" in cdf else pd.Series([], dtype=float)
            sim = float(sim_vals.max()) if not sim_vals.empty else None
            cpn = cdf["competitor_product_name"].dropna()
            comp_product_name = str(cpn.iloc[0]) if not cpn.empty else None
            priced = cdf[cdf["competitor_sale_price"] > 0]
            fresh = priced[priced.get("is_recent_competitor", False) == True]  # noqa: E712
            if not is_mapped:
                action = "Needs Mapping" if (sim is None or sim < 0.85) else "Review Match"
            elif priced.empty:
                action = "Needs Price Update"
            elif not fresh.empty:
                action = "Complete"
            else:
                action = "Needs Price Update"
            # FRESH-only modal — the single basis for both estimates and the Min/Max-PI
            # chips. A pair with no fresh price anywhere has no fresh modal, so it never
            # produces an estimate and drops out of the chip ranking (it cannot be
            # judged on a stale price).
            fresh_modal = _modal(fresh["competitor_sale_price"]) if not fresh.empty else None
            # Cross-FP stale modal — only for a pair with NO fresh price anywhere. Used
            # solely to fill the matrix (badged "outdated") when the estimate toggle is
            # on; it never feeds the blend, used counts, or chips.
            stale_only = fresh.empty and not priced.empty
            stale_modal = _modal(priced["competitor_sale_price"]) if stale_only else None
            stale_days_s = priced["days_since_update"].dropna() if "days_since_update" in priced else pd.Series([], dtype=float)
            stale_days = int(stale_days_s.min()) if (stale_only and not stale_days_s.empty) else None
            agg_pi = round(bf_sale / fresh_modal, 4) if (bf_sale and fresh_modal) else None
            comp_meta[comp] = {
                "competitor_name": comp,
                "is_mapped": is_mapped,
                "competitor_product_name": comp_product_name,
                "similarity_score": _s(sim),
                "action": action,
                "agg_price": _s(fresh_modal),   # Min/Max chips read this (fresh-only)
                "agg_pi": _s(agg_pi),
                "fresh_modal": fresh_modal,
                "stale_only": stale_only,
                "stale_modal": _s(stale_modal),
                "stale_days": stale_days,
            }

        # Build the matrix rows (one per FP)
        rows = []
        used_pis = []
        priced_fresh = 0
        estimated_cells = 0
        outdated_cells = 0
        for fp in fp_names:
            fdf = sub[sub["fp_name"] == fp]
            fp_bf_recent = fdf[fdf.get("is_recent_breadfast", False) == True]  # noqa: E712
            fp_bf = _modal(fp_bf_recent["bf_sale_price"]) if not fp_bf_recent.empty else None
            if fp_bf is None:
                fp_bf = _modal(fdf["bf_sale_price"])
            cells = []
            for comp in competitors:
                meta = comp_meta[comp]
                cell = {"competitor_name": comp, "state": "not_mapped",
                        "price": None, "pi": None, "days_since_update": None,
                        "is_estimated": False, "is_outdated": False}
                if not meta["is_mapped"]:
                    cells.append(cell)
                    continue
                cfdf = fdf[fdf["competitor_name"] == comp]
                priced = cfdf[cfdf["competitor_sale_price"] > 0]
                fresh = priced[priced.get("is_recent_competitor", False) == True] if not priced.empty else priced  # noqa: E712
                if not fresh.empty:
                    # Observed FRESH price at this FP — trusted, always blended.
                    price = _modal(fresh["competitor_sale_price"])
                    days = fresh["days_since_update"].dropna()
                    cell["price"] = _s(price)
                    cell["days_since_update"] = int(days.min()) if not days.empty else None
                    pi = (fp_bf / price) if (fp_bf and price) else None
                    cell["pi"] = _s(round(pi, 4)) if pi is not None else None
                    cell["state"] = "priced"
                    priced_fresh += 1
                    if pi is not None:
                        used_pis.append(pi)
                elif price_fallback and meta["fresh_modal"] and fp_bf:
                    # ESTIMATED: no fresh price at this FP, but the pair IS fresh at
                    # some FP → fill with its FRESH modal. Counts toward the blend.
                    est = meta["fresh_modal"]
                    cell["price"] = _s(est)
                    cell["pi"] = _s(round(fp_bf / est, 4))
                    cell["state"] = "estimated"
                    cell["is_estimated"] = True
                    estimated_cells += 1
                    used_pis.append(fp_bf / est)
                elif not priced.empty:
                    # OUTDATED (observed): a competitor price is observed at THIS FP but
                    # isn't fresh. Show the local stale modal, flagged outdated — never
                    # blended. Always shown where actually observed, in either mode.
                    price = _modal(priced["competitor_sale_price"])
                    days = priced["days_since_update"].dropna()
                    cell["price"] = _s(price)
                    cell["days_since_update"] = int(days.min()) if not days.empty else None
                    cell["pi"] = _s(round(fp_bf / price, 4)) if (fp_bf and price) else None
                    cell["state"] = "outdated"
                    cell["is_outdated"] = True
                    outdated_cells += 1
                elif price_fallback and meta["stale_only"] and meta["stale_modal"]:
                    # OUTDATED (filled, toggle ON only): the pair has only stale prices
                    # anywhere. In fill mode, surface the cross-FP stale modal so the
                    # matrix isn't sparse — but badge it outdated and keep it OUT of the
                    # blend, used count, and chips. With the toggle OFF this branch is
                    # skipped, so unobserved FPs stay "no_price" (no stale fill).
                    out = meta["stale_modal"]
                    cell["price"] = _s(out)
                    cell["pi"] = _s(round(fp_bf / out, 4)) if fp_bf else None
                    cell["days_since_update"] = meta["stale_days"]
                    cell["state"] = "outdated"
                    cell["is_outdated"] = True
                    outdated_cells += 1
                else:
                    cell["state"] = "no_price"
                cells.append(cell)
            rows.append({"fp_name": fp, "bf_sale_price": _s(fp_bf), "cells": cells})

        blended = round(sum(used_pis) / len(used_pis), 4) if used_pis else None
        overall_action = _REV[max((_PRIO.get(m["action"], 0) for m in comp_meta.values()), default=0)]

        bf_updated = sub["bf_price_updated_at"].dropna()
        return {
            "found": True,
            "product": {
                "product_id": str(product_id),
                "product_name": str(first["product_name"]),
                "brand_name": str(first["brand_name"]),
                "main_category_name": str(first.get("main_category_name", "")),
                "sub_category_name": str(first.get("sub_category_name", "")),
                "global_tier": _s(first.get("global_tier")),
                "bf_sale_price": _s(bf_sale),
                "bf_regular_price": _s(float(first["bf_regular_price"])) if pd.notna(first.get("bf_regular_price")) else None,
                "bf_price_updated_at": str(bf_updated.max()) if not bf_updated.empty else None,
            },
            "competitors": [
                {k: v for k, v in comp_meta[c].items()
                 if k not in ("fresh_modal", "stale_only", "stale_modal", "stale_days")}
                for c in competitors
            ],

            "rows": rows,
            "summary": {
                "blended_pi": blended,
                "total_cells": len(competitors) * len(fp_names),
                "priced_fresh_cells": priced_fresh,
                "estimated_cells": estimated_cells,
                "outdated_cells": outdated_cells,
                "action": overall_action,
            },
        }

    # ─── Shared helpers ─────────────────────────────────────────

    @staticmethod
    def _worst_action_per_product(df: pd.DataFrame) -> pd.Series:
        """Returns Series: product_id → worst action across all competitor rows.
        Priority: Needs Mapping > Review Match > Needs Price Update > Complete.
        """
        _PRIO = {"Needs Mapping": 3, "Review Match": 2, "Review AI Match": 2, "Needs Price Update": 1, "Complete": 0}
        _REV  = {3: "Needs Mapping", 2: "Review Match", 1: "Needs Price Update", 0: "Complete"}
        return (
            df.groupby("product_id")["action_type"]
            .apply(lambda x: _REV[max(_PRIO.get(a, 0) for a in x)])
        )

    @staticmethod
    def _multi_match(df, column, value):
        """Filter column by a single value or comma-separated list."""
        if "," in value:
            return df[df[column].isin([v.strip() for v in value.split(",")])]
        return df[df[column] == value]

    def _aggregate_to_global(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Collapse (product, fp, competitor) → (product, competitor).

        Price aggregation rules:
        - BF: Modal price from is_recent_breadfast=TRUE rows.
        - Competitor: Modal of FRESH observations; fall back to modal of ALL
          observations if no fresh; NULL if no observations at all.

        action_type is RECOMPUTED from aggregated state (not carried from a single FP):
          not mapped + no AI match  → Needs Mapping
          not mapped + AI match     → Review AI Match
          mapped + no obs anywhere  → Needs Price for FP
          mapped + ≥1 fresh obs     → Complete
          mapped + only stale obs   → Needs Price Update
        """
        # Competitor-only rows (gap layer) are a different grain: national, with
        # product_id = NULL. Collapsing on product_id would fold all of them into
        # one row per competitor, so they never enter this path — they are served
        # from the separate comp_catalogue materialization.
        if "row_type" in df.columns:
            df = df[df["row_type"] == "breadfast"]

        # 1. Modal BF sale price — from recent BF rows only
        bf_recent = df[df["is_recent_breadfast"] == True]
        bf_modal = (
            bf_recent.groupby("product_id")["bf_sale_price"]
            .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
            .rename("bf_sale_price_modal")
        )

        # 2. Competitor price: rows with any VALID observation (price > 0).
        # A competitor price of 0 is treated as no observation — it would make
        # sale_PI = bf_price / 0 = inf and poison the blended PI.
        comp_obs = df[df["competitor_sale_price"] > 0]
        comp_fresh = comp_obs[comp_obs["is_recent_competitor"] == True]

        # 2a. Modal price from fresh observations
        comp_fresh_modal = (
            comp_fresh.groupby(["product_id", "competitor_id"])["competitor_sale_price"]
            .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
            .rename("comp_price_fresh_modal")
        )

        # 2b. Modal price from ALL observations (fallback for when no fresh)
        comp_all_modal = (
            comp_obs.groupby(["product_id", "competitor_id"])["competitor_sale_price"]
            .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
            .rename("comp_price_all_modal")
        )

        # 2c. Flags: does (product, competitor) have any fresh / any observation
        has_fresh_pairs = set(
            map(tuple, comp_fresh[["product_id", "competitor_id"]].drop_duplicates().values)
        )
        has_obs_pairs = set(
            map(tuple, comp_obs[["product_id", "competitor_id"]].drop_duplicates().values)
        )

        # 3. Product-level base fields (same across all FPs — dedup by product_id)
        product_cols = [
            "product_id", "product_name", "commercial_category_name",
            "main_category_name", "sub_category_name", "brand_name",
            "total_revenue", "avg_daily_quantity", "weighted_score",
            "norm_revenue", "norm_quantity", "global_tier", "subcat_tier",
            "cumulative_revenue_share", "eligible_product", "bf_regular_price",
        ]
        product_base = df.drop_duplicates("product_id")[[c for c in product_cols if c in df.columns]].copy()

        # 4. Competitor-level base fields (product-level competitor link info)
        # NOTE: action_type, has_PI, updated, is_recent_* are EXCLUDED — recomputed below
        comp_cols_first = [
            "product_id", "competitor_id", "competitor_name",
            "competitor_product_id", "competitor_product_name",
            "is_mapped", "match_potential", "similarity_score",
            "match_potential_product_name", "classification",
        ]
        comp_base = df.drop_duplicates(["product_id", "competitor_id"])[
            [c for c in comp_cols_first if c in df.columns]
        ].copy()

        # min/max competitor sale price across observed FPs (spread)
        if "competitor_sale_price" in df.columns and not comp_obs.empty:
            spread = comp_obs.groupby(["product_id", "competitor_id"])["competitor_sale_price"].agg(["min", "max"])
            spread.columns = ["min_competitor_sale_price", "max_competitor_sale_price"]
            comp_base = comp_base.merge(spread, on=["product_id", "competitor_id"], how="left")

        # days_since_update: MIN (freshest) across observed FPs only
        if "days_since_update" in df.columns and not comp_obs.empty:
            days_agg = (
                comp_obs.groupby(["product_id", "competitor_id"])["days_since_update"]
                .min().rename("days_since_update")
            )
            comp_base = comp_base.merge(days_agg, on=["product_id", "competitor_id"], how="left")

        # Date columns: MAX (most recent) across observed FPs only
        for date_col in ["bf_price_updated_at", "competitor_price_updated_at"]:
            if date_col in df.columns and not comp_obs.empty:
                date_agg = (
                    comp_obs.groupby(["product_id", "competitor_id"])[date_col]
                    .max().rename(date_col)
                )
                # Drop any pre-existing column to avoid merge suffix conflicts
                if date_col in comp_base.columns:
                    comp_base = comp_base.drop(columns=[date_col])
                comp_base = comp_base.merge(date_agg, on=["product_id", "competitor_id"], how="left")
                # Convert NaN → None (Pydantic requires None, not NaN, for nullable strings)
                comp_base[date_col] = comp_base[date_col].where(comp_base[date_col].notna(), None)

        # 5. Merge everything
        result = (
            comp_base
            .merge(product_base, on="product_id", how="left")
            .merge(bf_modal, on="product_id", how="left")
            .merge(comp_fresh_modal, on=["product_id", "competitor_id"], how="left")
            .merge(comp_all_modal, on=["product_id", "competitor_id"], how="left")
        )

        # 6. Apply BF modal price
        if "bf_sale_price_modal" in result.columns:
            result["bf_sale_price"] = result["bf_sale_price_modal"]

        # 7. Apply competitor price: prefer FRESH modal, fallback to ALL-OBS modal
        result["competitor_sale_price"] = result["comp_price_fresh_modal"].fillna(
            result["comp_price_all_modal"]
        )

        # 8. Compute aggregated freshness flags from the pair sets
        pair_keys = list(zip(result["product_id"], result["competitor_id"]))
        result["is_recent_competitor"] = [k in has_fresh_pairs for k in pair_keys]
        result["has_PI"] = [k in has_obs_pairs for k in pair_keys]
        result["is_recent_breadfast"] = result["bf_sale_price"].notna()
        result["prices_recently_updated"] = (
            result["is_recent_breadfast"] & result["is_recent_competitor"]
        )
        result["updated"] = result["prices_recently_updated"]

        # 9. used_product = eligible AND has price AND fresh (matches SQL definition)
        if "eligible_product" in result.columns:
            result["used_product"] = (
                result["eligible_product"].fillna(False).astype(bool)
                & result["has_PI"]
                & result["prices_recently_updated"]
            )

        # 10. Recalculate PI
        result["sale_PI"] = result["bf_sale_price"] / result["competitor_sale_price"]

        # 11. Recompute action_type from aggregated state
        is_mapped = (
            result["is_mapped"].fillna(False).astype(bool)
            if "is_mapped" in result.columns
            else pd.Series([False] * len(result), index=result.index)
        )
        has_price = result["competitor_sale_price"] > 0
        is_fresh = result["is_recent_competitor"].fillna(False).astype(bool)
        sim = (
            pd.to_numeric(result["similarity_score"], errors="coerce")
            if "similarity_score" in result.columns
            else pd.Series([None] * len(result), index=result.index)
        )
        ai_match = sim.fillna(0) >= 0.85

        conditions = [
            ~is_mapped & ~ai_match,             # not mapped, no AI match
            ~is_mapped & ai_match,              # not mapped, AI match available
            is_mapped & ~has_price,             # mapped, no price observation anywhere
            is_mapped & has_price & is_fresh,   # mapped, ≥1 fresh observation
            is_mapped & has_price & ~is_fresh,  # mapped, only stale observations
        ]
        choices = [
            "Needs Mapping",
            "Review AI Match",
            "Needs Price for FP",
            "Complete",
            "Needs Price Update",
        ]
        result["action_type"] = np.select(conditions, choices, default="Needs Mapping")

        # 12. Drop intermediate columns
        result = result.drop(
            columns=["bf_sale_price_modal", "comp_price_fresh_modal", "comp_price_all_modal"],
            errors="ignore",
        )

        return result.reset_index(drop=True)

    def _apply_filters(self, df: pd.DataFrame, filters: dict = None) -> pd.DataFrame:
        # Ignore the passed df — choose source based on fp_names filter
        fp_names = filters.get("fp_names") if filters else None

        if fp_names:
            # FP-scoped mode: filter raw df to selected FPs, then aggregate
            names = [n.strip() for n in fp_names.split(",")]
            scoped = self._df[self._df["fp_name"].isin(names)]
            source = self._aggregate_to_global(scoped)
        else:
            # GLOBAL mode: use pre-computed aggregated df
            source = self._global_df

        if not filters:
            return source

        filtered = source.copy()
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

    # ─── Interface implementations ──────────────────────────────
    # These are identical to MockPricingDataService since they all
    # operate on self._df (a pandas DataFrame).

    def get_all_products(self, filters: dict = None) -> pd.DataFrame:
        return self._apply_filters(self._df, filters)

    @staticmethod
    def _shape_fp_competitor_pi(df: pd.DataFrame) -> dict:
        """Shape a (fp_name, competitor_name, blended_pi, used_count,
        eligible_count) frame into the API payload: a flat cell list with the
        Area parsed from the FP name, plus the sorted competitor list. The
        frontend pivots this into the matrix and the 'most exposed' ranking."""
        import math

        def _f(v):
            if v is None:
                return None
            if isinstance(v, float) and math.isnan(v):
                return None
            return v

        cells = []
        competitors = set()
        tot_used = 0
        tot_est = 0
        for _, r in df.iterrows():
            fp = r["fp_name"]
            comp = r["competitor_name"]
            if not fp or not comp:
                continue
            competitors.add(comp)
            pi = _f(r.get("blended_pi"))
            used = int(_f(r.get("used_count")) or 0)
            est = int(_f(r.get("estimated_count")) or 0)
            elig = int(_f(r.get("eligible_count")) or 0)
            tot_used += used
            tot_est += est
            # FP names are scoped "<Area> FP #<n>"; Area is the prefix.
            area = str(fp).split(" FP #")[0].strip() or "Other"
            cells.append({
                "fp_name": fp,
                "area": area,
                "competitor_name": comp,
                "blended_pi": round(float(pi), 4) if pi is not None else None,
                "used_count": used,
                "estimated_count": est,
                "observed_count": used - est,
                "eligible_count": elig,
                "coverage_pct": round(used / elig * 100, 1) if elig else 0.0,
                # Cell rests entirely on estimates (no fresh-priced product in it).
                "is_estimated": est > 0 and (used - est) == 0,
            })
        return {
            "competitors": sorted(competitors),
            "cells": cells,
            # Share of contributing products that are estimated (0 when fallback off).
            "estimated_pct": round(tot_est / tot_used * 100, 1) if tot_used else 0.0,
        }

    def _fallback_modal_map(self) -> dict:
        """(product_id, competitor_name) → estimate price: modal of the FRESH
        competitor prices over all FPs. A pair with no fresh price anywhere has
        no entry here, so it is never estimated (its stale price surfaces, flagged
        outdated, only in the product FP-matrix). Mirrors the fresh-only modal CTE
        in the DuckDB get_fp_competitor_pi fallback."""
        fresh = self._df[(self._df["competitor_sale_price"] > 0)
                         & (self._df.get("is_recent_competitor", False) == True)]  # noqa: E712

        def _mode(s):
            s = s.dropna()
            if s.empty:
                return None
            vc = s.value_counts()
            return float(min(vc[vc == vc.max()].index))

        return fresh.groupby(["product_id", "competitor_name"])["competitor_sale_price"].apply(_mode).to_dict()

    def get_fp_competitor_pi(self, filters: dict = None, price_fallback: bool = False) -> dict:
        """Quantity-weighted blended PI per (fulfillment point × competitor).

        Same blend as get_blended_pi_by_subcategory (Σ(sale_PI·qty)/Σ(qty) over
        used rows), grouped by fp_name × competitor_name off the FP grain. When
        price_fallback is on, mapped-but-not-fresh cells are filled with the
        per-(product, competitor) modal price and counted as estimated.
        """
        df = self._apply_filters(self._df, filters)
        if df is None or df.empty:
            return {"competitors": [], "cells": []}
        d = df[df["fp_name"].notna() & df["competitor_name"].notna()].copy()
        d["used_eff"] = d["used_product"] == True  # noqa: E712
        d["is_estimated"] = False
        d["pi_eff"] = d["sale_PI"]
        if price_fallback:
            modal = self._fallback_modal_map()
            d["modal_price"] = list(d.set_index(["product_id", "competitor_name"]).index.map(modal))
            fill = (~d["used_eff"]) & (d.get("is_mapped") == True) & (d["eligible_product"] == True) \
                & d["modal_price"].notna() & d["bf_sale_price"].notna()  # noqa: E712
            d.loc[fill, "used_eff"] = True
            d.loc[fill, "is_estimated"] = True
            d.loc[fill, "pi_eff"] = d.loc[fill, "bf_sale_price"] / d.loc[fill, "modal_price"]
        rows = []
        for (fp, comp), g in d.groupby(["fp_name", "competitor_name"]):
            elig = int(g.loc[g["eligible_product"] == True, "product_id"].nunique())
            if elig == 0:
                continue
            u = g[g["used_eff"]]
            qty = u["avg_daily_quantity"].sum()
            pi = (u["pi_eff"] * u["avg_daily_quantity"]).sum() / qty if qty else None
            rows.append({
                "fp_name": fp,
                "competitor_name": comp,
                "blended_pi": pi if (pi is not None and not pd.isna(pi)) else None,
                "used_count": int(u["product_id"].nunique()),
                "estimated_count": int(u.loc[u["is_estimated"], "product_id"].nunique()),
                "eligible_count": elig,
            })
        return self._shape_fp_competitor_pi(pd.DataFrame(rows))

    def get_blended_pi_by_subcategory(self, filters: dict = None, group_by: str = "sub_category") -> pd.DataFrame:
        # group_by is honored by the DuckDB serving path; this pandas fallback
        # returns the subcategory grain regardless.
        # Product-level aggregate — unaffected by the competitor price fallback
        # (a purely FP-grain effect; see get_fp_competitor_pi / get_product_fp_matrix).
        df = self._apply_filters(self._df, filters)
        used = df[df["used_product"] == True]
        if used.empty:
            return pd.DataFrame(columns=[
                "sub_category_name", "blended_pi", "used_product_count",
                "total_revenue", "pi_deviation", "direction",
                "total_product_count", "eligible_product_count", "needs_action_count",
            ])

        grouped = used.groupby("sub_category_name").apply(
            lambda g: pd.Series({
                "blended_pi": round(
                    (g["sale_PI"] * g["avg_daily_quantity"]).sum()
                    / g["avg_daily_quantity"].sum(), 4
                ) if g["avg_daily_quantity"].sum() > 0 else None,
                # Count distinct products (multi-competitor rows inflate count)
                "used_product_count": g["product_id"].nunique(),
                # Revenue is product-level — deduplicate before summing
                "total_revenue": round(
                    g.drop_duplicates("product_id")["total_revenue"].sum(), 2
                ),
                "product_pis": g[["product_name", "sale_PI", "avg_daily_quantity"]].dropna(subset=["sale_PI"]).rename(
                    columns={"avg_daily_quantity": "weight"}
                ).to_dict("records"),
            }),
            include_groups=False,
        ).reset_index()

        # Compute per-subcategory counts — use worst action per product across competitors
        worst_action = self._worst_action_per_product(df)
        unique_all = df.drop_duplicates("product_id").copy()
        unique_all["action_type"] = unique_all["product_id"].map(worst_action)
        all_counts = unique_all.groupby("sub_category_name").apply(
            lambda g: pd.Series({
                "total_product_count": len(g),
                "eligible_product_count": int(g["eligible_product"].sum()),
                "needs_action_count": int((g["eligible_product"] & (g["action_type"] != "Complete")).sum()),
            }),
            include_groups=False,
        ).reset_index()

        grouped = grouped.merge(all_counts, on="sub_category_name", how="left")
        grouped[["total_product_count", "eligible_product_count", "needs_action_count"]] = \
            grouped[["total_product_count", "eligible_product_count", "needs_action_count"]].fillna(0).astype(int)

        grouped["pi_deviation"] = grouped["blended_pi"].apply(
            lambda x: round(x - 1, 4) if pd.notna(x) else None
        )
        grouped["direction"] = grouped["pi_deviation"].apply(pi_direction)

        # Per-competitor blended PI, product PIs, and used counts
        comp_grouped = used.groupby(["sub_category_name", "competitor_name"]).apply(
            lambda g: pd.Series({
                "comp_blended_pi": round(
                    (g["sale_PI"] * g["avg_daily_quantity"]).sum()
                    / g["avg_daily_quantity"].sum(), 4
                ) if g["avg_daily_quantity"].sum() > 0 else None,
                "comp_product_pis": g[["product_name", "sale_PI", "avg_daily_quantity"]].dropna(
                    subset=["sale_PI"]
                ).rename(columns={"avg_daily_quantity": "weight"}).to_dict("records"),
                "comp_used_count": int(g["product_id"].nunique()),
            }),
            include_groups=False,
        ).reset_index()

        # Build dicts per subcategory
        def _build_comp_dict(sub_df, col):
            return dict(zip(sub_df["competitor_name"], sub_df[col]))

        comp_bpi = comp_grouped.groupby("sub_category_name").apply(
            lambda g: _build_comp_dict(g, "comp_blended_pi")
        )
        comp_pis = comp_grouped.groupby("sub_category_name").apply(
            lambda g: _build_comp_dict(g, "comp_product_pis")
        )
        comp_used = comp_grouped.groupby("sub_category_name").apply(
            lambda g: _build_comp_dict(g, "comp_used_count")
        )
        grouped["competitor_blended_pis"] = grouped["sub_category_name"].map(comp_bpi).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        grouped["competitor_product_pis"] = grouped["sub_category_name"].map(comp_pis).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        grouped["competitor_used_counts"] = grouped["sub_category_name"].map(comp_used).apply(
            lambda x: x if isinstance(x, dict) else {}
        )

        # Per-competitor mapping coverage
        # Total Active = ALL products in subcategory (SAME for all competitors)
        # Mapped = products mapped to THIS specific competitor (DIFFERENT per competitor)

        # Calculate total active products per subcategory (same for all competitors)
        total_active_per_subcat = df.groupby("sub_category_name")["product_id"].nunique().to_dict()

        # Get all (subcategory, competitor) combinations
        all_combinations = df[["sub_category_name", "competitor_name"]].drop_duplicates()

        # Calculate mapped products per (subcategory, competitor) - only where is_mapped=True
        mapped_counts = df[df["is_mapped"] == True].groupby(
            ["sub_category_name", "competitor_name"]
        )["product_id"].nunique().reset_index(name="comp_mapped_count")

        # Merge to include all combinations (even those with 0 mapped products)
        comp_mapping = all_combinations.merge(
            mapped_counts,
            on=["sub_category_name", "competitor_name"],
            how="left"
        )

        # Fill NaN (competitors with 0 mapped products) with 0
        comp_mapping["comp_mapped_count"] = comp_mapping["comp_mapped_count"].fillna(0).astype(int)

        # Add total active count (same for all competitors in a subcategory)
        comp_mapping["comp_eligible_count"] = comp_mapping["sub_category_name"].map(total_active_per_subcat)

        comp_eligible_cnts = comp_mapping.groupby("sub_category_name").apply(
            lambda g: _build_comp_dict(g, "comp_eligible_count")
        )
        comp_mapped_cnts = comp_mapping.groupby("sub_category_name").apply(
            lambda g: _build_comp_dict(g, "comp_mapped_count")
        )
        grouped["competitor_eligible_counts"] = grouped["sub_category_name"].map(comp_eligible_cnts).apply(
            lambda x: x if isinstance(x, dict) else {}
        )
        grouped["competitor_mapped_counts"] = grouped["sub_category_name"].map(comp_mapped_cnts).apply(
            lambda x: x if isinstance(x, dict) else {}
        )

        # Per-competitor needs_action counts per subcategory
        eligible_df = df[df["eligible_product"] == True]
        if not eligible_df.empty and "competitor_name" in eligible_df.columns:
            action_by_comp = eligible_df.groupby(["sub_category_name", "competitor_name"]).apply(
                lambda g: int((g["action_type"] != "Complete").sum()),
                include_groups=False,
            ).reset_index(name="comp_needs_action")
            comp_action_cnts = action_by_comp.groupby("sub_category_name").apply(
                lambda g: dict(zip(g["competitor_name"], g["comp_needs_action"]))
            )
            grouped["competitor_needs_action_counts"] = grouped["sub_category_name"].map(comp_action_cnts).apply(
                lambda x: x if isinstance(x, dict) else {}
            )
        else:
            grouped["competitor_needs_action_counts"] = [{}] * len(grouped)

        return grouped.sort_values("blended_pi", ascending=False).reset_index(drop=True)

    def get_coverage_funnel(self, filters: dict = None) -> dict:
        df = self._apply_filters(self._df, filters)
        # Use distinct product counts (multi-competitor rows inflate totals)
        unique = df.drop_duplicates("product_id")
        total = len(unique)
        if total == 0:
            return {"mapping_funnel": [], "coverage_funnel": []}

        all_mapped = int(df[df["has_PI"]]["product_id"].nunique())
        all_updated = int(df[df["has_PI"] & df["updated"]]["product_id"].nunique())
        eligible = int(unique["eligible_product"].sum())
        eligible_mapped = int(df[df["eligible_product"] & df["has_PI"]]["product_id"].nunique())
        used = int(df[df["used_product"]]["product_id"].nunique())

        def pct(n):
            return round(n / total * 100, 1) if total else 0

        return {
            "mapping_funnel": [
                {"name": "All Products", "count": total, "pct": 100.0},
                {"name": "Mapped Products", "count": all_mapped, "pct": pct(all_mapped)},
                {"name": "Recently Updated", "count": all_updated, "pct": pct(all_updated)},
            ],
            "coverage_funnel": [
                {"name": "All Products", "count": total, "pct": 100.0},
                {"name": "Eligible Products", "count": eligible, "pct": pct(eligible)},
                {"name": "Eligible Mapped", "count": eligible_mapped, "pct": pct(eligible_mapped)},
                {"name": "Used Products", "count": used, "pct": pct(used)},
            ],
        }

    def get_action_summary(self, filters: dict = None) -> dict:
        df = self._apply_filters(self._df, filters)
        worst_action = self._worst_action_per_product(df)
        unique = df.drop_duplicates("product_id").copy()
        unique["action_type"] = unique["product_id"].map(worst_action)
        eligible = unique[unique["eligible_product"] == True]
        needs_action = eligible[eligible["action_type"] != "Complete"]

        return {
            "total_needs_action": len(needs_action),
            "needs_mapping": int((eligible["action_type"] == "Needs Mapping").sum()),
            "review_match": int((eligible["action_type"] == "Review Match").sum()),
            "needs_price_update": int((eligible["action_type"] == "Needs Price Update").sum()),
        }

    def get_kpi_summary(self, filters: dict = None) -> dict:
        df = self._apply_filters(self._df, filters)
        used = df[df["used_product"] == True]
        worst_action = self._worst_action_per_product(df)
        unique = df.drop_duplicates("product_id").copy()
        unique["action_type"] = unique["product_id"].map(worst_action)
        eligible_unique = unique[unique["eligible_product"] == True]
        needs_action = eligible_unique[eligible_unique["action_type"] != "Complete"]

        blended = None
        if not used.empty and used["avg_daily_quantity"].sum() > 0:
            blended = round(
                (used["sale_PI"] * used["avg_daily_quantity"]).sum()
                / used["avg_daily_quantity"].sum(), 4
            )

        return {
            "total_products": int(df["product_id"].nunique()),
            "eligible_products": int(eligible_unique["product_id"].nunique()),
            "used_products": int(used["product_id"].nunique()),
            "avg_blended_pi": blended,
            "needs_action": len(needs_action),
        }

    def get_action_breakdown(self, filters: dict = None) -> list[dict]:
        df = self._apply_filters(self._df, filters)
        worst_action = self._worst_action_per_product(df)
        unique = df.drop_duplicates("product_id").copy()
        unique["action_type"] = unique["product_id"].map(worst_action)
        eligible = unique[unique["eligible_product"] == True]
        needs_action = eligible[eligible["action_type"] != "Complete"]

        if needs_action.empty:
            return []

        grouped = needs_action.groupby(["commercial_category_name", "action_type"]).size().reset_index(name="count")
        pivot = grouped.pivot_table(
            index="commercial_category_name", columns="action_type", values="count", fill_value=0
        ).reset_index()

        result = []
        for _, row in pivot.iterrows():
            nm = int(row.get("Needs Mapping", 0))
            ra = int(row.get("Review Match", 0))
            npu = int(row.get("Needs Price Update", 0))
            result.append({
                "category": row["commercial_category_name"],
                "needs_mapping": nm,
                "review_match": ra,
                "needs_price_update": npu,
                "total": nm + ra + npu,
            })

        return sorted(result, key=lambda x: x["total"], reverse=True)

    def get_worklist(
        self, filters: dict = None, page: int = 1, page_size: int = 50
    ) -> dict:
        df = self._apply_filters(self._df, filters)
        eligible = df[df["eligible_product"] == True]
        needs_action = eligible[eligible["action_type"] != "Complete"].copy()

        needs_action["tier_order"] = needs_action["global_tier"].map(TIER_ORDER)
        needs_action = needs_action.sort_values(
            ["tier_order", "total_revenue"], ascending=[False, False]
        )

        total_count = len(needs_action)
        start = (page - 1) * page_size
        page_df = needs_action.iloc[start:start + page_size]

        items = []
        for _, row in page_df.iterrows():
            items.append({
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "brand_name": row["brand_name"],
                "sub_category_name": row["sub_category_name"],
                "global_tier": row["global_tier"],
                "tier_order": int(row["tier_order"]),
                "action_type": row["action_type"],
                "action_symbol": ACTION_SYMBOLS.get(row["action_type"], ""),
                "competitor_name": row["competitor_name"] if pd.notna(row.get("competitor_name")) else None,
                "similarity_score": row["similarity_score"] if pd.notna(row["similarity_score"]) else None,
                "bf_sale_price": float(row["bf_sale_price"]),
                "competitor_sale_price": float(row["competitor_sale_price"]) if pd.notna(row.get("competitor_sale_price")) else None,
                "days_since_update": int(row["days_since_update"]) if pd.notna(row["days_since_update"]) else None,
                "total_revenue": float(row["total_revenue"]),
                "competitor_product_name": row["competitor_product_name"] if pd.notna(row.get("competitor_product_name")) else None,
                "match_potential_product_name": row["match_potential_product_name"] if pd.notna(row.get("match_potential_product_name")) else None,
                "eligible_product": bool(row["eligible_product"]),
                "used_product": bool(row["used_product"]),
            })

        return {"items": items, "total_count": total_count}

    def get_match_reviews(
        self, filters: dict = None, page: int = 1, page_size: int = 20
    ) -> dict:
        df = self._apply_filters(self._df, filters)
        matches = df[
            (df["match_potential"] == True) & (df["has_PI"] == False)
        ].copy()
        matches = matches.sort_values("similarity_score", ascending=False)

        total_count = len(matches)
        start = (page - 1) * page_size
        page_df = matches.iloc[start:start + page_size]

        items = []
        for _, row in page_df.iterrows():
            items.append({
                "product_id": row["product_id"],
                "bf_product_name": row["product_name"],
                "bf_brand": row["brand_name"],
                "bf_price": float(row["bf_sale_price"]),
                "competitor_name": row["competitor_name"] if pd.notna(row.get("competitor_name")) else None,
                "suggested_competitor_name": row["match_potential_product_name"] if pd.notna(row.get("match_potential_product_name")) else row["product_name"],
                "similarity_score": float(row["similarity_score"]) if pd.notna(row["similarity_score"]) else 0,
                "estimated_competitor_price": float(row["competitor_sale_price"]) if pd.notna(row.get("competitor_sale_price")) else float(row["bf_sale_price"] * 1.05),
            })

        return {"items": items, "total_count": total_count}

    def get_staleness_heatmap(self, filters: dict = None) -> dict:
        df = self._apply_filters(self._df, filters)
        mapped = df[df["has_PI"] == True].copy()

        if mapped.empty:
            return {"cells": [], "subcategories": [], "buckets": []}

        buckets = ["0-7d", "7-14d", "14-21d", "21-30d", "30d+"]

        def bucket_days(d):
            if d is None or pd.isna(d):
                return "30d+"
            d = int(d)
            if d <= 7:
                return "0-7d"
            if d <= 14:
                return "7-14d"
            if d <= 21:
                return "14-21d"
            if d <= 30:
                return "21-30d"
            return "30d+"

        mapped["bucket"] = mapped["days_since_update"].apply(bucket_days)

        top_subcats = (
            mapped.groupby("sub_category_name").size()
            .nlargest(25).index.tolist()
        )
        mapped = mapped[mapped["sub_category_name"].isin(top_subcats)]

        grouped = (
            mapped.groupby(["sub_category_name", "bucket"]).size()
            .reset_index(name="count")
        )

        cells = [
            {"sub_category_name": row["sub_category_name"],
             "bucket": row["bucket"],
             "count": int(row["count"])}
            for _, row in grouped.iterrows()
        ]

        return {
            "cells": cells,
            "subcategories": sorted(top_subcats),
            "buckets": buckets,
        }

    def get_executive_summary(self) -> dict:
        kpis = self.get_kpi_summary()
        blended = self.get_blended_pi_by_subcategory()

        top_5_cheapest = blended.nlargest(5, "blended_pi")[
            ["sub_category_name", "blended_pi", "used_product_count"]
        ].to_dict("records") if not blended.empty else []

        top_5_expensive = blended.nsmallest(5, "blended_pi")[
            ["sub_category_name", "blended_pi", "used_product_count"]
        ].to_dict("records") if not blended.empty else []

        coverage_pct = round(
            kpis["used_products"] / kpis["eligible_products"] * 100, 1
        ) if kpis["eligible_products"] > 0 else 0

        return {
            "overall_blended_pi": kpis["avg_blended_pi"],
            "coverage_pct": coverage_pct,
            "total_products": kpis["total_products"],
            "eligible_products": kpis["eligible_products"],
            "used_products": kpis["used_products"],
            "needs_action": kpis["needs_action"],
            "top_5_cheapest": top_5_cheapest,
            "top_5_expensive": top_5_expensive,
            # Counts subcategories that actually have a price index, which is
            # what this field has always meant. get_blended_pi_by_subcategory now
            # also returns fully-unmatched groups (so the Commercial table can
            # flag them rather than hide them), so a plain len() would silently
            # redefine this from 167 to 206.
            "subcategory_count": int(blended["blended_pi"].notna().sum())
            if not blended.empty else 0,
        }

    def get_executive_dashboard(self, filters: dict = None) -> dict:
        # Product-level aggregate — unaffected by the competitor price fallback.
        df = self._apply_filters(self._df, filters)

        # ─── KPIs ────────────────────────────────────────────────────
        unique = df.drop_duplicates("product_id").copy()
        worst_action = self._worst_action_per_product(df)
        unique["_wa"] = unique["product_id"].map(worst_action).fillna("Complete")
        eligible_unique = unique[unique["eligible_product"] == True]

        total_products = int(len(unique))
        eligible_count = int(len(eligible_unique))
        eligible_df = df[df["eligible_product"] == True]
        mapped_ids = set(eligible_df[eligible_df["sale_PI"].notna()]["product_id"])
        mapped_count = int(len(mapped_ids))
        mapped_pct = round(mapped_count / eligible_count * 100, 1) if eligible_count > 0 else 0.0

        needs_action_df = eligible_unique[eligible_unique["_wa"] != "Complete"]
        nm = int((needs_action_df["_wa"] == "Needs Mapping").sum())
        rm = int((needs_action_df["_wa"] == "Review Match").sum())
        npu = int((needs_action_df["_wa"] == "Needs Price Update").sum())

        used = df[df["used_product"] == True]
        blended_pi = None
        if not used.empty and used["avg_daily_quantity"].sum() > 0:
            blended_pi = round(
                (used["sale_PI"] * used["avg_daily_quantity"]).sum()
                / used["avg_daily_quantity"].sum(), 4
            )

        kpis = {
            "blended_pi": blended_pi,
            "total_products": total_products,
            "eligible_products": eligible_count,
            "eligible_pct": round(eligible_count / total_products * 100, 1) if total_products > 0 else 0.0,
            "mapped_products": mapped_count,
            "mapped_pct": mapped_pct,
            "needs_action": int(len(needs_action_df)),
            "needs_mapping": nm,
            "review_match": rm,
            "needs_price_update": npu,
        }

        # ─── Per-Competitor PI ────────────────────────────────────────
        # Mapping Coverage = mapped (per competitor) / total active (same for all competitors)
        # - total_active: ALL unique products in dataset (SAME for all competitors)
        # - mapped_products: products with is_mapped=True for THIS competitor (DIFFERENT per competitor)
        total_active_products = int(df["product_id"].nunique())
        # Eligible (top-80% revenue head) count — denominator for Utilization (used/eligible)
        eligible_active_products = int(df.drop_duplicates("product_id")["eligible_product"].fillna(False).astype(bool).sum())

        competitor_pi = []
        if "competitor_name" in df.columns:
            for comp, grp in df.groupby("competitor_name"):
                if pd.isna(comp):
                    continue
                used_grp = grp[grp["used_product"] == True]
                # Mapped count: products with is_mapped=True for THIS competitor (different per competitor)
                mapped_cnt = int(grp[grp["is_mapped"] == True]["product_id"].nunique())
                bpi = None
                if not used_grp.empty:
                    qty_sum = used_grp["avg_daily_quantity"].sum()
                    if qty_sum > 0:
                        bpi = round(
                            (used_grp["sale_PI"] * used_grp["avg_daily_quantity"]).sum() / qty_sum, 4
                        )
                used_cnt = int(grp[grp["used_product"] == True]["product_id"].nunique())
                competitor_pi.append({
                    "competitor_name": str(comp),
                    "blended_pi": bpi,
                    "pi_deviation": round(bpi - 1, 4) if bpi is not None else None,
                    "mapped_products": mapped_cnt,
                    "eligible_products": eligible_active_products,  # eligible head → Utilization = used/eligible
                    "used_products": used_cnt,
                })
            competitor_pi.sort(key=lambda x: (x["blended_pi"] or 0), reverse=True)

        # ─── Mapping Progress by Competitor ───────────────────────────
        mapping_progress = []
        if "competitor_name" in df.columns and "classification" in df.columns:
            for comp, grp in df.groupby("competitor_name"):
                if pd.isna(comp):
                    continue
                # mapped/not-mapped split driven by is_mapped (same definition as
                # Blended PI by competitor), NOT the classification string — the two
                # disagree in the source data and is_mapped is the source of truth.
                # PL/Not-PL from the classification token; not-mapped reasons counted
                # only among is_mapped=False. So mapped_not_pl+mapped_pl == mapped_products
                # and the donut is internally consistent and matches that table.
                gu = grp.drop_duplicates("product_id")
                cls = gu["classification"].fillna("")
                is_m = gu["is_mapped"] == True
                not_m = ~is_m
                not_pl = cls.str.contains("Not PL", na=False)
                mapped_not_pl = int((is_m & not_pl).sum())
                mapped_pl = int((is_m & ~not_pl).sum())
                pot_not_pl = int((not_m & (cls == "Not Mapped - Not PL - Potential Match")).sum())
                pot_pl = int((not_m & (cls == "Not Mapped - PL - Potential Match")).sum())
                no_pot_not_pl = int((not_m & (cls == "Not Mapped - Not PL - No Potential Match")).sum())
                no_pot_pl = int((not_m & (cls == "Not Mapped - PL - No Potential Match")).sum())
                no_match_not_pl = int((not_m & (cls == "Not Mapped - Not PL - No Match")).sum())
                no_match_pl = int((not_m & (cls == "Not Mapped - PL - No Match")).sum())
                total = (mapped_not_pl + mapped_pl + pot_not_pl + pot_pl
                         + no_pot_not_pl + no_pot_pl + no_match_not_pl + no_match_pl)
                mapped_total = mapped_not_pl + mapped_pl
                potential_total = pot_not_pl + pot_pl
                # No-Match (master-data decided unmappable) excluded from reach denominator
                reachable = total - (no_match_not_pl + no_match_pl)
                mapped_products = mapped_total  # = is_mapped count, by construction above
                mapping_progress.append({
                    "competitor_name": str(comp),
                    "mapped_not_pl": mapped_not_pl,
                    "mapped_pl": mapped_pl,
                    "potential_not_pl": pot_not_pl,
                    "potential_pl": pot_pl,
                    "no_potential_not_pl": no_pot_not_pl,
                    "no_potential_pl": no_pot_pl,
                    "no_match_not_pl": no_match_not_pl,
                    "no_match_pl": no_match_pl,
                    "total": total,
                    "mapped_products": mapped_products,
                    "mapped_pct": round(mapped_products / total * 100, 1) if total > 0 else 0.0,
                    "potential_reach_pct": round((mapped_total + potential_total) / reachable * 100, 1) if reachable > 0 else 0.0,
                })
            mapping_progress.sort(key=lambda x: x["mapped_pct"], reverse=True)

        # ─── Overall Classification Breakdown ─────────────────────────
        classification_breakdown = {
            "mapped_not_pl": 0, "mapped_pl": 0,
            "not_mapped_not_pl_potential": 0, "not_mapped_not_pl_no_potential": 0,
            "not_mapped_pl_potential": 0, "not_mapped_pl_no_potential": 0,
            "not_mapped_not_pl_no_match": 0, "not_mapped_pl_no_match": 0,
        }
        if "classification" in df.columns:
            counts = df["classification"].value_counts().to_dict()
            classification_breakdown = {
                "mapped_not_pl": int(counts.get("Mapped - Not PL", 0)),
                "mapped_pl": int(counts.get("Mapped - PL", 0)),
                "not_mapped_not_pl_potential": int(counts.get("Not Mapped - Not PL - Potential Match", 0)),
                "not_mapped_not_pl_no_potential": int(counts.get("Not Mapped - Not PL - No Potential Match", 0)),
                "not_mapped_pl_potential": int(counts.get("Not Mapped - PL - Potential Match", 0)),
                "not_mapped_pl_no_potential": int(counts.get("Not Mapped - PL - No Potential Match", 0)),
                "not_mapped_not_pl_no_match": int(counts.get("Not Mapped - Not PL - No Match", 0)),
                "not_mapped_pl_no_match": int(counts.get("Not Mapped - PL - No Match", 0)),
            }

        return {
            "kpis": kpis,
            "competitor_pi": competitor_pi,
            "mapping_progress": mapping_progress,
            "classification_breakdown": classification_breakdown,
        }

    def get_pi_trend(self) -> list[dict]:
        return []  # No historical data available

    def get_coverage_trend(self) -> list[dict]:
        return []  # No historical data available

    def get_category_performance(self, filters: dict = None) -> list[dict]:
        df = self._apply_filters(self._df, filters)
        used = df[df["used_product"] == True]

        if used.empty:
            return []

        grouped = used.groupby("commercial_category_name").apply(
            lambda g: pd.Series({
                "blended_pi": round(
                    (g["sale_PI"] * g["avg_daily_quantity"]).sum()
                    / g["avg_daily_quantity"].sum(), 4
                ) if g["avg_daily_quantity"].sum() > 0 else None,
                "product_count": g["product_id"].nunique(),
            }),
            include_groups=False,
        ).reset_index()

        grouped["pi_deviation"] = grouped["blended_pi"].apply(
            lambda x: round(x - 1, 4) if pd.notna(x) else None
        )

        result = []
        for _, row in grouped.iterrows():
            result.append({
                "category_name": row["commercial_category_name"],
                "blended_pi": float(row["blended_pi"]) if pd.notna(row["blended_pi"]) else None,
                "pi_deviation": float(row["pi_deviation"]) if pd.notna(row["pi_deviation"]) else None,
                "product_count": int(row["product_count"]),
            })

        return sorted(result, key=lambda x: x["blended_pi"] or 0, reverse=True)

    def get_week_over_week(self) -> list[dict]:
        return []  # No historical data available

    def get_filter_options(self, main_category: Optional[str] = None) -> dict:
        df = self._df

        if main_category:
            sub_cats = sorted(
                [v for v in df[df["commercial_category_name"] == main_category]["sub_category_name"].unique().tolist() if v is not None]
            )
        else:
            sub_cats = sorted([v for v in df["sub_category_name"].unique().tolist() if v is not None])

        return {
            "main_categories": sorted([v for v in df["commercial_category_name"].unique().tolist() if v is not None]),
            "sub_categories": sub_cats,
            "global_tiers": ["Top+", "Top", "Medium", "Low", "Very Low"],
            "subcat_tiers": ["Top+", "Top", "Medium", "Low", "Very Low"],
            "action_types": ["Needs Mapping", "Review Match", "Needs Price Update", "Complete"],
            "brands": sorted([v for v in df["brand_name"].unique().tolist() if v is not None]),
            "competitors": sorted([v for v in df["competitor_name"].unique().tolist() if v is not None]) if "competitor_name" in df.columns else [],
        }

    def get_fp_options(self) -> list[str]:
        """Return sorted list of distinct FP names from loaded data."""
        return sorted(self._df["fp_name"].dropna().unique().tolist())

    # ─── Competitor Products tab ─────────────────────────────────

    def _load_competitor_products(self) -> pd.DataFrame:
        import time
        query = COMPETITOR_BQ_QUERY.format(
            project=self._project,
            dataset=self._dataset,
            table=app_settings.BQ_COMPETITOR_TABLE,
        )
        print("[BigQuery] Loading competitor products...")
        t0 = time.time()
        job = self._client.query(query)
        rows = job.result()
        # Storage Read API (Arrow). date_as_object=True keeps DATE columns as
        # datetime.date — downstream timeline grouping and .isoformat() depend
        # on that exact dtype. Fall back to REST iterator if unavailable.
        try:
            arrow_tbl = rows.to_arrow(create_bqstorage_client=True)
        except Exception as exc:
            print(f"[BigQuery] Storage API unavailable ({exc}); using REST fallback")
            # Fresh iterator from the completed job — `rows` may already be
            # partially consumed, and a started RowIterator cannot be re-read.
            # create_bqstorage_client=False forces pure REST; the default
            # (True) would re-attempt the Storage API that just failed.
            arrow_tbl = job.result().to_arrow(create_bqstorage_client=False)
        df = arrow_tbl.to_pandas(date_as_object=True)
        del arrow_tbl
        print(f"[BigQuery] Competitor products: {len(df)} rows in {time.time() - t0:.1f}s")

        if df.empty:
            return df

        for col in ["competitor_sale_price",
                     "min_competitor_sale_price", "max_competitor_sale_price",
                     "bf_sale_price", "sale_PI", "similarity_score"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        for col in ["has_PI", "is_recent_competitor", "is_recent_breadfast", "match_potential"]:
            if col in df.columns:
                df[col] = df[col].fillna(False).astype(bool)

        df = self._derive_competitor_date_cols(df)
        return df.reset_index(drop=True)

    @staticmethod
    def _derive_competitor_date_cols(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize the competitor date columns and (re)build the derived
        `*_date` (datetime.date) + `days_since_crawl` columns.

        Idempotent and Parquet-round-trip-safe: accepts the raw date columns as
        datetime.date, datetime64, or ISO strings, and always leaves
        `competitor_last_updated_day` / `bf_last_updated_day` as ISO strings with
        matching `*_date` object columns (datetime.date) that downstream timeline
        grouping and `.isoformat()` calls depend on. `days_since_crawl` is
        recomputed relative to *today*, so it stays accurate across reloads.
        """
        now_ts = pd.Timestamp(datetime.now().date())
        for col in ["competitor_last_updated_day", "bf_last_updated_day"]:
            if col in df.columns:
                parsed = pd.to_datetime(df[col], errors="coerce")
                # datetime.date objects (object dtype) — matches the BQ-load dtype
                df[f"{col}_date"] = parsed.dt.date.where(parsed.notna(), None)
                iso = parsed.dt.strftime("%Y-%m-%d")
                df[col] = iso.where(parsed.notna(), None)

        if "competitor_last_updated_day_date" in df.columns:
            cdt = pd.to_datetime(df["competitor_last_updated_day_date"], errors="coerce")
            days = (now_ts - cdt).dt.days
            df["days_since_crawl"] = days.astype("object").where(days.notna(), None)
        else:
            df["days_since_crawl"] = None
        return df

    def _apply_competitor_filters(self, df: pd.DataFrame, filters: dict = None) -> pd.DataFrame:
        if not filters:
            return df
        f = df.copy()
        if filters.get("competitor"):
            f = self._multi_match(f, "competitor_name", filters["competitor"])
        if filters.get("category_level_1"):
            f = self._multi_match(f, "category_level_1", filters["category_level_1"])
        if filters.get("category_level_2"):
            f = self._multi_match(f, "category_level_2", filters["category_level_2"])
        if filters.get("category_level_3"):
            f = self._multi_match(f, "category_level_3", filters["category_level_3"])
        if filters.get("mapping_status"):
            status = filters["mapping_status"]
            if status == "Mapped":
                f = f[f["has_PI"] == True]
            elif status == "Unmapped":
                f = f[f["has_PI"] == False]
            elif status == "AI Match":
                f = f[(f["has_PI"] == False) & (f["match_potential"] == True)]
        if filters.get("freshness"):
            if filters["freshness"] == "Fresh":
                f = f[f["is_recent_competitor"] == True]
            elif filters["freshness"] == "Stale":
                f = f[f["is_recent_competitor"] == False]
        # Date range filters — BF date keeps nulls (unmatched competitor products)
        if filters.get("bf_date_from") and "bf_last_updated_day_date" in f.columns:
            d = pd.to_datetime(filters["bf_date_from"]).date()
            f = f[f["bf_last_updated_day_date"].isna() | (f["bf_last_updated_day_date"] >= d)]
        if filters.get("bf_date_to") and "bf_last_updated_day_date" in f.columns:
            d = pd.to_datetime(filters["bf_date_to"]).date()
            f = f[f["bf_last_updated_day_date"].isna() | (f["bf_last_updated_day_date"] <= d)]
        if filters.get("competitor_date_from") and "competitor_last_updated_day_date" in f.columns:
            d = pd.to_datetime(filters["competitor_date_from"]).date()
            f = f[f["competitor_last_updated_day_date"] >= d]
        if filters.get("competitor_date_to") and "competitor_last_updated_day_date" in f.columns:
            d = pd.to_datetime(filters["competitor_date_to"]).date()
            f = f[f["competitor_last_updated_day_date"] <= d]
        return f

    def get_competitor_products_kpis(self, filters: dict = None) -> dict:
        df = self._apply_competitor_filters(self._competitor_df, filters)
        if df.empty:
            return {"total_crawled": 0, "mapped": 0, "mapping_rate": 0, "fresh": 0}
        total = int(df["competitor_product_id"].nunique())
        mapped_bf = int(df[df["product_id"].notna()]["product_id"].nunique())
        matched_df = df[df["product_id"].notna()]
        mapped_competitor = int(matched_df["competitor_product_id"].nunique())
        fresh = int(df[df["is_recent_competitor"] == True]["competitor_product_id"].nunique())
        return {
            "total_crawled": total,
            "mapped_bf": mapped_bf,
            "mapped_competitor": mapped_competitor,
            "mapping_rate": round(mapped_competitor / total * 100, 1) if total > 0 else 0,
            "fresh": fresh,
        }

    def get_competitor_crawl_timeline(self, filters: dict = None) -> list[dict]:
        df = self._apply_competitor_filters(self._competitor_df, filters)
        if df.empty or "competitor_last_updated_day_date" not in df.columns:
            return []

        now = datetime.now().date()
        cutoff = now - pd.Timedelta(days=30)
        df = df[df["competitor_last_updated_day_date"] >= cutoff]

        if df.empty:
            return []

        grouped = df.groupby(
            [df["competitor_last_updated_day_date"], "competitor_name"]
        )["competitor_product_id"].nunique().reset_index(name="count")

        result = []
        for _, row in grouped.iterrows():
            result.append({
                "date": row["competitor_last_updated_day_date"].isoformat() if pd.notna(row["competitor_last_updated_day_date"]) else None,
                "competitor_name": row["competitor_name"],
                "count": int(row["count"]),
            })
        return sorted(result, key=lambda x: x["date"] or "")

    def _category_group_metrics(self, grp: pd.DataFrame) -> dict:
        total = int(grp["competitor_product_id"].nunique())
        matched = grp[grp["product_id"].notna()]
        mapped_bf = int(matched["product_id"].nunique())
        mapped_comp = int(matched["competitor_product_id"].nunique())
        unmapped = total - mapped_comp
        ai = int(grp[(grp["has_PI"] == False) & (grp["match_potential"] == True)]["competitor_product_id"].nunique())
        avg_price = grp["competitor_sale_price"].dropna().mean()
        return {
            "total": total,
            "mapped_bf": mapped_bf,
            "mapped_competitor": mapped_comp,
            "unmapped": unmapped,
            "mapping_pct": round(mapped_comp / total * 100, 1) if total > 0 else 0,
            "ai_match": ai,
            "avg_competitor_price": round(float(avg_price), 2) if pd.notna(avg_price) else None,
        }

    def get_competitor_category_breakdown(self, filters: dict = None) -> list[dict]:
        df = self._apply_competitor_filters(self._competitor_df, filters)
        if df.empty:
            return []

        levels = [
            ("competitor", ["competitor_name"]),
            ("l1", ["competitor_name", "category_level_1"]),
            ("l2", ["competitor_name", "category_level_1", "category_level_2"]),
            ("l3", ["competitor_name", "category_level_1", "category_level_2", "category_level_3"]),
        ]
        result = []
        for level, cols in levels:
            for keys, grp in df.groupby(cols):
                if not isinstance(keys, tuple):
                    keys = (keys,)
                if any(pd.isna(k) for k in keys):
                    keys = tuple("Other" if pd.isna(k) else k for k in keys)
                metrics = self._category_group_metrics(grp)
                row = {
                    "level": level,
                    "competitor_name": str(keys[0]),
                    "category_level_1": str(keys[1]) if len(keys) > 1 else None,
                    "category_level_2": str(keys[2]) if len(keys) > 2 else None,
                    "category_level_3": str(keys[3]) if len(keys) > 3 else None,
                    **metrics,
                }
                result.append(row)
        return result

    def get_competitor_mapping_summary(self, filters: dict = None) -> list[dict]:
        df = self._apply_competitor_filters(self._competitor_df, filters)
        if df.empty:
            return []

        result = []
        for comp, grp in df.groupby("competitor_name"):
            if pd.isna(comp):
                continue
            total = int(grp["competitor_product_id"].nunique())
            mapped_bf = int(grp[grp["product_id"].notna()]["product_id"].nunique())
            matched_grp = grp[grp["product_id"].notna()]
            mapped_competitor = int(matched_grp["competitor_product_id"].nunique())
            unmapped = total - mapped_competitor
            ai_match = int(grp[(grp["has_PI"] == False) & (grp["match_potential"] == True)]["competitor_product_id"].nunique())
            fresh = int(grp[grp["is_recent_competitor"] == True]["competitor_product_id"].nunique())
            stale = total - fresh
            avg_age = grp["days_since_crawl"].dropna().mean()
            result.append({
                "competitor_name": str(comp),
                "total": total,
                "mapped_bf": mapped_bf,
                "mapped_competitor": mapped_competitor,
                "unmapped": unmapped,
                "mapping_pct": round(mapped_competitor / total * 100, 1) if total > 0 else 0,
                "with_ai_match": ai_match,
                "fresh": fresh,
                "stale": stale,
                "avg_crawl_age": round(float(avg_age), 1) if pd.notna(avg_age) else None,
            })
        return sorted(result, key=lambda x: x["total"], reverse=True)

    def get_competitor_products_list(
        self, filters: dict = None, page: int = 1, page_size: int = 50,
        search: str = None, sort_by: str = None, sort_dir: str = "desc",
    ) -> dict:
        df = self._apply_competitor_filters(self._competitor_df, filters)

        if search:
            q = search.lower()
            mask = (
                df["competitor_product_name"].str.lower().str.contains(q, na=False) |
                df["bf_product_name"].str.lower().str.contains(q, na=False)
            )
            df = df[mask]

        sortable = {"competitor_sale_price", "days_since_crawl", "sale_PI",
                     "competitor_name", "competitor_product_name", "category_level_1"}
        if sort_by and sort_by in sortable and sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=(sort_dir == "asc"), na_position="last")
        else:
            df = df.sort_values("days_since_crawl", ascending=True, na_position="last")

        total = len(df)
        page_df = df.iloc[(page - 1) * page_size: page * page_size]

        items = []
        for _, row in page_df.iterrows():
            items.append({
                "competitor_name": row["competitor_name"] if pd.notna(row.get("competitor_name")) else None,
                "competitor_product_name": row["competitor_product_name"] if pd.notna(row.get("competitor_product_name")) else None,
                "competitor_product_id": str(row["competitor_product_id"]) if pd.notna(row.get("competitor_product_id")) else None,
                "category_level_1": row["category_level_1"] if pd.notna(row.get("category_level_1")) else None,
                "category_level_2": row["category_level_2"] if pd.notna(row.get("category_level_2")) else None,
                "category_level_3": row["category_level_3"] if pd.notna(row.get("category_level_3")) else None,
                "competitor_sale_price": float(row["competitor_sale_price"]) if pd.notna(row.get("competitor_sale_price")) else None,
                "last_crawled": row["competitor_last_updated_day"] if pd.notna(row.get("competitor_last_updated_day")) else None,
                "days_since_crawl": int(row["days_since_crawl"]) if pd.notna(row.get("days_since_crawl")) else None,
                "is_recent": bool(row["is_recent_competitor"]) if pd.notna(row.get("is_recent_competitor")) else False,
                "bf_product_name": row["bf_product_name"] if pd.notna(row.get("bf_product_name")) else None,
                "bf_sale_price": float(row["bf_sale_price"]) if pd.notna(row.get("bf_sale_price")) else None,
                "sale_PI": float(row["sale_PI"]) if pd.notna(row.get("sale_PI")) else None,
                "has_PI": bool(row["has_PI"]),
                "classification": row["classification"] if pd.notna(row.get("classification")) else None,
                "match_potential": bool(row["match_potential"]),
                "similarity_score": float(row["similarity_score"]) if pd.notna(row.get("similarity_score")) else None,
                "match_potential_product_name": row["match_potential_product_name"] if pd.notna(row.get("match_potential_product_name")) else None,
            })

        # Collect filter options for this tab
        # Competitors always from full dataset; categories cascade: L1 scoped by competitor, L2 by competitor+L1, L3 by competitor+L1+L2
        full_df = self._competitor_df
        cat_df = full_df
        if filters and filters.get("competitor"):
            comp_list = [c.strip() for c in filters["competitor"].split(",")]
            cat_df = full_df[full_df["competitor_name"].isin(comp_list)]
        l2_df = cat_df
        if filters and filters.get("category_level_1"):
            l1_list = [c.strip() for c in filters["category_level_1"].split(",")]
            l2_df = cat_df[cat_df["category_level_1"].isin(l1_list)]
        l3_df = l2_df
        if filters and filters.get("category_level_2"):
            l2_list = [c.strip() for c in filters["category_level_2"].split(",")]
            l3_df = l2_df[l2_df["category_level_2"].isin(l2_list)]
        filter_options = {
            "competitors": sorted([v for v in full_df["competitor_name"].dropna().unique().tolist()]),
            "categories_l1": sorted([v for v in cat_df["category_level_1"].dropna().unique().tolist()]),
            "categories_l2": sorted([v for v in l2_df["category_level_2"].dropna().unique().tolist()]),
            "categories_l3": sorted([v for v in l3_df["category_level_3"].dropna().unique().tolist()]),
        }

        return {"items": items, "total_count": total, "filter_options": filter_options}

    def get_competitor_products_export(self, filters: dict = None) -> list[dict]:
        df = self._apply_competitor_filters(self._competitor_df, filters)
        items = []
        for _, row in df.iterrows():
            items.append({
                "competitor_name": row.get("competitor_name"),
                "competitor_product_name": row.get("competitor_product_name"),
                "category_level_1": row.get("category_level_1"),
                "category_level_2": row.get("category_level_2"),
                "category_level_3": row.get("category_level_3"),
                "competitor_sale_price": float(row["competitor_sale_price"]) if pd.notna(row.get("competitor_sale_price")) else None,
                "last_crawled": row.get("competitor_last_updated_day"),
                "days_since_crawl": int(row["days_since_crawl"]) if pd.notna(row.get("days_since_crawl")) else None,
                "bf_product_name": row.get("bf_product_name"),
                "bf_sale_price": float(row["bf_sale_price"]) if pd.notna(row.get("bf_sale_price")) else None,
                "sale_PI": float(row["sale_PI"]) if pd.notna(row.get("sale_PI")) else None,
                "classification": row.get("classification"),
            })
        return items
