"""What the API *means* — the part OpenAPI cannot express.

Parameter names, types and requiredness are read from the live `/openapi.json`
at startup (see server.py), so they can never drift from the code. This module
holds only the semantics on top of that:

  summary   one line, shown in the inline catalogue
  requires  params the API accepts as optional but that are WRONG to omit
  heavy     fields dropped in lean mode, with a note saying what was lost
  caveats   the misreadings this endpoint's columns invite

The caveats are the reason this file exists. A number that arrives with no
warning gets narrated confidently, and the two rules most likely to produce a
wrong sentence -- PI direction, and never summing competitor-side counts -- both
apply to data that came back perfectly fine.

Package is `mcp_server`, not `mcp`: a local `mcp/` shadows the installed MCP SDK
whenever python runs from the repo root.
"""
from __future__ import annotations

# ── caveats reused across endpoints ──────────────────────────────────────────
PI_DIRECTION = (
    "PI = Breadfast price / competitor price. ABOVE 1.00 MEANS BREADFAST IS MORE "
    "EXPENSIVE. Internal decks use the inverted convention -- do not copy a "
    "cheaper/pricier label from anywhere else, derive it from this rule."
)
NEVER_SUM_COMP = (
    "Competitor-side counts (comp_only_products / 'They only') must NEVER be summed "
    "across rows: one of their products is bridged into several of our subcategories, "
    "so the total double-counts."
)
OURS_ONLY_CEILING = (
    "'Ours only' / our_only_products is a CEILING, not a work queue. It counts products "
    "we failed to match TOGETHER WITH products the competitor genuinely does not stock."
)
CARREFOUR_BLIND = (
    "Carrefour has no crawled catalogue. Its competitor-side figures are zero because "
    "nothing was collected, NOT because it stocks nothing -- a collection gap, not an "
    "assortment gap. Never rank it on assortment overlap."
)
ELIGIBLE_CONSTANT = (
    "'Eligible' reads the same on every competitor row by construction (the eligible set "
    "does not depend on which competitor you look at). That is correct, not a bug."
)
SHARED_BRAND_INFERRED = (
    "A brand counts as shared when the names match OR when >=50% of its products are "
    "matched at that competitor (our 'Froneri' is their 'Nestle'). The by-match half is "
    "an inference; shared_by_match_brands isolates it."
)
COMP_ONLY_UPPER_BOUND = (
    "Brand counts on the competitor side are an UPPER BOUND -- their name variants are "
    "not collapsed, so 7up / 7Up / 7UP count as three brands."
)
GAP_SINGLE_COMPETITOR = (
    "Gap endpoints are single-competitor by design. Omitting `competitor` returns 200 OK "
    "with all seven POOLED, which violates the no-summing rule above and is almost never "
    "what was asked."
)
VOCAB = (
    "Vocabulary is unified across the three views: Mapped (not Matched), Util % (not "
    "Priced or Coverage %). Do not reintroduce synonyms when narrating."
)
DRIFT = "Counts move by tens or hundreds between refreshes. Do not imply more precision than that."

# ── the exposed surface ──────────────────────────────────────────────────────
# Deliberately not all 44 endpoints: health/config/startup probes answer no
# business question, and the CSV /export routes are superseded by /workbook.
ENDPOINTS: dict[str, dict] = {
    # ── EXECUTIVE ────────────────────────────────────────────────────────────
    "/api/executive/summary": {
        "area": "executive", "rows_at": None,
        "summary": "Headline KPIs for the whole business. No filters.",
        "caveats": [PI_DIRECTION],
    },
    "/api/executive/dashboard": {
        "area": "executive", "rows_at": None,
        "summary": "Everything behind the Executive page: KPIs, per-competitor PI, "
                   "classification breakdown, mapping progress.",
        "caveats": [PI_DIRECTION, VOCAB,
                    "classification_breakdown is at PRODUCT grain and sums to the product "
                    "count, not to product x competitor pairs."],
    },
    "/api/executive/competitor-overview": {
        "area": "executive", "rows_at": None,
        "summary": "THE competitor scorecard -- one row per competitor: blended PI, Util %, "
                   "Mapped %, Mapped % in shared brands, Addressable %, their catalogue, "
                   "they-only, ours-only, brand counts. Start here for 'how do we compare'.",
        "caveats": [PI_DIRECTION, ELIGIBLE_CONSTANT, CARREFOUR_BLIND, OURS_ONLY_CEILING,
                    SHARED_BRAND_INFERRED, COMP_ONLY_UPPER_BOUND, VOCAB, DRIFT],
    },
    "/api/executive/category-performance": {
        "area": "executive", "rows_at": None,
        "summary": "Blended PI per commercial category.",
        "caveats": [PI_DIRECTION,
                    "used_product_count counts products CARRYING a PI, not products in the "
                    "category."],
    },
    "/api/executive/fp-competitor-pi": {
        "area": "executive", "rows_at": None,
        "summary": "Blended PI by fulfillment point x competitor (geographic exposure).",
        "caveats": [PI_DIRECTION],
    },
    "/api/executive/top-actions": {
        "area": "executive", "rows_at": "items",
        "summary": "Highest-revenue products needing action.",
        "caveats": [PI_DIRECTION],
    },
    "/api/executive/pi-trend": {
        "area": "executive", "rows_at": None, "summary": "Blended PI over time. No filters.",
        "caveats": [PI_DIRECTION],
    },
    "/api/executive/coverage-trend": {
        "area": "executive", "rows_at": None, "summary": "Coverage over time. No filters.",
        "caveats": [VOCAB],
    },
    "/api/executive/week-over-week": {
        "area": "executive", "rows_at": None, "summary": "Week-on-week movement. No filters.",
        "caveats": [PI_DIRECTION, DRIFT],
    },

    # ── COMMERCIAL ───────────────────────────────────────────────────────────
    "/api/commercial/kpis": {
        "area": "commercial", "rows_at": None,
        "summary": "Commercial page KPIs for the current filters.",
        "caveats": [PI_DIRECTION, VOCAB],
    },
    "/api/commercial/blended-pi": {
        "area": "commercial", "rows_at": "items",
        # 87.3% of this payload is the per-product scatter behind the strip plots.
        "heavy": ["product_pis", "competitor_product_pis"],
        "heavy_note": "per-product PI scatter behind the strip plots -- 87% of the payload, "
                      "and not readable in prose anyway",
        "order_by": ("blended_pi", "desc"), "tiebreak": "group_key",
        "summary": "Blended PI by subcategory (or commercial category via "
                   "group_by=commercial_category), with per-competitor PI and coverage. "
                   "2.0 MB unfiltered -- always narrow it or accept the row cap.",
        "caveats": [PI_DIRECTION, NEVER_SUM_COMP, OURS_ONLY_CEILING, VOCAB,
                    "A row with blended_pi = null is not an error: nothing in it is priced "
                    "and fresh on both sides. Those rows are shown deliberately, because "
                    "they are the biggest gaps.",
                    "Mapped % is over total_product_count; Util % is over "
                    "eligible_product_count (the top-80%-of-revenue head). Not "
                    "interchangeable denominators."],
    },
    "/api/commercial/products": {
        "area": "commercial", "rows_at": "items",
        "summary": "Product list at product x competitor grain. Paginated.",
        "caveats": [PI_DIRECTION, VOCAB],
    },
    "/api/commercial/products-pivoted": {
        "area": "commercial", "rows_at": "items",
        "summary": "One row per product with every competitor's price and PI as columns. "
                   "This is the one to use for 'how is product X priced against everyone'.",
        "caveats": [PI_DIRECTION,
                    "worst_pi is the HIGHEST PI across competitors, i.e. where we are most "
                    "expensive."],
    },
    "/api/commercial/products/{product_id}/fp-matrix": {
        "area": "commercial", "rows_at": None, "path_params": ["product_id"],
        "summary": "One product's full fulfillment-point x competitor price matrix.",
        "caveats": [PI_DIRECTION,
                    "Cell states: priced (fresh) / stale / no_price. price_fallback=true "
                    "fills mapped-but-stale cells with a modal price and marks them "
                    "'estimated' -- never treat those as observed."],
    },
    "/api/commercial/treemap": {
        "area": "commercial", "rows_at": None,
        "summary": "Revenue treemap by category/subcategory.", "caveats": [PI_DIRECTION],
    },
    "/api/commercial/funnel": {
        "area": "commercial", "rows_at": None,
        "summary": "Eligible -> updated -> used coverage funnel.", "caveats": [VOCAB],
    },

    # ── GAP ANALYSIS ─────────────────────────────────────────────────────────
    "/api/gap/kpis": {
        "area": "gap", "rows_at": None, "requires": ["competitor"],
        "summary": "Headline gap numbers against ONE competitor.",
        "caveats": [GAP_SINGLE_COMPETITOR, OURS_ONLY_CEILING, SHARED_BRAND_INFERRED, DRIFT],
    },
    "/api/gap/subcategories": {
        "area": "gap", "rows_at": None, "requires": ["competitor"],
        "heavy": ["shared_brand_list", "bf_only_brand_list", "comp_only_brand_list"],
        "heavy_note": "the full brand name lists per row -- 67% of the payload; the counts "
                      "beside them are kept",
        "order_by": ("daily_revenue", "desc"), "tiebreak": "sub_category_name",
        "summary": "Per-subcategory gap against ONE competitor: our SKUs, mapped, mapped live, "
                   "they-only, their catalogue, ours-only, brand overlap.",
        "caveats": [GAP_SINGLE_COMPETITOR, NEVER_SUM_COMP, OURS_ONLY_CEILING,
                    COMP_ONLY_UPPER_BOUND, VOCAB,
                    "comp_mapped_live + comp_only_products = comp_catalogue exactly. Mapped "
                    "does NOT, because Mapped counts OUR products and the other three count "
                    "THEIRS -- several of ours can share one of their listings.",
                    "Brand sets are WITHIN-subcategory: a brand can be shared in one and "
                    "ours-only in another."],
    },
    "/api/gap/brands": {
        "area": "gap", "rows_at": "items", "requires": ["competitor"],
        "heavy": ["comp_brand_variants"],
        "heavy_note": "every spelling the competitor uses for the brand, encoded "
                      "name:count|name:count",
        "summary": "Per-brand gap against ONE competitor. brand_type filters "
                   "shared / bf_only / comp_only / by_match.",
        "caveats": [GAP_SINGLE_COMPETITOR, OURS_ONLY_CEILING, SHARED_BRAND_INFERRED,
                    COMP_ONLY_UPPER_BOUND,
                    "A brand filter matches OUR brand name. Competitors spell brands "
                    "differently (7up / 7Up / 7UP), which is what comp_brand_variants shows."],
    },
    "/api/gap/products": {
        "area": "gap", "rows_at": "items", "requires": ["competitor"],
        "summary": "Product explorer, both sides. side=breadfast (ours) or side=competitor "
                   "(theirs). Paginated.",
        "caveats": [GAP_SINGLE_COMPETITOR,
                    "The two sides are DIFFERENT POPULATIONS and share key names. On a "
                    "competitor row, product_name/brand_name are THEIRS and "
                    "sub_category_name is the BRIDGED placement, not our own."],
    },
    "/api/gap/filters": {
        "area": "gap", "rows_at": None,
        "summary": "Valid competitors and scope options for the gap view.", "caveats": [],
    },

    # ── MASTER DATA ──────────────────────────────────────────────────────────
    "/api/master-data/action-summary": {
        "area": "master-data", "rows_at": None,
        "summary": "Matching/pricing workload by action type.", "caveats": [VOCAB],
    },
    "/api/master-data/action-breakdown": {
        "area": "master-data", "rows_at": None,
        "summary": "Action backlog broken down by category.", "caveats": [VOCAB],
    },
    "/api/master-data/worklist": {
        "area": "master-data", "rows_at": "items",
        "summary": "The prioritised master-data queue. Paginated.", "caveats": [VOCAB],
    },
    "/api/master-data/match-reviews": {
        "area": "master-data", "rows_at": "items",
        "summary": "AI match candidates awaiting review. Paginated.",
        "caveats": ["Similarity >= 0.85 is the potential-match threshold everywhere in the "
                    "tool."],
    },
    "/api/master-data/staleness-heatmap": {
        "area": "master-data", "rows_at": None,
        "summary": "Price freshness by category x competitor.",
        "caveats": ["Fresh means seen within 7 days, on BOTH sides."],
    },

    # ── COMPETITOR CATALOGUE ─────────────────────────────────────────────────
    "/api/competitor-products/kpis": {
        "area": "competitor-products", "rows_at": None,
        "summary": "Crawled-catalogue health per competitor.", "caveats": [CARREFOUR_BLIND],
    },
    "/api/competitor-products/category-breakdown": {
        "area": "competitor-products", "rows_at": None,
        "summary": "Their catalogue by their own category tree.",
        "caveats": [CARREFOUR_BLIND,
                    "These are THEIR category levels, not ours. Use /api/gap/subcategories "
                    "for anything expressed in our subcategories."],
    },
    "/api/competitor-products/mapping-summary": {
        "area": "competitor-products", "rows_at": None,
        "summary": "How much of their catalogue is mapped to us.", "caveats": [CARREFOUR_BLIND],
    },
    "/api/competitor-products/products": {
        "area": "competitor-products", "rows_at": "items",
        "summary": "Their raw catalogue rows. Paginated.", "caveats": [CARREFOUR_BLIND],
    },
    "/api/competitor-products/crawl-timeline": {
        "area": "competitor-products", "rows_at": None,
        "summary": "When their catalogue was last crawled.", "caveats": [CARREFOUR_BLIND],
    },

    # ── FILTER VOCABULARY ────────────────────────────────────────────────────
    # These are what the validator reads. There is no /api/filters root.
    "/api/filters/categories": {
        "area": "filters", "rows_at": None, "summary": "Valid commercial categories.", "caveats": []},
    "/api/filters/subcategories": {
        "area": "filters", "rows_at": None, "summary": "Valid subcategories (optionally within `main`).", "caveats": []},
    "/api/filters/tiers": {
        "area": "filters", "rows_at": None, "summary": "Valid global/subcat tiers.", "caveats": []},
    "/api/filters/competitors": {
        "area": "filters", "rows_at": None, "summary": "The seven competitor names.", "caveats": []},
    "/api/filters/fps": {
        "area": "filters", "rows_at": None, "summary": "Valid fulfillment points.", "caveats": []},

    # ── WORKBOOKS (write a file, return its path) ────────────────────────────
    "/api/gap/workbook": {
        "area": "workbook", "rows_at": None, "requires": ["competitor"], "workbook": True,
        "summary": "Styled .xlsx: Competitor Overview + Brands + Subcategories + Portfolio "
                   "for ONE competitor. sheets=all|brands|subcategories|products.",
        "caveats": [GAP_SINGLE_COMPETITOR],
    },
    "/api/executive/workbook": {
        "area": "workbook", "rows_at": None, "workbook": True,
        "summary": "Styled .xlsx: the full competitor scorecard.",
        "caveats": [PI_DIRECTION, CARREFOUR_BLIND],
    },
    "/api/commercial/workbook": {
        "area": "workbook", "rows_at": None, "workbook": True,
        "summary": "Styled .xlsx. sheets=blended-pi -> one grid tab plus a tab per "
                   "competitor; sheets=products -> every product with each competitor's "
                   "price and PI.",
        "caveats": [PI_DIRECTION],
    },
}

# Filter values the validator checks, and where it reads them from. Anything not
# listed is passed through unvalidated rather than guessed at.
VALIDATED_FILTERS = {
    "competitor":     "/api/filters/competitors",
    "main_category":  "/api/filters/categories",
    "sub_category":   "/api/filters/subcategories",
    "global_tier":    "/api/filters/tiers",
    "subcat_tier":    "/api/filters/tiers",
    "fp_names":       "/api/filters/fps",
}

# Params consumed by this server rather than forwarded.
SERVER_PARAMS = {"_rows", "_fields"}

AREA_ORDER = ["executive", "commercial", "gap", "master-data",
              "competitor-products", "filters", "workbook"]


def inline_catalogue() -> str:
    """The compact listing carried in the query tool's description."""
    out = []
    for area in AREA_ORDER:
        paths = [p for p, m in ENDPOINTS.items() if m["area"] == area]
        marks = []
        for p in sorted(paths):
            short = p.replace("/api/", "")
            if ENDPOINTS[p].get("requires"):
                short += "*"
            marks.append(short)
        out.append(f"  {area.upper():21} " + "  ".join(marks))
    return "\n".join(out)
