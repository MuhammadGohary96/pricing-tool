# Executive · Commercial · Gap — one filter model, one calculation basis

**Status:** shipped · **Date:** 2026-08-06 · **Branch:** `feat/brand-subcategory-gap`

The three analytics views now answer the same question about the same slice. Before this,
Gap Analysis kept its own filter store and its own price weighting, so the same subcategory
could show a different price index depending on which tab you were standing on.

Related: `docs/specs/executive-commercial-matchability.md` (the metrics),
`docs/specs/brand-subcategory-gap-tab.md` (the gap layer), `docs/ux/UX_AUDIT.md` (the audit
whose H3 "each view is an island" this closes).

---

## 1. The filter model

| Control | Executive | Commercial | Gap | Notes |
|---|---|---|---|---|
| Vertical (All / Beauty / Supermarket) | ✓ | ✓ | ✓ | shared store |
| Include private label | ✓ | ✓ | ✓ | shared store |
| Categories, Subcategories, Brands | ✓ | ✓ | ✓ | shared store |
| Tiers, FPs | ✓ | ✓ | **hidden** | see §1.1 |
| Action type | — | ✓ | — | Commercial-only vocabulary |
| Competitor | pills (visibility) | pills (visibility) | **single-select (filters)** | view-local, see §1.2 |

All of it lives in `stores/filters.js` except the competitor. One `FilterBar` component, with
`hideCompetitor` / `hideTier` / `hideFp` props.

### 1.1 Why tier and FP are hidden on Gap, but category is not

Gap's competitor-only rows are **national** (`fp_id` NULL) and carry no tier of ours, so tier
and FP can only ever narrow the Breadfast half of that screen. A filter that applies to one
column and silently not the next is worse than not offering it, so they are hidden.

Commercial category looked like the same problem and is not: the bridge assigns each
competitor product one of **our** subcategories, and our subcategories belong to our
commercial categories. So category reaches both sides through a subquery in
`_comp_side_where`, and both move together — Branded Beverages gives 902 ours / 923 theirs,
where before the fix theirs stayed at the unfiltered 10,084.

Vertical crosses over the same way, via the bridge's `beauty_path_share` rather than a
category of ours. Known blind spot: Seoudi and Rabbit file all beauty under one flat node, so
that share never crosses the cutoff and their beauty products survive a Supermarket filter.
The UI says so.

### 1.2 The competitor is one widget doing two jobs

`components/shared/CompetitorToggle.vue`, with a `single` prop.

* **multi** (Executive, Commercial) — **visibility only**. Dims what you are not looking at,
  changes no number, issues no request. Executive's blended PI is *defined* across all
  tracked competitors, so letting these pills filter it would move the headline every time
  someone focused the view.
* **single** (Gap) — **selects the subject** and refetches. Every number on that screen is
  "against whom", so unioning competitors would double-count what both of them stock.

The shape carries the distinction: pills when it dims, a squarer control with radio semantics
when it selects. Competitors with nothing crawled are marked "no catalogue" on the control
itself, so a screen of zeros is explained before it is read.

### 1.3 Sharing

URL sync and Saved Views cover all three views. Saved Views store the **shared** filters only
— a view that half-applied depending on where you opened it would be the §1.1 trap again. The
competitor is namespaced `gap_competitor` in the URL, so a Gap link reopens the same
comparison without setting Commercial's competitor.

**Not in the shared model:** the Competitors tab (`/competitor-products`) reads a different
table at a different grain and keeps its own filters. It is the one header tab that will
forget your filters — a decision, not an oversight. Master Data stays routed with no header
tab.

---

## 2. The calculation basis

**One method everywhere: collapse the filtered rows to one row per key, recompute modal
prices, then calculate.** That is `_BASE_CTE`, and `global_base` is it pre-materialized.

| Surface | Source | Grain |
|---|---|---|
| Commercial blended PI, Executive dashboard | `_BASE_CTE` / `global_base` | (product, competitor) |
| Gap blended PI + coverage | same, via `_collapsed_source` | (product, competitor) |
| Executive geographic grid | `_FP_BASE_CTE` | (product, competitor, **fp**) |

### 2.1 What Gap was doing wrong

It read `fp_grain` and summed across FP rows. `avg_daily_quantity` is a **national** figure,
so repeating it per FP row weights each product by *demand × number of FPs it is stocked in*.
Hair Care / Talabat came out at 1.061 that way against 0.945 correctly — off the same 18
products, with the weight sum inflated 21× — so the two screens disagreed about which side of
parity we were on, because of distribution breadth rather than price. `docs/DDD.md` requires
weighting by real demand. Fixed: 0 mismatches against Commercial across 7 competitors × 206
subcategories.

The BigQuery roll-up this formula came from groups **by** FP, where there is no
multiplication. Gap had applied a per-FP formula nationally.

### 2.2 The trap when reading `global_base`

Filtering the pre-built table afterwards is only valid for filters that remove **whole
products**. It is invalid for anything that slices rows *within* a product's modal partition,
because the modal was already chosen:

* `fp_names` — obvious, `global_base` has collapsed `fp_name` away.
* **`competitor`** — not obvious. `bf_sale_price` is **not competitor-invariant**: BigQuery
  emits `COALESCE(bf_eod_sale_price, scd_price)`, so each competitor contributes its own
  end-of-day Breadfast price. For "Rich Beef Stick" the modal is 78.75 across all competitors
  (369 rows) but 41.50 within Talabat (44 rows), moving its PI from 1.11 to 0.93.
* `action_type` — varies per (fp, competitor).

`_collapsed_source` re-runs the CTE for those three and uses the pre-built table otherwise.

### 2.3 The one remaining cross-view difference, and why it is left alone

Commercial's per-competitor **columns** are computed in an all-competitor scope; Gap's screen
is scoped to one competitor. By §2.2 those two scopes can pick different Breadfast modals.
Measured across 777 (subcategory × competitor) pairs: **2 differ at 4dp, 1 differs at the 2
decimals actually displayed** — Treats/Talabat, 1.01 versus 0.95.

Both are correct for their own scope, and closing the gap would mean either recomputing
Commercial's seven columns under seven separate scopes (expensive, and it moves existing
numbers) or reintroducing the filter-after bug. Left as is.

**The real root cause is upstream:** "the Breadfast price" should not depend on which
competitor you are comparing against, yet `COALESCE(bf_eod_sale_price, scd_price)` makes it
so. Fixing that in `docs/FP_granularity_pricing.sql` — one Breadfast price per (product, fp) —
would remove this class of discrepancy entirely, and would move existing numbers. Worth its
own decision.

---

## 3. Executive layout

Blended PI is the **sole hero**. Addressable and Benchmark freshness sit in a compact strip
directly above the Competitor Overview panel they summarise, not in the header: a hero plus
four equal peers reads as five numbers of equal weight, which defeats the five-second glance
`DESIGN_PROMPT.md` specs for this view, and `PRODUCT.md` names "every cell shouting at the
same volume" as an anti-reference.

---

## 4. Known and deliberately unresolved

1. **Private label has five predicates** across the backend, split per endpoint. We unified
   the *control*, not the predicate, so unchecking it drops slightly different sets on
   different panels. Disclosed in both definitions panels. Unifying moves numbers.
2. **Competitor-dependent Breadfast price** — §2.3.
3. **Executive's week-over-week is empty.** `/pi-trend`, `/coverage-trend` and
   `/week-over-week` return `[]`, yet leadership's documented key metric is "Overall Blended
   PI *and week-over-week trend*". Left by decision.
4. **`subcat_tier` is inert** — in the store, watched by Executive, never sent, not accepted
   by the router.
5. **`/commercial/funnel` and `/commercial/kpis`** are live and unrendered.
6. **Master Data's Match Review** is local-only state and loses work on refresh
   (`docs/ux/UX_AUDIT.md` C1). The view stays hidden.

---

## 5. Verification

```bash
python scripts/kpi_snapshot.py before.json           # 61 scalar KPI entries are the contract
python scripts/kpi_snapshot.py --diff before.json after.json
```

Isolate against a worktree at the previous commit on the **same** Parquet — a diff that spans
a cache rebuild reports dozens of phantom changes. Every stage of this work held 0 of 61
scalar entries moved.

Cross-checks that must hold:

- Gap blended PI == Commercial's per-competitor PI at the **same** scope (both filtered to
  that competitor): 0 mismatches across 7 × 206.
- Executive `total_products` == Gap `bf_products` for the same shared filters.
- `/executive/competitor-overview` == `/gap/kpis` on 63 metrics.
- `addressable_pct > 100` on zero rows; `/commercial/treemap` has no zero-value nodes.
