# Matchability in Executive & Commercial — shipped spec

**Status:** shipped · **Date:** 2026-08-06 · **Branch:** `feat/brand-subcategory-gap`
Plan: `~/.claude/plans/snazzy-juggling-codd.md`. Gap-layer spec:
`docs/specs/brand-subcategory-gap-tab.md`.

The gap layer previously served only `/gap-analysis`. Executive and Commercial now answer
**how much *can* be matched**, not only how much is — and the Executive view carries a live
version of the hand-maintained `Brand_Portfolio_Consolidated_excl_Beauty.xlsx` →
`Competitor Overview` sheet.

**Constraint honoured throughout: additive only.** No number already on screen changed
value. Two exceptions, both deliberate and signed off: the Commercial blended-PI table gains
*rows* (that was the point), and a false caption under "Competitors tracked" was corrected.

---

## 1. What was added

| Surface | Addition |
|---|---|
| Executive header | **Addressable** and **Benchmark freshness** stat tiles |
| Executive · Data coverage | **Competitor overview** panel — 16 columns, one row per competitor |
| Commercial · blended-PI | **Addr %** and **They only** columns; 39 previously hidden subcategories |
| Commercial · export | Addressable %, Confirmed no-match, Matched fresh, They only |

`GET /api/executive/competitor-overview` — filters are the existing Executive `_filters`.
No new scope control; the panel obeys the filter bar.

---

## 2. Metric definitions, and the grain trap

| Metric | Definition |
|---|---|
| **Matched** | `is_mapped` — linked to a competitor product, regardless of whether we priced it |
| **Matched fresh** | matched **and** the competitor product was seen in the last 7 days |
| **Confirmed no-match** | the matcher looked and rejected every candidate |
| **Addressable** | products − confirmed no-match |
| **Addressable %** | matched ÷ addressable — the honest ceiling |
| **Shared-brand %** | matched ÷ products whose brand the competitor also carries |
| **They only** | competitor products with no link to anything of ours, placed by the bridge |

### ⚠ Addressable % is grain-sensitive — the one thing to get right

Per **competitor** (Executive overview), `is_mapped` and `is_confirmed_no_match` are mutually
exclusive by construction, so counting them directly is safe.

Per **subcategory** (Commercial), the row pools every competitor. A product can be mapped to
Talabat *and* confirmed-no-match for Amazon simultaneously. Counting
`COUNT(DISTINCT product_id) FILTER (...)` on the pair grain therefore lets "matched" and
"no-match" overlap, `total − no_match` can fall **below** matched, and the rate goes above
100 % — it shipped at **1800 %** in review before being caught.

The fix, in `get_blended_pi_by_subcategory`: resolve the flags **per product first**
(`prod_flags`), then count (`gap_counts`):

```sql
prod_flags AS (
    SELECT __GRP__ AS group_key, product_id,
           BOOL_OR(is_mapped)                            AS is_mapped,
           BOOL_OR(is_mapped AND matched_comp_active_7d) AS matched_fresh,
           BOOL_OR(is_confirmed_no_match)                AS any_no_match,
           BOOL_OR(is_potential_match)                   AS any_potential
    FROM base_tmp GROUP BY 1, 2
)
-- then: confirmed_no_match = COUNT(*) FILTER (WHERE NOT is_mapped AND any_no_match)
```

At that grain "no-match" means **nobody** has an equivalent, which is what a category
manager reads it as. Regression check: `addressable_pct > 100` must return zero rows.

---

## 3. `pair_meta` — the plumbing rule

`_BASE_CTE`'s `pair_meta` carries an **explicit** column list and `base` is `pm.*`, so a
column absent from that list is invisible to every Executive/Commercial roll-up even though
it sits in the Parquet. Ten columns were added (`is_beauty`, `is_private_label`, `brand_key`,
`is_shared_brand`, `matched_comp_active_7d`, `is_confirmed_no_match`, `is_potential_match`,
`best_similarity_in_portfolio`, `competitor_has_v2_catalogue`, `comp_active_products`).

Rules when adding more:

* **`BOOL_OR` / `MAX`, never `ANY_VALUE`**, for anything that can vary across a pair's FP
  rows. `ANY_VALUE` is nondeterministic under DuckDB's parallel aggregation (see the
  `MIN(classification)` note in the same CTE) and Executive would then disagree with the Gap
  tab from one run to the next.
* **`NULLIF(TRIM(x), '')` on brand keys.** A blank brand otherwise becomes the single
  largest "brand". This bit twice: once in the gap layer, once in the Executive overview's
  `comp_side`, which reads `comp_catalogue` raw and so does *not* inherit `pair_meta`'s
  normalization — it showed `comp_only_brands` high by exactly 1 on every competitor.
* **Don't carry `mapped_bf_sub_category`** — on breadfast rows it only echoes
  `sub_category_name`, and every `global_base` column is materialized into pandas on each
  GLOBAL request.
* **Watch for collisions:** `base` computes 12 aliases (`sale_PI`, `used_product`,
  `action_type`, …) that also exist in `fp_grain`. Carrying one through `pair_meta` is a
  duplicate column and a hard startup failure.

Adding to `pair_meta` changes **no API payload** — every response is whitelisted
(`ProductRow`, `export_cols`, the `top-actions` dict). Only a restart is needed; no BigQuery
or Parquet rebuild.

---

## 4. Performance

`get_competitor_overview` first materialized `_BASE_CTE` per request (~4.6 s), which would
have made Executive's parallel fetch three heavy calls deep on one DuckDB lock. It now reads
the pre-materialized `global_base` unless an FP filter is present — `global_base` has no
`fp_name`, so only that case needs the CTE. **4.6 s → 0.025 s**; FP-scoped 0.13 s. The same
GLOBAL/FP-scoped split as `_apply_filters`; reuse it for any new roll-up.

---

## 5. Reading the panel honestly

* **A competitor with no crawled catalogue** (Carrefour) shows `Their catalogue = 0`,
  `They only = 0` and `Matched fresh = 0` against 4,037 matched. Flagged with a
  "no catalogue" chip — that is a *collection* gap, not an assortment gap, and our matching
  figures for it are still valid.
* **"Their catalogue (all)" is the one column the filters do not narrow.** For a
  beauty-heavy competitor it reads far larger than the rest of the row (Amazon: 32,034 vs the
  workbook's beauty-filtered 12,509). Labelled and tooltipped accordingly.
* **Never sum "They only" across rows** — one competitor product can bridge to several of
  our subcategories.

---

## 6. Tying to the workbook

Set **Vertical → Supermarket** (the workbook excludes beauty). 66 of 84 metrics land within
10 %. The remaining gaps have known causes, none of them bugs:

| Delta | Cause |
|---|---|
| BF PRODUCTS +489 on every row | the workbook's private-label rule is a prefix match (`breadfast%`); ours is `%breadfast%`. Five inconsistent predicates still exist in the backend — see below |
| CONFIRMED NO-MATCH up, POTENTIAL down | rev-2 sources matches from the daily comparison fact, moving products between those two buckets |
| SHARED BRANDS ~40 lower | we no longer count "(no brand)" as a brand |
| COMP PRODUCTS (Amazon) | not beauty-filtered — see §5 |

**Still unresolved:** private label has five predicates across the backend, split *per
endpoint* — Executive uses SQL `brand_name != 'Breadfast'`, Commercial products uses pandas
`contains('breadfast')`, so "Breadfast Bakery" is counted by one and excluded by the other in
the same session with the same toggle. `is_private_label` is now carried in `pair_meta` and
within reach of both. Unifying them **would move existing numbers**, so it was deliberately
left out and needs its own decision.

---

## 7. Verification

`scripts/kpi_snapshot.py` — 182 endpoint × filter combinations. Hold the **61 pure-scalar
KPI entries** to account; the rest carry a ~30-entry run-to-run nondeterminism floor.

**Isolate the change from data drift.** A naive before/after that spans a Parquet rebuild
reported 49 phantom scalar diffs. Snapshot a worktree at the previous commit against the
**same** Parquet:

```bash
git worktree add /tmp/prev <previous-sha>
cp scripts/kpi_snapshot.py .env /tmp/prev/
(cd /tmp/prev && python3 scripts/kpi_snapshot.py /tmp/before.json "$PWD/cache/pricing_data/fp_grain.parquet")
python3 scripts/kpi_snapshot.py /tmp/after.json cache/pricing_data/fp_grain.parquet
python3 scripts/kpi_snapshot.py --diff /tmp/before.json /tmp/after.json
```

Cross-checks that must hold:

- `/executive/competitor-overview?vertical=supermarket` == `/gap/kpis` at
  `scope=excl_beauty_pl&include_private_label=true` — 63 metrics, exact.
- `addressable_pct > 100` on zero rows; `matched ≤ addressable ≤ products` on every row.
- `/commercial/treemap` has zero-value nodes: none.
