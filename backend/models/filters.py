from pydantic import BaseModel
from typing import Optional


class FilterParams(BaseModel):
    main_category: Optional[str] = None
    sub_category: Optional[str] = None
    global_tier: Optional[str] = None
    subcat_tier: Optional[str] = None
    action_type: Optional[str] = None
