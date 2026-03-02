from fastapi import APIRouter, Request, Query
from typing import Optional

router = APIRouter(prefix="/api/filters", tags=["filters"])


@router.get("/categories")
def get_categories(request: Request):
    svc = request.app.state.data_service
    options = svc.get_filter_options()
    return {"categories": options["main_categories"]}


@router.get("/subcategories")
def get_subcategories(
    request: Request, main: Optional[str] = Query(None)
):
    svc = request.app.state.data_service
    options = svc.get_filter_options(main_category=main)
    return {"subcategories": options["sub_categories"]}


@router.get("/tiers")
def get_tiers(request: Request):
    svc = request.app.state.data_service
    options = svc.get_filter_options()
    return {
        "global_tiers": options["global_tiers"],
        "subcat_tiers": options["subcat_tiers"],
        "action_types": options["action_types"],
        "brands": options.get("brands", []),
    }
