from fastapi import APIRouter, Request, Query
from typing import Optional

router = APIRouter(prefix="/api/filters", tags=["filters"])


@router.get("/categories")
def get_categories(request: Request):
    svc = request.app.state.data_service
    options = svc.get_filter_options()
    return {"categories": options["main_categories"]}


@router.get("/main-categories")
def get_main_categories(request: Request, vertical: Optional[str] = Query(None)):
    # Storefront main category (main_category_name) — not the commercial
    # category that /categories serves. Narrowed by the Vertical it derives.
    svc = request.app.state.data_service
    options = svc.get_filter_options(vertical=vertical)
    return {"main_categories": options["storefront_main_categories"]}


@router.get("/subcategories")
def get_subcategories(
    request: Request,
    main: Optional[str] = Query(None, description="commercial category (comma-separated)"),
    main_category_name: Optional[str] = Query(None, description="storefront main category (comma-separated)"),
):
    svc = request.app.state.data_service
    options = svc.get_filter_options(main_category=main, main_category_name=main_category_name)
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


@router.get("/competitors")
def get_competitors(request: Request):
    svc = request.app.state.data_service
    options = svc.get_filter_options()
    return {"competitors": options.get("competitors", [])}


@router.get("/fps")
def get_fps(request: Request):
    svc = request.app.state.data_service
    return {"fps": svc.get_fp_options()}
