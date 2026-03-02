def format_pi(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:.4f}"


def format_pct(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:.1f}%"


def tier_stars(tier: str) -> str:
    mapping = {
        "Top+": "\u2605\u2605\u2605\u2605\u2605",
        "Top": "\u2605\u2605\u2605\u2605\u2606",
        "Medium": "\u2605\u2605\u2605\u2606\u2606",
        "Low": "\u2605\u2605\u2606\u2606\u2606",
        "Very Low": "\u2605\u2606\u2606\u2606\u2606",
    }
    return mapping.get(tier, "")
