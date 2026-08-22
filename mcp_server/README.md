# Pricing Intelligence MCP server

Ask the tool questions in plain English:

> *What's the blended PI for Amazon?*
> *What's the brand gap with Talabat in Ice Cream?*
> *Which subcategories are we most expensive in?*
> *Export the Talabat brand gap.*

It answers by calling the app's own HTTP API, so a number it reports cannot
disagree with the same number on screen.

## Connect it

Already registered for this project in [`.mcp.json`](../.mcp.json). Start the
backend, then start Claude Code from the repo root:

```bash
python3 -m uvicorn backend.main:app --port 8000     # leave running
```

The server needs the `mcp` SDK (`pip install mcp`) and reads the backend over
HTTP — it never opens DuckDB or BigQuery itself. A second DuckDB carries a
documented ~4.8 GB transient, and going through the API is also the only path
that still works once this is hosted for the team.

## Two tools

| | |
|---|---|
| `query_pricing_api(endpoint, params)` | GET any catalogued endpoint. The three `/workbook` endpoints write a styled `.xlsx` to `~/Desktop` and return its path. |
| `describe_api(path)` | Full parameter list and caveats for one endpoint. |

36 endpoints are catalogued. Health/config probes and the superseded CSV
`/export` routes are deliberately left out.

## What it refuses, and why

The server **validates and teaches; it never auto-corrects**. A wrong value is
an error naming the valid options, because a number answered for the wrong
scope is indistinguishable from one answered for the right one.

```
query_pricing_api("/api/gap/brands", {"sub_category": "Ice Cream"})

REFUSED — the call was not made.
/api/gap/brands requires `competitor`.
Competitor-side counts must NEVER be summed across rows: one of their products
is bridged into several of our subcategories, so the total double-counts.
Omitting it returns 200 OK with every competitor pooled, which reads like one
competitor's answer and is not one.
Valid values: Amazon, Amazon Now, Carrefour, Noon Minutes, Rabbit, Seoudi, Talabat
```

That one is not hypothetical — `competitor` is `Optional` on the gap router and
omitting it really does return a pooled 200.

`"talabat"` is likewise an error (`Closest: 'Talabat'`), not a silent correction.

## What rides along with every answer

Each response carries a `caveats` list scoped to the columns it returned — PI
direction, un-summable competitor counts, "Ours only" being a ceiling,
Carrefour's zeros being a collection gap rather than an assortment one. They sit
next to the data because a tool description read twenty turns ago is not where
the warning is needed.

## Response shaping

`/api/commercial/blended-pi` is 2.0 MB unfiltered — one call would fill the
whole context window. Responses are shaped and **say so**:

```json
"truncated": {
  "fields_dropped": ["product_pis", "competitor_product_pis"],
  "fields_dropped_are": "per-product PI scatter behind the strip plots — 87% of the payload",
  "restore_with": "_fields=\"full\"",
  "rows_returned": 25, "rows_total": 206,
  "order": "blended_pi desc, ties broken by group_key",
  "more_with": "_rows=N (max 500) or a narrower filter"
}
```

Two server-side params: `_rows` (default 25, max 500) and `_fields`
(`lean` | `full`).

Rows are put in a **deterministic** order before any cap. Two endpoints sort on
a single column with no tiebreak in SQL (`duckdb_service.py:870` and `:2191`),
so equal values come back in arbitrary order — harmless on screen, but under a
row cap it would mean the same question returned a different "top 25" each time.

## Config

| Variable | Default | |
|---|---|---|
| `PRICING_API_URL` | `http://127.0.0.1:8000` | |
| `PRICING_API_TOKEN` | *(unset)* | Sent as `Authorization: Bearer`. The hook for a hosted build; unused locally, where auth is off because `GOOGLE_CLIENT_ID` is unset. |
| `PRICING_MCP_EXPORT_DIR` | `~/Desktop` | Exports are date-stamped, never overwritten. |
| `PRICING_MCP_MAX_ROWS` | `25` | |

## Maintenance

Parameter names come from the live `/openapi.json` at startup, so they cannot
drift from the code. Hand-maintained in [`catalogue.py`](catalogue.py):

- which endpoints are exposed, and their one-line summaries
- `requires` — params the API accepts but that are wrong to omit
- `heavy` — fields dropped in lean mode
- `caveats` — the misreadings each endpoint's columns invite

Adding an endpoint to the API does **not** expose it here; add it to `ENDPOINTS`
with its caveats. That is deliberate — an endpoint with no caveats written for
it is one nobody has thought about yet.

## Known issue in the data, not in this server

`commercial_category_name` is **nondeterministic**: 43 of 206 subcategories span
more than one commercial category, and four `ANY_VALUE(commercial_category_name)`
calls in `duckdb_service.py` pick one per query. "Ice Cream" reads
*Branded - Fresh & Frozen - Shaaban* on one call and *Private Label - Snacks* on
the next, on the Commercial and Gap screens too. No metric is affected — rows
group by subcategory and this is a label carried alongside — but the column is
not trustworthy. Surfaced by the verification sweep here; fixing it changes what
is on screen, so it needs sign-off.
