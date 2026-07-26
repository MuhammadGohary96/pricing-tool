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


MOCK_COMPETITORS = [
    {"competitor_id": 4, "competitor_name": "Talabat"},
    {"competitor_id": 5, "competitor_name": "Carrefour"},
    {"competitor_id": 6, "competitor_name": "Instashop"},
]


class MockPricingDataService(PricingDataServiceInterface):

    def __init__(self, seed: int = 42):
        random.seed(seed)
        np.random.seed(seed)
        self._df = self._generate_products()
        self._global_df = self._aggregate_to_global(self._df)
        self._trend_data = self._generate_trend_data()
        self._competitor_df = self._generate_competitor_products()
        unique_products = self._df["product_id"].nunique()
        print(f"[MockData] Generated {len(self._df)} rows (FP grain) "
              f"({unique_products} products × {len(MOCK_COMPETITORS)} competitors × 3 FPs) across "
              f"{self._df['sub_category_name'].nunique()} subcategories")
        print(f"[MockData] Pre-aggregated GLOBAL view: {len(self._global_df)} rows")
        print(f"[MockData] Generated {len(self._competitor_df)} competitor product rows")

    def _generate_products(self) -> pd.DataFrame:
        # ── Step 0: FP list for multi-FP data generation ───────────────────────
        MOCK_FPS = [
            {"fp_id": "FP001", "fp_name": "New Cairo FP #1"},
            {"fp_id": "FP002", "fp_name": "Maadi FP #1"},
            {"fp_id": "FP003", "fp_name": "Sheikh Zayed City FP #1"},
        ]

        # ── Step 1: Generate product-level base data ──────────────────────────
        base_rows = []
        product_id_counter = 10001
        now = datetime.now()

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

                    total_revenue = round(max(100, float(np.random.lognormal(mean=9, sigma=2))), 2)
                    avg_daily_qty = round(max(0.1, float(np.random.lognormal(mean=3, sigma=1.5))), 2)
                    bf_sale_price = round(random.uniform(5, 350), 2)
                    bf_regular_price = round(bf_sale_price * random.uniform(1.0, 1.3), 2)
                    eligible = random.random() < 0.65
                    bf_updated = now - timedelta(days=random.randint(0, 60))
                    now_price = round(bf_sale_price * random.uniform(0.95, 1.05), 2)
                    now_sale = round(now_price * random.uniform(0.85, 0.98), 2) if random.random() < 0.4 else None

                    base_rows.append({
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
                        "eligible_product": eligible,
                        "bf_price_updated_at": bf_updated.isoformat(),
                        "now_price": now_price,
                        "now_sale_price": now_sale,
                    })
                    product_id_counter += 1

        # ── Step 2: Cross-join with competitors AND FPs, generate per-competitor data ──
        rows = []
        for base in base_rows:
            for fp in MOCK_FPS:
                for comp in MOCK_COMPETITORS:
                    row = {**base, **fp, **comp}

                    has_pi = base["eligible_product"] and random.random() < 0.55
                    is_recent_bf = random.random() < 0.85
                    is_recent_comp = random.random() < 0.75
                    is_mapped = has_pi

                if has_pi:
                    pi_value = round(max(0.70, min(1.50, float(np.random.normal(1.05, 0.12)))), 4)
                    # PI = bf / comp_sale  →  comp_sale = bf / PI
                    comp_sale = round(base["bf_sale_price"] / pi_value, 2)
                    comp_regular = round(comp_sale * random.uniform(1.0, 1.25), 2)
                    min_comp = round(comp_sale * random.uniform(0.90, 1.0), 2)
                    max_comp = round(comp_sale * random.uniform(1.0, 1.15), 2)
                    comp_updated = now - timedelta(days=random.randint(0, 35))
                    updated = (now - comp_updated).days <= 7
                    competitor_product_name = f"{comp['competitor_name']} {base['product_name']}"
                    sim_score = None
                    match_pot = False
                    match_potential_name = None
                else:
                    pi_value = None
                    comp_sale = None
                    comp_regular = None
                    min_comp = None
                    max_comp = None
                    comp_updated = None
                    updated = False
                    competitor_product_name = None
                    sim_score = round(random.uniform(0.3, 0.98), 2)
                    match_pot = sim_score >= 0.85
                    match_potential_name = f"{comp['competitor_name']} {base['product_name']}" if match_pot else None

                used = base["eligible_product"] and has_pi and updated

                if not has_pi and not match_pot:
                    action_type = "Needs Mapping"
                elif not has_pi and match_pot:
                    action_type = "Review Match"
                elif has_pi and not updated:
                    action_type = "Needs Price Update"
                else:
                    action_type = "Complete"

                    row.update({
                        "competitor_sale_price": comp_sale,
                        "min_competitor_sale_price": min_comp,
                        "max_competitor_sale_price": max_comp,
                        "sale_PI": pi_value,
                        "has_PI": has_pi,
                        "competitor_price_updated_at": comp_updated.isoformat() if comp_updated else None,
                        "updated": updated,
                        "similarity_score": sim_score,
                        "match_potential": match_pot,
                        "used_product": used,
                        "action_type": action_type,
                        "competitor_product_name": competitor_product_name,
                        "match_potential_product_name": match_potential_name,
                        "is_recent_breadfast": is_recent_bf,
                        "is_recent_competitor": is_recent_comp,
                        "prices_recently_updated": is_recent_bf and is_recent_comp,
                        "is_mapped": is_mapped,
                        "competitor_product_id": f"COMP-{comp['competitor_id']}-{product_id_counter}" if has_pi else None,
                    })
                    rows.append(row)

        df = pd.DataFrame(rows)

        # Compute normalized scores using unique products (scores are product-level)
        unique_products = df.drop_duplicates("product_id").set_index("product_id")

        for subcat in unique_products["sub_category_name"].unique():
            sub = unique_products[unique_products["sub_category_name"] == subcat]
            rev_min, rev_max = sub["total_revenue"].min(), sub["total_revenue"].max()
            qty_min, qty_max = sub["avg_daily_quantity"].min(), sub["avg_daily_quantity"].max()
            rev_range = rev_max - rev_min if rev_max > rev_min else 1
            qty_range = qty_max - qty_min if qty_max > qty_min else 1
            unique_products.loc[sub.index, "norm_revenue"] = ((sub["total_revenue"] - rev_min) / rev_range).round(4)
            unique_products.loc[sub.index, "norm_quantity"] = ((sub["avg_daily_quantity"] - qty_min) / qty_range).round(4)

        unique_products["weighted_score"] = (unique_products["norm_revenue"] * 0.5 + unique_products["norm_quantity"] * 0.5).round(4)

        unique_products["global_tier"] = pd.cut(
            unique_products["weighted_score"].rank(pct=True),
            bins=[0, 0.20, 0.40, 0.70, 0.90, 1.0],
            labels=["Very Low", "Low", "Medium", "Top", "Top+"],
            include_lowest=True,
        ).astype(str)

        for subcat in unique_products["sub_category_name"].unique():
            sub = unique_products[unique_products["sub_category_name"] == subcat]
            unique_products.loc[sub.index, "subcat_tier"] = pd.cut(
                sub["weighted_score"].rank(pct=True),
                bins=[0, 0.20, 0.40, 0.70, 0.90, 1.0],
                labels=["Very Low", "Low", "Medium", "Top", "Top+"],
                include_lowest=True,
            ).astype(str)

        # Join product-level scores back to multi-row DataFrame
        score_cols = ["norm_revenue", "norm_quantity", "weighted_score", "global_tier", "subcat_tier"]
        df = df.merge(
            unique_products[score_cols].reset_index(),
            on="product_id", how="left"
        )

        # PI deviation and days since update (per competitor row)
        df["pi_deviation"] = df["sale_PI"].apply(
            lambda x: round(x - 1, 4) if pd.notna(x) else None
        )
        df["days_since_update"] = df["competitor_price_updated_at"].apply(
            lambda x: (now - datetime.fromisoformat(x)).days if pd.notna(x) and x else None
        )

        # Compute classification per product×competitor row
        def _classify(row):
            is_pl = row["brand_name"] == "Breadfast"
            if pd.notna(row["sale_PI"]):
                return "Mapped - PL" if is_pl else "Mapped - Not PL"
            sim = row.get("similarity_score")
            has_potential = pd.notna(sim) and sim >= 0.85
            if is_pl:
                return "Not Mapped - PL - Potential Match" if has_potential else "Not Mapped - PL - No Potential Match"
            return "Not Mapped - Not PL - Potential Match" if has_potential else "Not Mapped - Not PL - No Potential Match"

        df["classification"] = df.apply(_classify, axis=1)
        return df.sort_values(["total_revenue", "competitor_id"], ascending=[False, True]).reset_index(drop=True)

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

        action_type is RECOMPUTED from aggregated state.
        """
        # 1. Modal BF sale price — from recent BF rows
        bf_recent = df[df.get("is_recent_breadfast", pd.Series([False] * len(df))) == True]
        if len(bf_recent) > 0:
            bf_modal = (
                bf_recent.groupby("product_id")["bf_sale_price"]
                .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
                .rename("bf_sale_price_modal")
            )
        else:
            bf_modal = pd.Series(dtype=float, name="bf_sale_price_modal")

        # 2. Competitor prices: rows with any observation
        if "competitor_sale_price" in df.columns:
            comp_obs = df[df["competitor_sale_price"].notna()]
        else:
            comp_obs = df.iloc[0:0]
        comp_fresh = comp_obs[comp_obs.get("is_recent_competitor", pd.Series([False] * len(comp_obs))) == True]

        # 2a. Modal price from FRESH observations
        if len(comp_fresh) > 0:
            comp_fresh_modal = (
                comp_fresh.groupby(["product_id", "competitor_id"])["competitor_sale_price"]
                .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
                .rename("comp_price_fresh_modal")
            )
        else:
            comp_fresh_modal = pd.Series(dtype=float, name="comp_price_fresh_modal")

        # 2b. Modal price from ALL observations (fallback)
        if len(comp_obs) > 0:
            comp_all_modal = (
                comp_obs.groupby(["product_id", "competitor_id"])["competitor_sale_price"]
                .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
                .rename("comp_price_all_modal")
            )
        else:
            comp_all_modal = pd.Series(dtype=float, name="comp_price_all_modal")

        # 2c. Pair sets for freshness flags
        has_fresh_pairs = set(
            map(tuple, comp_fresh[["product_id", "competitor_id"]].drop_duplicates().values)
        ) if len(comp_fresh) > 0 else set()
        has_obs_pairs = set(
            map(tuple, comp_obs[["product_id", "competitor_id"]].drop_duplicates().values)
        ) if len(comp_obs) > 0 else set()

        # 3. Product-level base fields
        product_cols = [
            "product_id", "product_name", "commercial_category_name",
            "main_category_name", "sub_category_name", "brand_name",
            "total_revenue", "avg_daily_quantity", "weighted_score",
            "norm_revenue", "norm_quantity", "global_tier", "subcat_tier",
            "eligible_product", "bf_regular_price",
        ]
        product_base = df.drop_duplicates("product_id")[[c for c in product_cols if c in df.columns]].copy()

        # 4. Competitor-level base fields (recompute action_type, has_PI, updated, is_recent_*)
        comp_cols_first = [
            "product_id", "competitor_id", "competitor_name",
            "competitor_product_id", "competitor_product_name",
            "is_mapped", "match_potential", "similarity_score",
            "match_potential_product_name",
        ]
        comp_base = df.drop_duplicates(["product_id", "competitor_id"])[
            [c for c in comp_cols_first if c in df.columns]
        ].copy()

        # min/max competitor sale price spread across observed FPs
        if "competitor_sale_price" in df.columns and len(comp_obs) > 0:
            spread = comp_obs.groupby(["product_id", "competitor_id"])["competitor_sale_price"].agg(["min", "max"])
            spread.columns = ["min_competitor_sale_price", "max_competitor_sale_price"]
            comp_base = comp_base.merge(spread, on=["product_id", "competitor_id"], how="left")

        # days_since_update: MIN (freshest) across observed FPs
        if "days_since_update" in df.columns and len(comp_obs) > 0:
            days_agg = (
                comp_obs.groupby(["product_id", "competitor_id"])["days_since_update"]
                .min().rename("days_since_update")
            )
            comp_base = comp_base.merge(days_agg, on=["product_id", "competitor_id"], how="left")

        # 5. Merge
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
        if "comp_price_fresh_modal" in result.columns and "comp_price_all_modal" in result.columns:
            result["competitor_sale_price"] = result["comp_price_fresh_modal"].fillna(
                result["comp_price_all_modal"]
            )

        # 8. Aggregated freshness flags
        pair_keys = list(zip(result["product_id"], result["competitor_id"]))
        result["is_recent_competitor"] = [k in has_fresh_pairs for k in pair_keys]
        result["has_PI"] = [k in has_obs_pairs for k in pair_keys]
        result["is_recent_breadfast"] = result["bf_sale_price"].notna()
        result["prices_recently_updated"] = (
            result["is_recent_breadfast"] & result["is_recent_competitor"]
        )
        result["updated"] = result["prices_recently_updated"]

        # 9. used_product = eligible AND has price AND fresh
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
        has_price = result["competitor_sale_price"].notna()
        is_fresh = result["is_recent_competitor"].fillna(False).astype(bool) if hasattr(result["is_recent_competitor"], "fillna") else pd.Series(result["is_recent_competitor"], index=result.index).astype(bool)
        sim = (
            pd.to_numeric(result["similarity_score"], errors="coerce")
            if "similarity_score" in result.columns
            else pd.Series([None] * len(result), index=result.index)
        )
        ai_match = sim.fillna(0) >= 0.85

        conditions = [
            ~is_mapped & ~ai_match,
            ~is_mapped & ai_match,
            is_mapped & ~has_price,
            is_mapped & has_price & is_fresh,
            is_mapped & has_price & ~is_fresh,
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

    # ─── Interface Implementations ─────────────────────────────

    def get_all_products(self, filters: dict = None) -> pd.DataFrame:
        return self._apply_filters(self._df, filters)

    def get_blended_pi_by_subcategory(self, filters: dict = None, group_by: str = "sub_category") -> pd.DataFrame:
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
                "used_product_count": g["product_id"].nunique(),
                "total_revenue": round(g.drop_duplicates("product_id")["total_revenue"].sum(), 2),
                "product_pis": g[["product_name", "sale_PI", "avg_daily_quantity"]].dropna(subset=["sale_PI"]).rename(
                    columns={"avg_daily_quantity": "weight"}
                ).to_dict("records"),
            }),
            include_groups=False,
        ).reset_index()

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
            estimated_price = round(row["bf_sale_price"] * random.uniform(0.90, 1.15), 2)
            items.append({
                "product_id": row["product_id"],
                "bf_product_name": row["product_name"],
                "bf_brand": row["brand_name"],
                "bf_price": float(row["bf_sale_price"]),
                "competitor_name": row.get("competitor_name"),
                "suggested_competitor_name": row["match_potential_product_name"] if pd.notna(row.get("match_potential_product_name")) else row["product_name"],
                "similarity_score": float(row["similarity_score"]),
                "estimated_competitor_price": estimated_price,
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

    def get_executive_dashboard(self, filters: dict = None) -> dict:
        df = self._apply_filters(self._df, filters)

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

        # Mapping Coverage = mapped (per competitor) / total active (same for all competitors)
        total_active_products = int(df["product_id"].nunique())

        competitor_pi = []
        if "competitor_name" in df.columns:
            for comp, grp in df.groupby("competitor_name"):
                if pd.isna(comp):
                    continue
                used_grp = grp[grp["used_product"] == True]
                # Mapped count: products with is_mapped=True for THIS competitor
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
                    "eligible_products": total_active_products,  # Total active = same for all
                    "used_products": used_cnt,
                })
            competitor_pi.sort(key=lambda x: (x["blended_pi"] or 0), reverse=True)

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

    def get_products_pivoted(
        self, filters: dict = None, page: int = 1, page_size: int = 50,
        sort_by: str = None, sort_dir: str = "desc", search: str = None,
    ) -> dict:
        import math

        # Strip competitor + action_type: competitor because we always show all as columns,
        # action_type because we recompute it as the worst action post-pivot.
        clean_filters = {k: v for k, v in (filters or {}).items() if k not in ("competitor", "action_type")}
        df = self._apply_filters(self._df, clean_filters)

        competitors = sorted(df["competitor_name"].dropna().unique().tolist()) if "competitor_name" in df.columns else []

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
        product_df["worst_pi"] = product_df[pi_cols].max(axis=1) if pi_cols else None

        # Compute product-level action as worst action across all competitors
        _NORM = {"Review AI Match": "Review Match"}
        action_cols = [f"{c}_action" for c in competitors if f"{c}_action" in product_df.columns]
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
            product_df = product_df[product_df["product_name"].str.lower().str.contains(q, na=False)]

        SORTABLE = {"worst_pi", "total_revenue", "weighted_score", "product_name", "bf_sale_price", "global_tier", "action_type"}
        if sort_by and sort_by in SORTABLE and sort_by in product_df.columns:
            product_df = product_df.sort_values(sort_by, ascending=(sort_dir == "asc"), na_position="last")
        else:
            product_df = product_df.sort_values("weighted_score", ascending=False, na_position="last")

        total = len(product_df)
        page_df = product_df.iloc[(page - 1) * page_size: page * page_size]

        def _s(val):
            if val is None:
                return None
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                return None
            return val

        items = []
        for _, row in page_df.iterrows():
            item = {
                "product_id": row.get("product_id"),
                "product_name": row.get("product_name"),
                "brand_name": row.get("brand_name"),
                "sub_category_name": row.get("sub_category_name"),
                "global_tier": row.get("global_tier"),
                "action_type": row.get("action_type"),
                "bf_sale_price": _s(float(row["bf_sale_price"])) if pd.notna(row.get("bf_sale_price")) else None,
                "bf_regular_price": _s(float(row["bf_regular_price"])) if pd.notna(row.get("bf_regular_price")) else None,
                "now_price": _s(float(row["now_price"])) if pd.notna(row.get("now_price")) else None,
                "now_sale_price": _s(float(row["now_sale_price"])) if pd.notna(row.get("now_sale_price")) else None,
                "total_revenue": _s(float(row["total_revenue"])) if pd.notna(row.get("total_revenue")) else None,
                "eligible_product": bool(row.get("eligible_product", False)),
                "used_product": bool(row.get("used_product", False)),
                "worst_pi": _s(float(row["worst_pi"])) if pd.notna(row.get("worst_pi")) else None,
                "weighted_score": _s(float(row["weighted_score"])) if pd.notna(row.get("weighted_score")) else None,
                "action_counts": row.get("_action_counts", {}),
            }
            for comp in competitors:
                item[f"{comp}_price"] = _s(float(row[f"{comp}_price"])) if pd.notna(row.get(f"{comp}_price")) else None
                item[f"{comp}_pi"] = _s(float(row[f"{comp}_pi"])) if pd.notna(row.get(f"{comp}_pi")) else None
                item[f"{comp}_action"] = row.get(f"{comp}_action")
                item[f"{comp}_days_stale"] = int(row[f"{comp}_days_stale"]) if pd.notna(row.get(f"{comp}_days_stale")) else None
            items.append(item)

        return {"items": items, "total_count": total, "competitors": competitors}

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

    def get_fp_options(self) -> list[str]:
        """Return sorted list of distinct FP names from loaded data."""
        return sorted(self._df["fp_name"].dropna().unique().tolist())

    # ─── Competitor Products Tab ─────────────────────────────────

    def _generate_competitor_products(self) -> pd.DataFrame:
        now = datetime.now()
        competitors = [
            {"competitor_id": 4, "competitor_name": "Talabat"},
            {"competitor_id": 5, "competitor_name": "Carrefour"},
            {"competitor_id": 6, "competitor_name": "Instashop"},
        ]
        category_hierarchy = {
            "Food": {
                "Dairy & Eggs": ["Milk", "Cheese", "Yogurt", "Eggs", "Butter"],
                "Beverages": ["Juice", "Water", "Soft Drinks", "Tea & Coffee"],
                "Snacks": ["Chips", "Biscuits", "Chocolate", "Nuts"],
                "Bakery": ["Bread", "Pastries", "Cakes"],
                "Frozen": ["Frozen Vegetables", "Ice Cream", "Ready Meals"],
            },
            "Home Care": {
                "Cleaning": ["Surface Cleaner", "Floor Cleaner", "Disinfectant"],
                "Laundry": ["Detergent", "Fabric Softener", "Bleach"],
                "Kitchen": ["Dish Soap", "Trash Bags", "Foil & Wrap"],
            },
            "Personal Care": {
                "Hair Care": ["Shampoo", "Conditioner", "Hair Styling"],
                "Body Care": ["Body Wash", "Deodorant", "Lotion"],
                "Oral Care": ["Toothpaste", "Toothbrush", "Mouthwash"],
            },
            "Baby & Pet": {
                "Baby": ["Diapers", "Baby Food", "Baby Wipes"],
                "Pet": ["Dog Food", "Cat Food", "Pet Treats"],
            },
        }

        rows = []
        comp_pid = 50001
        bf_products = self._df.drop_duplicates("product_id")

        for comp in competitors:
            n_products = random.randint(600, 800)
            for _ in range(n_products):
                l1 = random.choice(list(category_hierarchy.keys()))
                l2 = random.choice(list(category_hierarchy[l1].keys()))
                l3 = random.choice(category_hierarchy[l1][l2])

                brand = random.choice(BRANDS[:40])
                size = random.choice(["100g", "250ml", "500ml", "1L", "1kg", "200g", "750ml"])
                product_name = f"{brand} {l3} {size}"
                comp_sale = round(random.uniform(5, 300), 2)
                comp_regular = round(comp_sale * random.uniform(1.0, 1.25), 2)
                min_price = round(comp_sale * random.uniform(0.85, 1.0), 2)
                max_price = round(comp_sale * random.uniform(1.0, 1.2), 2)

                crawl_days_ago = random.randint(0, 45)
                crawl_date = (now - timedelta(days=crawl_days_ago)).date()
                is_recent = crawl_days_ago <= 7

                # ~40% mapped to BF
                has_pi = random.random() < 0.40
                match_pot = False
                sim_score = None
                match_name = None
                bf_name = None
                bf_price = None
                sale_pi = None
                classification = None
                bf_updated = None
                is_recent_bf = False

                if has_pi:
                    bf_row = bf_products.sample(1).iloc[0]
                    bf_name = bf_row["product_name"]
                    bf_price = float(bf_row["bf_sale_price"])
                    sale_pi = round(bf_price / comp_sale, 4) if comp_sale > 0 else None
                    bf_updated_date = (now - timedelta(days=random.randint(0, 30))).date()
                    bf_updated = bf_updated_date.isoformat()
                    is_recent_bf = random.random() < 0.7
                    classification = "Mapped - Not PL" if bf_row["brand_name"] != "Breadfast" else "Mapped - PL"
                else:
                    # ~15% of unmapped have AI match
                    sim_score = round(random.uniform(0.3, 0.98), 2)
                    match_pot = sim_score >= 0.85
                    if match_pot:
                        bf_row = bf_products.sample(1).iloc[0]
                        match_name = bf_row["product_name"]
                        classification = "Not Mapped - Potential Match"
                    else:
                        classification = "Not Mapped - No Potential Match"

                rows.append({
                    "product_id": bf_row["product_id"] if has_pi else None,
                    "bf_product_name": bf_name,
                    "brand_name": brand,
                    "main_category_name": l1,
                    "sub_category_name": l2,
                    "competitor_id": comp["competitor_id"],
                    "competitor_name": comp["competitor_name"],
                    "competitor_product_id": comp_pid,
                    "competitor_product_name": product_name,
                    "category_level_1": l1,
                    "category_level_2": l2,
                    "category_level_3": l3,
                    "competitor_sale_price": comp_sale,
                    "competitor_regular_price": comp_regular,
                    "min_competitor_sale_price": min_price,
                    "max_competitor_sale_price": max_price,
                    "bf_sale_price": bf_price,
                    "competitor_last_updated_day": crawl_date.isoformat(),
                    "competitor_last_updated_day_date": crawl_date,
                    "bf_last_updated_day": bf_updated,
                    "is_recent_competitor": is_recent,
                    "is_recent_breadfast": is_recent_bf,
                    "has_PI": has_pi,
                    "sale_PI": sale_pi,
                    "classification": classification,
                    "match_potential": match_pot,
                    "similarity_score": sim_score,
                    "match_potential_product_name": match_name,
                    "days_since_crawl": crawl_days_ago,
                })
                comp_pid += 1

        return pd.DataFrame(rows)

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
            return {"total_crawled": 0, "mapped_bf": 0, "mapped_competitor": 0, "mapping_rate": 0, "fresh": 0}
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
        cutoff = now - timedelta(days=30)
        df = df[df["competitor_last_updated_day_date"] >= cutoff]
        if df.empty:
            return []

        grouped = df.groupby(
            ["competitor_last_updated_day_date", "competitor_name"]
        )["competitor_product_id"].nunique().reset_index(name="count")

        result = []
        for _, row in grouped.iterrows():
            result.append({
                "date": row["competitor_last_updated_day_date"].isoformat(),
                "competitor_name": row["competitor_name"],
                "count": int(row["count"]),
            })
        return sorted(result, key=lambda x: x["date"])

    def _category_group_metrics(self, grp):
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
                "competitor_product_id": int(row["competitor_product_id"]) if pd.notna(row.get("competitor_product_id")) else None,
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
