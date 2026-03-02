import random
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from backend.services.data_interface import PricingDataServiceInterface
from backend.utils.calculations import (
    compute_blended_pi,
    pi_direction,
    ACTION_SYMBOLS,
    TIER_ORDER,
)

# Realistic category/subcategory hierarchy for an Egyptian grocery delivery company
CATEGORY_SUBCATEGORIES = {
    "Food & Beverage": [
        "Milk & Dairy", "Cheese", "Yogurt", "Eggs", "Butter & Ghee",
        "Juice", "Water", "Soft Drinks", "Tea & Coffee", "Energy Drinks",
        "Bread & Bakery", "Pasta & Noodles", "Rice & Grains", "Canned Food",
        "Cooking Oil", "Sauces & Condiments", "Spices & Herbs", "Sugar & Sweeteners",
        "Flour & Baking", "Honey & Jam", "Chocolate", "Biscuits & Cookies",
        "Chips & Snacks", "Nuts & Seeds", "Dried Fruits", "Cereal & Oats",
        "Frozen Vegetables", "Frozen Meat", "Frozen Seafood", "Frozen Ready Meals",
        "Ice Cream", "Fresh Fruits", "Fresh Vegetables", "Fresh Herbs",
        "Deli Meats", "Fresh Meat", "Fresh Poultry", "Fresh Seafood",
    ],
    "Home Care": [
        "Laundry Detergent", "Fabric Softener", "Bleach & Disinfectant",
        "Dish Soap", "Surface Cleaner", "Glass Cleaner", "Floor Cleaner",
        "Air Freshener", "Trash Bags", "Aluminum Foil & Wrap",
        "Paper Towels", "Toilet Paper", "Tissues",
        "Sponges & Scrubbers", "Mops & Brooms", "Insect Repellent",
        "Laundry Accessories", "Bathroom Cleaner", "Kitchen Cleaner",
        "Oven Cleaner", "Drain Cleaner",
    ],
    "Personal Care": [
        "Shampoo", "Conditioner", "Body Wash", "Bar Soap", "Deodorant",
        "Toothpaste", "Toothbrush", "Mouthwash", "Face Wash", "Face Cream",
        "Body Lotion", "Hand Cream", "Sunscreen", "Razor & Shaving",
        "Hair Styling", "Hair Color", "Cotton & Pads", "Feminine Hygiene",
        "Hand Sanitizer", "Wet Wipes",
    ],
    "Baby Care": [
        "Diapers", "Baby Wipes", "Baby Formula", "Baby Food",
        "Baby Shampoo", "Baby Lotion", "Baby Oil", "Baby Accessories",
        "Baby Cereal", "Nursing Supplies",
    ],
    "Pet Care": [
        "Dog Food", "Cat Food", "Pet Treats", "Cat Litter",
        "Pet Accessories", "Pet Hygiene",
    ],
    "Health & Wellness": [
        "Vitamins", "Supplements", "First Aid", "Pain Relief",
        "Cold & Flu", "Digestive Health", "Eye Care", "Oral Care Therapeutic",
    ],
    "Stationery & Home": [
        "Batteries", "Light Bulbs", "Candles", "School Supplies",
        "Adhesive & Tape", "Storage & Organization",
    ],
}

BRANDS = [
    "Juhayna", "Domty", "Almarai", "Labanita", "Dina Farms",
    "Persil", "Ariel", "Tide", "Dettol", "Clorox",
    "Pepsi", "Coca-Cola", "Schweppes", "Fayrouz", "Birell",
    "Chipsy", "Doritos", "Tiger", "Molto", "Bisco Misr",
    "Nescafe", "Lipton", "Ahmad Tea", "El Arosa", "Rabea",
    "Heinz", "Knorr", "Maggi", "Wadi Food", "Regina",
    "Pampers", "Huggies", "Fine", "Seoudi", "El Rashidi",
    "Sunsilk", "Head & Shoulders", "Dove", "Lux", "Palmolive",
    "Colgate", "Signal", "Oral-B", "Nivea", "Garnier",
    "Crystal", "Hayat", "Nestle", "Cadbury", "Galaxy",
    "Breadfast", "Breadfast",  # Private label — appears twice to increase frequency
]


class MockPricingDataService(PricingDataServiceInterface):

    def __init__(self, seed: int = 42):
        random.seed(seed)
        np.random.seed(seed)
        self._df = self._generate_products()
        self._trend_data = self._generate_trend_data()
        print(f"[MockData] Generated {len(self._df)} products across "
              f"{self._df['sub_category_name'].nunique()} subcategories")

    def _generate_products(self) -> pd.DataFrame:
        rows = []
        product_id_counter = 10001

        for main_cat, subcats in CATEGORY_SUBCATEGORIES.items():
            commercial_cat = main_cat
            for subcat in subcats:
                n_products = random.randint(8, 25)
                for _ in range(n_products):
                    brand = random.choice(BRANDS)
                    size = random.choice([
                        "100g", "200g", "250ml", "500ml", "1L", "1kg",
                        "2L", "400g", "750ml", "150g", "300g", "5L",
                        "50g", "125g", "6 Pack", "12 Pack",
                    ])
                    product_name = f"{brand} {subcat.split(' & ')[0]} {size}"

                    # Revenue follows log-normal distribution
                    total_revenue = float(np.random.lognormal(mean=9, sigma=2))
                    total_revenue = round(max(100, total_revenue), 2)

                    avg_daily_qty = float(np.random.lognormal(mean=3, sigma=1.5))
                    avg_daily_qty = round(max(0.1, avg_daily_qty), 2)

                    # Prices
                    bf_sale_price = round(random.uniform(5, 350), 2)
                    bf_regular_price = round(bf_sale_price * random.uniform(1.0, 1.3), 2)

                    # Eligibility (top ~65%)
                    eligible = random.random() < 0.65

                    # Mapping status
                    has_pi = eligible and random.random() < 0.55

                    # Competitor pricing (only if mapped)
                    if has_pi:
                        pi_value = float(np.random.normal(1.05, 0.12))
                        pi_value = round(max(0.70, min(1.50, pi_value)), 4)
                        talabat_sale = round(bf_sale_price * pi_value, 2)
                        talabat_regular = round(talabat_sale * random.uniform(1.0, 1.25), 2)
                    else:
                        pi_value = None
                        talabat_sale = None
                        talabat_regular = None

                    # Freshness
                    now = datetime.now()
                    bf_updated = now - timedelta(days=random.randint(0, 60))
                    if has_pi:
                        tal_updated = now - timedelta(days=random.randint(0, 35))
                        updated = (now - tal_updated).days <= 7
                    else:
                        tal_updated = None
                        updated = False

                    # Matching (for unmapped products)
                    competitor_name = None
                    match_potential_name = None
                    if not has_pi:
                        sim_score = round(random.uniform(0.3, 0.98), 2)
                        match_pot = sim_score >= 0.85
                        if match_pot:
                            match_potential_name = f"Talabat {product_name}"
                    else:
                        sim_score = None
                        match_pot = False
                        competitor_name = f"Talabat {product_name}"

                    used = eligible and has_pi and updated

                    # Mock live catalog prices
                    now_price = round(bf_sale_price * random.uniform(0.95, 1.05), 2)
                    now_sale = round(now_price * random.uniform(0.85, 0.98), 2) if random.random() < 0.4 else None

                    rows.append({
                        "product_id": f"BF-{product_id_counter}",
                        "product_name": product_name,
                        "brand_name": brand,
                        "main_category_name": main_cat,
                        "commercial_category_name": commercial_cat,
                        "sub_category_name": subcat,
                        "total_revenue": total_revenue,
                        "avg_daily_quantity": avg_daily_qty,
                        "bf_sale_price": bf_sale_price,
                        "bf_regular_price": bf_regular_price,
                        "talabat_sale_price": talabat_sale,
                        "talabat_regular_price": talabat_regular,
                        "sale_PI": pi_value,
                        "has_PI": has_pi,
                        "eligible_product": eligible,
                        "bf_price_updated_at": bf_updated.isoformat(),
                        "talabat_price_updated_at": tal_updated.isoformat() if tal_updated else None,
                        "updated": updated,
                        "similarity_score": sim_score,
                        "match_potential": match_pot,
                        "used_product": used,
                        "now_price": now_price,
                        "now_sale_price": now_sale,
                        "competitor_product_name": competitor_name,
                        "match_potential_product_name": match_potential_name,
                    })
                    product_id_counter += 1

        df = pd.DataFrame(rows)

        # Compute normalized scores within subcategory
        for subcat in df["sub_category_name"].unique():
            mask = df["sub_category_name"] == subcat
            sub_df = df.loc[mask]

            rev_min, rev_max = sub_df["total_revenue"].min(), sub_df["total_revenue"].max()
            qty_min, qty_max = sub_df["avg_daily_quantity"].min(), sub_df["avg_daily_quantity"].max()

            rev_range = rev_max - rev_min if rev_max > rev_min else 1
            qty_range = qty_max - qty_min if qty_max > qty_min else 1

            df.loc[mask, "norm_revenue"] = ((sub_df["total_revenue"] - rev_min) / rev_range).round(4)
            df.loc[mask, "norm_quantity"] = ((sub_df["avg_daily_quantity"] - qty_min) / qty_range).round(4)

        df["weighted_score"] = (df["norm_revenue"] * 0.5 + df["norm_quantity"] * 0.5).round(4)

        # Global tier assignment
        df["global_tier"] = pd.cut(
            df["weighted_score"].rank(pct=True),
            bins=[0, 0.20, 0.40, 0.70, 0.90, 1.0],
            labels=["Very Low", "Low", "Medium", "Top", "Top+"],
            include_lowest=True,
        ).astype(str)

        # Subcategory tier assignment
        for subcat in df["sub_category_name"].unique():
            mask = df["sub_category_name"] == subcat
            sub_df = df.loc[mask]
            df.loc[mask, "subcat_tier"] = pd.cut(
                sub_df["weighted_score"].rank(pct=True),
                bins=[0, 0.20, 0.40, 0.70, 0.90, 1.0],
                labels=["Very Low", "Low", "Medium", "Top", "Top+"],
                include_lowest=True,
            ).astype(str)

        # Action type
        def _action_type(row):
            if not row["has_PI"] and not row["match_potential"]:
                return "Needs Mapping"
            elif not row["has_PI"] and row["match_potential"]:
                return "Review Match"
            elif row["has_PI"] and not row["updated"]:
                return "Needs Price Update"
            return "Complete"

        df["action_type"] = df.apply(_action_type, axis=1)

        # PI deviation and days since update
        df["pi_deviation"] = df["sale_PI"].apply(
            lambda x: round(x - 1, 4) if pd.notna(x) else None
        )
        now = datetime.now()
        df["days_since_update"] = df["talabat_price_updated_at"].apply(
            lambda x: (now - datetime.fromisoformat(x)).days if pd.notna(x) and x else None
        )

        return df.sort_values("total_revenue", ascending=False).reset_index(drop=True)

    def _generate_trend_data(self) -> pd.DataFrame:
        dates = [datetime.now().date() - timedelta(days=i) for i in range(29, -1, -1)]
        base_pi = 1.03
        base_coverage = 38.0

        pi_values = []
        cov_values = []
        used_counts = []
        total = len(self._df)

        for i, d in enumerate(dates):
            slope = i * 0.001
            noise = np.random.normal(0, 0.008)
            pi_values.append(round(base_pi + slope + noise, 4))

            cov_slope = i * 0.32
            cov_noise = np.random.normal(0, 0.5)
            cov_values.append(round(base_coverage + cov_slope + cov_noise, 2))

            used_counts.append(int(total * (base_coverage + cov_slope) / 100))

        return pd.DataFrame({
            "date": [d.isoformat() for d in dates],
            "blended_pi": pi_values,
            "coverage_pct": cov_values,
            "used_count": used_counts,
        })

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

    # ─── Interface Implementations ─────────────────────────────

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
            # Generate a plausible Talabat name (slight variation)
            tal_name = row["product_name"].replace("BF-", "").strip()
            size_variants = {"100g": "105g", "200g": "195g", "250ml": "250ml",
                            "500ml": "500ml", "1L": "1L", "1kg": "1000g"}
            for orig, variant in size_variants.items():
                if orig in tal_name:
                    tal_name = tal_name.replace(orig, variant)
                    break

            estimated_price = round(row["bf_sale_price"] * random.uniform(0.90, 1.15), 2)

            items.append({
                "product_id": row["product_id"],
                "bf_product_name": row["product_name"],
                "bf_brand": row["brand_name"],
                "bf_price": float(row["bf_sale_price"]),
                "suggested_talabat_name": row["match_potential_product_name"] if pd.notna(row.get("match_potential_product_name")) else f"Talabat - {tal_name}",
                "similarity_score": float(row["similarity_score"]),
                "estimated_talabat_price": estimated_price,
            })

        return {"items": items, "total_count": total_count}

    def get_staleness_heatmap(self, filters: dict = None) -> dict:
        df = self._apply_filters(self._df, filters)
        mapped = df[df["has_PI"] == True].copy()

        if mapped.empty:
            return {"cells": [], "subcategories": [], "buckets": []}

        buckets = ["0-7d", "7-14d", "14-21d", "21-30d", "30d+"]

        def bucket_days(d):
            if d is None:
                return "30d+"
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

        # Top 25 subcategories by product count
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
        ].to_dict("records")

        top_5_expensive = blended.nsmallest(5, "blended_pi")[
            ["sub_category_name", "blended_pi", "used_product_count"]
        ].to_dict("records")

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
        return self._trend_data[["date", "blended_pi"]].rename(
            columns={"blended_pi": "value"}
        ).to_dict("records")

    def get_coverage_trend(self) -> list[dict]:
        return self._trend_data[["date", "coverage_pct"]].rename(
            columns={"coverage_pct": "value"}
        ).to_dict("records")

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
        trend = self._trend_data
        if len(trend) < 8:
            return []

        current_row = trend.iloc[-1]
        prev_row = trend.iloc[-8]

        metrics = [
            ("Blended PI", current_row["blended_pi"], prev_row["blended_pi"]),
            ("Coverage %", current_row["coverage_pct"], prev_row["coverage_pct"]),
            ("Used Products", current_row["used_count"], prev_row["used_count"]),
        ]

        # Add needs_action delta (fake it from coverage trend)
        action_current = self.get_action_summary()["total_needs_action"]
        action_prev = action_current + random.randint(50, 200)
        metrics.append(("Actions Remaining", action_current, action_prev))

        result = []
        for name, current, previous in metrics:
            delta = round(current - previous, 4)
            direction = "\u25B2" if delta > 0 else ("\u25BC" if delta < 0 else "\u2014")
            result.append({
                "metric_name": name,
                "current": float(current),
                "previous": float(previous),
                "delta": float(delta),
                "direction": direction,
            })

        return result

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
