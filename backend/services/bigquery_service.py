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

from datetime import datetime
from typing import Optional

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

BQ_QUERY = """
SELECT
    product_id,
    product_name_en,
    brand_name,
    main_category_name,
    commercial_category_name,
    sub_category_name,
    CAST(avg_daily_revenue          AS FLOAT64) AS avg_daily_revenue,
    CAST(avg_daily_quantity         AS FLOAT64) AS avg_daily_quantity,
    CAST(combined_score_global      AS FLOAT64) AS combined_score_global,
    CAST(norm_revenue_global        AS FLOAT64) AS norm_revenue_global,
    CAST(norm_quantity_global       AS FLOAT64) AS norm_quantity_global,
    global_tier,
    subcat_tier,
    eligible_product,
    CAST(breadfast_sale_price       AS FLOAT64) AS breadfast_sale_price,
    competitor_id,
    competitor_name,
    CAST(competitor_sale_price      AS FLOAT64) AS competitor_sale_price,
    CAST(min_competitor_sale_price  AS FLOAT64) AS min_competitor_sale_price,
    CAST(max_competitor_sale_price  AS FLOAT64) AS max_competitor_sale_price,
    CAST(sale_PI                    AS FLOAT64) AS sale_PI,
    has_PI,
    updated,
    CAST(similarity_score           AS FLOAT64) AS similarity_score,
    match_potential,
    used_product,
    action_type,
    classification,
    breadfast_last_updated_day,
    competitor_last_updated_day,
    competitor_product_name,
    match_potential_product_name
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

        if self._startup_status:
            self._startup_status["stage"] = "Loading products from BigQuery..."
        self._df = self._load_from_bigquery()
        print(
            f"[BigQuery] Loaded {len(self._df)} products across "
            f"{self._df['sub_category_name'].nunique()} subcategories"
        )

        # Initialize price columns as null — enriched later via user token
        if "now_price" not in self._df.columns:
            self._df["now_price"] = None
        if "now_sale_price" not in self._df.columns:
            self._df["now_sale_price"] = None

        # Load competitor products analysis table
        if self._startup_status:
            self._startup_status["stage"] = "Loading competitor products..."
        self._competitor_df = self._load_competitor_products()

    def _load_from_bigquery(self) -> pd.DataFrame:
        import time
        query = BQ_QUERY.format(
            project=self._project,
            dataset=self._dataset,
            table=self._table,
        )
        print("[BigQuery] Submitting query...")
        t0 = time.time()
        job = self._client.query(query)
        print(f"[BigQuery] Job submitted ({job.job_id}), waiting for BQ execution...")
        rows = job.result()  # wait for query to finish — returns RowIterator
        t1 = time.time()
        print(f"[BigQuery] Query executed in {t1 - t0:.1f}s — building DataFrame from rows...")
        df = pd.DataFrame([dict(row) for row in rows])
        print(f"[BigQuery] Built DataFrame ({len(df)} rows) in {time.time() - t1:.1f}s (total {time.time() - t0:.1f}s)")

        # Rename columns to match internal names
        df = df.rename(columns=COLUMN_MAP)

        # Cast BQ NUMERIC (decimal.Decimal) columns to float64
        numeric_cols = [
            "total_revenue", "avg_daily_quantity", "weighted_score",
            "norm_revenue", "norm_quantity", "sale_PI",
            "bf_sale_price", "competitor_sale_price", "competitor_regular_price",
            "min_competitor_sale_price", "max_competitor_sale_price",
            "similarity_score", "cumulative_revenue_share",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Cast booleans (BQ may return NaN for nullable bools)
        for col in ["eligible_product", "has_PI", "updated", "match_potential", "used_product"]:
            if col in df.columns:
                df[col] = df[col].fillna(False).astype(bool)

        # Cast product_id to string
        df["product_id"] = df["product_id"].astype(str)

        # Derive pi_deviation
        df["pi_deviation"] = df["sale_PI"].apply(
            lambda x: round(x - 1, 4) if pd.notna(x) else None
        )

        # Derive days_since_update
        now = datetime.now().date()
        df["days_since_update"] = df["competitor_price_updated_at"].apply(
            lambda x: (now - x).days if pd.notna(x) else None
        )

        # Convert date columns to ISO strings for JSON serialization
        for col in ["bf_price_updated_at", "competitor_price_updated_at"]:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: x.isoformat() if pd.notna(x) else None
                )

        # Fill bf_regular_price if missing (not in BQ table)
        if "bf_regular_price" not in df.columns:
            df["bf_regular_price"] = df["bf_sale_price"]

        # Fill competitor_regular_price if missing
        if "competitor_regular_price" not in df.columns:
            df["competitor_regular_price"] = df["competitor_sale_price"]

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
            comp_df = df[df["competitor_name"] == comp][
                ["product_id", "competitor_sale_price", "sale_PI", "action_type", "days_since_update"]
            ].drop_duplicates("product_id")
            product_df = product_df.merge(
                comp_df.rename(columns={
                    "competitor_sale_price": f"{comp}_price",
                    "sale_PI": f"{comp}_pi",
                    "action_type": f"{comp}_action",
                    "days_since_update": f"{comp}_days_stale",
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
                item[price_key] = _s(float(row[price_key])) if pd.notna(row.get(price_key)) else None
                item[pi_key] = _s(float(row[pi_key])) if pd.notna(row.get(pi_key)) else None
                item[action_key] = row.get(action_key)
                item[days_key] = int(row[days_key]) if pd.notna(row.get(days_key)) else None
            items.append(item)

        return {"items": items, "total_count": total, "competitors": competitors}

    def enrich_with_catalog_prices(self, token: str, progress_status: dict = None):
        """Fetch live prices from Breadfast Catalog API using the user's token."""
        from backend.config import settings
        from backend.services.catalog_client import fetch_prices_by_ids

        # Only fetch for our BQ products (numeric IDs)
        numeric_ids = [
            int(pid) for pid in self._df["product_id"].unique()
            if isinstance(pid, str) and pid.isdigit()
        ]

        prices = fetch_prices_by_ids(
            settings.BF_CATALOG_URL, token, numeric_ids,
            progress_status=progress_status,
        )

        if not prices:
            return 0

        self._df["now_price"] = self._df["product_id"].apply(
            lambda pid: prices.get(int(pid), {}).get("now_price") if pid.isdigit() else None
        )
        self._df["now_sale_price"] = self._df["product_id"].apply(
            lambda pid: prices.get(int(pid), {}).get("now_sale_price") if pid.isdigit() else None
        )

        matched = self._df["now_price"].notna().sum()
        print(f"[Catalog] Enriched {matched} of {len(self._df)} products with accurate prices")
        return int(matched)

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

    def _apply_filters(self, df: pd.DataFrame, filters: dict = None) -> pd.DataFrame:
        if not filters:
            return df
        filtered = df.copy()
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

    def get_blended_pi_by_subcategory(self, filters: dict = None) -> pd.DataFrame:
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
            "subcategory_count": len(blended),
        }

    def get_executive_dashboard(self, filters: dict = None) -> dict:
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
        competitor_pi = []
        if "competitor_name" in df.columns:
            for comp, grp in df.groupby("competitor_name"):
                if pd.isna(comp):
                    continue
                used_grp = grp[grp["used_product"] == True]
                mapped_cnt = int(grp[grp["sale_PI"].notna()]["product_id"].nunique())
                bpi = None
                if not used_grp.empty:
                    qty_sum = used_grp["avg_daily_quantity"].sum()
                    if qty_sum > 0:
                        bpi = round(
                            (used_grp["sale_PI"] * used_grp["avg_daily_quantity"]).sum() / qty_sum, 4
                        )
                eligible_cnt = int(grp[grp["eligible_product"] == True]["product_id"].nunique())
                used_cnt = int(grp[grp["used_product"] == True]["product_id"].nunique())
                competitor_pi.append({
                    "competitor_name": str(comp),
                    "blended_pi": bpi,
                    "pi_deviation": round(bpi - 1, 4) if bpi is not None else None,
                    "mapped_products": mapped_cnt,
                    "eligible_products": eligible_cnt,
                    "used_products": used_cnt,
                })
            competitor_pi.sort(key=lambda x: (x["blended_pi"] or 0), reverse=True)

        # ─── Mapping Progress by Competitor ───────────────────────────
        mapping_progress = []
        if "competitor_name" in df.columns and "classification" in df.columns:
            for comp, grp in df.groupby("competitor_name"):
                if pd.isna(comp):
                    continue
                grp_u = grp.drop_duplicates("product_id")
                counts = grp_u["classification"].value_counts().to_dict()
                mapped_not_pl = int(counts.get("Mapped - Not PL", 0))
                mapped_pl = int(counts.get("Mapped - PL", 0))
                pot_not_pl = int(counts.get("Not Mapped - Not PL - Potential Match", 0))
                pot_pl = int(counts.get("Not Mapped - PL - Potential Match", 0))
                no_pot_not_pl = int(counts.get("Not Mapped - Not PL - No Potential Match", 0))
                no_pot_pl = int(counts.get("Not Mapped - PL - No Potential Match", 0))
                total = mapped_not_pl + mapped_pl + pot_not_pl + pot_pl + no_pot_not_pl + no_pot_pl
                mapped_total = mapped_not_pl + mapped_pl
                potential_total = pot_not_pl + pot_pl
                mapping_progress.append({
                    "competitor_name": str(comp),
                    "mapped_not_pl": mapped_not_pl,
                    "mapped_pl": mapped_pl,
                    "potential_not_pl": pot_not_pl,
                    "potential_pl": pot_pl,
                    "no_potential_not_pl": no_pot_not_pl,
                    "no_potential_pl": no_pot_pl,
                    "total": total,
                    "mapped_pct": round(mapped_total / total * 100, 1) if total > 0 else 0.0,
                    "potential_reach_pct": round((mapped_total + potential_total) / total * 100, 1) if total > 0 else 0.0,
                })
            mapping_progress.sort(key=lambda x: x["mapped_pct"], reverse=True)

        # ─── Overall Classification Breakdown ─────────────────────────
        classification_breakdown = {
            "mapped_not_pl": 0, "mapped_pl": 0,
            "not_mapped_not_pl_potential": 0, "not_mapped_not_pl_no_potential": 0,
            "not_mapped_pl_potential": 0, "not_mapped_pl_no_potential": 0,
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
        df = pd.DataFrame([dict(row) for row in rows])
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

        now = datetime.now().date()
        for col in ["competitor_last_updated_day", "bf_last_updated_day"]:
            if col in df.columns:
                df[f"{col}_date"] = df[col]  # keep raw date for timeline grouping
                df[col] = df[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)

        if "competitor_last_updated_day_date" in df.columns:
            df["days_since_crawl"] = df["competitor_last_updated_day_date"].apply(
                lambda x: (now - x).days if pd.notna(x) else None
            )
        else:
            df["days_since_crawl"] = None

        return df.reset_index(drop=True)

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
