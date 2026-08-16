"""Sheet specs shared by more than one router.

`excel_report` is the generic writer — palette, layout, number formats. This
module holds the DOMAIN sheets that two views both export, so the same panel
cannot drift into two different files. Sheets used by only one router stay in
that router.

Right now that is the competitor overview: the Gap workbook ships it as the
cross-competitor summary tab, and the Executive scorecard IS it, so they must
agree column for column.
"""
from __future__ import annotations

from .excel_report import metric_col as _metric, num as _num, pct as _pct


# The scorecard's Price-position group. Only Executive shows these — the Gap
# workbook mirrors the hand-built Brand_Portfolio sheet, which has no PI column.
_PRICE_POSITION = [
    # PI = BF / competitor, so ABOVE 1.00 means we are more expensive. `invert`
    # flips the threshold colours accordingly: orange high, green low. Getting
    # this backwards is the single most-repeated mistake in this codebase.
    {"field": "blended_pi", "header": "BLENDED PI", "format": "decimal2",
     "low_threshold": 0.98, "high_threshold": 1.02, "invert": True},
    _metric("priced_pct", "UTIL %"),
    {"field": "eligible_products", "header": "ELIGIBLE", "format": "number"},
    {"field": "used_products", "header": "USED", "format": "number"},
]


def competitor_overview_sheet(rows, price_position: bool = False) -> dict:
    """One row per competitor: matching and assortment coverage.

    price_position=True adds Blended PI / Util % / Eligible / Used, which is the
    Executive scorecard's full column set.
    """
    return {
        "name": "Competitor Overview",
        "title": "Competitor Overview — matching and assortment coverage",
        "columns": [
            {"field": "competitor_name", "header": "COMPETITOR", "width": 16},
            *(_PRICE_POSITION if price_position else []),
            {"field": "bf_products", "header": "BF PRODUCTS", "format": "number"},
            {"field": "matched", "header": "MAPPED", "format": "number"},
            {"field": "matched_fresh", "header": "MAPPED FRESH", "format": "number"},
            _metric("mapping_pct", "MAPPING %"),
            _metric("mapping_pct_shared", "MAPPING % (SHARED BRANDS)", width=22),
            {"field": "confirmed_no_match", "header": "CONFIRMED NO-MATCH", "format": "number"},
            {"field": "addressable", "header": "ADDRESSABLE", "format": "number"},
            _metric("addressable_pct", "ADDRESSABLE %"),
            {"field": "potential_match", "header": "POTENTIAL MATCH", "format": "number"},
            {"field": "comp_products", "header": "THEIR CATALOGUE", "format": "number"},
            {"field": "comp_products_in_scope", "header": "THEIR CATALOGUE (IN SCOPE)",
             "format": "number", "width": 22},
            {"field": "comp_only_products", "header": "THEY ONLY", "format": "number"},
            {"field": "our_only_products", "header": "OURS ONLY", "format": "number"},
            {"field": "shared_brands", "header": "SHARED BRANDS", "format": "number"},
            *([{"field": "shared_by_match_brands", "header": "SHARED BRANDS (BY MATCH)",
                "format": "number", "width": 22}] if price_position else []),
            {"field": "bf_only_brands", "header": "BF-ONLY BRANDS", "format": "number"},
            {"field": "comp_only_brands", "header": "COMP-ONLY BRANDS", "format": "number"},
            {"field": "has_catalogue", "header": "HAS CATALOGUE", "width": 14},
        ],
        "rows": [{
            "competitor_name": r.get("competitor_name"),
            "blended_pi": r.get("blended_pi"),
            "priced_pct": _pct(r.get("priced_pct")),
            "eligible_products": _num(r.get("eligible_products")),
            "used_products": _num(r.get("used_products")),
            "bf_products": _num(r.get("bf_products")),
            "matched": _num(r.get("matched")),
            "matched_fresh": _num(r.get("matched_fresh")),
            "mapping_pct": _pct(r.get("mapping_pct")),
            "mapping_pct_shared": _pct(r.get("mapping_pct_shared")),
            "confirmed_no_match": _num(r.get("confirmed_no_match")),
            "addressable": _num(r.get("addressable")),
            "addressable_pct": _pct(r.get("addressable_pct")),
            "potential_match": _num(r.get("potential_match")),
            "comp_products": _num(r.get("comp_products")),
            "comp_products_in_scope": _num(r.get("comp_products_in_scope")),
            "comp_only_products": _num(r.get("comp_only_products")),
            "our_only_products": _num(r.get("our_only_products")),
            "shared_brands": _num(r.get("shared_brands")),
            "shared_by_match_brands": _num(r.get("shared_by_match_brands")),
            "bf_only_brands": _num(r.get("bf_only_brands")),
            "comp_only_brands": _num(r.get("comp_only_brands")),
            "has_catalogue": r.get("has_catalogue"),
        } for r in rows],
    }
