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


def competitor_overview_sheet(rows) -> dict:
    """One row per competitor: matching and assortment coverage.

    The Gap workbook's cross-competitor summary tab, mirroring the hand-built
    Brand_Portfolio sheet. Executive splits the same data across three sheets
    instead — see executive_scorecard_sheets.
    """
    return {
        "name": "Competitor Overview",
        "title": "Competitor Overview — matching and assortment coverage",
        "columns": [
            {"field": "competitor_name", "header": "COMPETITOR", "width": 16},
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


# ─────────────────────────────────────────────────────────────────────────────
# Executive scorecard — one sheet per on-screen table
# ─────────────────────────────────────────────────────────────────────────────
# The panel asks three questions and the file answers them the same way, so a
# sheet can be sent on its own without the other two columns' worth of context.
def _overlap_pct(r):
    union = _num(r.get("our_only_products")) + _num(r.get("matched")) + _num(r.get("comp_only_products"))
    return round(_num(r.get("matched")) / union, 5) if union else None


def _breadth(r):
    bf = _num(r.get("bf_products"))
    return round(_num(r.get("comp_products_in_scope")) / bf, 2) if bf else None


def executive_scorecard_sheets(rows) -> list[dict]:
    comp = {"field": "competitor_name", "header": "COMPETITOR", "width": 16}
    return [
        {
            "name": "Price position",
            "title": "Price position — what we charge against what they charge",
            "note": "PI = Breadfast price / competitor price. Above 1.00 means Breadfast is more "
                    "expensive. Confidence % = Used / Eligible — how much of the revenue-weighted "
                    "range the PI beside it is built on. Eligible / Mapped / Used are the "
                    "funnel behind it: the drop to Mapped is a matching gap, the drop to "
                    "Used a freshness one.",
            "columns": [
                comp,
                # ABOVE 1.00 means we are more expensive, so the thresholds are
                # inverted: orange high, green low, with a 2% dead band.
                {"field": "blended_pi", "header": "BLENDED PI", "format": "decimal2",
                 "low_threshold": 0.98, "high_threshold": 1.02, "invert": True},
                _metric("priced_pct", "CONFIDENCE %"),
                {"field": "bf_products", "header": "OUR SKUS", "format": "number"},
                {"field": "eligible_products", "header": "ELIGIBLE", "format": "number"},
                {"field": "mapped_eligible", "header": "MAPPED", "format": "number"},
                {"field": "used_products", "header": "USED", "format": "number"},
            ],
            "rows": [{
                "competitor_name": r.get("competitor_name"),
                "blended_pi": r.get("blended_pi"),
                "priced_pct": _pct(r.get("priced_pct")),
                "bf_products": _num(r.get("bf_products")),
                "eligible_products": _num(r.get("eligible_products")),
                "mapped_eligible": _num(r.get("mapped_eligible")),
                "used_products": _num(r.get("used_products")),
            } for r in rows],
        },
        {
            "name": "Mapping coverage",
            "title": "Mapping coverage — how much of our range is matched, and how much can be",
            "note": "The same chain twice: base, mapped, rate, rejected, addressable, ceiling — "
                    "first over everything we sell, then over just the brands this competitor "
                    "carries. Addressable = base minus confirmed no-match, so products the "
                    "matcher positively rejected leave the denominator rather than counting "
                    "against it. The last column is the true ceiling: anything short of 100% "
                    "there is work that can actually be done. The two POTENTIAL columns differ by "
                    "the products whose brand the competitor does not stock — a strong candidate "
                    "there is a false lead, not a backlog item.",
            "columns": [
                comp,
                # The same chain twice -- base, mapped, rate, rejected, addressable,
                # ceiling -- once over everything we sell and once over just the
                # brands they stock. Headers carry the qualifier because a sheet
                # has no group row to lean on.
                {"field": "bf_products", "header": "OUR SKUS", "format": "number"},
                {"field": "matched", "header": "MAPPED", "format": "number"},
                {"field": "matched_fresh", "header": "FRESH", "format": "number"},
                _metric("mapping_pct", "MAPPED %"),
                {"field": "confirmed_no_match", "header": "CONFIRMED NO-MATCH", "format": "number"},
                {"field": "addressable", "header": "ADDRESSABLE", "format": "number"},
                _metric("addressable_pct", "ADDRESSABLE %"),
                {"field": "potential_match", "header": "POTENTIAL", "format": "number"},
                {"field": "shared_brand_products", "header": "OUR SKUS (SHARED BRANDS)",
                 "format": "number", "width": 22},
                # No thresholds: how much of our range sits in brands they carry
                # is an assortment fact, not a rate anyone is failing at.
                {"field": "shared_brand_pct", "header": "OF OUR RANGE", "format": "percent", "width": 16},
                {"field": "matched_shared_brand", "header": "MAPPED (SHARED)", "format": "number", "width": 18},
                _metric("mapping_pct_shared", "MAPPED % (SHARED)", width=20),
                {"field": "confirmed_no_match_shared", "header": "NO-MATCH (SHARED)",
                 "format": "number", "width": 20},
                {"field": "addressable_shared", "header": "ADDRESSABLE (SHARED)",
                 "format": "number", "width": 22},
                _metric("addressable_pct_shared", "ADDRESSABLE % (SHARED)", width=22),
                {"field": "potential_match_shared", "header": "POTENTIAL (SHARED)",
                 "format": "number", "width": 20},
            ],
            "rows": [{
                "competitor_name": r.get("competitor_name"),
                "bf_products": _num(r.get("bf_products")),
                "matched": _num(r.get("matched")),
                "mapping_pct": _pct(r.get("mapping_pct")),
                "shared_brand_products": _num(r.get("shared_brand_products")),
                "shared_brand_pct": _pct(r.get("shared_brand_pct")),
                "matched_shared_brand": _num(r.get("matched_shared_brand")),
                "mapping_pct_shared": _pct(r.get("mapping_pct_shared")),
                "confirmed_no_match_shared": _num(r.get("confirmed_no_match_shared")),
                "addressable_shared": _num(r.get("addressable_shared")),
                "addressable_pct_shared": _pct(r.get("addressable_pct_shared")),
                "potential_match_shared": _num(r.get("potential_match_shared")),
                "matched_fresh": _num(r.get("matched_fresh")),
                "confirmed_no_match": _num(r.get("confirmed_no_match")),
                "addressable": _num(r.get("addressable")),
                "addressable_pct": _pct(r.get("addressable_pct")),
                "potential_match": _num(r.get("potential_match")),
            } for r in rows],
        },
        {
            "name": "Assortment gap",
            "title": "Assortment gap — what they stock that we don't, and the reverse",
            "note": "The same six columns twice: over everything we sell, then over brands this "
                    "competitor also carries. Both partitions close exactly — BOTH + BOTH DELISTED "
                    "+ OURS ONLY = OUR SKUS, and THEIR CATALOGUE = its paired half plus THEY ONLY. "
                    "BOTH counts OUR products, so it is not the paired half of their catalogue: "
                    "several of ours can share one of their listings. Never sum THEY ONLY across "
                    "views — one of their products bridges to several of our subcategories. A "
                    "competitor with no crawled catalogue is a COLLECTION gap, not an assortment one.",
            "columns": [
                comp,
                {"field": "bf_products", "header": "OUR SKUS", "format": "number"},
                {"field": "both_live", "header": "BOTH", "format": "number"},
                {"field": "mapped_comp_delisted", "header": "BOTH, THEY DELISTED", "format": "number", "width": 18},
                {"field": "our_only_products", "header": "OURS ONLY", "format": "number"},
                {"field": "comp_products_in_scope", "header": "THEIR CATALOGUE", "format": "number"},
                {"field": "comp_only_products", "header": "THEY ONLY", "format": "number"},
                {"field": "shared_brand_products", "header": "OUR SKUS (SHARED)", "format": "number", "width": 20},
                {"field": "both_live_shared", "header": "BOTH (SHARED)", "format": "number", "width": 18},
                {"field": "mapped_comp_delisted_shared", "header": "BOTH THEY DELISTED (SHARED)",
                 "format": "number", "width": 22},
                {"field": "our_only_shared", "header": "OURS ONLY (SHARED)", "format": "number", "width": 20},
                {"field": "comp_catalogue_shared", "header": "THEIR CATALOGUE (SHARED)",
                 "format": "number", "width": 24},
                {"field": "comp_only_shared", "header": "THEY ONLY (SHARED)", "format": "number", "width": 20},
                # No thresholds: a 26% overlap is healthy, and the default rate
                # colours would paint every row orange.
                {"field": "overlap_pct", "header": "OVERLAP %", "format": "percent"},
                {"field": "breadth", "header": "THEIR RANGE ×", "format": "decimal2"},
                # File-only: the unfiltered total, for reconciling against BigQuery.
                {"field": "comp_products", "header": "THEIR CATALOGUE (UNFILTERED)",
                 "format": "number", "width": 26},
                {"field": "shared_brands", "header": "SHARED BRANDS", "format": "number"},
                {"field": "shared_by_match_brands", "header": "SHARED (BY MATCH)", "format": "number", "width": 20},
                {"field": "bf_only_brands", "header": "BF-ONLY BRANDS", "format": "number"},
                {"field": "comp_only_brands", "header": "COMP-ONLY BRANDS", "format": "number"},
                {"field": "has_catalogue", "header": "HAS CATALOGUE", "width": 14},
            ],
            "rows": [{
                "competitor_name": r.get("competitor_name"),
                "bf_products": _num(r.get("bf_products")),
                "both_live": max(0, _num(r.get("matched")) - _num(r.get("mapped_comp_delisted"))),
                "mapped_comp_delisted": _num(r.get("mapped_comp_delisted")),
                "our_only_products": _num(r.get("our_only_products")),
                "comp_products_in_scope": _num(r.get("comp_products_in_scope")),
                "comp_only_products": _num(r.get("comp_only_products")),
                "shared_brand_products": _num(r.get("shared_brand_products")),
                "both_live_shared": max(0, _num(r.get("matched_shared_brand"))
                                           - _num(r.get("mapped_comp_delisted_shared"))),
                "mapped_comp_delisted_shared": _num(r.get("mapped_comp_delisted_shared")),
                "our_only_shared": max(0, _num(r.get("shared_brand_products"))
                                          - _num(r.get("matched_shared_brand"))),
                "comp_catalogue_shared": _num(r.get("comp_catalogue_shared")),
                "comp_only_shared": _num(r.get("comp_only_shared")),
                # Blank rather than 0 where nothing was crawled: 0% overlap would
                # read as "we share nothing with them", which is not what a
                # missing catalogue means.
                "overlap_pct": _overlap_pct(r) if r.get("has_catalogue") else None,
                "breadth": _breadth(r) if r.get("has_catalogue") else None,
                "comp_products": _num(r.get("comp_products")),
                "shared_brands": _num(r.get("shared_brands")),
                "shared_by_match_brands": _num(r.get("shared_by_match_brands")),
                "bf_only_brands": _num(r.get("bf_only_brands")),
                "comp_only_brands": _num(r.get("comp_only_brands")),
                "has_catalogue": r.get("has_catalogue"),
            } for r in rows],
        },
    ]
