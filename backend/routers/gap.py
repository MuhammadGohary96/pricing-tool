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
    brand_scope: Optional[str] = Query(
        None, description="'shared' = only products whose brand the competitor also carries"
    ),
    # Scope uses the same two controls as Executive and Commercial, so one filter
    # bar drives all three views. The old `scope=excl_beauty_pl` enum is gone;
    # vertical=Supermarket + exclude_private_label=true is what it used to mean.
    # Default is unscoped, matching the other two views.
    vertical: Optional[str] = Query(None, description="Beauty | Supermarket"),
    exclude_private_label: Optional[bool] = Query(None),
    private_label_only: Optional[bool] = Query(None),
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
    if brand_scope:
        params["brand_scope"] = brand_scope
    if vertical:
        params["vertical"] = vertical
    if exclude_private_label:
        params["exclude_private_label"] = True
    if private_label_only:
        params["private_label_only"] = True
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
    brand_type: Optional[str] = Query(
        None, description="shared | bf_only | comp_only | by_match (combinable)"),
    limit: int = Query(300, ge=1, le=5000),
):
    rows = _svc(request).get_gap_by_brand(filters)
    if brand_type:
        wanted = {t.strip() for t in brand_type.split(",") if t.strip()}
        # by_match is a cross-cutting view, not a brand_type: those brands ARE
        # shared and must keep showing under 'shared'. Selecting it asks "which
        # brands did the match evidence promote", which is an audit of the rule
        # rather than a category of brand.
        by_match = "by_match" in wanted
        wanted.discard("by_match")
        rows = [
            r for r in rows
            if (by_match and r.get("shared_by_match"))
            or (wanted and r["brand_type"] in wanted)
        ]
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


# ─────────────────────────────────────────────────────────────────────────────
# Styled workbook export
# ─────────────────────────────────────────────────────────────────────────────
# Built server-side, not in the browser: the community build of SheetJS cannot
# write cell styling at all, so a client-side workbook can only ever be an
# unformatted grid. openpyxl gives the house style — title, uppercase headers on
# a light fill, zebra striping, frozen header, autofilter, threshold colours.
#
# Percentages are divided by 100 on the way out. The service returns 20.3 and the
# cells carry a 0.0% number format, which multiplies by 100 for display — writing
# 20.3 straight in would render 2030%.
from ..services.excel_report import pct as _pct, num as _num, metric_col as _metric
# Shared with Executive, which renders the same panel on screen.
from ..services.report_sheets import competitor_overview_sheet


_TYPE_LABEL = {"shared": "Shared", "bf_only": "Only ours", "comp_only": "Only theirs"}


def _variant_names(raw: str) -> str:
    """"Nestle:45|Paradise:39" -> "Nestle, Paradise".

    rfind, not split(':'), because a brand name can contain one. Entries whose
    name half is blank are dropped: a competitor product with an empty (not
    NULL) brand_name encodes as ":1", which otherwise rode along to the end of
    the list looking like a parsing failure.
    """
    if not raw:
        return ""
    out = []
    for part in str(raw).split("|"):
        i = part.rfind(":")
        name = (part[:i] if i > 0 else "").strip()
        if name:
            out.append(name)
    return ", ".join(out)


def _brands_sheet(rows, competitor):
    return {
        "name": f"{competitor} Brands",
        "title": f"{competitor} — Brand Portfolio",
        "columns": [
            {"field": "brand", "header": "BRAND", "width": 26},
            {"field": "type", "header": "TYPE", "width": 14},
            # Neither column existed in the hand-built workbook, which could not
            # tell a name match from an evidence match: Froneri read "Only ours"
            # there at 95% mapped. THEIR BRAND NAMES lists every spelling on
            # their shelf, so 7Up / 7UP / 7up show as the three brands they are.
            {"field": "evidence", "header": "OVERLAP EVIDENCE", "width": 26},
            {"field": "their_names", "header": "THEIR BRAND NAMES", "width": 44},
            {"field": "bf_products", "header": "BF PRODUCTS", "format": "number"},
            {"field": "matched", "header": "MAPPED", "format": "number"},
            _metric("mapping_pct", "MAPPING %"),
            {"field": "confirmed_no_match", "header": "CONFIRMED NO-MATCH", "format": "number"},
            _metric("addressable_pct", "ADDRESSABLE RATE"),
            {"field": "potential_match", "header": "POTENTIAL MATCH", "format": "number"},
            {"field": "bf_unmatched", "header": "BF UNMATCHED", "format": "number"},
            {"field": "comp_catalogue", "header": "THEIR CATALOGUE", "format": "number"},
            {"field": "comp_only_products", "header": "COMP-ONLY PRODUCTS", "format": "number"},
            {"field": "our_only_products", "header": "OURS-ONLY PRODUCTS", "format": "number"},
            {"field": "bf_subcategories", "header": "OUR SUBCATEGORIES", "format": "number"},
            {"field": "comp_subcategories", "header": "THEIR SUBCATEGORIES", "format": "number"},
            {"field": "daily_revenue", "header": "REVENUE/DAY", "format": "number"},
            {"field": "unmatched_revenue", "header": "UNMATCHED REVENUE", "format": "number"},
        ],
        "rows": [{
            "brand": r.get("brand_name"),
            "type": _TYPE_LABEL.get(r.get("brand_type"), r.get("brand_type")),
            "evidence": "Matched under another name" if r.get("shared_by_match") else "Brand name",
            "their_names": _variant_names(r.get("comp_brand_variants")),
            "bf_products": _num(r.get("bf_products")),
            "matched": _num(r.get("matched")),
            "mapping_pct": _pct(r.get("mapping_pct")),
            "confirmed_no_match": _num(r.get("confirmed_no_match")),
            "addressable_pct": _pct(r.get("addressable_pct")),
            "potential_match": _num(r.get("potential_match")),
            "bf_unmatched": _num(r.get("bf_products")) - _num(r.get("matched")),
            "comp_catalogue": _num(r.get("comp_catalogue")),
            "comp_only_products": _num(r.get("comp_only_products")),
            "our_only_products": _num(r.get("our_only_products")),
            "bf_subcategories": _num(r.get("bf_subcategories")),
            "comp_subcategories": _num(r.get("comp_subcategories")),
            "daily_revenue": _num(r.get("daily_revenue")),
            "unmatched_revenue": _num(r.get("unmatched_revenue")),
        } for r in rows],
    }


def _subcategories_sheet(rows, competitor):
    return {
        "name": f"{competitor} Subcategories",
        "title": f"{competitor} — Subcategory Coverage",
        "note": "Brand sets are WITHIN-SUBCATEGORY: a brand can be shared in one "
                "subcategory and ours-only in another.",
        "columns": [
            {"field": "sub_category_name", "header": "SUBCATEGORY", "width": 30},
            {"field": "commercial_category_name", "header": "COMMERCIAL CATEGORY", "width": 26},
            {"field": "bf_products", "header": "BF PRODUCTS", "format": "number"},
            {"field": "matched", "header": "MAPPED", "format": "number"},
            _metric("mapping_pct", "MAPPING %"),
            _metric("mapping_pct_shared", "MAPPING % (SHARED BRANDS)", width=22),
            {"field": "confirmed_no_match", "header": "CONFIRMED NO-MATCH", "format": "number"},
            {"field": "potential_match", "header": "POTENTIAL MATCH", "format": "number"},
            _metric("addressable_pct", "ADDRESSABLE RATE"),
            {"field": "matched_but_stale", "header": "MAPPED BUT STALE", "format": "number"},
            {"field": "comp_catalogue", "header": "THEIR CATALOGUE", "format": "number"},
            {"field": "comp_only_products", "header": "COMP-ONLY PRODUCTS", "format": "number"},
            {"field": "shared_brands", "header": "SHARED BRANDS #", "format": "number"},
            {"field": "shared_by_match_brands", "header": "SHARED BRANDS # (BY MATCH)", "format": "number", "width": 22},
            {"field": "bf_only_brands", "header": "BF-ONLY BRANDS #", "format": "number"},
            {"field": "comp_only_brands", "header": "COMP-ONLY BRANDS #", "format": "number"},
            {"field": "daily_revenue", "header": "REVENUE/DAY", "format": "number"},
            {"field": "unmatched_revenue", "header": "UNMATCHED REVENUE", "format": "number"},
        ],
        "rows": [{
            "sub_category_name": r.get("sub_category_name"),
            "commercial_category_name": r.get("commercial_category_name"),
            "bf_products": _num(r.get("bf_products")),
            "matched": _num(r.get("matched")),
            "mapping_pct": _pct(r.get("mapping_pct")),
            "mapping_pct_shared": _pct(r.get("mapping_pct_shared")),
            "confirmed_no_match": _num(r.get("confirmed_no_match")),
            "potential_match": _num(r.get("potential_match")),
            "addressable_pct": _pct(r.get("addressable_pct")),
            "matched_but_stale": _num(r.get("matched_but_stale")),
            "comp_catalogue": _num(r.get("comp_catalogue")),
            "comp_only_products": _num(r.get("comp_only_products")),
            "shared_brands": _num(r.get("shared_brands")),
            "shared_by_match_brands": _num(r.get("shared_by_match_brands")),
            "bf_only_brands": _num(r.get("bf_only_brands")),
            "comp_only_brands": _num(r.get("comp_only_brands")),
            "daily_revenue": _num(r.get("daily_revenue")),
            "unmatched_revenue": _num(r.get("unmatched_revenue")),
        } for r in rows],
    }


def _portfolio_sheet(rows, competitor):
    return {
        "name": f"{competitor} Portfolio",
        "title": f"{competitor} — Product Portfolio",
        "note": "Both sides in one sheet: SIDE says whose shelf the row is from.",
        "bold_first_col": False,
        "columns": [
            {"field": "brand", "header": "BRAND", "width": 24},
            {"field": "side", "header": "SIDE", "width": 12},
            {"field": "status", "header": "STATUS", "width": 22},
            {"field": "bf_product_name", "header": "BF_PRODUCT_NAME", "width": 44},
            {"field": "bf_sub_category", "header": "BF_SUB_CATEGORY", "width": 26},
            {"field": "mapped_bf_sub_category", "header": "MAPPED_BF_SUB_CATEGORY", "width": 26},
            {"field": "bridge_level", "header": "BRIDGE_LEVEL", "width": 18},
            {"field": "comp_product_name", "header": "COMP_PRODUCT_NAME", "width": 44},
            {"field": "comp_brand_name", "header": "COMP_BRAND_NAME", "width": 22},
            {"field": "category_level_1", "header": "CATEGORY_LEVEL_1", "width": 22},
            {"field": "category_level_2", "header": "CATEGORY_LEVEL_2", "width": 22},
            {"field": "category_level_3", "header": "CATEGORY_LEVEL_3", "width": 22},
            {"field": "is_shared_brand", "header": "IS_SHARED_BRAND", "width": 15},
            {"field": "matched_comp_active_7d", "header": "MATCHED_COMP_ACTIVE_7D", "width": 20},
            {"field": "is_potential_match", "header": "IS_POTENTIAL_MATCH", "width": 18},
            {"field": "best_similarity", "header": "BEST_SIMILARITY_SCORE", "format": "percent2",
             "width": 18},
        ],
        "rows": [_portfolio_row(r) for r in rows],
    }


def _portfolio_status(r: dict) -> str:
    """The label the screen shows, reproduced for the file.

    Not returned by the API -- the UI derives it -- so the export used to read a
    key that never existed and wrote an empty STATUS column for every row.
    """
    if r.get("_side") == "Competitor":
        return "They only"
    if r.get("is_mapped"):
        return "Mapped" if r.get("matched_comp_active_7d") else "Mapped · stale"
    if r.get("is_confirmed_no_match"):
        return "Confirmed no match"
    if r.get("is_potential_match"):
        return "Potential match"
    return "Unresolved"


def _portfolio_row(r: dict) -> dict:
    """One Portfolio row, mapped SIDE-AWARE.

    The two populations arrive under the SAME key names -- `product_name` is our
    product on a Breadfast row and theirs on a competitor row, `brand_name`
    likewise, and `sub_category_name` is our subcategory on one side and the
    BRIDGED one on the other. Reading them blind put their product names in the
    BF column and left MAPPED_BF_SUB_CATEGORY, COMP_PRODUCT_NAME and
    COMP_BRAND_NAME empty, because those keys are never present under those
    names at all.
    """
    theirs = r.get("_side") == "Competitor"
    # Their brand for one of OUR products comes from the brand-variants string
    # ("Nestle:45|Paradise:39"); take the biggest, which is first.
    variants = _variant_names(r.get("comp_brand_variants"))
    return {
        # Whosever brand it is: ours on a Breadfast row, theirs on a competitor
        # row. The SIDE column says which, so one key serves both.
        "brand": r.get("brand_name") or "",
        "side": r.get("_side"),
        "status": _portfolio_status(r),
        "bf_product_name": "" if theirs else (r.get("product_name") or ""),
        "bf_sub_category": "" if theirs else (r.get("sub_category_name") or ""),
        # Ours sits in its own subcategory; theirs is placed by the bridge, and
        # the API returns that placement as sub_category_name.
        "mapped_bf_sub_category": r.get("sub_category_name") or "",
        "bridge_level": (r.get("bridge_level") or "") if theirs else "bf_own",
        "comp_product_name": (r.get("product_name") if theirs
                              else r.get("competitor_product_name")) or "",
        "comp_brand_name": (r.get("brand_name") if theirs
                            else (variants.split(", ")[0] if variants else "")) or "",
        "category_level_1": r.get("category_level_1") or "",
        "category_level_2": r.get("category_level_2") or "",
        "category_level_3": r.get("category_level_3") or "",
        "is_shared_brand": r.get("is_shared_brand"),
        "matched_comp_active_7d": r.get("matched_comp_active_7d"),
        "is_potential_match": r.get("is_potential_match"),
        "best_similarity": r.get("best_similarity"),
    }


@router.get("/workbook")
def export_workbook(
    request: Request,
    filters: dict = Depends(_filters),
    sheets: str = Query("all", description="all | brands | subcategories | products"),
):
    """Stream the gap analysis as a styled workbook."""
    from fastapi.responses import StreamingResponse
    from ..services.excel_report import build_workbook

    svc = _svc(request)
    competitor = (filters.get("competitor") or "Competitor").split(",")[0].strip()
    wanted = sheets.strip().lower()
    specs = []

    if wanted in ("all", "overview"):
        # Deliberately NOT competitor-scoped: this is the cross-competitor
        # summary, and narrowing it would leave a one-row sheet.
        all_comps = {k: v for k, v in filters.items() if k != "competitor"}
        specs.append(competitor_overview_sheet(svc.get_competitor_overview(all_comps)))
    if wanted in ("all", "brands"):
        specs.append(_brands_sheet(svc.get_gap_by_brand(filters), competitor))
    if wanted in ("all", "subcategories"):
        specs.append(_subcategories_sheet(svc.get_gap_by_subcategory(filters), competitor))
    if wanted in ("all", "products"):
        rows = []
        for side, label in (("breadfast", "Breadfast"), ("competitor", "Competitor")):
            page = svc.get_gap_products(filters, side=side, page=1, page_size=100_000)
            rows += [{**r, "_side": label} for r in page["items"]]
        specs.append(_portfolio_sheet(rows, competitor))

    if not specs:
        raise HTTPException(status_code=400, detail=f"unknown sheets value: {sheets}")

    safe = "".join(ch for ch in competitor if ch.isalnum()) or "Competitor"
    name = f"{safe}_Brand_Portfolio.xlsx" if wanted == "all" else f"{safe}_{wanted}.xlsx"
    return StreamingResponse(
        build_workbook(specs),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
