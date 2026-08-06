"""Brand & Subcategory Gap Analysis.

Answers, per brand and per Breadfast subcategory, for a given competitor: how
much of our assortment is matched and how much *can* be, which brands we share
/ own alone / they own alone, which of their products we do not carry, and the
price position + commercial weight of every gap.

Two populations are served side by side — our products (FP grain collapsed to
product grain) and the competitor-only catalogue (national). See
DuckDBPricingDataService.get_gap_* for why they must not be mixed.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional

router = APIRouter(prefix="/api/gap", tags=["gap"])


def _filters(
    competitor: Optional[str] = Query(None),
    main_category: Optional[str] = Query(None),
    sub_category: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    global_tier: Optional[str] = Query(None),
    subcat_tier: Optional[str] = Query(None),
    fp_names: Optional[str] = Query(None),
    # Scope now uses the same two controls as Executive and Commercial, so one
    # filter bar drives all three views. The old `scope=excl_beauty_pl` enum is
    # gone; use vertical=Supermarket + exclude_private_label=true for what it
    # used to mean. Default is unscoped, matching the other two views.
    vertical: Optional[str] = Query(None, description="Beauty | Supermarket"),
    exclude_private_label: Optional[bool] = Query(None),
) -> dict:
    params: dict = {}
    if competitor:
        params["competitor"] = competitor
    if main_category:
        params["main_category"] = main_category
    if sub_category:
        params["sub_category"] = sub_category
    if brand:
        params["brand"] = brand
    if global_tier:
        params["global_tier"] = global_tier
    if subcat_tier:
        params["subcat_tier"] = subcat_tier
    if fp_names:
        params["fp_names"] = fp_names
    if vertical:
        params["vertical"] = vertical
    if exclude_private_label:
        params["exclude_private_label"] = True
    return params


def _svc(request: Request):
    """The gap grain is DuckDB-only.

    Deliberately not added to the data_interface ABC: that contract is enforced
    at instantiation, so a new abstract method would break DATA_SOURCE=mock
    outright. Same precedent as get_fp_competitor_pi / get_product_fp_matrix.
    """
    svc = request.app.state.data_service
    if svc is None or not hasattr(svc, "get_gap_kpis"):
        raise HTTPException(
            status_code=503,
            detail="Gap analysis requires the DuckDB data service "
                   "(DATA_SOURCE=bigquery with USE_DUCKDB enabled).",
        )
    return svc


@router.get("/filters")
def get_gap_filters(request: Request):
    """Option lists for the tab's own controls. Competitors carry their
    catalogue flag so the UI can explain an empty competitor rather than
    silently showing zeros."""
    return _svc(request).get_gap_filter_options()


@router.get("/kpis")
def get_kpis(request: Request, filters: dict = Depends(_filters)):
    return _svc(request).get_gap_kpis(filters)


@router.get("/subcategories")
def get_subcategories(request: Request, filters: dict = Depends(_filters)):
    return _svc(request).get_gap_by_subcategory(filters)


@router.get("/brands")
def get_brands(
    request: Request,
    filters: dict = Depends(_filters),
    brand_type: Optional[str] = Query(None, description="shared | bf_only | comp_only"),
    limit: int = Query(300, ge=1, le=5000),
):
    rows = _svc(request).get_gap_by_brand(filters)
    if brand_type:
        wanted = {t.strip() for t in brand_type.split(",") if t.strip()}
        rows = [r for r in rows if r["brand_type"] in wanted]
    return {"items": rows[:limit], "total_count": len(rows)}


@router.get("/products")
def get_products(
    request: Request,
    filters: dict = Depends(_filters),
    side: str = Query("breadfast", description="breadfast | competitor"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_dir: str = Query("desc"),
):
    return _svc(request).get_gap_products(
        filters, side=side, page=page, page_size=page_size,
        search=search, sort_by=sort_by, sort_dir=sort_dir,
    )


@router.get("/export")
def export_gap(
    request: Request,
    filters: dict = Depends(_filters),
    view: str = Query("subcategories", description="subcategories | brands | products"),
    side: str = Query("breadfast", description="products view only: breadfast | competitor"),
):
    """Full unpaginated rows for the shared ExportButton path."""
    svc = _svc(request)
    if view == "brands":
        return svc.get_gap_by_brand(filters)
    if view == "products":
        return svc.get_gap_products(
            filters, side=side, page=1, page_size=100_000
        )["items"]
    return svc.get_gap_by_subcategory(filters)
