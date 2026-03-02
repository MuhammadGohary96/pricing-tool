"""
BigQuery-backed pricing data service.

Reads from dbt_gohary.pricing_index_analysis (created by PI-query.sql)
and provides the same interface as MockPricingDataService.

Column mapping from BQ table → internal DataFrame:
  product_name_en         → product_name
  avg_daily_revenue       → total_revenue
  breadfast_sale_price    → bf_sale_price
  combined_score_global   → weighted_score
  norm_revenue_global     → norm_revenue
  norm_quantity_global     → norm_quantity
  breadfast_last_updated_day → bf_price_updated_at
  talabat_last_updated_day   → talabat_price_updated_at

Derived fields (computed after load):
  action_type     ← from has_PI, match_potential, updated
  pi_deviation    ← sale_PI - 1
  days_since_update ← days since talabat_last_updated_day
"""

from datetime import datetime
from typing import Optional

import pandas as pd

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
    "talabat_last_updated_day": "talabat_price_updated_at",
}

BQ_QUERY = """
SELECT
    product_id,
    product_name_en,
    brand_name,
    main_category_name,
    commercial_category_name,
    sub_category_name,
    avg_daily_revenue,
    avg_daily_quantity,
    combined_score_global,
    norm_revenue_global,
    norm_quantity_global,
    global_tier,
    subcat_tier,
    eligible_product,
    breadfast_sale_price,
    talabat_sale_price,
    sale_PI,
    has_PI,
    updated,
    similarity_score,
    match_potential,
    used_product,
    breadfast_last_updated_day,
    talabat_last_updated_day,
    competitor_product_name,
    match_potential_product_name
FROM `{project}.{dataset}.{table}`
ORDER BY combined_score_global DESC
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

    def _load_from_bigquery(self) -> pd.DataFrame:
        query = BQ_QUERY.format(
            project=self._project,
            dataset=self._dataset,
            table=self._table,
        )
        df = self._client.query(query).to_dataframe()

        # Rename columns to match internal names
        df = df.rename(columns=COLUMN_MAP)

        # Cast BQ NUMERIC (decimal.Decimal) columns to float64
        numeric_cols = [
            "total_revenue", "avg_daily_quantity", "weighted_score",
            "norm_revenue", "norm_quantity", "sale_PI",
            "bf_sale_price", "talabat_sale_price", "similarity_score",
            "cumulative_revenue_share",
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

        # Derive action_type
        def _action_type(row):
            if not row["has_PI"] and not row["match_potential"]:
                return "Needs Mapping"
            elif not row["has_PI"] and row["match_potential"]:
                return "Review Match"
            elif row["has_PI"] and not row["updated"]:
                return "Needs Price Update"
            return "Complete"

        df["action_type"] = df.apply(_action_type, axis=1)

        # Derive pi_deviation
        df["pi_deviation"] = df["sale_PI"].apply(
            lambda x: round(x - 1, 4) if pd.notna(x) else None
        )

        # Derive days_since_update
        now = datetime.now().date()
        df["days_since_update"] = df["talabat_price_updated_at"].apply(
            lambda x: (now - x).days if pd.notna(x) else None
        )

        # Convert date columns to ISO strings for JSON serialization
        for col in ["bf_price_updated_at", "talabat_price_updated_at"]:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: x.isoformat() if pd.notna(x) else None
                )

        # Fill bf_regular_price if missing (not in BQ table)
        if "bf_regular_price" not in df.columns:
            df["bf_regular_price"] = df["bf_sale_price"]

        # Fill talabat_regular_price if missing
        if "talabat_regular_price" not in df.columns:
            df["talabat_regular_price"] = df["talabat_sale_price"]

        return df.reset_index(drop=True)

    def enrich_with_catalog_prices(self, token: str, progress_status: dict = None):
        """Fetch live prices from Breadfast Catalog API using the user's token."""
        from backend.config import settings
        from backend.services.catalog_client import fetch_prices_by_ids

        # Only fetch for our BQ products (numeric IDs)
        numeric_ids = [
            int(pid) for pid in self._df["product_id"]
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
                "used_product_count": len(g),
                "total_revenue": round(g["total_revenue"].sum(), 2),
                "product_pis": g[["product_name", "sale_PI", "avg_daily_quantity"]].dropna(subset=["sale_PI"]).rename(
                    columns={"avg_daily_quantity": "weight"}
                ).to_dict("records"),
            }),
            include_groups=False,
        ).reset_index()

        # Compute per-subcategory counts from ALL products
        all_counts = df.groupby("sub_category_name").apply(
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

        return grouped.sort_values("blended_pi", ascending=False).reset_index(drop=True)

    def get_coverage_funnel(self, filters: dict = None) -> dict:
        df = self._apply_filters(self._df, filters)
        total = len(df)
        if total == 0:
            return {"mapping_funnel": [], "coverage_funnel": []}

        all_mapped = int(df["has_PI"].sum())
        all_updated = int((df["has_PI"] & df["updated"]).sum())
        eligible = int(df["eligible_product"].sum())
        eligible_mapped = int((df["eligible_product"] & df["has_PI"]).sum())
        used = int(df["used_product"].sum())

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
        eligible = df[df["eligible_product"] == True]
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
        eligible = df[df["eligible_product"] == True]
        needs_action = eligible[eligible["action_type"] != "Complete"]

        blended = None
        if not used.empty and used["avg_daily_quantity"].sum() > 0:
            blended = round(
                (used["sale_PI"] * used["avg_daily_quantity"]).sum()
                / used["avg_daily_quantity"].sum(), 4
            )

        return {
            "total_products": len(df),
            "eligible_products": len(eligible),
            "used_products": len(used),
            "avg_blended_pi": blended,
            "needs_action": len(needs_action),
        }

    def get_action_breakdown(self, filters: dict = None) -> list[dict]:
        df = self._apply_filters(self._df, filters)
        eligible = df[df["eligible_product"] == True]
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
                "similarity_score": row["similarity_score"] if pd.notna(row["similarity_score"]) else None,
                "bf_sale_price": float(row["bf_sale_price"]),
                "talabat_sale_price": float(row["talabat_sale_price"]) if pd.notna(row["talabat_sale_price"]) else None,
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
                "suggested_talabat_name": row["match_potential_product_name"] if pd.notna(row.get("match_potential_product_name")) else row["product_name"],
                "similarity_score": float(row["similarity_score"]) if pd.notna(row["similarity_score"]) else 0,
                "estimated_talabat_price": float(row["talabat_sale_price"]) if pd.notna(row.get("talabat_sale_price")) else float(row["bf_sale_price"] * 1.05),
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
                "product_count": len(g),
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
        }
