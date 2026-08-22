# Brand & Subcategory Gap Analysis — shipped spec

**Status:** shipped · **Date:** 2026-08-03 · **Branch:** `feat/brand-subcategory-gap`
**Route:** `/gap-analysis` · **API:** `/api/gap/*`

The fifth workspace. It answers, for **one competitor at a time**, per brand and per
Breadfast subcategory: how much of our range is matched and how much *can* be, which brands
we share / own alone / they own alone, which of their products we don't carry and where
those belong in our taxonomy, and the price position + commercial weight of every gap.

Planning doc: `docs/plans/brand-subcategory-gap-tab-plan.md` (§8 carries the re-baselined
validation numbers). Validated BigQuery layer: `docs/specs/gap-analysis-sql-extension.sql`.

---

## 1. The one thing to get right

`sale_PI = Breadfast ÷ competitor`, so **PI > 1.00 means Breadfast is MORE expensive.**
The wireframes, the deck, `DESIGN_PROMPT.md` and `docs/specs/PI-query.sql` all use the
inverted gen-1 convention. Never copy a PI number or a cheaper/expensive label from those.
`PIMeter.vue` and this tab are correct.

---

## 2. Two grains, deliberately kept apart

`dbt_gohary.competitor_price_monitoring_fps` now holds two row types, discriminated by
`row_type`:

| | `'breadfast'` | `'competitor'` |
|---|---|---|
| grain | (product, fp, competitor) | (competitor, competitor product) |
| rows | ~2,912,800 | 65,713 |
| `product_id` / `fp_id` | populated | **NULL** — national |
| serves | every existing tab, plus our side of the gap | "they carry, we don't" |

**`_BASE_CTE` collapses on `(product_id, competitor_id)`.** Competitor rows carry
`product_id = NULL`, so without a guard all 72,779 would fold into one row per competitor
and silently corrupt every Executive / Commercial / Master-Data number. The guard lives in
five places, all in SQL — routers only build filter dicts:

* `duckdb_service._BASE_CTE` (`scoped`), injected via `_base_cte()` → `_as_and()`
* `duckdb_service.get_fp_competitor_pi` — both branches **and** its `modal` CTE
* `duckdb_service._load_product_rows`
* `duckdb_service._init_duckdb` FP pre-warm probe
* `bigquery_service._aggregate_to_global` (the pandas path)

Competitor rows are served from a separate DuckDB table, `comp_catalogue`, materialized
alongside `global_base` in `_init_duckdb` / `refresh_parquet`. They need no collapsing —
BigQuery already emits exactly one row per (competitor, competitor product).

`_assert_gap_schema()` fails fast at startup on a pre-gap Parquet, because **a restart does
not pick up new columns** — `_load_data` rehydrates whatever file is on disk. Force a
rebuild with `python scripts/rebuild_parquet.py`.

---

## 3. Adding a column, end to end

1. `docs/FP_granularity_pricing.sql` → `bq query < …` (**CREATE OR REPLACE on the live
   table** — confirm with the owner first).
2. `bigquery_service.FPS_QUERY` — the explicit column list. A column not listed here
   silently never reaches the app.
3. Cast lists in `_load_from_bigquery` if it is numeric, boolean or an id.
4. `python scripts/rebuild_parquet.py`, then check `cache/pricing_data/fp_grain.json`.

`COLUMN_MAP` renames on load: `avg_daily_revenue → total_revenue`, `product_name_en →
product_name`, `breadfast_sale_price → bf_sale_price`, `competitor_last_updated_day →
competitor_price_updated_at`. Write roll-up SQL against the **renamed** names.

Roll-up SQL is **DuckDB**: `COUNT(*) FILTER (WHERE …)` not `COUNTIF`, `CASE WHEN` not
`IF()`, `list_sort(list_distinct(list(x) FILTER (…)))` for the brand lists.

---

## 3b. Competitor catalogue dedup

Competitor catalogues contain the same product many times over. `comp_products` collapses
each **(competitor, normalized name, brand)** group to exactly one row:

1. a matched copy wins (`is_matched_any DESC`),
2. otherwise the most recently seen (`comp_last_seen DESC`),
3. ties broken on `competitor_product_key` so the choice is stable between builds.

Rows with an empty name are never collapsed — a missing name is not evidence of duplication.
Bundles (`' + '` in the name) are dropped unless matched, since we don't carry bundles.

This lives at the single definition of the catalogue **on purpose**, so it applies to
everything downstream: the brand universe, the category bridge, the recommendation flags,
the catalogue-health counts and the competitor-only output branch. If you ever need a
non-deduped view, add a separate CTE — do not relax this one.

Watch for a regression here: an `OR is_matched_any = 1` style short-circuit in the `QUALIFY`
keeps *every* matched copy rather than one, and the symptom is subtle because the leaked rows
all classify as `Matched Out Of Scope` (`comp_matched_any` has no `fp_registry` gate, so it
flags products that `paired_comp_keys` does not exclude). That bug cost 8.5 % of the
catalogue. Regression check:

```sql
SELECT COUNT(*) FROM (
  SELECT competitor_name, LOWER(TRIM(product_name_en)) nn, brand_key, COUNT(*) n
  FROM `bf-data-dev-qz06.dbt_gohary.competitor_price_monitoring_fps`
  WHERE row_type = 'competitor'
  GROUP BY 1,2,3 HAVING COUNT(*) > 1 AND nn <> ''
)  -- must be 0
```

---

## 4. Metric definitions

| Metric | Definition | Why |
|---|---|---|
| **Matched %** | `is_mapped` ÷ products in scope | Linkage, not pricing. Resolves plan §9.1 — `FP_AGGREGATION_LOGIC.md` mandates `is_mapped`, `FP_FILTER_FIXES.md` documents `has_PI`; the BigQuery roll-up uses `is_mapped` and so do we. |
| **Addressable %** | `is_mapped` ÷ (products − confirmed no-match) | Products the matcher positively rejected can never be matched, so leaving them in the denominator understates the team's real ceiling. |
| **Shared-brand %** | `is_mapped` ÷ products whose brand the competitor also carries | Separates a matching backlog from a genuine assortment difference. Not guaranteed ≥ Matched % — Vegetables is 29.9 vs 17.2. |
| **Confirmed no-match** | not mapped, no positive recommendation, ≥1 negative one | A real assortment gap, not a backlog item. Stricter source than STEP 12: filtered to `pricing_tool_version='v2'` and `country_code='EG'`, so a v1-era rejection can't drive it. |
| **Potential match** | not mapped, not confirmed-no-match, best similarity ≥ 0.85 **still in portfolio** | Ready for review. 0.85 everywhere. |
| **Blended PI** | quantity-weighted `sale_PI`, at **FP grain** | Matches the BigQuery `subcategory_summary` roll-up. See the caveat in §6. |
| **Coverage %** | used ÷ eligible products | Plan §9.2 picked `used/eligible`; labelled as such in the definitions panel. |
| **They carry, we don't** | active competitor products with no pair, placed by the category bridge | **Never sum across subcategories** — one competitor product can bridge to several (plan §9.7). |

**Scope.** Beauty and private label are excluded by default: there, "we don't carry it" is
usually a deliberate assortment call. The two sides need different predicates — ours by
`main_category_name`, theirs by the bridge's `beauty_path_share > 0.90`, because a
competitor-only row has no category of ours to read.

**Filters.** The two sides also don't share a column vocabulary. Only `competitor`, `brand`
and `sub_category` cross over (subcategory maps to the bridged `mapped_bf_sub_category` on
their side). Replaying tier / commercial-category / action-type filters against competitor
rows would delete the whole catalogue.

---

## 5. API

```
GET /api/gap/filters                       competitors (+has_catalogue, matched_products), subcategories, categories
GET /api/gap/kpis                          headline numbers
GET /api/gap/subcategories                 the subcategory roll-up
GET /api/gap/brands                        brand roll-up; ?brand_type=shared|bf_only|comp_only
GET /api/gap/products                      ?side=breadfast|competitor, paginated, searchable
GET /api/gap/export                        ?view=subcategories|brands|products — full rows
```

Shared filter params: `competitor`, `main_category`, `sub_category`, `brand`,
`global_tier`, `subcat_tier`, `fp_names`, plus `scope` (`excl_beauty_pl` default | `all`)
and `include_private_label`.

**No `@abstractmethod`s were added to `data_interface.py`.** That ABC is enforced at
instantiation, so a new abstract method breaks `DATA_SOURCE=mock` outright. The router
returns a 503 with an explanatory message when the service isn't DuckDB-backed — the same
precedent as `get_fp_competitor_pi` and `get_product_fp_matrix`.

---

## 6. Known limitations, all disclosed in the UI

1. **Blended PI here is FP-grain**, per the plan and the BigQuery roll-up. The Commercial
   tab's blended PI is the product-collapsed `_BASE_CTE` recompute. The two can differ for
   the same subcategory. If that becomes confusing in practice, unify on the Commercial
   definition — but that is a product decision, not a bug fix.
2. **Carrefour has no live v2 catalogue.** `competitor_has_v2_catalogue = false`; the
   competitor-only side is empty. The tab says so rather than showing zeros. Our own
   matching figures for Carrefour are still valid.
3. **Seoudi and Rabbit beauty blind spot** (plan §9.5). Their flat "Beauty and Personal
   Care" node keeps in-scope evidence, so `beauty_path_share` never crosses 0.90 and their
   beauty products survive the exclude-beauty scope. Banner shown.
4. **Brand-name variants don't collapse** (plan §9.4). `L'Oréal Paris` / `L'Oreal` /
   `Elvive` are three brands, so "brands only they carry" is an upper bound. Standing note
   on the brand table. Fuzzy brand resolution is its own task.
5. **Private label has two definitions in the codebase** (plan §9.3) — SQL
   `brand_name != 'Breadfast'` vs pandas `contains('breadfast')`. The gap layer uses the
   wider pandas convention so "Breadfast Bakery" is a first-class brand row. Still
   un-normalised elsewhere.
6. **Multi-competitor is possible via the API but not offered in the UI.** The picker is
   single-select: unioning competitors would double-count products they both stock and make
   brand counts meaningless.
7. **Scope won't tie to the source workbooks** (plan §9.6) — the tool's universe is
   `product_type='single'` only. Expected.

---

## 7. Verification

`scripts/kpi_snapshot.py` is the regression harness — 182 endpoint × filter combinations
across Executive, Commercial, Master-Data and the filter option lists.

```bash
python scripts/kpi_snapshot.py before.json                 # current cache
python scripts/kpi_snapshot.py after.json  path/to.parquet # a specific Parquet
python scripts/kpi_snapshot.py --diff before.json after.json
```

It canonicalizes row order before comparing, because DuckDB's parallel aggregation makes
both result-set order and `ANY_VALUE` picks unstable between two runs of identical code.
**Establish that noise floor before reading any diff** — roughly 30 of the 182 entries
differ run-to-run for free. The 61 pure-scalar KPI entries are stable and are the ones to
hold to account.
