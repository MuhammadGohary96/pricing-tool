"""MCP server for the Breadfast Pricing Intelligence Tool.

Answers plain-English pricing questions by calling the app's own HTTP API, so a
number it reports can never disagree with the same number on screen. It does not
touch DuckDB or BigQuery directly: a second DuckDB boot carries a documented
~4.8 GB transient, and going through the API is also the only path that works
once this is hosted for the team.

  query_pricing_api(endpoint, params)   GET any catalogued endpoint, or write a
                                        styled workbook to disk
  describe_api(path)                    full parameter detail on demand

Design, as agreed:

  * ONE generic tool rather than purpose-shaped ones, with a compact endpoint
    catalogue inline in its description so paths are never guessed.
  * VALIDATE AND TEACH, never auto-correct. "talabat" is an error naming the
    seven valid values; it does not silently become "Talabat". The server
    picking a value on your behalf is the failure mode this design exists to
    avoid -- see the gap-pooling note below.
  * Responses declare what was dropped. The heavy fields are per-row scatter
    arrays that carry no prose meaning and 87% of the bytes.
  * Every response carries the caveats for the columns it returned, because the
    misreadings apply to data that came back perfectly fine, and a tool
    description read twenty turns ago is not where the warning is needed.

Config (all optional):
  PRICING_API_URL         default http://127.0.0.1:8000
  PRICING_API_TOKEN       sent as `Authorization: Bearer ...`; the hook for the
                          hosted build, unused locally where auth is off
  PRICING_MCP_EXPORT_DIR  default ~/Desktop
  PRICING_MCP_MAX_ROWS    default 25
"""
from __future__ import annotations

import datetime as _dt
import difflib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

from .catalogue import (
    ENDPOINTS, SERVER_PARAMS, VALIDATED_FILTERS, inline_catalogue,
    PI_DIRECTION, NEVER_SUM_COMP, OURS_ONLY_CEILING, CARREFOUR_BLIND,
)

# stdout is the JSON-RPC channel under stdio transport, and httpx logs a line per
# request. They land on stderr rather than corrupting the protocol, but they bury
# anything worth reading in Claude Code's MCP log.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

API_URL = os.environ.get("PRICING_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.environ.get("PRICING_API_TOKEN", "")
EXPORT_DIR = Path(os.environ.get("PRICING_MCP_EXPORT_DIR", "~/Desktop")).expanduser()
MAX_ROWS = int(os.environ.get("PRICING_MCP_MAX_ROWS", "25"))
ROW_CEILING = 500

_START_HINT = (
    f"No response from the Pricing API at {API_URL}. Start it with:\n"
    "  cd '/Users/m1pro/Downloads/Pricing Tool' && "
    "python3 -m uvicorn backend.main:app --port 8000\n"
    "First boot rebuilds the DuckDB cache and takes a few minutes."
)


# ─────────────────────────────────────────────────────────────────────────────
# Live schema — parameter names come from the API itself, never hand-maintained
# ─────────────────────────────────────────────────────────────────────────────
_schema: dict[str, set[str]] | None = None
_vocab: dict[str, list[str]] = {}


def _client() -> httpx.Client:
    headers = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}
    return httpx.Client(base_url=API_URL, headers=headers, timeout=180.0)


def _load_schema() -> dict[str, set[str]]:
    """Allowed query params per path, read from the live OpenAPI document.

    Hand-listing these is what drifts. /openapi.json is public (it is in
    auth.PUBLIC_PATHS), so this works before any token is configured.
    """
    global _schema
    if _schema is None:
        with _client() as c:
            doc = c.get("/openapi.json").json()
        _schema = {
            path: {p["name"] for p in (ops.get("get") or {}).get("parameters", [])}
            for path, ops in doc.get("paths", {}).items() if "get" in ops
        }
    return _schema


def _vocab_for(field: str) -> list[str]:
    """Valid values for a filter, from the app's own /api/filters/* endpoints."""
    if field not in _vocab:
        try:
            with _client() as c:
                payload = c.get(VALIDATED_FILTERS[field]).json()
        except Exception:
            return []
        vals: list[str] = []
        stack = [payload]
        while stack:                      # the five endpoints differ in shape
            node = stack.pop()
            if isinstance(node, str):
                vals.append(node)
            elif isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                stack.extend(node.get("items", node.values()))
        # tiers/fps come back as objects; keep the plain names only
        _vocab[field] = sorted({v for v in vals if isinstance(v, str) and v})
    return _vocab[field]


# ─────────────────────────────────────────────────────────────────────────────
# Errors that teach
# ─────────────────────────────────────────────────────────────────────────────
class Refused(Exception):
    """A call rejected before it reached the API, with the fix in the message."""


def _closest(value: str, options: list[str]) -> str:
    hits = difflib.get_close_matches(value, options, n=3, cutoff=0.6)
    if not hits:
        hits = [o for o in options if value.lower() in o.lower()][:3]
    return f" Closest: {', '.join(repr(h) for h in hits)}." if hits else ""


def _normalise(endpoint: str) -> str:
    ep = "/" + endpoint.strip().lstrip("/")
    if not ep.startswith("/api/"):
        ep = "/api/" + ep.lstrip("/")
    return ep.split("?")[0].rstrip("/") or ep


def _match_path(ep: str) -> str:
    """Resolve a concrete path onto its catalogue template (…/{product_id}/…)."""
    if ep in ENDPOINTS:
        return ep
    for tpl in ENDPOINTS:
        if "{" in tpl:
            rx = "^" + re.sub(r"\{[^}]+\}", r"[^/]+", tpl) + "$"
            if re.match(rx, ep):
                return tpl
    known = "\n".join(f"  {p}" for p in sorted(ENDPOINTS))
    raise Refused(f"Unknown endpoint {ep!r}.{_closest(ep, list(ENDPOINTS))}\n"
                  f"Catalogued endpoints:\n{known}")


def _validate(tpl: str, ep: str, params: dict) -> dict:
    meta = ENDPOINTS[tpl]
    allowed = _load_schema().get(tpl, set()) | SERVER_PARAMS

    # 1 ── required-by-meaning, not by schema. The gap router accepts a missing
    #      competitor and returns 200 OK with all seven POOLED, which is exactly
    #      the double-count the no-summing rule forbids. Verified, not theoretical.
    for req in meta.get("requires", []):
        if not params.get(req):
            raise Refused(
                f"{tpl} requires `{req}`.\n"
                f"{NEVER_SUM_COMP}\n"
                f"Omitting it returns 200 OK with every competitor pooled, which reads "
                f"like one competitor's answer and is not one.\n"
                f"Valid values: {', '.join(_vocab_for(req)) or 'see /api/filters/competitors'}")

    # 2 ── unknown params, named against what this endpoint actually accepts
    for k in params:
        if k not in allowed and k not in (meta.get("path_params") or []):
            raise Refused(f"{tpl} does not accept `{k}`.{_closest(k, sorted(allowed))}\n"
                          f"Accepted: {', '.join(sorted(allowed))}")

    # 3 ── filter VALUES, exact match only. No fuzzy resolution: a confident
    #      single match can still be the wrong subcategory, and a number
    #      answered for the wrong scope is indistinguishable from a right one.
    for field, raw in params.items():
        if field not in VALIDATED_FILTERS or raw in (None, ""):
            continue
        options = _vocab_for(field)
        if not options:
            continue
        # csv everywhere except the gap router's single-valued competitor
        single = field == "competitor" and "competitor" in (meta.get("requires") or [])
        values = [str(raw)] if single else [v.strip() for v in str(raw).split(",")]
        if single and "," in str(raw):
            raise Refused(f"{tpl} takes ONE competitor, not a list ({raw!r}).\n{NEVER_SUM_COMP}")
        for v in values:
            if v not in options:
                raise Refused(
                    f"{field}={v!r} is not a valid value.{_closest(v, options)}\n"
                    f"Values are case- and spelling-exact; this server does not guess.\n"
                    + (f"All {len(options)}: {', '.join(options)}" if len(options) <= 25
                       else f"{len(options)} valid values — call "
                            f"query_pricing_api('{VALIDATED_FILTERS[field]}') for the list."))
    return {k: v for k, v in params.items() if k not in SERVER_PARAMS}


# ─────────────────────────────────────────────────────────────────────────────
# Shaping
# ─────────────────────────────────────────────────────────────────────────────
def _rows_of(payload: Any, tpl: str):
    """(rows, put_back) — where the row list lives in this endpoint's payload."""
    at = ENDPOINTS[tpl].get("rows_at")
    if at and isinstance(payload, dict) and isinstance(payload.get(at), list):
        return payload[at], lambda new: payload.__setitem__(at, new)
    if isinstance(payload, list):
        return payload, None
    return None, None


def _shape(payload: Any, tpl: str, want_rows: int, lean: bool) -> dict:
    meta = ENDPOINTS[tpl]
    rows, put_back = _rows_of(payload, tpl)
    note: dict[str, Any] = {}

    if rows is not None:
        total = len(rows)
        # Deterministic order BEFORE any cap. Two of these endpoints sort on a
        # single column with no tiebreak, so equal values come back in arbitrary
        # order -- fine on screen, but under a row cap it means the same question
        # asked twice returns a different "top 25". Same primary key the SQL
        # uses, with a name tiebreak added.
        order = meta.get("order_by")
        if order and rows and isinstance(rows[0], dict) and order[0] in rows[0]:
            field, direction = order
            tie = meta.get("tiebreak") or field
            def _k(r):
                v = r.get(field)
                return (v is None,                                   # NULLS LAST
                        -(v or 0) if direction == "desc" else (v or 0),
                        str(r.get(tie) or ""))
            rows = sorted(rows, key=_k)
        heavy = meta.get("heavy") or []
        if lean and heavy and rows and isinstance(rows[0], dict):
            present = [h for h in heavy if h in rows[0]]
            if present:
                rows = [{k: v for k, v in r.items() if k not in present} for r in rows]
                note["fields_dropped"] = present
                note["fields_dropped_are"] = meta.get("heavy_note", "")
                note["restore_with"] = '_fields="full"'
        if total > want_rows:
            rows = rows[:want_rows]
            note["rows_returned"] = want_rows
            note["rows_total"] = total
            note["order"] = (f"{meta['order_by'][0]} {meta['order_by'][1]}, ties broken by "
                             f"{meta.get('tiebreak')}" if meta.get("order_by")
                             else "as returned by the API, not re-sorted here")
            note["more_with"] = f'_rows=N (max {ROW_CEILING}) or a narrower filter'
        if put_back:
            put_back(rows)
        else:
            payload = rows

    out: dict[str, Any] = {}
    if meta.get("caveats"):
        out["caveats"] = meta["caveats"]
    if note:
        out["truncated"] = note
    out["data"] = payload
    return out


def _save_workbook(resp: httpx.Response, tpl: str, params: dict) -> dict:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    disp = resp.headers.get("content-disposition", "")
    name = (re.search(r'filename="([^"]+)"', disp) or [None, "export.xlsx"])[1]
    stem, _, ext = name.rpartition(".")
    # Date-stamped: exports repeat, and silently overwriting yesterday's file is
    # the kind of loss nobody notices until they need it.
    path = EXPORT_DIR / f"{stem}_{_dt.date.today():%Y-%m-%d}.{ext}"
    n = 2
    while path.exists():
        path = EXPORT_DIR / f"{stem}_{_dt.date.today():%Y-%m-%d}_{n}.{ext}"
        n += 1
    path.write_bytes(resp.content)

    sheets = []
    try:
        import openpyxl
        sheets = openpyxl.load_workbook(path, read_only=True).sheetnames
    except Exception:
        pass
    return {"file": str(path), "sheets": sheets, "bytes": len(resp.content),
            "scope": params or "no filters (whole business)",
            "caveats": ENDPOINTS[tpl].get("caveats", [])}


# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────
INSTRUCTIONS = f"""Breadfast Pricing Intelligence — live competitor pricing and assortment.

READ THESE BEFORE NARRATING ANY NUMBER:
1. {PI_DIRECTION}
2. {NEVER_SUM_COMP}
3. {OURS_ONLY_CEILING}
4. {CARREFOUR_BLIND}
5. Vocabulary: Mapped (not Matched), Util % (not Priced or Coverage %).

Responses carry a `caveats` list for the columns they returned. Read it — it is
scoped to what you actually got back, and it overrides any assumption above.
"""

QUERY_DESC = f"""Call the Pricing Intelligence API. GET only; read-only apart from the
three /workbook endpoints, which write a styled .xlsx to {EXPORT_DIR} and return its path.

PI = Breadfast price / competitor price. ABOVE 1.00 MEANS BREADFAST IS MORE EXPENSIVE.

Endpoints (* = requires `competitor`, single value, never a list):
{inline_catalogue()}

Filters are shared across most endpoints: main_category, sub_category, brand,
global_tier, competitor, vertical (Beauty|Supermarket), exclude_private_label,
private_label_only, brand_scope (shared|shared_by_match), fp_names. Values are
case- and spelling-exact and are NOT auto-corrected — a wrong one is an error
naming the valid options.

Server-side params: _rows (default {MAX_ROWS}, max {ROW_CEILING}), _fields ("lean" drops
per-row scatter arrays, "full" keeps everything).

Call describe_api(path) for one endpoint's full parameter list and caveats.

Start here: /api/executive/competitor-overview for "how do we compare", or
/api/gap/subcategories + /api/gap/brands for "what do they stock that we don't"."""


def query_pricing_api(endpoint: str, params: dict[str, Any] | None = None) -> str:
    """Query the Pricing Intelligence API. See the tool description for the endpoint list."""
    params = dict(params or {})
    try:
        ep = _normalise(endpoint)
        tpl = _match_path(ep)
        meta = ENDPOINTS[tpl]

        want_rows = min(int(params.get("_rows", MAX_ROWS)), ROW_CEILING)
        lean = str(params.get("_fields", "lean")).lower() != "full"

        # Path params are substituted, not forwarded as query string.
        for name in meta.get("path_params") or []:
            if "{" in tpl and params.get(name):
                ep = tpl.replace("{" + name + "}", str(params.pop(name)))
        if "{" in ep:
            missing = re.findall(r"\{([^}]+)\}", ep)
            raise Refused(f"{tpl} needs path parameter(s): {', '.join(missing)}")

        query = _validate(tpl, ep, params)

        with _client() as c:
            resp = c.get(ep, params=query)
        if resp.status_code >= 400:
            body = resp.text[:400]
            raise Refused(f"API returned {resp.status_code} for {ep}\n{body}")

        if meta.get("workbook"):
            return json.dumps(_save_workbook(resp, tpl, query), indent=1, sort_keys=True)
        return json.dumps(_shape(resp.json(), tpl, want_rows, lean),
                          indent=1, default=str, sort_keys=True)

    except Refused as e:
        return f"REFUSED — the call was not made.\n\n{e}"
    except httpx.HTTPError:
        return _START_HINT
    except Exception as e:                                   # noqa: BLE001
        return f"ERROR {type(e).__name__}: {e}"


def describe_api(path: str = "") -> str:
    """Full parameter list and caveats for one endpoint, or the catalogue if omitted."""
    if not path:
        return QUERY_DESC
    try:
        tpl = _match_path(_normalise(path))
    except Refused as e:
        return str(e)
    meta = ENDPOINTS[tpl]
    try:
        allowed = sorted(_load_schema().get(tpl, set()))
    except httpx.HTTPError:
        return _START_HINT
    out = {
        "endpoint": tpl,
        "area": meta["area"],
        "summary": meta["summary"],
        "requires": meta.get("requires", []),
        "accepts": allowed,
        "validated_values": {k: v for k, v in VALIDATED_FILTERS.items() if k in allowed},
        "writes_a_file": bool(meta.get("workbook")),
        "heavy_fields_dropped_unless_fields_full": meta.get("heavy", []),
        "caveats": meta.get("caveats", []),
    }
    return json.dumps(out, indent=1)


def build() -> MCPServer:
    server = MCPServer(
        name="breadfast-pricing",
        title="Breadfast Pricing Intelligence",
        instructions=INSTRUCTIONS,
        version="0.1.0",
    )
    server.add_tool(query_pricing_api, description=QUERY_DESC)
    server.add_tool(describe_api)
    return server


def main() -> None:
    build().run(transport="stdio")


if __name__ == "__main__":
    main()
