import math
from typing import Annotated, Optional

from pydantic import BeforeValidator


def _nan_to_none(v):
    # pandas 3 returns a SQL NULL in a string column as NaN (a float) or pd.NA,
    # not None. Either fails a plain `str | None` field and 500s the endpoint.
    if isinstance(v, float) and math.isnan(v):
        return None
    if type(v).__name__ == "NAType":
        return None
    return v


# A string column that may be NULL in the data. Use it for any model field
# filled straight from a DataFrame row.
NullableStr = Annotated[Optional[str], BeforeValidator(_nan_to_none)]
