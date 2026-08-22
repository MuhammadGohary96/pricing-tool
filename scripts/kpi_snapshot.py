"""Capture a deterministic snapshot of every existing Executive / Commercial /
Master-Data number, so a pipeline change can be proven not to move any of them.

Loads the service straight from a Parquet file (no BigQuery round-trip) and
calls the same service methods the routers call, over a matrix of filters.

    python scripts/kpi_snapshot.py <out.json> [parquet_path]

Compare two snapshots with:

    python scripts/kpi_snapshot.py --diff before.json after.json
"""

import json
import math
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


# ---------------------------------------------------------------- normalizing
def norm(obj):
    """Make service output JSON-comparable and float-stable."""
    import numpy as np
    import pandas as pd

    if obj is None:
        return None
    if isinstance(obj, pd.DataFrame):
        return [norm(r) for r in obj.to_dict(orient="records")]
    if isinstance(obj, dict):
        return {str(k): norm(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple, set)):
        return [norm(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        # NaN != NaN would make every diff noisy
        return None if math.isnan(f) else round(f, 6)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return norm(obj.model_dump())
    if isinstance(obj, (int, str)):
        return obj
    return str(obj)


# ------------------------------------------------------------- filter matrix
# Deliberately covers GLOBAL, single-FP, category, competitor, vertical and
# private-label paths — the branches that behave differently in _BASE_CTE.
def filter_matrix(svc):
    fps = svc.get_fp_options()
    opts = svc.get_filter_options()
    cats = opts.get("main_categories") or []
    subs = opts.get("sub_categories") or []
    comps = opts.get("competitors") or []

    m = {"global": {}}
    if fps:
        m["fp_first"] = {"fp_names": fps[0]}
        if len(fps) > 2:
            m["fp_multi"] = {"fp_names": ",".join(fps[:3])}
    if cats:
        m["category"] = {"main_category": cats[0]}
    if subs:
        m["subcategory"] = {"sub_category": subs[0]}
    if comps:
        m["competitor"] = {"competitor": comps[0]}
        if len(comps) > 1:
            m["competitor_multi"] = {"competitor": ",".join(comps[:2])}
    m["vertical_supermarket"] = {"vertical": "supermarket"}
    m["vertical_beauty"] = {"vertical": "beauty"}
    m["excl_private_label"] = {"exclude_private_label": True}
    if fps and comps:
        m["fp_and_competitor"] = {"fp_names": fps[0], "competitor": comps[0]}
    return m


def call(snapshot, key, fn, *args, **kwargs):
    try:
        snapshot[key] = norm(fn(*args, **kwargs))
    except Exception as exc:  # a method that raises must raise identically later
        snapshot[key] = {"__error__": f"{type(exc).__name__}: {exc}"}


def capture(svc):
    snap = {}

    # ---- filter option lists (these also prove no new values leaked in) ----
    call(snap, "filters/options", svc.get_filter_options)
    call(snap, "filters/fps", svc.get_fp_options)

    # ---- unfiltered / trend endpoints ----
    call(snap, "executive/summary", svc.get_executive_summary)
    call(snap, "executive/pi-trend", svc.get_pi_trend)
    call(snap, "executive/coverage-trend", svc.get_coverage_trend)
    call(snap, "executive/week-over-week", svc.get_week_over_week)

    for name, f in filter_matrix(svc).items():
        p = f"[{name}]"
        # Executive
        call(snap, f"executive/dashboard {p}", svc.get_executive_dashboard, f)
        call(snap, f"executive/category-performance {p}", svc.get_category_performance, f)
        call(snap, f"executive/fp-competitor-pi {p}", svc.get_fp_competitor_pi, f, False)
        call(snap, f"executive/fp-competitor-pi+fallback {p}", svc.get_fp_competitor_pi, f, True)
        # Commercial
        call(snap, f"commercial/kpis {p}", svc.get_kpi_summary, f)
        call(snap, f"commercial/blended-pi.sub {p}", svc.get_blended_pi_by_subcategory, f, "sub_category")
        call(snap, f"commercial/blended-pi.cat {p}", svc.get_blended_pi_by_subcategory, f, "commercial_category")
        call(snap, f"commercial/funnel {p}", svc.get_coverage_funnel, f)
        # get_all_products returns the full frame the /products route slices;
        # snapshot a stable head so the diff stays readable but still catches
        # row-set and per-row value changes.
        call(snap, f"commercial/products.count {p}", lambda ff: len(svc.get_all_products(ff)), f)
        call(
            snap,
            f"commercial/products.head {p}",
            lambda ff: svc.get_all_products(ff)
            .sort_values(["product_id", "competitor_name"], na_position="last")
            .head(25),
            f,
        )
        call(
            snap,
            f"commercial/products-pivoted {p}",
            svc.get_products_pivoted,
            f, 1, 25, None, "desc", None,
        )
        # Master data
        call(snap, f"master-data/action-summary {p}", svc.get_action_summary, f)
        call(snap, f"master-data/action-breakdown {p}", svc.get_action_breakdown, f)
        call(snap, f"master-data/worklist {p}", svc.get_worklist, f, 1, 50)
        call(snap, f"master-data/match-reviews {p}", svc.get_match_reviews, f, 1, 50)
        call(snap, f"master-data/staleness-heatmap {p}", svc.get_staleness_heatmap, f)

    return snap


# --------------------------------------------------------------------- diff
def flatten(o, prefix=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = o
    return out


def canonicalize(o):
    """Sort every list-of-records by its own content.

    DuckDB aggregates in parallel, so the ROW ORDER of a result set (and of the
    nested product_pis lists) is not stable between two runs of the *same* code
    on the *same* data. Comparing raw order therefore reports thousands of
    phantom diffs — two adjacent subcategories swapping places looks like every
    one of their fields changed. Sorting by content compares the row *sets*,
    which is what "did any number move?" actually means.
    """
    if isinstance(o, dict):
        return {k: canonicalize(v) for k, v in o.items()}
    if isinstance(o, list):
        items = [canonicalize(v) for v in o]
        if items and all(isinstance(i, (dict, list)) for i in items):
            items.sort(key=lambda i: json.dumps(i, sort_keys=True, default=str))
        return items
    return o


def _rows(v):
    """Serialize a list entry as a multiset of row strings."""
    from collections import Counter
    return Counter(json.dumps(r, sort_keys=True, default=str) for r in v)


def do_diff(before_path, after_path, canonical=True):
    a = json.loads(Path(before_path).read_text())
    b = json.loads(Path(after_path).read_text())
    if canonical:
        a, b = canonicalize(a), canonicalize(b)

    keys = sorted(set(a) | set(b))
    bad = []
    for k in keys:
        if k not in a or k not in b:
            bad.append((k, "entry only on one side", None, None))
        elif a[k] != b[k]:
            bad.append((k, None, a[k], b[k]))

    n_leaves = len(flatten(a))
    print(f"{len(keys)} entries, {n_leaves:,} leaf values compared"
          + ("  (row order canonicalized)" if canonical else "  (raw order)"))
    if not bad:
        print("\n*** IDENTICAL — every existing number is unchanged. ***")
        return 0

    print(f"\n{len(bad)} ENTRIES DIFFER:\n")
    for k, note, av, bv in bad:
        print(f"── {k}")
        if note:
            print(f"     {note}")
        elif isinstance(av, list) and isinstance(bv, list):
            ra, rb = _rows(av), _rows(bv)
            only_a, only_b = ra - rb, rb - ra
            if not only_a and not only_b:
                print(f"     same {len(av)} rows, order only")
                continue
            print(f"     rows: {len(av)} → {len(bv)};  "
                  f"{sum(only_a.values())} only-before, {sum(only_b.values())} only-after")
            for r in list(only_a)[:3]:
                print(f"       - {r[:220]}")
            for r in list(only_b)[:3]:
                print(f"       + {r[:220]}")
        else:
            fa, fb = flatten(av), flatten(bv)
            ch = [x for x in set(fa) & set(fb) if fa[x] != fb[x]]
            for x in sorted(ch)[:12]:
                print(f"       {x}: {fa[x]!r} → {fb[x]!r}")
            for x in sorted(set(fa) - set(fb))[:5]:
                print(f"       - {x}: {fa[x]!r}")
            for x in sorted(set(fb) - set(fa))[:5]:
                print(f"       + {x}: {fb[x]!r}")
    return 1


def main():
    if sys.argv[1:2] == ["--diff"]:
        args = [a for a in sys.argv[2:] if a != "--raw"]
        sys.exit(do_diff(args[0], args[1], canonical="--raw" not in sys.argv))

    out = sys.argv[1]
    if len(sys.argv) > 2:
        os.environ["DUCKDB_PARQUET_PATH"] = str(Path(sys.argv[2]).resolve())
    os.environ.setdefault("DATA_SOURCE", "bigquery")

    from backend.services import create_data_service_from_parquet

    svc = create_data_service_from_parquet()
    if svc is None:
        raise SystemExit("could not build the service from Parquet")
    print(f"service: {type(svc).__name__}")

    snap = capture(svc)
    Path(out).write_text(json.dumps(snap, indent=1, sort_keys=True))
    print(f"wrote {out}: {len(snap)} entries, {len(flatten(snap)):,} leaf values")


if __name__ == "__main__":
    main()
