import pandas as pd
import numpy as np


def compute_action_type(row) -> str:
    if not row.get("has_PI") and not row.get("match_potential"):
        return "Needs Mapping"
    elif not row.get("has_PI") and row.get("match_potential"):
        return "Review Match"
    elif row.get("has_PI") and not row.get("updated"):
        return "Needs Price Update"
    return "Complete"


def compute_blended_pi(df: pd.DataFrame) -> float | None:
    used = df[df["used_product"] == True]
    if used.empty or used["avg_daily_quantity"].sum() == 0:
        return None
    return float(
        (used["sale_PI"] * used["avg_daily_quantity"]).sum()
        / used["avg_daily_quantity"].sum()
    )


def pi_direction(deviation: float | None) -> str:
    if deviation is None:
        return "\u2014"
    if deviation > 0.001:
        return "\u25B2"
    if deviation < -0.001:
        return "\u25BC"
    return "\u2014"


ACTION_SYMBOLS = {
    "Needs Mapping": "\u2298",
    "Review Match": "\u26A1",
    "Needs Price Update": "\u27F3",
    "Complete": "\u2713",
}

TIER_ORDER = {"Top+": 5, "Top": 4, "Medium": 3, "Low": 2, "Very Low": 1}
