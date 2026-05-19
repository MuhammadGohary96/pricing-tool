"""
Phase 0 Spike: Prove DuckDB delivers ≥10× speedup over pandas for single-FP filter.

Compares:
  PANDAS path: existing get_blended_pi_by_subcategory(fp_names=...)
  DUCKDB path: equivalent SQL against Parquet

Pass criterion: DuckDB p50 < 3s AND ≥10× faster than pandas.
"""
import pickle
import time
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

CACHE_PICKLE = Path("cache/pricing_data/pricing_data_a601afbb4b707977_v1.2.pkl")
PARQUET_PATH = Path("cache/pricing_data/fp_grain.parquet")
N_RUNS = 5


def banner(s: str):
    print()
    print("=" * 70)
    print(s)
    print("=" * 70)


def load_cached_df() -> pd.DataFrame:
    banner("Loading existing pickle cache")
    t0 = time.time()
    with open(CACHE_PICKLE, "rb") as f:
        wrapper = pickle.load(f)
    # cache_service stores: { "data": {...}, "timestamp": ..., "version": ... }
    cached = wrapper["data"] if "data" in wrapper else wrapper
    df = cached["_df"]
    print(f"  Loaded _df: {len(df):,} rows × {len(df.columns)} cols in {time.time()-t0:.1f}s")
    print(f"  Memory: {df.memory_usage(deep=True).sum() / 1024 / 1024:.0f} MB")
    return df


def write_parquet(df: pd.DataFrame, path: Path):
    banner("Writing Parquet")
    t0 = time.time()
    # Convert via pyarrow with explicit schema handling for object dtypes
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(
        table,
        path,
        compression="snappy",
        row_group_size=100_000,
        use_dictionary=True,
    )
    size_mb = path.stat().st_size / 1024 / 1024
    print(f"  Wrote {path}: {size_mb:.0f} MB in {time.time()-t0:.1f}s")
    print(f"  Compression ratio: {df.memory_usage(deep=True).sum() / path.stat().st_size:.1f}x smaller on disk")


# ---------------------------------------------------------------------------
# PANDAS BENCHMARK — mimics the slow path in get_blended_pi_by_subcategory
# ---------------------------------------------------------------------------
def pandas_blended_pi_for_fp(df: pd.DataFrame, fp_name: str) -> pd.DataFrame:
    """Mirror the current slow path: filter to FP → aggregate → blended PI."""
    # 1. Filter to FP
    scoped = df[df["fp_name"] == fp_name]

    # 2. Aggregate to global per (product, competitor) — modal fresh prices
    bf_recent = scoped[scoped["is_recent_breadfast"] == True]
    bf_modal = bf_recent.groupby("product_id")["bf_sale_price"].agg(
        lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None
    )
    comp_obs = scoped[scoped["competitor_sale_price"].notna()]
    comp_fresh = comp_obs[comp_obs["is_recent_competitor"] == True]
    comp_fresh_modal = comp_fresh.groupby(["product_id", "competitor_id"])["competitor_sale_price"].agg(
        lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None
    )

    # 3. Build a per-(product, competitor) frame with aggregated prices
    base = scoped.drop_duplicates(["product_id", "competitor_id"])[
        ["product_id", "competitor_id", "product_name", "sub_category_name",
         "avg_daily_quantity", "total_revenue", "eligible_product",
         "is_mapped", "match_potential", "similarity_score"]
    ].copy()
    base = base.merge(comp_fresh_modal.rename("comp_modal"),
                       on=["product_id", "competitor_id"], how="left")
    base = base.merge(bf_modal.rename("bf_modal"), on="product_id", how="left")
    base["sale_PI"] = base["bf_modal"] / base["comp_modal"]
    base["used_product"] = (
        base["eligible_product"].fillna(False).astype(bool)
        & base["comp_modal"].notna()
        & base["bf_modal"].notna()
    )

    # 4. Aggregate per subcategory using quantity-weighted PI
    used = base[base["used_product"]]
    if used.empty:
        return pd.DataFrame(columns=["sub_category_name", "blended_pi", "used_product_count"])

    result = used.groupby("sub_category_name").apply(
        lambda g: pd.Series({
            "blended_pi": round(
                (g["sale_PI"] * g["avg_daily_quantity"]).sum()
                / g["avg_daily_quantity"].sum(), 4
            ) if g["avg_daily_quantity"].sum() > 0 else None,
            "used_product_count": g["product_id"].nunique(),
        }),
        include_groups=False,
    ).reset_index()
    return result.sort_values("sub_category_name").reset_index(drop=True)


# ---------------------------------------------------------------------------
# DUCKDB BENCHMARK — same result via SQL against Parquet
# ---------------------------------------------------------------------------
DUCKDB_SQL = """
WITH scoped AS (
    SELECT *
    FROM read_parquet(?)
    WHERE fp_name = ?
),
-- Match pandas mode().iloc[0]: pick smallest value among the most-frequent
bf_modal AS (
    SELECT product_id, bf_sale_price AS bf_modal FROM (
        SELECT product_id, bf_sale_price, COUNT(*) AS cnt,
               ROW_NUMBER() OVER (
                   PARTITION BY product_id
                   ORDER BY COUNT(*) DESC, bf_sale_price ASC
               ) AS rn
        FROM scoped
        WHERE is_recent_breadfast = TRUE AND bf_sale_price IS NOT NULL
        GROUP BY product_id, bf_sale_price
    ) WHERE rn = 1
),
comp_modal AS (
    SELECT product_id, competitor_id, competitor_sale_price AS comp_modal FROM (
        SELECT product_id, competitor_id, competitor_sale_price, COUNT(*) AS cnt,
               ROW_NUMBER() OVER (
                   PARTITION BY product_id, competitor_id
                   ORDER BY COUNT(*) DESC, competitor_sale_price ASC
               ) AS rn
        FROM scoped
        WHERE competitor_sale_price IS NOT NULL AND is_recent_competitor = TRUE
        GROUP BY product_id, competitor_id, competitor_sale_price
    ) WHERE rn = 1
),
base AS (
    SELECT
        s.product_id,
        s.competitor_id,
        s.sub_category_name,
        s.avg_daily_quantity,
        s.eligible_product,
        cm.comp_modal,
        bm.bf_modal,
        bm.bf_modal / cm.comp_modal AS sale_PI,
        (s.eligible_product
            AND cm.comp_modal IS NOT NULL
            AND bm.bf_modal   IS NOT NULL) AS used_product
    FROM (SELECT DISTINCT product_id, competitor_id, sub_category_name,
                  avg_daily_quantity, eligible_product
          FROM scoped) s
    LEFT JOIN comp_modal cm USING (product_id, competitor_id)
    LEFT JOIN bf_modal   bm USING (product_id)
)
SELECT
    sub_category_name,
    ROUND(
        SUM(sale_PI * avg_daily_quantity) FILTER (WHERE used_product)
        / NULLIF(SUM(avg_daily_quantity) FILTER (WHERE used_product), 0),
        4
    ) AS blended_pi,
    COUNT(DISTINCT product_id) FILTER (WHERE used_product) AS used_product_count
FROM base
GROUP BY sub_category_name
HAVING COUNT(DISTINCT product_id) FILTER (WHERE used_product) > 0
ORDER BY sub_category_name
"""


def duckdb_blended_pi_for_fp(conn: duckdb.DuckDBPyConnection, fp_name: str) -> pd.DataFrame:
    return conn.execute(DUCKDB_SQL, [str(PARQUET_PATH), fp_name]).df()


def time_runs(label: str, fn, *args, n: int = N_RUNS) -> list[float]:
    times = []
    for i in range(n):
        t0 = time.time()
        result = fn(*args)
        dt = time.time() - t0
        times.append(dt)
        print(f"  [{label}] run {i+1}: {dt:.2f}s ({len(result)} rows)")
    return times


def parity_check(pd_df: pd.DataFrame, du_df: pd.DataFrame) -> tuple[bool, str]:
    """Compare results within tolerance."""
    if len(pd_df) != len(du_df):
        return False, f"row count differs: pandas={len(pd_df)}, duckdb={len(du_df)}"

    # Sort both by sub_category_name for stable comparison
    pd_sorted = pd_df.sort_values("sub_category_name").reset_index(drop=True)
    du_sorted = du_df.sort_values("sub_category_name").reset_index(drop=True)

    if not (pd_sorted["sub_category_name"] == du_sorted["sub_category_name"]).all():
        return False, "subcategory names differ"

    # Compare blended_pi within 0.0001 tolerance, allowing both NaN
    pd_pi = pd_sorted["blended_pi"].fillna(-999)
    du_pi = du_sorted["blended_pi"].fillna(-999)
    diff = (pd_pi - du_pi).abs()
    max_diff = diff.max()
    if max_diff > 0.001:
        mismatches = pd_sorted[diff > 0.001].head(3)
        return False, f"blended_pi max diff = {max_diff:.4f}, e.g.:\n{mismatches}"

    # Compare used_product_count exactly
    if not (pd_sorted["used_product_count"] == du_sorted["used_product_count"]).all():
        diff_rows = pd_sorted[pd_sorted["used_product_count"] != du_sorted["used_product_count"]]
        return False, f"used_product_count differs in {len(diff_rows)} rows"

    return True, "OK"


def main():
    df = load_cached_df()

    # Pick a representative FP — one with enough USED products (not just row count)
    used_rows = df[df["used_product"] == True]
    fp_used_counts = used_rows.groupby("fp_name").size().sort_values(ascending=False)
    print(f"\n  Top 5 FPs by USED rows: {dict(fp_used_counts.head())}")
    test_fp = fp_used_counts.index[0]  # biggest FP by used products
    print(f"  Test FP: '{test_fp}' ({fp_used_counts.iloc[0]:,} used rows)")

    # Write Parquet (one-time cost)
    if not PARQUET_PATH.exists():
        write_parquet(df, PARQUET_PATH)
    else:
        print(f"\n  Reusing existing Parquet: {PARQUET_PATH} ({PARQUET_PATH.stat().st_size / 1024 / 1024:.0f} MB)")

    # ---- PANDAS BENCHMARK ----
    banner(f"PANDAS: blended_pi by subcategory for FP='{test_fp}'")
    pd_times = time_runs("pandas", pandas_blended_pi_for_fp, df, test_fp)
    pd_result = pandas_blended_pi_for_fp(df, test_fp)

    # ---- DUCKDB BENCHMARK ----
    banner(f"DUCKDB: blended_pi by subcategory for FP='{test_fp}'")
    conn = duckdb.connect(":memory:", read_only=False)
    conn.execute("PRAGMA threads=4")
    du_times = time_runs("duckdb", duckdb_blended_pi_for_fp, conn, test_fp)
    du_result = duckdb_blended_pi_for_fp(conn, test_fp)
    conn.close()

    # ---- PARITY ----
    banner("Parity check")
    ok, msg = parity_check(pd_result, du_result)
    print(f"  Status: {'✅ PASS' if ok else '❌ FAIL'} — {msg}")
    if not ok:
        print("\n  Pandas head:")
        print(pd_result.head())
        print("\n  DuckDB head:")
        print(du_result.head())

    # ---- VERDICT ----
    banner("Verdict")
    pd_p50 = sorted(pd_times)[len(pd_times) // 2]
    du_p50 = sorted(du_times)[len(du_times) // 2]
    speedup = pd_p50 / du_p50 if du_p50 > 0 else float("inf")

    print(f"  Pandas  p50: {pd_p50:.2f}s  (mean {sum(pd_times)/len(pd_times):.2f}s)")
    print(f"  DuckDB  p50: {du_p50:.2f}s  (mean {sum(du_times)/len(du_times):.2f}s)")
    print(f"  Speedup:     {speedup:.1f}×")
    print()
    pass_speed = du_p50 < 3.0
    pass_ratio = speedup >= 10
    pass_parity = ok
    if pass_speed and pass_ratio and pass_parity:
        print("  ✅ PASS — proceed with Phase 1")
    else:
        print("  ❌ FAIL — revisit plan")
        if not pass_speed:
            print(f"    - DuckDB p50 {du_p50:.2f}s exceeds 3s target")
        if not pass_ratio:
            print(f"    - Speedup {speedup:.1f}× below 10× requirement")
        if not pass_parity:
            print(f"    - Results don't match pandas implementation")


if __name__ == "__main__":
    main()
