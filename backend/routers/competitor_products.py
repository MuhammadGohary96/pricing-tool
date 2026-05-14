from fastapi import APIRouter, Depends, Query, Request
from typing import Optional

router = APIRouter(prefix="/api/competitor-products", tags=["competitor-products"])


def _filters(
    competitor: Optional[str] = Query(None),
    category_level_1: Optional[str] = Query(None),
    category_level_2: Optional[str] = Query(None),
    category_level_3: Optional[str] = Query(None),
    mapping_status: Optional[str] = Query(None),
    freshness: Optional[str] = Query(None),
    bf_date_from: Optional[str] = Query(None),
    bf_date_to: Optional[str] = Query(None),
    competitor_date_from: Optional[str] = Query(None),
    competitor_date_to: Optional[str] = Query(None),
) -> dict:
    params = {}
    if competitor:
        params["competitor"] = competitor
    if category_level_1:
        params["category_level_1"] = category_level_1
    if category_level_2:
        params["category_level_2"] = category_level_2
    if category_level_3:
        params["category_level_3"] = category_level_3
    if mapping_status:
        params["mapping_status"] = mapping_status
    if freshness:
        params["freshness"] = freshness
    if bf_date_from:
        params["bf_date_from"] = bf_date_from
    if bf_date_to:
        params["bf_date_to"] = bf_date_to
    if competitor_date_from:
        params["competitor_date_from"] = competitor_date_from
    if competitor_date_to:
        params["competitor_date_to"] = competitor_date_to
    return params


@router.get("/kpis")
def get_kpis(request: Request, filters: dict = Depends(_filters)):
    return request.app.state.data_service.get_competitor_products_kpis(filters)


@router.get("/crawl-timeline")
def get_crawl_timeline(request: Request, filters: dict = Depends(_filters)):
    return request.app.state.data_service.get_competitor_crawl_timeline(filters)


@router.get("/category-breakdown")
def get_category_breakdown(request: Request, filters: dict = Depends(_filters)):
    return request.app.state.data_service.get_competitor_category_breakdown(filters)


@router.get("/mapping-summary")
def get_mapping_summary(request: Request, filters: dict = Depends(_filters)):
    return request.app.state.data_service.get_competitor_mapping_summary(filters)


@router.get("/products")
def get_products(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_dir: str = Query("desc"),
    filters: dict = Depends(_filters),
):
    return request.app.state.data_service.get_competitor_products_list(
        filters, page=page, page_size=page_size,
        search=search, sort_by=sort_by, sort_dir=sort_dir,
    )


@router.get("/export")
def export_products(request: Request, filters: dict = Depends(_filters)):
    return request.app.state.data_service.get_competitor_products_export(filters)
