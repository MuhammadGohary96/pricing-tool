from fastapi import APIRouter, Depends, Query, Request
from typing import Optional

router = APIRouter(prefix="/api/executive", tags=["executive"])


def _filters(
    main_category: Optional[str] = Query(None),
    sub_category: Optional[str] = Query(None),
    global_tier: Optional[str] = Query(None),
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
    if brand:
        params["brand"] = brand
    if exclude_private_label:
        params["exclude_private_label"] = True
    return params


@router.get("/summary")
def get_summary(request: Request):
    svc = request.app.state.data_service
    return svc.get_executive_summary()


@router.get("/pi-trend")
def get_pi_trend(request: Request):
    svc = request.app.state.data_service
    return svc.get_pi_trend()


@router.get("/coverage-trend")
def get_coverage_trend(request: Request):
    svc = request.app.state.data_service
    return svc.get_coverage_trend()


@router.get("/category-performance")
def get_category_performance(request: Request, filters: dict = Depends(_filters)):
    svc = request.app.state.data_service
    return svc.get_category_performance(filters)


@router.get("/week-over-week")
def get_week_over_week(request: Request):
    svc = request.app.state.data_service
    return svc.get_week_over_week()


@router.get("/top-actions")
def get_top_actions(request: Request, limit: int = Query(10, ge=1, le=50)):
    """Top revenue products that need action, sorted by revenue descending."""
    import math

    svc = request.app.state.data_service
    df = svc.get_all_products()
    # Filter to eligible products needing action
    needs = df[(df["eligible_product"] == True) & (df["action_type"] != "Complete")]
    needs = needs.sort_values("total_revenue", ascending=False).head(limit)

    def _safe(val):
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return val

    items = []
    for _, row in needs.iterrows():
        items.append({
            "product_id": row["product_id"],
            "product_name": row["product_name"],
            "sub_category_name": row["sub_category_name"],
            "action_type": row["action_type"],
            "total_revenue": round(float(row["total_revenue"]), 2),
            "bf_sale_price": _safe(row.get("bf_sale_price")),
            "sale_PI": _safe(row.get("sale_PI")),
        })
    return {"items": items}
