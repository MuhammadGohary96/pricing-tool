import io
import math
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from typing import Optional

from backend.models.metrics import (
    TreemapNode,
    TreemapData,
    BlendedPIRow,
    BlendedPITable,
    ProductPIPoint,
)
from backend.models.product import ProductRow, ProductDetailTable

router = APIRouter(prefix="/api/commercial", tags=["commercial"])


def _filters(
    main_category: Optional[str] = Query(None),
    sub_category: Optional[str] = Query(None),
    global_tier: Optional[str] = Query(None),
    subcat_tier: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    competitor: Optional[str] = Query(None),
    vertical: Optional[str] = Query(None),
    exclude_private_label: Optional[bool] = Query(None),
    private_label_only: Optional[bool] = Query(None),
    fp_names: Optional[str] = Query(None),
    brand_scope: Optional[str] = Query(
        None, description="'shared' = only products whose brand the competitor also carries"
    ),
) -> dict:
    params = {}
    if main_category:
        params["main_category"] = main_category
    if sub_category:
        params["sub_category"] = sub_category
    if global_tier:
        params["global_tier"] = global_tier
    if subcat_tier:
        params["subcat_tier"] = subcat_tier
    if action_type:
        params["action_type"] = action_type
    if brand:
        params["brand"] = brand
    if competitor:
        params["competitor"] = competitor
    if vertical:
        params["vertical"] = vertical
    if exclude_private_label:
        params["exclude_private_label"] = True
    if private_label_only:
        params["private_label_only"] = True
    if fp_names:
        params["fp_names"] = fp_names
    if brand_scope:
        params["brand_scope"] = brand_scope
    return params


def _safe(val):
    """Convert NaN/None to None for JSON serialization."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


@router.get("/kpis")
def get_kpis(request: Request, filters: dict = Depends(_filters)):
    svc = request.app.state.data_service
    return svc.get_kpi_summary(filters)


@router.get("/treemap")
def get_treemap(request: Request, filters: dict = Depends(_filters)):
    # Product-level aggregate — unaffected by the competitor price fallback.
    svc = request.app.state.data_service
    df = svc.get_blended_pi_by_subcategory(filters)
    # The source method now also returns groups with nothing matched (so the
    # blended-PI table can flag them instead of hiding them). A treemap sizes by
    # revenue, so a zero-revenue node would be an invisible-but-present rect —
    # keep this panel exactly as it was.
    if "total_revenue" in df.columns:
        df = df[df["total_revenue"] > 0]
    children = []
    for _, row in df.iterrows():
        children.append(TreemapNode(
            name=row["sub_category_name"],
            value=float(row["total_revenue"]),
            blended_pi=_safe(row.get("blended_pi")),
            product_count=int(row["used_product_count"]),
            color_value=_safe(row.get("pi_deviation")),
        ))
    return TreemapData(children=children)


def _serialize_pi_points(raw_pis):
    """Convert raw product PI dicts to ProductPIPoint objects."""
    return [
        ProductPIPoint(
            product_name=p["product_name"],
            sale_PI=round(float(p["sale_PI"]), 4),
            weight=round(float(p["weight"]), 2),
        )
        for p in (raw_pis if isinstance(raw_pis, list) else [])
        if p.get("sale_PI") is not None
    ]


@router.get("/blended-pi")
def get_blended_pi(
    request: Request,
    filters: dict = Depends(_filters),
    group_by: str = Query("sub_category"),
):
    # Product-level aggregate — unaffected by the competitor price fallback.
    # group_by: 'sub_category' (default) | 'commercial_category' (rolled up).
    svc = request.app.state.data_service
    gb = group_by if group_by in ("sub_category", "commercial_category") else "sub_category"
    df = svc.get_blended_pi_by_subcategory(filters, group_by=gb)
    all_competitors = set()
    items = []
    for _, row in df.iterrows():
        product_pis = _serialize_pi_points(row.get("product_pis", []))

        # Per-competitor blended PIs
        comp_bpi = row.get("competitor_blended_pis", {})
        if not isinstance(comp_bpi, dict):
            comp_bpi = {}
        comp_bpi = {k: _safe(v) for k, v in comp_bpi.items()}
        all_competitors.update(comp_bpi.keys())

        # Per-competitor product PIs
        raw_comp_pis = row.get("competitor_product_pis", {})
        if not isinstance(raw_comp_pis, dict):
            raw_comp_pis = {}
        comp_product_pis = {
            comp_name: _serialize_pi_points(pis_list)
            for comp_name, pis_list in raw_comp_pis.items()
        }

        comp_used = row.get("competitor_used_counts", {})
        if not isinstance(comp_used, dict):
            comp_used = {}
        comp_actions = row.get("competitor_needs_action_counts", {})
        if not isinstance(comp_actions, dict):
            comp_actions = {}
        comp_eligible = row.get("competitor_eligible_counts", {})
        if not isinstance(comp_eligible, dict):
            comp_eligible = {}
        comp_mapped = row.get("competitor_mapped_counts", {})
        if not isinstance(comp_mapped, dict):
            comp_mapped = {}

        def _cdict(key):
            v = row.get(key, {})
            return v if isinstance(v, dict) else {}
        comp_addr = _cdict("competitor_addressable_pcts")
        comp_only = _cdict("competitor_comp_only_counts")
        comp_fresh = _cdict("competitor_matched_fresh_counts")
        comp_nomatch = _cdict("competitor_no_match_counts")
        comp_our_only = _cdict("competitor_our_only_counts")

        items.append(BlendedPIRow(
            group_key=str(row.get("group_key", row.get("sub_category_name")) or ""),
            sub_category_name=row.get("sub_category_name"),
            commercial_category_name=row.get("commercial_category_name"),
            blended_pi=_safe(row.get("blended_pi")),
            pi_deviation=_safe(row.get("pi_deviation")),
            direction=row["direction"],
            used_product_count=int(row["used_product_count"]),
            total_revenue=float(row["total_revenue"]),
            total_product_count=int(row.get("total_product_count", 0)),
            eligible_product_count=int(row.get("eligible_product_count", 0)),
            mapped_product_count=int(row.get("mapped_product_count", 0)),
            needs_action_count=int(row.get("needs_action_count", 0)),
            matched_fresh_count=int(row.get("matched_fresh_count", 0) or 0),
            confirmed_no_match_count=int(row.get("confirmed_no_match_count", 0) or 0),
            potential_match_count=int(row.get("potential_match_count", 0) or 0),
            addressable_pct=_safe(row.get("addressable_pct")),
            comp_only_products=int(row.get("comp_only_products", 0) or 0),
            our_only_count=int(row.get("our_only_count", 0) or 0),
            product_pis=product_pis,
            competitor_blended_pis=comp_bpi,
            competitor_product_pis=comp_product_pis,
            competitor_used_counts={k: int(v) for k, v in comp_used.items()},
            competitor_needs_action_counts={k: int(v) for k, v in comp_actions.items()},
            competitor_eligible_counts={k: int(v) for k, v in comp_eligible.items()},
            competitor_mapped_counts={k: int(v) for k, v in comp_mapped.items()},
            competitor_addressable_pcts={k: _safe(v) for k, v in comp_addr.items()},
            competitor_comp_only_counts={k: int(v or 0) for k, v in comp_only.items()},
            competitor_matched_fresh_counts={k: int(v or 0) for k, v in comp_fresh.items()},
            competitor_no_match_counts={k: int(v or 0) for k, v in comp_nomatch.items()},
            competitor_our_only_counts={k: int(v or 0) for k, v in comp_our_only.items()},
        ))
    return BlendedPITable(items=items, competitors=sorted(all_competitors))


@router.get("/products")
def get_products(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query("desc"),
    search: Optional[str] = Query(None),
    filters: dict = Depends(_filters),
):
    svc = request.app.state.data_service
    df = svc.get_all_products(filters)

    # Server-side search
    if search:
        q = search.lower()
        mask = (
            df["product_name"].str.lower().str.contains(q, na=False, regex=False)
            | df["brand_name"].str.lower().str.contains(q, na=False, regex=False)
        )
        df = df[mask]

    # Server-side sort
    SORTABLE = {
        "product_name", "brand_name", "bf_sale_price", "now_price",
        "now_sale_price", "competitor_sale_price", "sale_PI", "global_tier",
        "subcat_tier", "action_type", "total_revenue", "avg_daily_quantity",
        "similarity_score", "days_since_update",
    }
    if sort_by and sort_by in SORTABLE and sort_by in df.columns:
        ascending = sort_dir != "desc"
        df = df.sort_values(sort_by, ascending=ascending, na_position="last")
    else:
        # Default sort by revenue descending
        df = df.sort_values("total_revenue", ascending=False, na_position="last")

    total = len(df)
    start = (page - 1) * page_size
    page_df = df.iloc[start : start + page_size]

    items = []
    for _, row in page_df.iterrows():
        items.append(ProductRow(
            product_id=row["product_id"],
            product_name=row["product_name"],
            brand_name=row["brand_name"],
            main_category_name=row["main_category_name"],
            commercial_category_name=row["commercial_category_name"],
            sub_category_name=row["sub_category_name"],
            total_revenue=float(row["total_revenue"]),
            avg_daily_quantity=float(row["avg_daily_quantity"]),
            norm_revenue=float(row["norm_revenue"]),
            norm_quantity=float(row["norm_quantity"]),
            weighted_score=float(row["weighted_score"]),
            global_tier=row["global_tier"],
            subcat_tier=row["subcat_tier"],
            eligible_product=bool(row["eligible_product"]),
            bf_sale_price=float(row["bf_sale_price"]),
            bf_regular_price=float(row["bf_regular_price"]),
            competitor_id=int(row["competitor_id"]) if _safe(row.get("competitor_id")) is not None else None,
            competitor_name=_safe(row.get("competitor_name")),
            competitor_sale_price=_safe(row.get("competitor_sale_price")),
            min_competitor_sale_price=_safe(row.get("min_competitor_sale_price")),
            max_competitor_sale_price=_safe(row.get("max_competitor_sale_price")),
            sale_PI=_safe(row.get("sale_PI")),
            has_PI=bool(row["has_PI"]),
            bf_price_updated_at=row.get("bf_price_updated_at"),
            competitor_price_updated_at=_safe(row.get("competitor_price_updated_at")),
            updated=bool(row["updated"]),
            has_updated_price=bool(row.get("prices_recently_updated", False)),
            similarity_score=_safe(row.get("similarity_score")),
            match_potential=bool(row["match_potential"]),
            used_product=bool(row["used_product"]),
            action_type=row["action_type"],
            classification=_safe(row.get("classification")),
            pi_deviation=_safe(row.get("pi_deviation")),
            days_since_update=int(row["days_since_update"]) if _safe(row.get("days_since_update")) is not None else None,
            now_price=_safe(row.get("now_price")),
            now_sale_price=_safe(row.get("now_sale_price")),
            competitor_product_name=_safe(row.get("competitor_product_name")),
            match_potential_product_name=_safe(row.get("match_potential_product_name")),
        ))
    return ProductDetailTable(items=items, total_count=total)


@router.get("/products-pivoted")
def get_products_pivoted(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query("desc"),
    search: Optional[str] = Query(None),
    filters: dict = Depends(_filters),
):
    svc = request.app.state.data_service
    return svc.get_products_pivoted(
        filters=filters, page=page, page_size=page_size,
        sort_by=sort_by, sort_dir=sort_dir, search=search,
    )


@router.get("/products/{product_id}/fp-matrix")
def get_product_fp_matrix(
    request: Request,
    product_id: str,
    price_fallback: bool = Query(False),
    filters: dict = Depends(_filters),
):
    """Per-FP × per-competitor pricing matrix for a single product (modal view).

    price_fallback=true fills mapped-but-not-fresh cells with the
    product×competitor modal price (state 'estimated').
    """
    svc = request.app.state.data_service
    return svc.get_product_fp_matrix(product_id, filters, price_fallback=price_fallback)


@router.post("/catalog/enrich")
def enrich_catalog_prices(request: Request):
    """No-op. now_price/now_sale_price are now sourced from BigQuery
    (bf_regular_price / modal sale price), so we no longer fetch live prices
    from the Catalog API. Returns immediately as "done" so the frontend's
    enrichment poll completes without spinning.
    """
    enrichment = request.app.state.enrichment_status
    enrichment["done"] = True
    enrichment["in_progress"] = False
    enrichment["error"] = None
    return {"ok": True, "already_enriched": True, "source": "bigquery"}

    return {"ok": True, "started": True}


@router.get("/funnel")
def get_funnel(request: Request, filters: dict = Depends(_filters)):
    svc = request.app.state.data_service
    return svc.get_coverage_funnel(filters)


@router.get("/export")
def export_products(request: Request, filters: dict = Depends(_filters)):
    svc = request.app.state.data_service
    df = svc.get_all_products(filters)

    export_cols = [
        "product_id", "product_name", "brand_name", "commercial_category_name",
        "sub_category_name", "global_tier", "action_type",
        "bf_sale_price", "now_price", "now_sale_price",
        "competitor_name", "competitor_sale_price", "sale_PI",
        "total_revenue", "avg_daily_quantity", "days_since_update",
        "competitor_product_name", "match_potential_product_name", "similarity_score",
    ]
    export_df = df[[c for c in export_cols if c in df.columns]]

    buf = io.StringIO()
    export_df.to_csv(buf, index=False)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products_export.csv"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Styled workbook export
# ─────────────────────────────────────────────────────────────────────────────
# Rendered server-side for the same reason as /api/gap/workbook and
# /api/executive/workbook: the community build of SheetJS writes values but no
# cell formatting, so the browser cannot produce the house style at all.
#
# Percentages go out as FRACTIONS — the cells carry a 0.0% format, which
# multiplies by 100 for display, so writing 20.3 straight in renders 2030%.
from backend.services.excel_report import build_workbook, metric_col as _metric, pct as _pct


def _pi_col(field, header, width=None):
    """PI = BF ÷ competitor, so ABOVE 1.00 means WE ARE MORE EXPENSIVE. `invert`
    puts orange on the high side accordingly; a ±2% dead band keeps near-parity
    rows uncoloured instead of flipping on rounding noise."""
    col = {"field": field, "header": header, "format": "decimal2",
           "low_threshold": 0.98, "high_threshold": 1.02, "invert": True}
    if width:
        col["width"] = width
    return col


def _blended_rows(df, comps):
    """The blended-PI table as plain dicts, one per group, with the per-competitor
    dicts already resolved for `comps`."""
    out = []
    for _, row in df.iterrows():
        def _d(key):
            v = row.get(key, {})
            return v if isinstance(v, dict) else {}
        pis = {c: _safe(v) for c, v in _d("competitor_blended_pis").items() if c in comps}
        vals = [v for v in pis.values() if v is not None]
        out.append({
            "commercial_category_name": row.get("commercial_category_name") or "",
            "sub_category_name": row.get("sub_category_name") or "",
            "min_pi": min(vals) if vals else None,
            "max_pi": max(vals) if vals else None,
            "pis": pis,
            "total": int(row.get("total_product_count", 0) or 0),
            "eligible": int(row.get("eligible_product_count", 0) or 0),
            "used": _d("competitor_used_counts"),
            "mapped": _d("competitor_mapped_counts"),
            "addressable": _d("competitor_addressable_pcts"),
            "no_match": _d("competitor_no_match_counts"),
            "fresh": _d("competitor_matched_fresh_counts"),
            "comp_only": _d("competitor_comp_only_counts"),
            "our_only": _d("competitor_our_only_counts"),
        })
    # Matches the table's default sort — worst position first.
    out.sort(key=lambda r: (r["max_pi"] is None, -(r["max_pi"] or 0)))
    return out


def _blended_sheets(rows, comps, group_by):
    is_subcat = group_by == "sub_category"

    def base_cols(width=26):
        cols = [{"field": "commercial_category_name", "header": "COMMERCIAL CATEGORY", "width": width}]
        if is_subcat:
            cols.append({"field": "sub_category_name", "header": "SUBCATEGORY", "width": width})
        return cols

    def base_vals(r):
        v = {"commercial_category_name": r["commercial_category_name"]}
        if is_subcat:
            v["sub_category_name"] = r["sub_category_name"]
        return v

    # Sheet 1 reproduces what is on screen: every competitor's PI side by side,
    # so a row can be read across without opening seven tabs.
    grid = {
        "name": "Blended PI",
        "title": "Blended PI by " + ("subcategory" if is_subcat else "commercial category"),
        "note": "PI = Breadfast price ÷ competitor price. Above 1.00 means Breadfast is more expensive. "
                "Blank = nothing priced on both sides in that row.",
        "columns": [
            *base_cols(),
            _pi_col("min_pi", "MIN PI"),
            _pi_col("max_pi", "MAX PI"),
            *[_pi_col(f"pi::{c}", c.upper()) for c in comps],
            {"field": "total", "header": "TOTAL", "format": "number"},
            {"field": "eligible", "header": "ELIGIBLE", "format": "number"},
        ],
        "rows": [{
            **base_vals(r), "min_pi": r["min_pi"], "max_pi": r["max_pi"],
            **{f"pi::{c}": r["pis"].get(c) for c in comps},
            "total": r["total"], "eligible": r["eligible"],
        } for r in rows],
    }

    # Then one tab per competitor with that competitor's coverage detail — the
    # columns the table shows for whichever competitor header is selected.
    detail = []
    for comp in comps:
        detail.append({
            "name": comp,
            "title": f"{comp} — blended PI and coverage",
            "columns": [
                *base_cols(),
                _pi_col("blended_pi", "BLENDED PI"),
                {"field": "total", "header": "TOTAL", "format": "number"},
                {"field": "eligible", "header": "ELIGIBLE", "format": "number"},
                {"field": "used", "header": "USED", "format": "number"},
                {"field": "mapped", "header": "MAPPED", "format": "number"},
                _metric("mapping_pct", "MAPPED %"),
                _metric("utilization_pct", "UTIL %"),
                _metric("addressable_pct", "ADDR %", low=0.60, high=0.90),
                {"field": "no_match", "header": "CONFIRMED NO-MATCH", "format": "number"},
                {"field": "fresh", "header": "MAPPED FRESH", "format": "number"},
                *([{"field": "comp_only", "header": "THEY ONLY", "format": "number"}] if is_subcat else []),
                {"field": "our_only", "header": "OURS ONLY", "format": "number"},
            ],
            "rows": [{
                **base_vals(r),
                "blended_pi": r["pis"].get(comp),
                "total": r["total"],
                "eligible": r["eligible"],
                "used": r["used"].get(comp, 0),
                "mapped": r["mapped"].get(comp, 0),
                # Same denominators the table uses: Mapped % over TOTAL, Util %
                # over ELIGIBLE. Not interchangeable — eligible is the top-80%
                # revenue head, total is the whole row.
                "mapping_pct": _pct(round(100.0 * r["mapped"].get(comp, 0) / r["total"], 1)) if r["total"] else None,
                "utilization_pct": _pct(round(100.0 * r["used"].get(comp, 0) / r["eligible"], 1)) if r["eligible"] else None,
                "addressable_pct": _pct(r["addressable"].get(comp)),
                "no_match": r["no_match"].get(comp, 0),
                "fresh": r["fresh"].get(comp, 0),
                "comp_only": r["comp_only"].get(comp, 0),
                "our_only": r["our_only"].get(comp, 0),
            } for r in rows],
        })
    return [grid, *detail]


def _products_sheet(payload, comps):
    """The pivot, one row per product, priced against every competitor."""
    return {
        "name": "Products",
        "title": "Products — price position by competitor",
        "note": "PI = Breadfast price ÷ competitor price; above 1.00 means Breadfast is more expensive. "
                "Worst PI is the highest across competitors. Blank = no usable competitor price.",
        "columns": [
            {"field": "product_name", "header": "PRODUCT", "width": 46},
            {"field": "product_id", "header": "PRODUCT ID", "width": 14},
            {"field": "brand_name", "header": "BRAND", "width": 22},
            {"field": "sub_category_name", "header": "SUBCATEGORY", "width": 26},
            {"field": "global_tier", "header": "TIER", "width": 10},
            {"field": "action_type", "header": "ACTION", "width": 20},
            {"field": "bf_sale_price", "header": "BF SALE PRICE", "format": "decimal2"},
            _pi_col("worst_pi", "WORST PI"),
            {"field": "total_revenue", "header": "TOTAL REVENUE", "format": "number"},
            *[c for comp in comps for c in (
                {"field": f"{comp}_price", "header": f"{comp.upper()} PRICE", "format": "decimal2"},
                _pi_col(f"{comp}_pi", f"{comp.upper()} PI"),
            )],
        ],
        "rows": [{
            "product_name": r.get("product_name"),
            "product_id": r.get("product_id"),
            "brand_name": r.get("brand_name"),
            "sub_category_name": r.get("sub_category_name"),
            "global_tier": r.get("global_tier"),
            "action_type": r.get("action_type"),
            "bf_sale_price": r.get("bf_sale_price"),
            "worst_pi": r.get("worst_pi"),
            "total_revenue": r.get("total_revenue"),
            **{f"{comp}_{k}": r.get(f"{comp}_{k}") for comp in comps for k in ("price", "pi")},
        } for r in payload.get("items", [])],
    }


@router.get("/workbook")
def export_workbook(
    request: Request,
    filters: dict = Depends(_filters),
    sheets: str = Query("blended-pi", description="blended-pi | products"),
    group_by: str = Query("sub_category"),
    competitors: Optional[str] = Query(
        None, description="Comma-separated competitors to include — the pills, "
                          "which are client-side visibility and not part of the query."
    ),
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query("desc"),
    search: Optional[str] = Query(None),
):
    """Stream a Commercial table as a styled workbook."""
    svc = request.app.state.data_service
    wanted = sheets.strip().lower()
    wanted_comps = [c.strip() for c in (competitors or "").split(",") if c.strip()]

    if wanted == "products":
        # Every product, not just the page on screen. The client-side CSV this
        # replaced serialized `props.data`, which is one page of 50 — an export
        # that silently drops 99% of the rows is worse than no export.
        payload = svc.get_products_pivoted(
            filters=filters, page=1, page_size=1_000_000,
            sort_by=sort_by, sort_dir=sort_dir, search=search,
        )
        comps = [c for c in payload.get("competitors", []) if not wanted_comps or c in wanted_comps]
        specs = [_products_sheet(payload, comps)]
        name = "Products_Price_Position.xlsx"
    else:
        gb = group_by if group_by in ("sub_category", "commercial_category") else "sub_category"
        df = svc.get_blended_pi_by_subcategory(filters, group_by=gb)
        # Same competitor set the table draws columns for: the union of the
        # per-row PI dicts, keys included even where the value is null.
        found = set()
        for _, row in df.iterrows():
            d = row.get("competitor_blended_pis")
            if isinstance(d, dict):
                found.update(d)
        comps = [c for c in sorted(found) if not wanted_comps or c in wanted_comps]
        specs = _blended_sheets(_blended_rows(df, comps), comps, gb)
        name = "Blended_PI.xlsx"

    return StreamingResponse(
        build_workbook(specs),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
