from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional

router = APIRouter(prefix="/api/executive", tags=["executive"])


def _filters(
    main_category: Optional[str] = Query(None),
    sub_category: Optional[str] = Query(None),
    global_tier: Optional[str] = Query(None),
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


@router.get("/summary")
def get_summary(request: Request):
    svc = request.app.state.data_service
    return svc.get_executive_summary()


@router.get("/dashboard")
def get_dashboard(request: Request, filters: dict = Depends(_filters)):
    # Product-level aggregates are unaffected by the competitor price fallback
    # (it is a purely FP-grain effect — see get_fp_competitor_pi).
    svc = request.app.state.data_service
    return svc.get_executive_dashboard(filters)


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


@router.get("/fp-competitor-pi")
def get_fp_competitor_pi(
    request: Request,
    price_fallback: bool = Query(False),
    filters: dict = Depends(_filters),
):
    """Blended PI per (fulfillment point × competitor) — geographic exposure.

    price_fallback=true fills mapped-but-not-fresh FP cells with the
    per-(product, competitor) modal price, counted as estimated.
    """
    svc = request.app.state.data_service
    return svc.get_fp_competitor_pi(filters, price_fallback=price_fallback)


@router.get("/competitor-overview")
def get_competitor_overview(request: Request, filters: dict = Depends(_filters)):
    """Matching + assortment coverage per competitor — the live equivalent of the
    hand-maintained "Competitor Overview" workbook sheet.

    DuckDB-only, like /fp-competitor-pi: no @abstractmethod is added to
    data_interface.py because that ABC is enforced at instantiation and would
    break DATA_SOURCE=mock.
    """
    svc = request.app.state.data_service
    if svc is None or not hasattr(svc, "get_competitor_overview"):
        raise HTTPException(
            status_code=503,
            detail="Competitor overview requires the DuckDB data service "
                   "(DATA_SOURCE=bigquery with USE_DUCKDB enabled).",
        )
    return svc.get_competitor_overview(filters)


@router.get("/week-over-week")
def get_week_over_week(request: Request):
    svc = request.app.state.data_service
    return svc.get_week_over_week()


@router.get("/top-actions")
def get_top_actions(request: Request, limit: int = Query(10, ge=1, le=50), filters: dict = Depends(_filters)):
    """Top revenue products that need action, sorted by revenue descending."""
    import math

    svc = request.app.state.data_service
    df = svc.get_all_products(filters)
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


# ─────────────────────────────────────────────────────────────────────────────
# Styled workbook export
# ─────────────────────────────────────────────────────────────────────────────
# Same reasoning as /api/gap/workbook: the community build of SheetJS writes
# values but no cell formatting, so a browser-built file can only ever be an
# unformatted grid. openpyxl on the server gives the house style — title,
# uppercase headers on a light fill, zebra striping, frozen header, autofilter,
# threshold colours — and Executive, Commercial and Gap all stream the same one.
@router.get("/workbook")
def export_workbook(
    request: Request,
    filters: dict = Depends(_filters),
    competitors: Optional[str] = Query(
        None, description="Comma-separated rows to keep — the competitor pills, "
                          "which are client-side visibility and not part of the query."
    ),
):
    """Stream the competitor scorecard as a styled workbook."""
    from fastapi.responses import StreamingResponse
    from ..services.excel_report import build_workbook
    from ..services.report_sheets import executive_scorecard_sheets

    svc = request.app.state.data_service
    if svc is None or not hasattr(svc, "get_competitor_overview"):
        raise HTTPException(
            status_code=503,
            detail="The scorecard export requires the DuckDB data service.",
        )

    rows = svc.get_competitor_overview(filters)
    if competitors:
        keep = {c.strip() for c in competitors.split(",") if c.strip()}
        rows = [r for r in rows if r.get("competitor_name") in keep]

    # One sheet per on-screen table, so a sheet can be sent on its own. The Gap
    # workbook keeps the single combined sheet, which mirrors a hand-built file.
    return StreamingResponse(
        build_workbook(executive_scorecard_sheets(rows)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Competitor_Scorecard.xlsx"'},
    )
