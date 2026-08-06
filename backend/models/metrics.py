from pydantic import BaseModel
from typing import Optional


class CommercialKPIs(BaseModel):
    total_products: int
    eligible_products: int
    used_products: int
    avg_blended_pi: Optional[float] = None
    needs_action: int


class TreemapNode(BaseModel):
    name: str
    value: float
    blended_pi: Optional[float] = None
    product_count: int
    color_value: Optional[float] = None


class TreemapData(BaseModel):
    children: list[TreemapNode]


class ProductPIPoint(BaseModel):
    product_name: str
    sale_PI: float
    weight: float


class BlendedPIRow(BaseModel):
    # group_key = the value grouped on (subcategory name, or commercial category
    # name in the rolled-up view). sub_category_name is null in category mode.
    group_key: str
    sub_category_name: Optional[str] = None
    commercial_category_name: Optional[str] = None
    blended_pi: Optional[float] = None
    pi_deviation: Optional[float] = None
    direction: str
    used_product_count: int
    total_revenue: float
    total_product_count: int = 0
    eligible_product_count: int = 0
    mapped_product_count: int = 0
    needs_action_count: int = 0
    # Matchability — same definitions as the gap tab and the Executive
    # competitor overview. comp_only_products is 0 in commercial-category grain:
    # the category bridge maps onto our subcategories only.
    matched_fresh_count: int = 0
    confirmed_no_match_count: int = 0
    potential_match_count: int = 0
    addressable_pct: Optional[float] = None
    comp_only_products: int = 0
    product_pis: list[ProductPIPoint] = []
    competitor_blended_pis: dict[str, Optional[float]] = {}
    competitor_product_pis: dict[str, list[ProductPIPoint]] = {}
    competitor_used_counts: dict[str, int] = {}
    competitor_needs_action_counts: dict[str, int] = {}
    competitor_eligible_counts: dict[str, int] = {}
    competitor_mapped_counts: dict[str, int] = {}
    # Per-competitor matchability, so Addr % and They only follow the selected
    # competitor header like Used and Mapped already do.
    competitor_addressable_pcts: dict[str, Optional[float]] = {}
    competitor_comp_only_counts: dict[str, int] = {}
    competitor_matched_fresh_counts: dict[str, int] = {}
    competitor_no_match_counts: dict[str, int] = {}


class BlendedPITable(BaseModel):
    items: list[BlendedPIRow]
    competitors: list[str] = []


class FunnelStage(BaseModel):
    name: str
    count: int
    pct: float
    symbol: str


class CoverageFunnel(BaseModel):
    stages: list[FunnelStage]


class ActionSummary(BaseModel):
    total_needs_action: int
    needs_mapping: int
    review_match: int
    needs_price_update: int


class ActionBreakdownRow(BaseModel):
    category: str
    needs_mapping: int
    review_match: int
    needs_price_update: int
    total: int


class WorklistRow(BaseModel):
    product_id: str
    product_name: str
    brand_name: str
    sub_category_name: str
    global_tier: str
    tier_order: int
    action_type: str
    action_symbol: str
    competitor_name: Optional[str] = None
    similarity_score: Optional[float] = None
    bf_sale_price: float
    competitor_sale_price: Optional[float] = None
    days_since_update: Optional[int] = None
    total_revenue: float


class WorklistTable(BaseModel):
    items: list[WorklistRow]
    total_count: int


class MatchReviewRow(BaseModel):
    product_id: str
    bf_product_name: str
    bf_brand: str
    bf_price: float
    competitor_name: Optional[str] = None
    suggested_competitor_name: str
    similarity_score: float
    estimated_competitor_price: float


class MatchReviewTable(BaseModel):
    items: list[MatchReviewRow]
    total_count: int


class StalenessCell(BaseModel):
    sub_category_name: str
    bucket: str
    count: int


class StalenessHeatmap(BaseModel):
    cells: list[StalenessCell]
    subcategories: list[str]
    buckets: list[str]


class TrendPoint(BaseModel):
    date: str
    value: float


class ExecutiveSummary(BaseModel):
    overall_blended_pi: Optional[float] = None
    coverage_pct: float
    total_products: int
    used_products: int
    needs_action: int
    top_5_cheapest: list[dict]
    top_5_expensive: list[dict]
    subcategory_count: int


class CategoryPI(BaseModel):
    category_name: str
    blended_pi: Optional[float] = None
    pi_deviation: Optional[float] = None
    product_count: int


class WoWDelta(BaseModel):
    metric_name: str
    current: float
    previous: float
    delta: float
    direction: str


class FilterOptions(BaseModel):
    main_categories: list[str]
    sub_categories: list[str]
    global_tiers: list[str]
    subcat_tiers: list[str]
    action_types: list[str]
    competitors: list[str] = []
