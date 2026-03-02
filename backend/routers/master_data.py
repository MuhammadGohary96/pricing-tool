import math
from fastapi import APIRouter, Depends, Query, Request
from typing import Optional

router = APIRouter(prefix="/api/master-data", tags=["master-data"])


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


@router.get("/action-summary")
def get_action_summary(request: Request, filters: dict = Depends(_filters)):
    svc = request.app.state.data_service
    return svc.get_action_summary(filters)


@router.get("/action-breakdown")
def get_action_breakdown(request: Request, filters: dict = Depends(_filters)):
    svc = request.app.state.data_service
    return svc.get_action_breakdown(filters)


@router.get("/worklist")
def get_worklist(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    filters: dict = Depends(_filters),
):
    svc = request.app.state.data_service
    return svc.get_worklist(filters, page=page, page_size=page_size)


@router.get("/match-reviews")
def get_match_reviews(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    filters: dict = Depends(_filters),
):
    svc = request.app.state.data_service
    return svc.get_match_reviews(filters, page=page, page_size=page_size)


@router.get("/staleness-heatmap")
def get_staleness_heatmap(request: Request, filters: dict = Depends(_filters)):
    svc = request.app.state.data_service
    return svc.get_staleness_heatmap(filters)
