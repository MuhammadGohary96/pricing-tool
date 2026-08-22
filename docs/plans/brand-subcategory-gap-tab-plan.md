# Plan — Brand & Subcategory Gap Analysis Tab

**Status:** ready to implement · **Revised:** 2026-08-03 (rev 2)
**Audience:** a fresh Claude Code session working in this repo.

Everything below was verified against the live codebase and against BigQuery.
Reference numbers are real. **Rev 2 changes:** the match source is now exclusively
`fct_daily_competitor_price_comparison`, and 11 corrections from a full codebase
recon have been folded in (§9 lists them).

---

## 0. Before you touch anything

```bash
git fetch origin && git checkout -B feat/brand-subcategory-gap origin/main
```

Local `main` is stale (`7e811f7`). `origin/main` is `de56d49` (PR #6). The current
HEAD `feat/blended-pi-subcategory-columns` @ `733c3e1` is **already merged**.
A stale worktree exists at `.claude/worktrees/practical-noyce-1e3e46` — never edit there.

**Task #1 is not this feature.** `docs/FP_granularity_pricing.sql` is stale and did
**not** build the live table. Production differs in two places:

| | Repo file (stale) | Production (real) |
|---|---|---|
| `competitor_registry` | `WHERE competitor_name != 'Breadfast'` → 12 competitors | `WHERE competitor_name IN ('Amazon','Amazon Now','Seoudi','Talabat','Noon Minutes','Rabbit','Carrefour')` → 7 |
| `fp_registry` | `REGEXP_CONTAINS(fp_name, r'FP #\d+$')` | `(REGEXP_CONTAINS(fp_name, r'FP #\d+$') OR lower(fp_name) LIKE '%sahel%')` |

Arithmetic proof: 2,885,967 live rows ÷ 409,490 per competitor ≈ **7.05**.
**Sync the repo file to the production query and commit it first**, then apply this plan.

---

## 1. Goal

A fourth analytics tab answering, per **brand** and per **Breadfast subcategory**, for each
competitor: how much of our assortment is mapped and how much *can* be; which brands we
share / are ours alone / are theirs alone; which competitor products we don't carry and
**which of our subcategories each belongs to**; and the price position + commercial weight
of every gap.

---

## 2. Decisions already taken (do not re-litigate)

| # | Decision |
|---|---|
| 1 | Competitor-only rows are **national**: `fp_id`/`fp_name` NULL, `row_type` = `'breadfast'` \| `'competitor'`. |
| 2 | Private label **kept** and flagged `is_private_label`; tab defaults to excluding it from gap rates, stays togglable. |
| 3 | Beauty **kept** and flagged (`is_beauty` ours, `beauty_path_share` theirs). One pipeline, UI toggle. |
| 4 | BigQuery stays **product grain**. Brand × competitor and subcategory × competitor roll-ups are computed **in-app by DuckDB**. |
| 5 | Category bridge computed **in BigQuery**, product-level. |
| 6 | Similarity threshold **0.85 everywhere**. |
| 7 | **All 7 competitors** incl. Carrefour + a `competitor_has_v2_catalogue` data-quality flag. |
| 8 | Four measure families: mapping/gap, brand overlap, price index, commercial weight. |
| 9 | **Match source = `fct_daily_competitor_price_comparison` only** (rev 2). `fct_competitor_price_monitoring` is not used, so gap metrics can never contradict `is_mapped` / `sale_PI`. |

---

## 3. Architecture (verified)

```
BigQuery  bf-data-dev-qz06.dbt_gohary.competitor_price_monitoring_fps   (2,885,967 rows · location EU)
   ↓  bigquery_service.py  FPS_QUERY          ← EXPLICIT 41-COLUMN LIST (+4 derived = 45)
   ↓  cache/pricing_data/fp_grain.parquet     (100.9 MB, sorted fp_name/sub_category_name/product_id)
   ↓  duckdb_service.py
        VIEW  fp_grain                        ← the ONLY place fp_id/fp_name survive
        TABLE global_base = _BASE_CTE(∅)      ← :109-123, ~150 K rows
   ↓  routers/{executive,commercial,master_data}.py     (competitor_products.py reads a DIFFERENT table)
   ↓  api/client.js → stores/*.js → views/*.vue
```

**No request ever touches BigQuery** — BQ is batch-refresh only (`docs/BQ_PERFORMANCE_PLAN.md:93-102`).
Refresh: hourly daemon `_auto_refresh_loop` (`backend/main.py:230-257`) comparing
`latest_bq_modified()` against `sync_state.json`.

### 3.1 ⚠️ Five landmines

1. **`_BASE_CTE` (`duckdb_service.py:300-433`) collapses to ONE ROW PER `(product_id, competitor_id)`**
   and **recomputes** modal prices, `sale_PI`, `used_product`, `action_type` locally rather than
   trusting the BQ columns of the same name. Competitor-only rows have `product_id = NULL` and
   would **all collapse into one row per competitor**. They must bypass it entirely — see §5.
2. **`FPS_QUERY` is an explicit 41-column list.** A column added in BigQuery but not there
   silently never reaches the app.
3. **A restart does not pick up new columns.** `_load_data` (`main.py:157-224`) rehydrates the
   existing Parquet. Force a refresh or delete the cache.
4. **PI direction:** live code is `sale_PI = BF ÷ competitor` → **PI > 1 means Breadfast is MORE
   EXPENSIVE** (`duckdb_service.py:397`, `docs/FP_Price_Index.md:23-38`, `docs/DDD.md:19`).
   The wireframes, the deck, `DESIGN_PROMPT.md`, the TechSpec and `docs/specs/PI-query.sql:385`
   all use the **inverted gen-1 convention**. Never copy a PI number or a cheaper/expensive
   label from those. This is the single most likely way to ship an inverted feature.
5. **`BQ_TABLE` disagreement:** `config.py:8`, `.env.sample:7`, `PRODUCTION.md:16` all say
   `pricing_index_analysis`; `.env` says `competitor_price_monitoring_fps`. **`.env` wins.**
   Fix the three stale references — a deploy trusting the sample fails.

### 3.2 Existing tabs

| Route | View | Persona |
|---|---|---|
| `/executive` | `views/ExecutiveView.vue` (426 L) | leadership |
| `/commercial` | `views/CommercialView.vue` (243 L) | category managers |
| `/master-data` | `views/MasterDataView.vue` (126 L) | master-data team (routed, no header tab) |
| `/competitor-products` | `views/CompetitorProductsView.vue` (420 L) | **the template** — reads `BQ_COMPETITOR_TABLE = competitor_products_analysis` |

Follow `docs/specs/phase-3-competitor-products-tab.md` end-to-end. Tabs are declared in
`components/layout/AppHeader.vue` (`const tabs = [...]`), routed in `router/index.js`.

### 3.3 Reusable UI (do not rebuild)

`PageShell` · `PageHeader` (+`#stats` slot) · `PillButton` (`variant: brand|ghost`) ·
`MultiSelect` · `ExportButton` (single export path) · `EmptyState` · `TierBadge` ·
`ProductPivotTable` (`fixedCols` :303-311) · `BlendedPITable` (`groupBy` :203).
Design tokens are binding — `DESIGN.md` (`bg-paper #FAF8FC`, Geist).

---

## 4. Data layer (BigQuery)

Validated SQL: **`docs/specs/gap-analysis-sql-extension.sql`**. Additive — 6 new CTE groups,
~18 new columns, one `UNION ALL` branch, spliced after STEP 12 / STEP 13.

**Source contract:** all match determination flows from the query's own STEP 8/9/9b CTEs
(`competitor_raw` → `competitor_clean` → `competitor_mapping`), i.e. the daily comparison fact.
`dim_competitor_products` is read **only as the competitor catalogue** — it must be, since the
daily fact contains matched pairs only and never-matched competitor products exist nowhere else.

**Validation performed (rev 2):** `--dry_run` passes (37.6 GB). Executed aggregated →
BF branch unchanged; competitor branch adds **72,825 national rows** (+2.5 %):

| Competitor | comp-only rows | bridged | has catalogue |
|---|---|---|---|
| Amazon | 33,698 | 27,334 | ✓ |
| Talabat | 11,589 | 9,320 | ✓ |
| Seoudi | 9,779 | 9,432 | ✓ |
| Amazon Now | 8,713 | 6,148 | ✓ |
| Rabbit | 4,556 | 4,193 | ✓ |
| Noon Minutes | 4,490 | 3,318 | ✓ |
| **Carrefour** | **0** | 0 | **✗ (flagged)** |

> The comp-row count is higher than the 63,898 in rev 1 because the daily fact recognises
> fewer matches than the monitoring table, so fewer competitor products count as "paired".
> Expected and correct under decision 9.

### 4.1 New columns

`row_type` · `is_beauty` · `is_private_label` · `brand_key` · `is_shared_brand` ·
`matched_comp_active_7d` · `is_confirmed_no_match` · `is_potential_match` ·
`best_similarity_in_portfolio` · `competitor_product_key` · `comp_brand_name` ·
`category_level_1..4` · `mapped_bf_sub_category` · `mapped_bf_sub_categories_all` ·
`mapped_pct_of_comp_category` · `bridge_level` · `beauty_path_share` ·
`competitor_has_v2_catalogue`

On Breadfast rows `mapped_bf_sub_category` echoes the product's own subcategory, so **one
filter slices both sides**. `is_mapped` is untouched — it remains the single match truth.

---

## 5. Pipeline changes

1. **`docs/FP_granularity_pricing.sql`** — sync to production (§0), then splice in the
   extension. Re-run `CREATE OR REPLACE TABLE`.
2. **`backend/services/bigquery_service.py`** — add every new column to `FPS_QUERY`'s column
   list. Note `COLUMN_MAP` (:43-52) renames on load: **`avg_daily_revenue → total_revenue`**.
3. **Force a Parquet rebuild** (landmine 3). Confirm `fp_grain.json` shows the new columns.
4. **Keep competitor rows out of the Breadfast path** — three edits, *not* in the routers
   (routers only build filter dicts and contain no SQL):
   * `duckdb_service.py:301` — add `row_type = 'breadfast'` to the `scoped` CTE inside `_BASE_CTE`
   * `duckdb_service.py:684` — same in `get_fp_competitor_pi`
   * `bigquery_service.py:740` — same in the pandas `_aggregate_to_global`
   `competitor_products.py` reads a different table — **no change**.
   **Then diff every Executive/Commercial/Master-Data KPI before vs after. They must be identical.**
5. **Add a second DuckDB materialization for the competitor side** — copy
   `_materialize_global_base` (`duckdb_service.py:109-123`):
   ```sql
   CREATE OR REPLACE TABLE comp_catalogue AS
   SELECT * FROM fp_grain WHERE row_type = 'competitor';
   ```
   No collapsing: these rows are already one per competitor product, national.
   **Do not send them through `_BASE_CTE`** (landmine 1).
6. **`routers/gap.py`** + service methods (§6), then the frontend (§7).

---

## 6. Backend endpoint

```python
router = APIRouter(prefix="/api/gap", tags=["gap"])
# GET /api/gap/kpis · /brands · /subcategories · /products
```

* mirror the `_filters()` dependency pattern from `routers/commercial.py:19-52` (widest set),
  and **add** `scope` (`all` | `excl_beauty_pl`) and `include_private_label`
* register in `backend/main.py`
* **Do NOT add `@abstractmethod`s to `data_interface.py`.** The ABC is enforced at
  instantiation, so a new abstract method breaks `DATA_SOURCE=mock` — the mode the
  verification checklist relies on. Follow the established precedent
  (`get_fp_competitor_pi`, `get_product_fp_matrix`): implement on the concrete DuckDB
  service only, or add a mock implementation too.
* auth is global via `google_auth_middleware` (`backend/auth.py:35`) — nothing to do

---

## 7. DuckDB roll-up SQL

**Dialect rules:** this is DuckDB, not BigQuery. Use `COUNT(*) FILTER (WHERE ...)` (the
codebase convention), **not** `COUNTIF`. Use `CASE WHEN`, not `IF()`. The revenue column is
**`total_revenue`**, not `avg_daily_revenue` (renamed by `COLUMN_MAP`).

### 7.1 Scope predicate (drives the UI toggle)

```sql
-- scope = 'excl_beauty_pl'  (Breadfast side)
AND NOT COALESCE(is_beauty, FALSE)
AND NOT COALESCE(is_private_label, FALSE)
-- competitor side of the same toggle: drop beauty-only categories
AND COALESCE(beauty_path_share, 0) <= 0.90
```

### 7.2 Subcategory × competitor

```sql
WITH bf_prod AS (                    -- collapse FP replication FIRST
  SELECT sub_category_name, product_id,
         any_value(brand_key)            AS brand_key,
         max(is_mapped)                  AS is_mapped,
         max(is_shared_brand)            AS is_shared_brand,
         max(is_confirmed_no_match)      AS no_match,
         max(is_potential_match)         AS potential,
         any_value(total_revenue)        AS rev,
         any_value(avg_daily_quantity)   AS qty
  FROM global_base            -- already row_type='breadfast' after §5 step 4
  WHERE 1=1 /* + scope + filters */
  GROUP BY 1,2
),
bf_side AS (
  SELECT sub_category_name,
    count(*)                                            AS bf_products,
    count(*) FILTER (WHERE is_mapped)                    AS matched,
    round(100.0*count(*) FILTER (WHERE is_mapped)/nullif(count(*),0),1)                AS mapping_pct,
    round(100.0*count(*) FILTER (WHERE is_mapped AND is_shared_brand)
              /nullif(count(*) FILTER (WHERE is_shared_brand),0),1)                    AS mapping_pct_shared,
    count(*) FILTER (WHERE no_match)                     AS confirmed_no_match,
    round(100.0*count(*) FILTER (WHERE is_mapped)
              /nullif(count(*)-count(*) FILTER (WHERE no_match),0),1)                  AS addressable_pct,
    count(*) FILTER (WHERE potential)                    AS potential_match,
    count(DISTINCT brand_key) FILTER (WHERE is_shared_brand)      AS shared_brands,
    count(DISTINCT brand_key) FILTER (WHERE NOT is_shared_brand)  AS bf_only_brands,
    round(sum(rev),0)                                    AS daily_revenue
  FROM bf_prod GROUP BY 1
),
pi_side AS (                         -- PI stays at FP grain: query the fp_grain VIEW
  SELECT sub_category_name,
    round(sum(CASE WHEN used_product THEN sale_PI*avg_daily_quantity END)
          /nullif(sum(CASE WHEN used_product THEN avg_daily_quantity END),0),3)         AS blended_PI,
    round(100.0*count(DISTINCT product_id) FILTER (WHERE used_product)
              /nullif(count(DISTINCT product_id) FILTER (WHERE eligible_product),0),1)  AS coverage_pct
  FROM fp_grain WHERE row_type='breadfast' GROUP BY 1
),
comp_side AS (                       -- competitor-only, placed via the bridge
  SELECT mapped_bf_sub_category AS sub_category_name,
         count(*)                                                  AS comp_only_products,
         count(DISTINCT brand_key) FILTER (WHERE NOT is_shared_brand) AS comp_only_brands
  FROM comp_catalogue
  WHERE mapped_bf_sub_category IS NOT NULL
  GROUP BY 1
)
SELECT * FROM bf_side
LEFT JOIN pi_side   USING (sub_category_name)
LEFT JOIN comp_side USING (sub_category_name);
```

`blended_PI` is **quantity-weighted** (`avg_daily_quantity`). `docs/FP_AGGREGATION_LOGIC.md:349-459`
says revenue-weighted — **that section is wrong**; `DDD.md` rule 9, `FP_Price_Index.md:131-160`
and the live SQL all say quantity.

### 7.3 Brand × competitor

Identical shape, `GROUP BY brand_key` (display `brand_name`), plus
`count(DISTINCT sub_category_name)` for category spread. Brand type: `shared` if both sides
have products, `bf_only` if only ours, `comp_only` if only theirs.

### 7.4 Brand lists per subcategory (within-subcategory scope)

A brand counts as shared for a subcategory only if **both sides have products in that
subcategory**. Catalogue-level sharing produces confusing rows (a competitor selling a
brand's jam made it look "shared" inside Vegetables). Use `list_sort(list_distinct(...))` /
`string_agg` — both DuckDB-native.

---

## 8. Validation

**RE-BASELINED 2026-08-03** from the shipped `/api/gap/subcategories`, **Talabat, excl.
beauty, private label kept** (`scope=excl_beauty_pl&include_private_label=true` — the scope
the original table was built under; the tab's own default also drops private label):

| Subcategory | BF prod | Matched | Map % | Map % shared | No-match | Addr % | Blended PI | Coverage % | Comp-only | Shared br | BF-only br | Comp-only br |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Ice Cream | 200 | 149 | 74.5 | 92.0 | 44 | 95.5 | 0.996 | 76.3 | 100 | 5 | 6 | 11 |
| Chocolate | 269 | 226 | 84.0 | 93.3 | 39 | 98.3 | 0.991 | 77.2 | 303 | 26 | 6 | 26 |
| Long-Life Milk | 35 | 34 | 97.1 | 97.1 | 1 | 100.0 | 1.006 | 100.0 | 8 | 5 | 0 | 1 |
| Branded Cheese | 152 | 122 | 80.3 | 80.3 | 29 | 99.2 | 1.023 | 79.4 | 142 | 12 | 0 | 12 |
| Chips | 171 | 112 | 65.5 | 80.5 | 55 | 96.6 | 0.993 | 58.0 | 111 | 11 | 5 | 14 |
| Poultry | 71 | 33 | 46.5 | 86.8 | 29 | 78.6 | 1.070 | 76.9 | 57 | 3 | 3 | 1 |
| Vegetables | 87 | 26 | 29.9 | 17.2 | 49 | 68.4 | 1.075 | 18.4 | 93 | 2 | 4 | 5 |
| Fruits | 95 | 7 | 7.4 | 0.0 | 71 | 29.2 | 1.093 | 6.8 | 78 | 2 | 4 | 7 |

Talabat headline KPIs at this scope: 8,289 products · 4,839 matched (58.4 %) ·
3,235 confirmed no-match · 95.7 % addressable · 9,319 competitor-only (7,218 bridged) ·
506 shared / 248 BF-only / 884 comp-only brands.

> Comp-only columns are **post-dedup** (see the dedup note below). Every Breadfast-side
> column is unchanged by that fix.

> **What moved vs. the rev-1 table, and why.** All 8 blended PIs and all 8 matched counts
> came out identical, which is the strongest signal the roll-up is faithful. Two families
> of difference, both predicted:
> * `comp_only_products` is systematically higher (Ice Cream 94→114, Chocolate 267→324,
>   Long-Life Milk 6→22). Rev 2 sources matches from the daily comparison fact, which
>   recognises fewer matches than the monitoring table, so more competitor products count
>   as unpaired. Expected and correct under decision 9.
> * `bf_products` grew in fresh ranges (Fruits 78→95, Vegetables 79→87, Chips 169→171) over
>   the 8 days between the reference and the rebuild, which cascades into Map %, Addr %
>   and Coverage % for those rows. Ambient assortment churn, not a logic change.
> Ice Cream, Chocolate, Long-Life Milk and Poultry match on **every** metric except
> `comp_only_products`.

Checklist — **all verified 2026-08-03**:

- [x] existing Executive / Commercial / Master-Data KPIs unmoved by the `row_type` guard.
      Proved two ways: `_BASE_CTE` output is bit-identical between pre-change code on a
      Breadfast-only Parquet and guarded code on the full Parquet (85,862 pairs / 12,266
      products / 8,769 used / 33,824 eligible / 27,036 mapped / blended PI 1.00822005); and
      `scripts/kpi_snapshot.py` over 182 endpoint × filter combinations (532,560 leaf
      values) shows all 61 pure-scalar KPI entries identical. The 30 entries that do differ
      also differ between two runs of *identical* code on *identical* data — pre-existing
      `ANY_VALUE` / row-order nondeterminism under DuckDB's parallel aggregation, not a
      regression. Use `scripts/kpi_snapshot.py --diff a.json b.json` (canonicalizes row
      order; `--raw` to keep it).
- [x] competitor rows total **65,713** after the duplicate fix below (72,779 before it; the
      plan's ≈72,825 estimate carried the same duplication). Carrefour = 0 with
      `competitor_has_v2_catalogue = false`.
- [x] **zero** remaining (competitor, name, brand) groups with more than one row.
- [x] `matched ≤ addressable ≤ bf_products` on every roll-up row, across all 7 competitors
      × both scopes — 0 violations.
- [x] `comp_catalogue` = 72,779 == competitor rows in the Parquet (proves they bypassed
      `_BASE_CTE`).
- [x] verified against **DuckDB**, not mock.
- [x] did **not** assert `mapping_pct ≤ mapping_pct_shared` — Vegetables (29.9 vs 17.2) and
      Branded Cheese (equal) confirm it does not hold.

### Duplicate competitor products — fixed 2026-08-03

The `comp_products` dedup was meant to reduce each (competitor, name, brand) group to one
row: a matched copy if there is one, otherwise the most recently seen. Its `QUALIFY` had an
`OR is_matched_any = 1` short-circuit that kept **every** matched copy instead of one.

That leaked **6,159 duplicate rows — 8.5 % of the competitor catalogue**: 19 identical
"Flower Hair Clip" rows for Amazon, 18 "Ice Cream" for Amazon Now. All were
`Matched Out Of Scope`, which is the diagnostic: `comp_matched_any` has no `fp_registry`
gate, so it flags a product matched that `paired_comp_keys` (FP-gated, via
`competitor_mapping`) does not exclude — so every copy fell through to the comp-only branch.

The fix is a single deterministic ranking, applied at the one place the catalogue is
defined so it carries into the brand universe, the category bridge, the recommendation
flags, the catalogue-health counts and the comp-only branch alike:

```sql
QUALIFY name_norm = ''                      -- an unnamed row is not evidence of duplication
     OR ROW_NUMBER() OVER (
            PARTITION BY competitor_id, name_norm, brand_norm
            ORDER BY is_matched_any DESC,   -- a matched copy wins
                     comp_last_seen DESC,   -- else the freshest
                     competitor_product_key -- deterministic tiebreak
        ) = 1
```

Removed 19,116 catalogue rows (10,170 of them active); competitor output rows 72,779 →
**65,713**. Same-name survivors are genuinely different brands — "Flower Hair Clip" keeps
Daphne and Catch Up; "Ice Cream" keeps one row per ice-cream brand.

**No Executive / Commercial / Master-Data number moved.** The dedup only feeds gap-only
columns; `grep` confirms **zero** references to `comp_products` / `comp_brand` / `rec_flags`
/ `competitor_catalogue` / `bridge_*` anywhere in STEPS 1-13, which are the sole source of
`classification`, `used_product`, `sale_PI` and `is_mapped`. The 4 scalar entries that did
shift between the two rebuilds (+1 Rabbit used product, ±2 classification, blended PI in the
4th decimal) are ambient source drift: breadfast rows went 2,912,511 → 2,912,763 over the
same interval, and the dedup cannot add a breadfast row.

### Two further bugs the first rebuild surfaced, both fixed in `bigquery_service.py`:

* `product_id` / `fp_id` / `fp_name` were cast with a bare `.astype(str)`. Those columns
  became nullable for the first time (competitor rows), so NULL turned into the literal
  strings `"nan"` / `"None"` — `"None"` appeared as a 64th entry in the FP dropdown. The
  integer path also needed a nullable-`Int64` hop: without it every `product_id` rendered
  as `"1180345.0"`.
* The DuckDB FP pre-warm picked its target FP with `ORDER BY COUNT(*) DESC`. The competitor
  rows share one NULL `fp_name` group that is larger than any real FP (72,779 vs ~46,000),
  so it selected NULL and silently degraded into a second GLOBAL query.

---

## 9. Unresolved / risks

| # | Item | Action |
|---|---|---|
| 1 | **Mapping-coverage numerator** — `FP_AGGREGATION_LOGIC.md:683-726` mandates `is_mapped`; `FP_FILTER_FIXES.md:99-150` documents the shipped code as `has_PI`. | Verify against `duckdb_service.py:609-676` before reusing either formula. |
| 2 | **Coverage denominator** — `used/eligible` vs `used/total_products`. | Pick one, label it in the UI. |
| 3 | **Private label has two definitions** — SQL `brand_name != 'Breadfast'` (`:289`) vs pandas `contains('breadfast')` (`:184`). "Breadfast Bakery" is kept by one, dropped by the other. The extension uses the **wider** pandas convention because brand grain makes `Breadfast` a first-class row. | Normalise before shipping. |
| 4 | **Brand-name variants don't collapse** — `L'Oréal Paris` / `L'Oreal` / `Elvive` stay separate, so comp-only brand counts are overstated. | Fuzzy brand matching is its own task. |
| 5 | **Seoudi / Rabbit beauty blind spot** — their flat "Beauty and Personal Care" category keeps in-scope evidence, so `beauty_path_share` never crosses 0.90 and their beauty products survive the excl-beauty scope. | Disclose in the UI. |
| 6 | **Scope differs from the source workbooks** — the tool's universe is `dim_product_commercial_profile` = `product_type='single'` only (no `group`). Numbers will not tie to the Excel analysis. | Expected, not a bug. |
| 7 | **Comp products can bridge to several subcategories** | Never sum `comp_only_products` across subcategories. |
| 8 | **Row-count folklore** — `BQ_PERFORMANCE_PLAN.md:12` says 4,754,589 rows; that predates the 7-competitor scope. Live = **2,885,967**. | Ignore the old figure. |

---

## 10. Sequence

1. `git checkout -B feat/brand-subcategory-gap origin/main`; sync + commit `FP_granularity_pricing.sql`.
2. Splice the extension; `--dry_run`; rebuild the BQ table.
3. Add columns to `FPS_QUERY`; force Parquet rebuild; confirm the sidecar.
4. `row_type='breadfast'` in the three SQL locations; **diff KPIs**.
5. `comp_catalogue` materialization; `routers/gap.py`; service methods (no ABC changes).
6. `views/BrandGapView.vue` + store + api client entry + route + `AppHeader` tab.
7. Re-baseline §8, write a spec into `docs/specs/` per convention.

---

## 11. Artefacts

* `docs/specs/gap-analysis-sql-extension.sql` — the validated BQ layer (rev 2)
* `docs/specs/gap-analysis-rollup-reference.sql` — reference roll-ups
* `docs/specs/phase-3-competitor-products-tab.md` — the tab template
* `docs/FP_AGGREGATION_LOGIC.md` · `docs/FP_Price_Index.md` — FP + PI rules (mind §9.1, §7.2)
* `DESIGN.md` · `docs/DDD.md` · `PRODUCT.md` — tokens, domain language, personas
