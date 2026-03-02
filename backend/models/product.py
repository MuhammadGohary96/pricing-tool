from pydantic import BaseModel
from typing import Optional


class ProductRow(BaseModel):
    product_id: str
    product_name: str
    brand_name: str
    main_category_name: str
    commercial_category_name: str
    sub_category_name: str
    total_revenue: float
    avg_daily_quantity: float
    norm_revenue: float
    norm_quantity: float
    weighted_score: float
    global_tier: str
    subcat_tier: str
    eligible_product: bool
    bf_sale_price: float
    bf_regular_price: float
    talabat_sale_price: Optional[float] = None
    talabat_regular_price: Optional[float] = None
    sale_PI: Optional[float] = None
    has_PI: bool
    bf_price_updated_at: Optional[str] = None
    talabat_price_updated_at: Optional[str] = None
    updated: bool
    similarity_score: Optional[float] = None
    match_potential: bool
    used_product: bool
    action_type: str
    pi_deviation: Optional[float] = None
    days_since_update: Optional[int] = None
    now_price: Optional[float] = None
    now_sale_price: Optional[float] = None
    competitor_product_name: Optional[str] = None
    match_potential_product_name: Optional[str] = None


class ProductPriceUpdate(BaseModel):
    now_price: Optional[float] = None
    now_sale_price: Optional[float] = None


class ProductDetailTable(BaseModel):
    items: list[ProductRow]
    total_count: int
