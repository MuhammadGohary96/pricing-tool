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
    sub_category_name: str
    blended_pi: Optional[float] = None
    pi_deviation: Optional[float] = None
    direction: str
    used_product_count: int
    total_revenue: float
    total_product_count: int = 0
    eligible_product_count: int = 0
    needs_action_count: int = 0
    product_pis: list[ProductPIPoint] = []


class BlendedPITable(BaseModel):
    items: list[BlendedPIRow]


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
    similarity_score: Optional[float] = None
    bf_sale_price: float
    talabat_sale_price: Optional[float] = None
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
    suggested_talabat_name: str
    similarity_score: float
    estimated_talabat_price: float


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
