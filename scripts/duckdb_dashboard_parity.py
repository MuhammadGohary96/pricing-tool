"""
Phase 2.2 parity check: executive/dashboard pandas vs DuckDB.

Hits the live backend twice (USE_DUCKDB=true and =false would each need a
restart) — so instead this script hits the running backend, captures the
response, then compares the structure section by section using the JSON
we already saved.

Usage:
  # 1. Backend with USE_DUCKDB=true, get response
  USE_DUCKDB=true uvicorn ... &
  curl localhost:8000/api/executive/dashboard?fp_names=New+Cairo+FP+%231 \\
      > /tmp/dashboard_duckdb.json

  # 2. Backend with USE_DUCKDB=false
  USE_DUCKDB=false uvicorn ... &
  curl localhost:8000/api/executive/dashboard?fp_names=New+Cairo+FP+%231 \\
      > /tmp/dashboard_pandas.json

  # 3. Compare
  python3 scripts/duckdb_dashboard_parity.py
"""
import json
import sys
from pathlib import Path


def compare_kpis(pd_kpis: dict, du_kpis: dict) -> list[str]:
    diffs = []
    for k in sorted(set(pd_kpis) | set(du_kpis)):
        pv = pd_kpis.get(k)
        dv = du_kpis.get(k)
        if isinstance(pv, float) and isinstance(dv, float):
            if abs(pv - dv) > 0.01:
                diffs.append(f"  kpis.{k}: pandas={pv} duckdb={dv} (diff {abs(pv-dv):.4f})")
        elif pv != dv:
            diffs.append(f"  kpis.{k}: pandas={pv} duckdb={dv}")
    return diffs


def compare_competitor_pi(pd_list: list, du_list: list) -> list[str]:
    diffs = []
    pd_map = {c["competitor_name"]: c for c in pd_list}
    du_map = {c["competitor_name"]: c for c in du_list}
    common = sorted(set(pd_map) & set(du_map))
    only_pd = set(pd_map) - set(du_map)
    only_du = set(du_map) - set(pd_map)
    if only_pd:
        diffs.append(f"  competitor_pi: only in pandas: {only_pd}")
    if only_du:
        diffs.append(f"  competitor_pi: only in duckdb: {only_du}")

    for comp in common:
        p, d = pd_map[comp], du_map[comp]
        for field in ("blended_pi", "pi_deviation"):
            pv, dv = p.get(field), d.get(field)
            if pv is None and dv is None:
                continue
            if pv is None or dv is None:
                diffs.append(f"  competitor_pi.{comp}.{field}: pandas={pv} duckdb={dv}")
                continue
            if abs(pv - dv) > 0.001:
                diffs.append(f"  competitor_pi.{comp}.{field}: pandas={pv} duckdb={dv}")
        for field in ("mapped_products", "eligible_products", "used_products"):
            if p.get(field) != d.get(field):
                diffs.append(f"  competitor_pi.{comp}.{field}: pandas={p.get(field)} duckdb={d.get(field)}")
    return diffs


def compare_mapping_progress(pd_list: list, du_list: list) -> list[str]:
    diffs = []
    pd_map = {c["competitor_name"]: c for c in pd_list}
    du_map = {c["competitor_name"]: c for c in du_list}
    for comp in sorted(set(pd_map) | set(du_map)):
        p = pd_map.get(comp, {})
        d = du_map.get(comp, {})
        for field in ("mapped_not_pl", "mapped_pl", "potential_not_pl", "potential_pl",
                      "no_potential_not_pl", "no_potential_pl", "total"):
            if p.get(field) != d.get(field):
                diffs.append(f"  mapping_progress.{comp}.{field}: pandas={p.get(field)} duckdb={d.get(field)}")
        for field in ("mapped_pct", "potential_reach_pct"):
            pv, dv = p.get(field), d.get(field)
            if pv is None and dv is None:
                continue
            if pv is None or dv is None or abs(pv - dv) > 0.1:
                diffs.append(f"  mapping_progress.{comp}.{field}: pandas={pv} duckdb={dv}")
    return diffs


def main():
    pd_path = Path("/tmp/dashboard_pandas.json")
    du_path = Path("/tmp/dashboard_duckdb.json")
    if not pd_path.exists() or not du_path.exists():
        print("Missing one of /tmp/dashboard_pandas.json or /tmp/dashboard_duckdb.json")
        sys.exit(1)

    pd_data = json.loads(pd_path.read_text())
    du_data = json.loads(du_path.read_text())

    all_diffs = []
    print("=== kpis ===")
    diffs = compare_kpis(pd_data.get("kpis", {}), du_data.get("kpis", {}))
    if not diffs:
        print("  ✅ all match")
    else:
        all_diffs.extend(diffs)
        for d in diffs:
            print(d)

    print()
    print("=== competitor_pi ===")
    diffs = compare_competitor_pi(pd_data.get("competitor_pi", []), du_data.get("competitor_pi", []))
    if not diffs:
        print(f"  ✅ all match across {len(pd_data.get('competitor_pi', []))} competitors")
    else:
        all_diffs.extend(diffs)
        for d in diffs[:10]:
            print(d)
        if len(diffs) > 10:
            print(f"  ... and {len(diffs)-10} more")

    print()
    print("=== mapping_progress ===")
    diffs = compare_mapping_progress(pd_data.get("mapping_progress", []), du_data.get("mapping_progress", []))
    if not diffs:
        print(f"  ✅ all match across {len(pd_data.get('mapping_progress', []))} competitors")
    else:
        all_diffs.extend(diffs)
        for d in diffs[:10]:
            print(d)
        if len(diffs) > 10:
            print(f"  ... and {len(diffs)-10} more")

    print()
    print("=== classification_breakdown ===")
    pd_c = pd_data.get("classification_breakdown", {})
    du_c = du_data.get("classification_breakdown", {})
    diffs = []
    for k in sorted(set(pd_c) | set(du_c)):
        if pd_c.get(k) != du_c.get(k):
            diffs.append(f"  classification_breakdown.{k}: pandas={pd_c.get(k)} duckdb={du_c.get(k)}")
    if not diffs:
        print("  ✅ all match")
    else:
        all_diffs.extend(diffs)
        for d in diffs:
            print(d)

    print()
    print("=" * 50)
    if not all_diffs:
        print("✅ FULL PARITY")
    else:
        print(f"❌ {len(all_diffs)} differences found")


if __name__ == "__main__":
    main()
