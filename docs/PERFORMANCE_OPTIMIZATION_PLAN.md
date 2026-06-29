# Performance Optimization Plan - Comprehensive Strategy

**Date:** 2026-05-18  
**Priority:** HIGH - All performance aspects  
**Target:** Zero downtime, faster startup, faster queries

---

## Executive Summary

### Current Performance
- ⏱️ **Startup**: 20 minutes (blocking - app unusable)
- ⏱️ **FP-scoped queries**: 800-1500ms
- ⏱️ **GLOBAL queries**: <50ms (good)
- 🔄 **Data refresh**: Requires full app restart (20 min downtime)

### Target Performance
- ⏱️ **Startup**: <5 seconds (from cache, zero downtime)
- ⏱️ **Background reload**: 10-15 minutes (non-blocking, with progress)
- ⏱️ **FP-scoped queries**: <200ms (7x faster)
- ⏱️ **GLOBAL queries**: <50ms (maintain current)
- 🔄 **Data refresh**: Every 6 hours, automatic, zero downtime

### Key Innovation: **Background Loading Strategy**
```
App Startup → Load from cache (5 sec) → Serve requests
    ↓ (parallel)
Background thread → Fetch new data from BigQuery (15 min) → Replace cache → Notify UI
```

**Result**: Users never wait for data loading! 🎉

---

## Architecture Overview

### Current Architecture (Blocking)
```
User opens app
    ↓
Load 4.5M rows from BigQuery (20 min) ← BLOCKING
    ↓
Aggregate to GLOBAL view (2 min)
    ↓
App ready
```

### New Architecture (Non-Blocking)
```
User opens app
    ↓
Load from disk cache (5 sec) ← INSTANT
    ↓
App ready, serving cached data
    ↓ (parallel, in background)
Check if cache is stale (>6 hours)
    ↓
If stale: Background thread loads fresh data (15 min)
    ↓
Progress shown in UI (non-intrusive)
    ↓
When complete: Hot-swap data, notify user
```

---

## Implementation Plan

### **Phase 1: Background Loading Infrastructure** 🎯
**Goal**: Zero-downtime data loading  
**Priority**: CRITICAL  
**Effort**: 2-3 days  
**Impact**: Eliminates 20-min startup wait

#### 1.1: Disk-Based Cache System
**File**: `backend/services/cache_service.py` (NEW)

```python
import pickle
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

class DataCache:
    """Disk-based cache for pricing data."""
    
    CACHE_DIR = Path("cache/pricing_data")
    CACHE_VERSION = "v1.1"  # Increment when schema changes
    MAX_AGE_HOURS = 6
    
    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
    def get_cache_path(self, cache_key: str) -> Path:
        """Get path for cache file."""
        return self.CACHE_DIR / f"{cache_key}_{self.CACHE_VERSION}.pkl"
    
    def save(self, cache_key: str, data: dict):
        """Save data to cache with timestamp."""
        cache_file = self.get_cache_path(cache_key)
        cache_data = {
            "data": data,
            "timestamp": datetime.now(),
            "version": self.CACHE_VERSION,
        }
        with open(cache_file, "wb") as f:
            pickle.dump(cache_data, f)
        print(f"[Cache] Saved {cache_key} to {cache_file}")
    
    def load(self, cache_key: str) -> dict | None:
        """Load data from cache if fresh enough."""
        cache_file = self.get_cache_path(cache_key)
        if not cache_file.exists():
            return None
            
        try:
            with open(cache_file, "rb") as f:
                cache_data = pickle.load(f)
            
            # Check version
            if cache_data.get("version") != self.CACHE_VERSION:
                print(f"[Cache] Version mismatch, invalidating cache")
                return None
            
            # Check age
            age = datetime.now() - cache_data["timestamp"]
            if age > timedelta(hours=self.MAX_AGE_HOURS):
                print(f"[Cache] Stale cache ({age.total_seconds()/3600:.1f} hours old)")
                return None
            
            print(f"[Cache] Loaded {cache_key} from cache ({age.total_seconds()/60:.1f} min old)")
            return cache_data["data"]
            
        except Exception as e:
            print(f"[Cache] Error loading cache: {e}")
            return None
    
    def is_stale(self, cache_key: str) -> bool:
        """Check if cache needs refresh."""
        cache_file = self.get_cache_path(cache_key)
        if not cache_file.exists():
            return True
            
        try:
            with open(cache_file, "rb") as f:
                cache_data = pickle.load(f)
            age = datetime.now() - cache_data["timestamp"]
            return age > timedelta(hours=self.MAX_AGE_HOURS)
        except:
            return True
```

#### 1.2: Background Data Loader
**File**: `backend/services/background_loader.py` (NEW)

```python
import threading
from typing import Callable

class BackgroundDataLoader:
    """Loads data in background thread with progress tracking."""
    
    def __init__(self, app_state):
        self.app_state = app_state
        self.loading = False
        self.progress = {"stage": "Idle", "progress": 0, "total": 0}
        self.thread = None
    
    def start_background_load(self, load_func: Callable):
        """Start background data loading."""
        if self.loading:
            print("[Background] Already loading, skipping")
            return
        
        self.loading = True
        self.progress = {"stage": "Starting background load...", "progress": 0, "total": 0}
        
        def _load_wrapper():
            try:
                print("[Background] Starting data load")
                new_data = load_func(progress_callback=self._update_progress)
                
                # Hot-swap: replace app data atomically
                self.app_state.data_service = new_data
                self.progress = {"stage": "Complete", "progress": 1, "total": 1}
                
                # Save to cache
                from backend.services.cache_service import DataCache
                cache = DataCache()
                cache.save("pricing_data", {
                    "_df": new_data._df,
                    "_global_df": new_data._global_df,
                })
                
                print("[Background] Data load complete and cached")
                
            except Exception as e:
                print(f"[Background] Load failed: {e}")
                self.progress = {"stage": f"Error: {e}", "progress": 0, "total": 0}
            finally:
                self.loading = False
        
        self.thread = threading.Thread(target=_load_wrapper, daemon=True)
        self.thread.start()
    
    def _update_progress(self, stage: str, progress: int, total: int):
        """Callback for progress updates."""
        self.progress = {"stage": stage, "progress": progress, "total": total}
    
    def get_progress(self) -> dict:
        """Get current progress."""
        return {**self.progress, "loading": self.loading}
```

#### 1.3: Update Main App to Use Background Loading
**File**: `backend/main.py`

```python
from backend.services.cache_service import DataCache
from backend.services.background_loader import BackgroundDataLoader

@app.on_event("startup")
async def startup():
    cache = DataCache()
    app.state.background_loader = BackgroundDataLoader(app.state)
    app.state.startup_status = {"ready": False, "stage": "Loading from cache..."}
    
    # Try to load from cache first
    cached_data = cache.load("pricing_data")
    
    if cached_data:
        # Load from cache (fast!)
        print("[Startup] Loading from cache...")
        svc = create_data_service_from_cache(cached_data)
        app.state.data_service = svc
        app.state.startup_status = {"ready": True, "stage": "Ready (from cache)"}
        print("[Startup] App ready from cache in <5 seconds")
        
        # Check if cache is stale, start background refresh
        if cache.is_stale("pricing_data"):
            print("[Startup] Cache is stale, starting background refresh")
            app.state.background_loader.start_background_load(load_fresh_data)
    else:
        # No cache, must load now (first run)
        print("[Startup] No cache found, loading fresh data...")
        svc = create_data_service(startup_status=app.state.startup_status)
        app.state.data_service = svc
        app.state.startup_status["ready"] = True
        
        # Save to cache for next time
        cache.save("pricing_data", {
            "_df": svc._df,
            "_global_df": svc._global_df,
        })

# Add endpoint to check background loading status
@app.get("/api/background-status")
def get_background_status():
    return app.state.background_loader.get_progress()
```

**Impact**:
- ✅ First startup: 20 min (unavoidable, but only once)
- ✅ Subsequent startups: <5 seconds from cache
- ✅ Background refresh: Every 6 hours, non-blocking
- ✅ Zero downtime for users

---

### **Phase 2: Quick Wins - Optimize Current Loading** ⚡
**Goal**: Reduce initial 20-min load to ~10 minutes  
**Priority**: HIGH  
**Effort**: 1 day  
**Impact**: 50% faster startup (for first-time load)

#### 2.1: Use PyArrow for Faster DataFrame Construction
**File**: `backend/services/bigquery_service.py`

```python
# BEFORE (slow)
df = pd.DataFrame([dict(row) for row in rows])

# AFTER (fast - use PyArrow)
from google.cloud import bigquery
import pyarrow

# Enable PyArrow in BigQuery client
client = bigquery.Client(project=project_id, location=location)
job = client.query(query)

# Use to_arrow() instead of iterating rows
arrow_table = job.to_arrow()  # Fast!
df = arrow_table.to_pandas()  # Fast conversion

# Or use directly in one step:
df = job.to_dataframe(create_bqstorage_client=True)  # Uses BigQuery Storage API
```

**Expected Impact**: 5-7 minutes saved (row iteration is slow)

#### 2.2: Load Only Required Columns
**File**: `backend/services/bigquery_service.py`

```python
# Add column filtering to query
REQUIRED_COLUMNS = [
    "product_id", "product_name", "fp_name", "competitor_id", "competitor_name",
    "bf_sale_price", "competitor_sale_price", "sale_PI", "total_revenue",
    "avg_daily_quantity", "eligible_product", "used_product", "has_PI",
    "action_type", "is_recent_breadfast", "is_recent_competitor",
    # ... only columns actually used
]

# Modify query to select specific columns
FPS_QUERY = f"""
SELECT
    {', '.join(REQUIRED_COLUMNS)}
FROM `{{project}}.{{dataset}}.competitor_price_monitoring_fps`
"""
```

**Expected Impact**: 2-3 minutes saved + 20% less memory

#### 2.3: Parallel Aggregation for GLOBAL View
**File**: `backend/services/bigquery_service.py`

```python
from concurrent.futures import ThreadPoolExecutor
import numpy as np

def _aggregate_to_global_parallel(self, df: pd.DataFrame) -> pd.DataFrame:
    """Parallel version of aggregation."""
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Run aggregations in parallel
        bf_future = executor.submit(self._aggregate_bf_prices, df)
        comp_future = executor.submit(self._aggregate_comp_prices, df)
        product_future = executor.submit(self._get_product_base, df)
        
        # Wait for all to complete
        bf_modal = bf_future.result()
        comp_modal = comp_future.result()
        product_base = product_future.result()
    
    # Merge results
    result = self._merge_aggregations(product_base, bf_modal, comp_modal)
    return result
```

**Expected Impact**: 1-2 minutes saved on aggregation

#### 2.4: Optimize DataFrame Operations
```python
# Use categorical dtypes for string columns (saves memory + faster)
df["competitor_name"] = df["competitor_name"].astype("category")
df["fp_name"] = df["fp_name"].astype("category")
df["action_type"] = df["action_type"].astype("category")

# Use float32 instead of float64 where precision not critical
df["bf_sale_price"] = df["bf_sale_price"].astype("float32")
df["competitor_sale_price"] = df["competitor_sale_price"].astype("float32")
```

**Expected Impact**: 30% less memory, 10-15% faster operations

**Total Quick Wins Impact**: 20 min → ~10 min (50% improvement)

---

### **Phase 3: Pre-Aggregated BigQuery Views** 📊
**Goal**: Reduce data volume from BigQuery  
**Priority**: MEDIUM  
**Effort**: 1-2 days  
**Impact**: 10 min → 3-5 min startup

#### 3.1: Create Aggregated View in BigQuery
**File**: `docs/bq_aggregated_view.sql` (NEW)

```sql
-- Create pre-aggregated view at product×competitor grain
-- Runs in BigQuery, not in Python
CREATE OR REPLACE VIEW `bf-data-dev-qz06.dbt_gohary.pricing_data_aggregated` AS

WITH recent_bf_prices AS (
  SELECT 
    product_id,
    MODE(bf_sale_price) AS bf_sale_price_modal
  FROM `bf-data-dev-qz06.dbt_gohary.competitor_price_monitoring_fps`
  WHERE is_recent_breadfast = TRUE
  GROUP BY product_id
),

recent_comp_prices AS (
  SELECT 
    product_id,
    competitor_id,
    MODE(competitor_sale_price) AS competitor_sale_price_modal
  FROM `bf-data-dev-qz06.dbt_gohary.competitor_price_monitoring_fps`
  WHERE is_recent_competitor = TRUE
  GROUP BY product_id, competitor_id
),

used_products AS (
  SELECT
    product_id,
    competitor_id,
    LOGICAL_OR(used_product) AS used_product_any
  FROM `bf-data-dev-qz06.dbt_gohary.competitor_price_monitoring_fps`
  WHERE is_recent_breadfast = TRUE 
    AND is_recent_competitor = TRUE
  GROUP BY product_id, competitor_id
)

SELECT 
  p.product_id,
  p.product_name,
  p.brand_name,
  p.sub_category_name,
  p.competitor_id,
  p.competitor_name,
  COALESCE(bf.bf_sale_price_modal, p.bf_sale_price) AS bf_sale_price,
  COALESCE(cp.competitor_sale_price_modal, p.competitor_sale_price) AS competitor_sale_price,
  COALESCE(bf.bf_sale_price_modal, p.bf_sale_price) / 
    COALESCE(cp.competitor_sale_price_modal, p.competitor_sale_price) AS sale_PI,
  COALESCE(u.used_product_any, FALSE) AS used_product,
  p.eligible_product,
  p.has_PI,
  p.action_type,
  p.total_revenue,
  -- ... other fields
FROM (
  SELECT DISTINCT ON (product_id, competitor_id) *
  FROM `bf-data-dev-qz06.dbt_gohary.competitor_price_monitoring_fps`
) p
LEFT JOIN recent_bf_prices bf USING (product_id)
LEFT JOIN recent_comp_prices cp USING (product_id, competitor_id)
LEFT JOIN used_products u USING (product_id, competitor_id)
```

#### 3.2: Update Python Service to Use Aggregated View
```python
# Change query to use pre-aggregated view
AGGREGATED_QUERY = """
SELECT * FROM `{project}.{dataset}.pricing_data_aggregated`
"""

# Now loading 152K rows instead of 4.5M rows
# 30x less data → 30x faster!
```

**Expected Impact**: 
- Load time: 10 min → 3-5 min
- Memory: 2GB → 100MB
- Queries: Same speed or faster

**Trade-off**: 
- ❌ Lose per-FP price visibility (can't see exact price at each FP)
- ✅ Keep FP-scoped filtering (can filter to specific FPs, just aggregated)
- ✅ Same blended PI calculations

**Recommendation**: Create BOTH views - let user choose at startup:
- `MODE=detailed` → Load 4.5M rows (full fidelity)
- `MODE=aggregated` → Load 152K rows (faster, less detail)

---

### **Phase 4: Query Optimization** 🚀
**Goal**: Speed up FP-scoped queries  
**Priority**: HIGH  
**Effort**: 2-3 days  
**Impact**: 1500ms → <200ms (7x faster)

#### 4.1: Index Key Columns
```python
# Add indexes for common filter columns
df = df.set_index(["product_id", "fp_name", "competitor_id"], drop=False)

# Queries become much faster with indexed columns
scoped = df.loc[df["fp_name"].isin(selected_fps)]  # Fast lookup
```

#### 4.2: Cache Aggregation Results Per FP Combination
```python
from functools import lru_cache

class BigQueryPricingDataService:
    def __init__(self):
        self._aggregation_cache = {}  # Cache by FP combination
    
    def _apply_filters(self, df, filters):
        fp_names = filters.get("fp_names")
        
        if fp_names:
            # Check cache first
            cache_key = tuple(sorted(fp_names.split(",")))
            if cache_key in self._aggregation_cache:
                print(f"[Cache] Hit for FPs: {cache_key}")
                source = self._aggregation_cache[cache_key]
            else:
                # Aggregate and cache
                names = [n.strip() for n in fp_names.split(",")]
                scoped = self._df[self._df["fp_name"].isin(names)]
                source = self._aggregate_to_global(scoped)
                self._aggregation_cache[cache_key] = source
                print(f"[Cache] Cached for FPs: {cache_key}")
        else:
            source = self._global_df
        
        # Apply remaining filters...
```

**Expected Impact**: 
- First query for FP combo: 800-1500ms (no change)
- Subsequent queries for same FPs: <50ms (cached)
- Typical user workflow: Select FPs once, query many times → 95% of queries cached

#### 4.3: Optimize Groupby Operations
```python
# Use observed=True to skip empty categories
df.groupby("sub_category_name", observed=True).apply(...)

# Use built-in aggregations instead of lambda
df.groupby("sub_category_name").agg({
    "sale_PI": "mean",
    "total_revenue": "sum",
    "product_id": "nunique",
})  # Much faster than .apply(lambda g: ...)
```

#### 4.4: Lazy Loading for Product Details
```python
# Don't load all products at once, paginate efficiently
def get_products_page(self, page, page_size, filters):
    # Only aggregate what's needed for this page
    df = self._apply_filters(self._df, filters)
    
    # Sort first, then slice (avoid aggregating all rows)
    df = df.sort_values("total_revenue", ascending=False)
    start = (page - 1) * page_size
    return df.iloc[start:start + page_size]
```

**Total Query Optimization Impact**: 1500ms → 200ms average (first query), <50ms (cached queries)

---

### **Phase 5: Frontend Optimizations** 🎨
**Goal**: Faster rendering and perceived performance  
**Priority**: MEDIUM  
**Effort**: 2 days  
**Impact**: Smoother UI, perceived 2-3x faster

#### 5.1: Virtual Scrolling for Large Tables
**File**: `frontend/src/components/commercial/ProductDetailTable.vue`

```vue
<template>
  <!-- Use vue-virtual-scroller for large tables -->
  <RecycleScroller
    :items="products"
    :item-size="48"
    :buffer="100"
    key-field="product_id"
    v-slot="{ item }"
  >
    <tr>
      <td>{{ item.product_name }}</td>
      <td>{{ item.bf_sale_price }}</td>
      <!-- ... -->
    </tr>
  </RecycleScroller>
</template>

<script setup>
import { RecycleScroller } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
</script>
```

**Impact**: Can render 10,000+ rows smoothly, only renders visible rows

#### 5.2: Debounce Filter Changes
```javascript
// Wait 300ms after user stops typing before querying
import { useDebounceFn } from '@vueuse/core'

const debouncedFetch = useDebounceFn(() => {
  store.fetchProducts()
}, 300)
```

#### 5.3: Show Skeleton Loaders During Load
```vue
<template>
  <div v-if="loading" class="skeleton-loader">
    <!-- Show placeholder UI while loading -->
    <div class="skeleton-row" v-for="i in 10" :key="i"></div>
  </div>
  <div v-else>
    <!-- Real data -->
  </div>
</template>
```

#### 5.4: Background Data Refresh Notification
```vue
<template>
  <!-- Non-intrusive banner when background refresh happens -->
  <Transition name="slide-down">
    <div v-if="backgroundLoading" class="refresh-banner">
      <Loader2 class="animate-spin" />
      Refreshing data in background... {{ backgroundProgress }}%
      <button @click="dismissBanner">Dismiss</button>
    </div>
  </Transition>
</template>
```

**Impact**: Users feel app is responsive even during background loads

---

## Implementation Timeline

### Week 1: Critical Path
- **Day 1-2**: Phase 1 (Background Loading) - PRIORITY 1
  - Implement cache service
  - Implement background loader
  - Update main.py
  - Test cache load/save
  
- **Day 3**: Phase 2 (Quick Wins) - PRIORITY 2
  - Switch to PyArrow
  - Column filtering
  - Categorical dtypes
  - Test and measure

- **Day 4-5**: Phase 4.1-4.3 (Query Optimization) - PRIORITY 3
  - Implement aggregation cache
  - Optimize groupby operations
  - Test FP-scoped query performance

### Week 2: Enhancements
- **Day 6-7**: Phase 3 (Pre-aggregated Views) - OPTIONAL
  - Create BigQuery view
  - Test aggregated mode
  - Compare performance
  
- **Day 8-9**: Phase 5 (Frontend) - POLISH
  - Virtual scrolling
  - Skeleton loaders
  - Background refresh UI

- **Day 10**: Testing & Documentation
  - End-to-end performance testing
  - Update documentation
  - User training

---

## Expected Performance Improvements

### Startup Time
| Scenario | Before | After Phase 1 | After Phase 2 | After Phase 3 |
|----------|--------|---------------|---------------|---------------|
| **First startup** | 20 min | 20 min | 10 min | 5 min |
| **Subsequent startups** | 20 min | **5 sec** | **5 sec** | **3 sec** |
| **With 6hr refresh** | Manual | **Auto, 0 downtime** | Auto, 0 downtime | Auto, 0 downtime |

### Query Performance
| Query Type | Before | After Phase 4 | Improvement |
|------------|--------|---------------|-------------|
| **GLOBAL queries** | 50ms | 40ms | 20% faster |
| **FP-scoped (first)** | 1500ms | 200ms | **7.5x faster** |
| **FP-scoped (cached)** | 1500ms | **30ms** | **50x faster** |
| **Product details** | 2000ms | 150ms | **13x faster** |

### Memory Usage
| Mode | Before | After Phase 2 | After Phase 3 |
|------|--------|---------------|---------------|
| **RAM usage** | 2.0 GB | 1.4 GB | 100 MB |
| **Cache disk** | 0 MB | 500 MB | 50 MB |

---

## Success Metrics

### Phase 1 Success (Background Loading)
- ✅ App starts in <10 seconds (from cache)
- ✅ Data refreshes every 6 hours automatically
- ✅ Users can work during background refresh
- ✅ Background progress visible in UI
- ✅ Zero downtime for data refreshes

### Phase 2 Success (Quick Wins)
- ✅ First-time load reduced to <10 minutes
- ✅ Memory usage reduced by 30%
- ✅ Cache save/load works reliably

### Phase 4 Success (Query Optimization)
- ✅ FP-scoped queries <200ms (first time)
- ✅ FP-scoped queries <50ms (cached)
- ✅ Product details table loads <200ms
- ✅ 95%+ queries served from cache

### Phase 5 Success (Frontend)
- ✅ Tables render 10,000+ rows smoothly
- ✅ No UI freezing during data operations
- ✅ Background refresh doesn't disrupt user
- ✅ Perceived performance "feels instant"

---

## Risk Mitigation

### Risk 1: Cache Corruption
**Mitigation**: Version cache files, validate on load, fall back to fresh load
```python
if cache_version != CURRENT_VERSION:
    invalidate_cache()
    load_fresh()
```

### Risk 2: Background Load Fails
**Mitigation**: Retry logic, keep serving stale data, alert user
```python
if background_load_fails:
    retry_after_delay()
    show_warning("Using cached data, refresh failed")
```

### Risk 3: Memory Issues on Laptop
**Mitigation**: Monitor RAM usage, implement memory limits, graceful degradation
```python
if get_memory_usage() > 3.5GB:  # Leave 0.5GB for OS
    clear_aggregation_cache()
    warn_user("Low memory, cleared cache")
```

### Risk 4: BigQuery Quota Exceeded
**Mitigation**: Rate limiting, backoff strategy, cache longer
```python
if quota_exceeded:
    extend_cache_ttl(24_hours)
    notify_admin()
```

---

## Rollback Plan

Each phase is independent and can be rolled back:

### Rollback Phase 1 (Background Loading)
```bash
# Disable cache loading
export USE_CACHE=false
# App reverts to direct BigQuery load
```

### Rollback Phase 2 (Quick Wins)
```bash
# Revert to DataFrame iteration method
git revert <commit-hash>
```

### Rollback Phase 3 (Pre-aggregated Views)
```python
# Switch back to full FP-grain query
USE_AGGREGATED_VIEW = False
```

---

## Testing Strategy

### Performance Testing
```python
# backend/tests/test_performance.py
def test_cache_load_time():
    """Cache load should be <5 seconds."""
    start = time.time()
    data = cache.load("pricing_data")
    elapsed = time.time() - start
    assert elapsed < 5.0, f"Cache load took {elapsed}s"

def test_fp_query_time():
    """FP-scoped queries should be <200ms."""
    start = time.time()
    result = svc.get_all_products({"fp_names": "New Cairo FP #1"})
    elapsed = time.time() - start
    assert elapsed < 0.2, f"Query took {elapsed}s"

def test_background_refresh():
    """Background refresh should not block app."""
    app.state.background_loader.start_background_load(load_fresh_data)
    
    # App should still respond
    response = client.get("/api/commercial/kpis")
    assert response.status_code == 200
    
    # Background should be running
    assert app.state.background_loader.loading == True
```

### Load Testing
```bash
# Use locust or similar for load testing
locust -f tests/loadtest.py --users 10 --spawn-rate 2
```

---

## Monitoring & Observability

### Add Performance Metrics
```python
# backend/middleware/performance.py
from time import time
from fastapi import Request

@app.middleware("http")
async def add_performance_header(request: Request, call_next):
    start = time()
    response = await call_next(request)
    elapsed = time() - start
    response.headers["X-Response-Time"] = str(elapsed)
    
    # Log slow queries
    if elapsed > 1.0:
        logger.warning(f"Slow request: {request.url} took {elapsed}s")
    
    return response
```

### Cache Hit Rate Monitoring
```python
class CacheMetrics:
    hits = 0
    misses = 0
    
    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0

# Expose via endpoint
@app.get("/api/metrics/cache")
def get_cache_metrics():
    return {
        "hit_rate": cache_metrics.hit_rate,
        "hits": cache_metrics.hits,
        "misses": cache_metrics.misses,
    }
```

---

## Configuration

### Environment Variables
```bash
# .env
CACHE_ENABLED=true
CACHE_MAX_AGE_HOURS=6
CACHE_DIR=./cache/pricing_data
USE_PYARROW=true
USE_AGGREGATED_VIEW=false
ENABLE_QUERY_CACHE=true
MAX_MEMORY_GB=3.5
BACKGROUND_REFRESH_ENABLED=true
```

### Config File
```python
# backend/config.py
class Settings(BaseSettings):
    # Cache settings
    CACHE_ENABLED: bool = True
    CACHE_MAX_AGE_HOURS: int = 6
    CACHE_DIR: Path = Path("cache/pricing_data")
    
    # Performance settings
    USE_PYARROW: bool = True
    USE_AGGREGATED_VIEW: bool = False
    ENABLE_QUERY_CACHE: bool = True
    MAX_MEMORY_GB: float = 3.5
    
    # Background loading
    BACKGROUND_REFRESH_ENABLED: bool = True
    BACKGROUND_REFRESH_INTERVAL_HOURS: int = 6
```

---

## Documentation Updates Needed

1. **User Guide**: How to use background refresh feature
2. **Admin Guide**: Cache management, clearing cache, troubleshooting
3. **Performance Guide**: Expected latencies, cache behavior, optimization tips
4. **API Docs**: New `/api/background-status` endpoint
5. **Deployment Guide**: Cache directory setup, permissions

---

## Summary

### Key Innovations
1. **🎯 Background Loading**: Zero-downtime, auto-refresh every 6 hours
2. **⚡ Quick Wins**: 50% faster startup (20 min → 10 min)
3. **🚀 Query Cache**: 7-50x faster FP-scoped queries
4. **📊 Pre-aggregated Views**: Optional 3-5 min startup mode
5. **🎨 Frontend Polish**: Virtual scrolling, smooth UX

### Total Impact
- **Startup**: 20 min → **5 sec** (from cache)
- **Background refresh**: **Zero downtime**
- **FP queries**: 1500ms → **30-200ms**
- **User experience**: **Dramatically improved**

### Investment
- **Time**: 1-2 weeks implementation
- **Budget**: No infrastructure costs (disk-based cache)
- **Risk**: Low (phased rollout, independent phases)

### Recommendation
**Start with Phase 1 (Background Loading)** - this gives the biggest user experience improvement with zero infrastructure costs. Then add Phase 2 (Quick Wins) and Phase 4 (Query Cache) for complete optimization.

---

## Next Steps

1. **Review this plan** - any questions or concerns?
2. **Prioritize phases** - confirm Phase 1 → 2 → 4 order
3. **Start implementation** - I can begin Phase 1 immediately
4. **Test iteratively** - validate each phase before moving to next

Ready to start? 🚀
