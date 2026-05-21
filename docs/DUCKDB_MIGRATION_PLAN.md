# DuckDB Migration Plan — Filter Performance Optimization

**Version:** 1.2
**Created:** 2026-05-19
**Status:** Phase 0 ✅ · Phase 1 ✅ · Phase 2.1 ✅ · Phase 2.2 ✅ · Phase 2.3 ✅
**Estimated effort:** 4–6 working days
**Goal:** Reduce filter-change latency from 22–33s to **<2s**.

## Progress log

| Phase | Status | Result |
|---|---|---|
| Phase 0 — Spike | ✅ Done | 533× speedup on single-FP `blended-pi`, perfect parity |
| Phase 1 — DuckDB service + first endpoint | ✅ Done | `blended-pi` live: 33s → 0.1s (305×) |
| Phase 2.1 — Per-competitor enrichment for blended-pi | ✅ Done | Full parity on 148 subcats; sorted Parquet + 3-stage pre-warm |
| Phase 2.2 — executive/dashboard | ✅ Done | 22s → 0.12-0.28s (~140×). Full parity across kpis/competitor_pi/mapping_progress/classification_breakdown |
| Phase 2.3 — products-pivoted (+ all _apply_filters consumers) | ✅ Done | 22s → 0.67s (33×). Overrode `_apply_filters` so EVERY filter-heavy method speeds up automatically |
| Phase 3 — Polish + observability | ⏳ Pending | Server-Timing header, slow query log, parquet refresh on bg loader |

---

## 1. Why this plan exists

### Current problem

Endpoints that apply filters (FP, category, competitor) are slow because they execute pandas operations over a 4.5M-row in-memory DataFrame on every request:

| Endpoint | No filter (GLOBAL) | Single FP filter |
|---|---:|---:|
| `/api/commercial/blended-pi` | ~3s | **33s** ❌ |
| `/api/executive/dashboard` | ~1s | **22s** ❌ |
| `/api/commercial/products-pivoted` | ~3s | **22s** ❌ |

Each request scans the entire 4.5M-row DataFrame, applies a boolean mask in pandas (slow on object dtypes), then re-aggregates per-product / per-competitor / per-subcategory via `groupby().apply(...)` (the slowest pandas pattern). Memory bandwidth saturated, no indexes, no precomputed shortcuts.

### Why DuckDB solves this

DuckDB is an in-process columnar OLAP engine purpose-built for the exact pattern we have: large analytical scans + filters + aggregations. Key properties:

- **Columnar storage** (Parquet on disk) → only reads the columns the query touches
- **Vectorized execution** → SIMD-friendly, ~10–100× faster than pandas for aggregations
- **Predicate pushdown** → applies WHERE clauses during scan
- **Zone maps** on Parquet row groups → skips entire chunks that can't match
- **Lock-free concurrent reads** → multi-request scaling without GIL contention
- **In-process** → no server, no network round-trip, ~10MB dependency
- **SQL** → expressing the existing aggregations is straightforward

Expected end state for the same endpoints:

| Endpoint | Target | Mechanism |
|---|---:|---|
| `/api/commercial/blended-pi` (single FP) | **0.3–1.5s** | DuckDB scans Parquet with FP filter pushed down |
| `/api/executive/dashboard` (single FP) | **0.3–1.5s** | Same |
| `/api/commercial/products-pivoted` (single FP) | **0.5–2s** | Pivot computed in SQL, paginated |

---

## 2. Constraints (from user)

- **Latency target:** 2–3s end-to-end for filter changes
- **Filter patterns:** Mostly single-FP filters, then category/competitor filters with no FP
- **Memory budget:** Stay at ~2GB
- **Data staleness:** Hours-old data is acceptable (refresh once a day is fine)

---

## 3. Target architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  STARTUP                                                        │
│                                                                 │
│  1. Check ./cache/pricing_data/*.parquet                        │
│  2. If fresh (<24h) → use existing Parquet files                │
│  3. If stale/missing → BigQuery export → Parquet → load DuckDB  │
│  4. Open DuckDB connection on Parquet files (lazy)              │
│  5. App ready in ~5s (cache hit) or ~25min (cold start)         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  REQUEST PATH (filter change)                                   │
│                                                                 │
│  GET /api/commercial/blended-pi?fp_names=New Cairo FP %231      │
│       │                                                         │
│       ▼                                                         │
│  Endpoint builds SQL with parameterized filters                 │
│       │                                                         │
│       ▼                                                         │
│  DuckDB executes:                                               │
│    - Predicate pushdown on Parquet row groups (FP filter)       │
│    - Columnar scan (only reads ~12 of ~50 columns)              │
│    - Vectorized aggregation                                     │
│       │                                                         │
│       ▼                                                         │
│  Result returned as Arrow → Pydantic → JSON                     │
│  ~0.5–1.5s total                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Storage layout

```
cache/pricing_data/
├── fp_grain.parquet               # 4.5M rows, product × fp × competitor (PRIMARY)
├── fp_grain_meta.json             # row count, max(updated_at), schema_version
└── competitor_products.parquet    # competitor product registry table
```

Parquet partitioning: **single file** initially (simpler, DuckDB handles row-group skipping). If FP-filtered queries are still slow after Phase 2, partition by `fp_name` (one parquet per FP → ~80MB each).

### DuckDB connection model

- **One connection per worker** (uvicorn worker), shared across requests in that worker via thread-safe handle
- Read-only mode (we never write at runtime)
- Files on disk; DuckDB memory-maps row groups as needed

---

## 4. Phases

### Phase 0 — Spike (½ day)

**Goal:** Prove the speedup is real before committing to migration.

- Add `duckdb` dependency: `pip install duckdb pyarrow`
- Write a one-off script (`scripts/duckdb_spike.py`) that:
  1. Loads the existing pickle cache
  2. Dumps `_df` to `fp_grain.parquet` via `df.to_parquet()`
  3. Runs the equivalent of `get_blended_pi_by_subcategory` for single-FP filter in DuckDB SQL
  4. Times it and compares to current pandas implementation
- **Pass criterion:** ≥10× speedup over current pandas for single-FP filter case (must be <3s)
- **Fail action:** Revisit plan — consider hybrid pandas+precompute instead

**Deliverable:** Single timing table. No code changes to the app.

---

### Phase 1 — DuckDB-backed data service (2 days)

**Goal:** Build a new data service that mirrors the current `BigQueryPricingDataService` interface but uses DuckDB internally. Keep the pandas implementation alive in parallel for fallback.

**1.1 Parquet writer**

Add `backend/services/parquet_cache.py`:
- `save_to_parquet(df: pd.DataFrame, path: Path)` — writes with snappy compression, row group size 100K
- `is_fresh(path: Path, max_age_hours: int) -> bool` — same TTL semantics as current `cache_service.py`
- Loads from existing pickle on first run; writes Parquet alongside

**1.2 DuckDB service class**

Add `backend/services/duckdb_service.py`:

```python
class DuckDBPricingDataService(PricingDataServiceInterface):
    def __init__(self, parquet_path: Path):
        self.conn = duckdb.connect(":memory:", read_only=False)
        self.conn.execute(f"CREATE VIEW fp_grain AS SELECT * FROM read_parquet('{parquet_path}')")
        # Pre-warm: read schema + row counts
        self.conn.execute("SELECT COUNT(*) FROM fp_grain").fetchone()
```

Implement (in priority order):
1. `get_blended_pi_by_subcategory(filters)` — biggest win, most complex
2. `get_executive_dashboard(filters)` — uses similar aggregations
3. `get_products_pivoted(filters, page, page_size)` — pagination via DuckDB `LIMIT/OFFSET`
4. `get_kpi_summary(filters)` — simple aggregations
5. Remaining methods (`get_top_actions`, `get_category_performance`, etc.)

Each method:
- Builds parameterized SQL (use `?` placeholders, NEVER f-string user input)
- Executes via `self.conn.execute(sql, params).arrow()` → zero-copy to pandas if needed
- Wraps result in same shape as the current pandas implementation returns

**1.3 SQL translations (the meat)**

The current `_aggregate_to_global` becomes a CTE-based SQL view. Sketch:

```sql
-- Fresh observations only
WITH fresh AS (
    SELECT product_id, competitor_id,
           MODE(competitor_sale_price) AS fresh_modal
    FROM fp_grain
    WHERE competitor_sale_price IS NOT NULL
      AND is_recent_competitor = TRUE
      AND fp_name IN (?)         -- filter pushed down
    GROUP BY product_id, competitor_id
),
all_obs AS (
    SELECT product_id, competitor_id,
           MODE(competitor_sale_price) AS all_modal,
           MIN(days_since_update)      AS min_days,
           MAX(competitor_price_updated_at) AS max_updated_at
    FROM fp_grain
    WHERE competitor_sale_price IS NOT NULL
      AND fp_name IN (?)
    GROUP BY product_id, competitor_id
),
bf_modal AS (
    SELECT product_id, MODE(bf_sale_price) AS bf_price
    FROM fp_grain
    WHERE is_recent_breadfast = TRUE
      AND fp_name IN (?)
    GROUP BY product_id
),
aggregated AS (
    SELECT
        p.product_id, p.competitor_id, ...,
        COALESCE(f.fresh_modal, a.all_modal)              AS competitor_sale_price,
        bf.bf_price                                       AS bf_sale_price,
        (f.fresh_modal IS NOT NULL)                       AS is_recent_competitor,
        (a.all_modal IS NOT NULL)                         AS has_PI,
        a.min_days                                        AS days_since_update,
        a.max_updated_at                                  AS competitor_price_updated_at
    FROM (SELECT DISTINCT product_id, competitor_id FROM fp_grain WHERE fp_name IN (?)) p
    LEFT JOIN fresh f USING (product_id, competitor_id)
    LEFT JOIN all_obs a USING (product_id, competitor_id)
    LEFT JOIN bf_modal bf USING (product_id)
)
SELECT
    sub_category_name,
    competitor_name,
    SUM(sale_PI * avg_daily_quantity) / SUM(avg_daily_quantity) FILTER (WHERE used_product) AS blended_pi,
    COUNT(DISTINCT product_id) FILTER (WHERE used_product)     AS used_count,
    COUNT(DISTINCT product_id) FILTER (WHERE eligible_product) AS eligible_count,
    ...
FROM aggregated
GROUP BY sub_category_name, competitor_name;
```

Notes:
- DuckDB has `MODE()` aggregate built-in (matches pandas modal logic)
- `FILTER` clause = vectorized conditional aggregation, much faster than `CASE WHEN`
- `LIST(...)` aggregate can return product PIs as JSON for the tooltip data

**1.4 Factory + feature flag**

In `backend/services/__init__.py`, add an env var:

```python
USE_DUCKDB = settings.USE_DUCKDB  # default False

def create_data_service(...):
    if settings.USE_DUCKDB:
        return DuckDBPricingDataService(...)
    return BigQueryPricingDataService(...)  # existing fallback
```

This lets us cut over per-endpoint by checking the flag, and instantly roll back by flipping it off.

**1.5 Background refresh**

Adapt `background_loader.py`:
- Same trigger (cache TTL >24h)
- Loads from BigQuery → writes Parquet → swaps DuckDB connection atomically
- Old Parquet kept for 1 cycle in case of read-in-flight

---

### Phase 2 — Endpoint migration (1.5 days)

**Goal:** Move endpoints one-by-one to DuckDB, validate parity, then deprecate pandas paths.

**2.1 Per-endpoint cutover protocol**

For each endpoint:
1. **Implement** DuckDB version
2. **Test** parity: run both, diff outputs (acceptable: rounding within 0.0001, ordering with same tiebreaker)
3. **Benchmark**: hit endpoint 5× with cold cache, 5× hot. Record p50, p95.
4. **Flip flag** for that endpoint
5. **Monitor** in dev for 1 day
6. **Delete** pandas implementation only after all endpoints migrated

Order (highest-impact first):
1. `/api/commercial/blended-pi` (most painful: 33s)
2. `/api/executive/dashboard`
3. `/api/commercial/products-pivoted`
4. `/api/executive/competitor-pi` (same path as #2 in many implementations)
5. Smaller endpoints (kpi-summary, top-actions, category-performance)

**2.2 Parity test harness**

Add `tests/test_duckdb_parity.py`:
- For each migrated endpoint, run with 5 representative filter combinations
- Compare DuckDB result vs pandas result field-by-field
- Tolerance: 0.0001 for floats, exact match for counts and strings

This is a one-time safety net for the cutover, not permanent test coverage.

---

### Phase 3 — Polish + observability (1 day)

**3.1 Per-request timing**

Add a `Server-Timing` HTTP header to filter endpoints:
- `Server-Timing: db;dur=412, transform;dur=23, json;dur=18`

Lets us see at a glance whether slowness is DB or downstream.

**3.2 Slow query log**

Log any DuckDB query taking >500ms with the SQL text. If we hit this, it's an indexing/predicate issue we missed.

**3.3 Update PERFORMANCE_OPTIMIZATION_PLAN.md**

Mark Phase 4 (Query Optimization) as superseded by DuckDB migration. Cross-reference this doc.

**3.4 Update FP_AGGREGATION_LOGIC.md**

The aggregation logic still applies, but the implementation is now SQL. Add a "DuckDB implementation" section showing the CTE structure for reference.

---

## 5. File-by-file changes

### New files

| File | Purpose | LOC est. |
|---|---|---:|
| `backend/services/duckdb_service.py` | Main DuckDB service class | ~600 |
| `backend/services/parquet_cache.py` | Parquet write/read/freshness helpers | ~100 |
| `scripts/duckdb_spike.py` | Phase 0 benchmark script (throwaway) | ~80 |
| `tests/test_duckdb_parity.py` | Parity tests | ~200 |
| `docs/DUCKDB_QUERIES.md` | Reference SQL for each endpoint | ~300 |

### Modified files

| File | Change | Risk |
|---|---|---|
| `backend/services/__init__.py` | Factory branches on `USE_DUCKDB` flag | Low |
| `backend/services/background_loader.py` | Writes Parquet instead of pickle when flag on | Low |
| `backend/services/cache_service.py` | Add `.parquet` path support | Low |
| `backend/config.py` | Add `USE_DUCKDB: bool = False` | Low |
| `backend/main.py` | Pass flag through to data service | Low |
| `requirements.txt` | Add `duckdb>=0.10`, `pyarrow>=14` | Low |

### Unchanged

- Router files (`backend/routers/*`): same interface, just behind a different implementation
- Pydantic models (`backend/models/*`): same response shape
- All frontend code: no changes needed
- Pandas implementation: kept until Phase 2 fully complete, then deleted

---

## 6. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| MODE() in DuckDB doesn't match pandas `mode()` on ties | Medium | Verify in Phase 0 spike. If different, use `arg_max` with count subquery as workaround. |
| Parquet write fails for object dtypes / NaN dates | Low | Convert via pyarrow with explicit schema; we already normalize dates to ISO strings. |
| Memory spike during Parquet write of 4.5M rows | Low | Write in batches via `pyarrow.parquet.ParquetWriter`; already chunked in batch loader. |
| Multiple uvicorn workers each open DuckDB | Low | Each worker gets its own read-only connection to the same Parquet — fine. |
| Aggregation parity bug ships to prod | High | Phase 2 parity tests; flag-controlled rollout per endpoint; keep pandas in tree until all migrated. |
| Cold start slower than expected | Low | Pre-warm by running `SELECT COUNT(*)` after connection open. |
| Stale results during background refresh | Low | Atomic swap: write to `fp_grain.new.parquet`, rename, reconnect. |
| New dependency introduces deployment friction | Low | DuckDB is a single pip install, no native compilation needed on macOS/Linux. |
| Date/timezone handling differs between pandas and DuckDB | Medium | Already store dates as ISO strings in current cache; DuckDB casts strings cleanly. |

---

## 7. Acceptance criteria

A migration is "done" when **all** of the following hold:

1. ✅ Phase 0 spike shows ≥10× speedup on the `blended-pi` single-FP query
2. ✅ All 5 priority endpoints serve from DuckDB with `USE_DUCKDB=true`
3. ✅ p50 latency on single-FP filter ≤ 2s for `blended-pi`, `executive/dashboard`, `products-pivoted`
4. ✅ Parity tests pass for all 5 endpoints across 5 filter combinations
5. ✅ Cache-hit startup time ≤ 10s
6. ✅ Background refresh works end-to-end (BigQuery → Parquet → reconnect)
7. ✅ Pandas implementation deleted, `USE_DUCKDB` flag removed (default-on, no opt-out)
8. ✅ Memory usage at steady state ≤ 1.5GB
9. ✅ Frontend works with zero changes
10. ✅ Documentation updated (this doc marked complete, FP_AGGREGATION_LOGIC.md cross-referenced)

---

## 8. What this plan does NOT do

These are out of scope. Add separately if needed.

- **Streaming/SSE for long requests** — DuckDB should make this unnecessary
- **Materialized views inside DuckDB** — only if Phase 2 benchmarks miss the 2s target
- **Multi-tenant query isolation** — same single-user assumption as today
- **GPU acceleration / DuckDB extensions** — premature
- **Switching the source of truth** — BigQuery remains the source; DuckDB is the read cache
- **Frontend changes** — none planned; UX should improve transparently

---

## 9. Decision log

Decisions made up front so we don't relitigate them during implementation:

- **DuckDB over SQLite**: 5–20× faster on analytical aggregations; columnar storage is the right tool.
- **Parquet over feather/arrow IPC**: better compression, more portable, DuckDB optimizes for it.
- **Single Parquet file initially**: simpler ops; partition only if benchmarks demand it.
- **Keep BigQuery as source of truth**: no plan to replicate writes; this is read-only cache.
- **Feature flag during cutover**: explicit roll-back path is worth the small extra code.
- **In-process DuckDB, not server**: zero deployment change; matches our 2GB constraint.
- **No new caching tier above DuckDB**: DuckDB IS the cache; layering more is premature.

---

## 10. Quick start (for the engineer implementing this)

1. Read this plan top-to-bottom (~10 min)
2. Read `backend/services/bigquery_service.py::_aggregate_to_global` (the core logic you'll translate)
3. Read `docs/FP_AGGREGATION_LOGIC.md` (the canonical rules)
4. Run Phase 0 spike, post timing in your project channel
5. If spike passes → proceed with Phase 1
6. Update the **Status** field at the top of this doc as you progress: `Proposed → In Progress → Done`
