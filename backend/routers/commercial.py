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
    fp_names: Optional[str] = Query(None),
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
    if fp_names:
        params["fp_names"] = fp_names
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
