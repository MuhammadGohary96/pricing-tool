from pydantic import BaseModel
from typing import Optional

from backend.models.types import NullableStr


class ProductRow(BaseModel):
    product_id: str
    product_name: str
    brand_name: NullableStr = None
    main_category_name: NullableStr = None
    commercial_category_name: NullableStr = None
    sub_category_name: NullableStr = None
    total_revenue: float
    avg_daily_quantity: float
    norm_revenue: float
    norm_quantity: float
    weighted_score: float
    global_tier: NullableStr = None
    subcat_tier: NullableStr = None
    eligible_product: bool
    bf_sale_price: float
    bf_regular_price: float
    competitor_id: Optional[int] = None
    competitor_name: NullableStr = None
    competitor_sale_price: Optional[float] = None
    min_competitor_sale_price: Optional[float] = None
    max_competitor_sale_price: Optional[float] = None
    sale_PI: Optional[float] = None
    has_PI: bool
    bf_price_updated_at: NullableStr = None
    competitor_price_updated_at: NullableStr = None
    updated: bool
    has_updated_price: bool = False
    similarity_score: Optional[float] = None
    match_potential: bool
    used_product: bool
    action_type: str
    classification: NullableStr = None
    pi_deviation: Optional[float] = None
    days_since_update: Optional[int] = None
    now_price: Optional[float] = None
    now_sale_price: Optional[float] = None
    competitor_product_name: NullableStr = None
    match_potential_product_name: NullableStr = None


class ProductDetailTable(BaseModel):
    items: list[ProductRow]
    total_count: int
