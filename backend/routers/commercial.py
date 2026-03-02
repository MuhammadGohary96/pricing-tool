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
from backend.models.product import ProductRow, ProductDetailTable, ProductPriceUpdate

router = APIRouter(prefix="/api/commercial", tags=["commercial"])


def _filters(
    main_category: Optional[str] = Query(None),
    sub_category: Optional[str] = Query(None),
    global_tier: Optional[str] = Query(None),
    subcat_tier: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    exclude_private_label: Optional[bool] = Query(None),
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
    if exclude_private_label:
        params["exclude_private_label"] = True
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
    svc = request.app.state.data_service
    df = svc.get_blended_pi_by_subcategory(filters)
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


@router.get("/blended-pi")
def get_blended_pi(request: Request, filters: dict = Depends(_filters)):
    svc = request.app.state.data_service
    df = svc.get_blended_pi_by_subcategory(filters)
    items = []
    for _, row in df.iterrows():
        raw_pis = row.get("product_pis", [])
        product_pis = [
            ProductPIPoint(
                product_name=p["product_name"],
                sale_PI=round(float(p["sale_PI"]), 4),
                weight=round(float(p["weight"]), 2),
            )
            for p in (raw_pis if isinstance(raw_pis, list) else [])
            if p.get("sale_PI") is not None
        ]
        items.append(BlendedPIRow(
            sub_category_name=row["sub_category_name"],
            blended_pi=_safe(row.get("blended_pi")),
            pi_deviation=_safe(row.get("pi_deviation")),
            direction=row["direction"],
            used_product_count=int(row["used_product_count"]),
            total_revenue=float(row["total_revenue"]),
            total_product_count=int(row.get("total_product_count", 0)),
            eligible_product_count=int(row.get("eligible_product_count", 0)),
            needs_action_count=int(row.get("needs_action_count", 0)),
            product_pis=product_pis,
        ))
    return BlendedPITable(items=items)


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
        "now_sale_price", "talabat_sale_price", "sale_PI", "global_tier",
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
            talabat_sale_price=_safe(row.get("talabat_sale_price")),
            talabat_regular_price=_safe(row.get("talabat_regular_price")),
            sale_PI=_safe(row.get("sale_PI")),
            has_PI=bool(row["has_PI"]),
            bf_price_updated_at=row.get("bf_price_updated_at"),
            talabat_price_updated_at=_safe(row.get("talabat_price_updated_at")),
            updated=bool(row["updated"]),
            similarity_score=_safe(row.get("similarity_score")),
            match_potential=bool(row["match_potential"]),
            used_product=bool(row["used_product"]),
            action_type=row["action_type"],
            pi_deviation=_safe(row.get("pi_deviation")),
            days_since_update=int(row["days_since_update"]) if _safe(row.get("days_since_update")) is not None else None,
            now_price=_safe(row.get("now_price")),
            now_sale_price=_safe(row.get("now_sale_price")),
            competitor_product_name=_safe(row.get("competitor_product_name")),
            match_potential_product_name=_safe(row.get("match_potential_product_name")),
        ))
    return ProductDetailTable(items=items, total_count=total)


@router.patch("/products/{product_id}")
def update_product_price(product_id: str, body: ProductPriceUpdate, request: Request):
    from backend.config import settings
    from backend.services.catalog_client import update_product_price as catalog_update

    # Use the user's Google token for Catalog API writes
    user_token = getattr(request.state, "access_token", None)

    catalog_synced = False
    catalog_error = None
    if product_id.isdigit() and user_token:
        try:
            catalog_update(
                base_url=settings.BF_CATALOG_URL,
                token=user_token,
                product_id=int(product_id),
                now_price=body.now_price,
                now_sale_price=body.now_sale_price,
            )
            catalog_synced = True
        except Exception as e:
            catalog_error = str(e)
            print(f"[Catalog] Write failed for product {product_id} ({getattr(request.state, 'email', '?')}): {e}")

    # Always update in-memory DataFrame so subsequent GETs reflect the change
    svc = request.app.state.data_service
    mask = svc._df["product_id"] == product_id
    if mask.any():
        if body.now_price is not None:
            svc._df.loc[mask, "now_price"] = body.now_price
        if body.now_sale_price is not None:
            svc._df.loc[mask, "now_sale_price"] = body.now_sale_price

    return {
        "ok": True,
        "product_id": product_id,
        "now_price": body.now_price,
        "now_sale_price": body.now_sale_price,
        "catalog_synced": catalog_synced,
        "catalog_error": catalog_error,
    }


@router.post("/catalog/enrich")
def enrich_catalog_prices(request: Request):
    """Bulk-fetch live prices from the Catalog API using the user's Google token."""
    import threading

    svc = request.app.state.data_service
    user_token = getattr(request.state, "access_token", None)
    enrichment = request.app.state.enrichment_status

    # Dev mode: no token available, skip catalog enrichment
    if not user_token:
        enrichment["done"] = True
        return {"ok": True, "already_enriched": True, "dev_mode": True}

    # Already enriched or in progress
    if enrichment.get("done"):
        return {"ok": True, "already_enriched": True}
    if enrichment.get("in_progress"):
        return {"ok": True, "in_progress": True}

    enrichment["in_progress"] = True
    enrichment["error"] = None

    def _enrich():
        try:
            matched = svc.enrich_with_catalog_prices(
                token=user_token,
                progress_status=enrichment,
            )
            enrichment["done"] = True
            enrichment["in_progress"] = False
            print(f"[Catalog] Enrichment complete — {matched} products enriched by {getattr(request.state, 'email', '?')}")
        except Exception as e:
            enrichment["error"] = str(e)
            enrichment["in_progress"] = False
            print(f"[Catalog] Enrichment failed: {e}")

    thread = threading.Thread(target=_enrich, daemon=True)
    thread.start()

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
        "bf_sale_price", "now_price", "now_sale_price", "talabat_sale_price", "sale_PI",
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
