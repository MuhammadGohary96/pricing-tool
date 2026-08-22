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
* **"Their catalogue" now narrows like everything else.** It used to be the one column no
  filter touched, because it was read straight off `comp_active_products` — a per-competitor
  BigQuery scalar with no brand or category dimension. Two changes fixed that:
  * `comp_active_products_shared` (BigQuery) — the same `COUNTIF` restricted to brands we
    also carry. The gap is large and competitor-specific: Amazon 22.5% of catalogue in brands
    we stock, Rabbit 65.6%.

    ⚠ **This does not equal the scoped count under Shared-only**, and the difference is not a
    bug in either. The scalar tests *their* product's brand label against our brand list. The
    scoped count's matched half tests *our* product's brand, because that half is filtered on
    the Breadfast rows — and the two brand strings do not always survive a match intact. They
    diverge by 15 (Noon) to 413 (Talabat) products. Only the scoped count composes with the
    other filters, so that is what the column shows; the scalar is kept in the export under a
    name that says which question it answers.
  * `competitor_product_key` populated on Breadfast rows (it was hard-coded `NULL`), plus
    `matched_comp_in_catalogue`. The paired and unpaired halves then **partition** the active
    catalogue — paired counted off our rows, unpaired off `comp_catalogue` — so the app can
    `COUNT(DISTINCT ...)` it under any filter. With no filter this reproduces
    `comp_active_products` exactly, which is the check that the partition is sound.

  `COUNT(DISTINCT ...)`, not `COUNT(*)`: one of their products can be matched to several of
  ours, and the Breadfast side is one row per (product, competitor).
* **`paired_comp_keys` is gated on reachability, and this moved "They only".** A competitor
  product can be matched to a Breadfast product the tool does not track — the universe is
  `product_type='single'` inside the top 80% of revenue, so a match to a bundle or a
  long-tail SKU is real but has no row here. Read flat, such a product was excluded from the
  competitor-only branch (it is matched) *and* absent from the Breadfast side (no row), so it
  fell out of the table entirely — 827 of Talabat's active products, 628 of Seoudi's, 127 of
  Amazon's. Harmless while the catalogue was a pre-aggregated total; fatal once the two
  halves are counted to reconcile against it, because they then summed to 94.7% of Talabat's
  catalogue with no filter to explain the gap.

  `paired_comp_keys` now `INNER JOIN`s the reachable `(product_id, competitor_id)` pairs from
  `final_product_data`, so those products become competitor-only rows and the partition
  closes exactly — **residual 0 for every competitor**, verified on the rebuilt table:

  | Competitor | Catalogue | Paired | They only | Residual |
  |---|---|---|---|---|
  | Amazon | 30,822 | 1,217 | 29,605 | 0 |
  | Talabat | 15,751 | 4,653 | 11,098 | 0 |
  | Seoudi | 12,543 | 3,126 | 9,417 | 0 |
  | Amazon Now | 8,788 | 1,998 | 6,790 | 0 |
  | Rabbit | 7,176 | 2,528 | 4,648 | 0 |
  | Noon Minutes | 6,989 | 2,491 | 4,498 | 0 |
  | Carrefour | 0 | 0 | 0 | 0 |

  **This is a deliberate number move, chosen over the alternative:** from the tool's point of
  view a product whose only counterpart lies outside the tracked range is one we do not
  carry. It raised "They only" across the Executive scorecard, the subcategory table and the
  Gap tab. The rejected alternative was to let the catalogue absorb the shortfall instead,
  which kept "They only" still but left the catalogue reading ~5% below the competitor's true
  total — and, worse, no column would then have been wrong in a way anyone could see.
* **Under a category or subcategory filter, unbridged competitor products are excluded**
  (deliberate, requested). A product of theirs the category bridge cannot attribute to one of
  our subcategories cannot be placed, so counting it would inflate whichever categories were
  picked. It is not a rounding matter — the unbridged share of the unpaired half runs from
  3.1% (Seoudi) to 31.4% (Amazon Now) — so the row hover states how many were excluded.
* **Brand overlap is inferred from matches, not just from the brand string.** `is_shared_brand`
  asked one question — do the two `brand_key`s agree? — and got it wrong whenever the same
  brand is labelled differently on each side. The worst case is a manufacturer versus a
  consumer brand: we carry **Froneri** (the Nestlé ice-cream JV) and Talabat shelves the very
  same products as Nestle, Paradise, Oreo, Squizz, Cadbury, KitKat and a dozen more. 59 of
  our 62 Froneri products were mapped at Talabat while the brand read *only ours* — in the
  column that exists to say what they stock. No slug normalisation reaches it: both sides
  already resolve slug-first, and `froneri` shares nothing with `nestle`.

  A brand now also counts as shared with a competitor when **≥50% of its products are mapped
  there**, computed on both sides:
  * ours → theirs: `bf_brand_shared_by_match`, over `final_product_data`
  * theirs → ours: `comp_brand_shared_by_match`, over `comp_products` vs `paired_comp_keys`
    (already reachability-gated, so "matched" means matched to something we actually sell)

  Two properties worth keeping:
  * **Computed over the whole range, never inside the app's filters.** If the percentage were
    recomputed per filter, Shared-only would feed on itself — switching it on changes which
    products are in scope, which changes each brand's mapped share, which changes which
    brands are shared. `is_shared_brand` stays a fixed property of (product, competitor).
  * **Evaluated per (brand, competitor).** At 50% Froneri is shared at all five competitors
    that have matches and stays *not* shared at Amazon and Carrefour, which have none. At the
    70% first considered, Rabbit (66.1%) would have denied a brand it demonstrably stocks.

  `shared_brand_by_match` records which way the overlap was established, and
  `comp_brand_variants` carries the evidence as `"brand:count|…"`, ranked, capped at 10 —
  every distinct **display name** on their shelf, grouped on the name rather than the
  `brand_key`, because the key is exactly what collapses `7Up` / `7UP` / `7up` into one. So
  the Gap table's "Their brand" column shows both a brand we label differently (Froneri →
  Nestle, Paradise, Oreo) and one we label the same that they spell several ways — the
  latter being why "brands only they carry" is an upper bound. Blank names are dropped. It is deliberately **not** a fourth `brand_type`: those brands *are*
  shared and must keep appearing under the Shared filter, so `by_match` rides alongside as a
  cross-cutting audit view instead.
* **Never sum "They only" across rows** — one competitor product can bridge to several of
  our subcategories.
* **"Ours only" is a ceiling, not the mirror of "They only".** It is every SKU of ours with
  no match at that competitor, so it counts what they genuinely do not stock together with
  what we merely failed to match. The row hover splits it three ways — confirmed not stocked,
  likely a matching miss (similarity ≥ 0.85), never ruled either way — because the mix
  decides whether it is an assortment story or a matching backlog. Amazon is the cautionary
  row: 10,198 unmatched, only 1,901 confirmed.

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
