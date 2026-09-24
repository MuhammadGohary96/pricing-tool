from pydantic import BaseModel
from typing import Optional

from backend.models.types import NullableStr


class FilterParams(BaseModel):
    main_category: NullableStr = None
    main_category_name: NullableStr = None
    sub_category: NullableStr = None
    global_tier: NullableStr = None
    subcat_tier: NullableStr = None
    action_type: NullableStr = None
