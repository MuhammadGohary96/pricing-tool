# Pricing Intelligence Web App — Implementation Plan

## Context

Breadfast needs an internal pricing intelligence tool to compare prices against Talabat (main competitor). Three audiences: Commercial Team (pricing decisions), Master Data Team (product mapping queue), Executive Leadership (position monitoring). Full specification in `Pricing_Intelligence_TechSpec.md`.

**Key decisions:**
- Start with **mock data** (no BigQuery credentials needed yet)
- Use **TanStack Table** (free, headless) instead of AG Grid
- Backend port **8001**, frontend port **5174**
- **34 components** total across all views (per TechSpec §5)

---

## Phase 1: Project Scaffolding + Mock Data Foundation ✅ DONE

**Goal:** Both projects running, frontend calls backend, navigation works.

### Backend (completed)
| File | Status |
|---|---|
| `main.py` — FastAPI app, CORS, lifespan handler | ✅ |
| `config.py` — Pydantic BaseSettings (DATA_SOURCE=mock, CORS=localhost:5174) | ✅ |
| `requirements.txt` | ✅ |
| `services/__init__.py` — Service factory (mock/BigQuery) | ✅ |
| `services/data_interface.py` — ABC with 15 methods | ✅ |
| `services/mock_data_service.py` — ~2500 products, seeded randomness | ✅ |
| `routers/health.py` — `GET /api/health` | ✅ |
| `routers/filters.py` — categories, subcategories, tiers | ✅ |
| `models/` — Pydantic models (product, metrics, filters) | ✅ |
| `utils/calculations.py` — Blended PI, action type logic | ✅ |
| `utils/formatters.py` — Number/symbol formatting | ✅ |

### Frontend (completed)
| File | Status |
|---|---|
| Vue 3 + Vite + TailwindCSS + ECharts + TanStack Table | ✅ |
| `vite.config.js` — proxy `/api` → localhost:8001, port 5174 | ✅ |
| `tailwind.config.js` — Breadfast brand tokens | ✅ |
| `src/assets/styles/breadfast.css` — CSS variables, Lato, sharp edges | ✅ |
| `src/router/index.js` — 3 routes | ✅ |
| `src/api/client.js` — Axios + all endpoint wrappers | ✅ |
| `src/stores/filters.js` — Shared filter state (Pinia) | ✅ |
| `src/components/layout/AppHeader.vue` — Nav tabs + logo | ✅ |
| `src/components/layout/FilterBar.vue` — Dropdowns + clear | ✅ |
| `src/components/layout/KpiCard.vue` — Reusable KPI card | ✅ |
| `src/views/*.vue` — Placeholder views | ✅ |

---

## Phase 2: Commercial View ✅ DONE

**Goal:** Full interactive commercial dashboard — treemap click → filter → table update.

**Ref:** TechSpec §4.1, §5.2, §6.1

### Backend — `routers/commercial.py`

| Endpoint | Service Method | Response Model |
|---|---|---|
| `GET /api/commercial/kpis` | `get_kpi_summary(filters)` | `CommercialKPIs` |
| `GET /api/commercial/treemap` | `get_blended_pi_by_subcategory(filters)` | `TreemapData` |
| `GET /api/commercial/blended-pi` | `get_blended_pi_by_subcategory(filters)` | `BlendedPITable` |
| `GET /api/commercial/products?page=&page_size=` | `get_all_products(filters)` + pagination | `ProductDetailTable` |
| `GET /api/commercial/funnel` | `get_coverage_funnel(filters)` | `CoverageFunnel` |

All endpoints accept `FilterParams` via query params.

### Frontend — Store

| File | Purpose |
|---|---|
| `src/stores/commercial.js` | Pinia store: kpis, treemap, blendedPI, products, funnel, loading, pagination |

### Frontend — Components (TechSpec §5.2)

| Component | Tech | Description |
|---|---|---|
| `SubcategoryTreemap.vue` | vue-echarts | Size=revenue, color=PI, click → filter subcategory |
| `BlendedPITable.vue` | TanStack Table | Subcategory ranking with inline PI bars, sortable |
| `ProductDetailTable.vue` | TanStack Table | Row-level product data, sortable, paginated |
| `CoverageFunnel.vue` | CSS/Tailwind | 5-stage horizontal funnel, progressive brand shading |
| `PIInlineBar.vue` | CSS | Small horizontal bar showing PI magnitude |
| `TierBadge.vue` | CSS | Styled tier badge (brand shading for Top+/Top) |
| `ActionBadge.vue` | CSS | Color-coded action label: ⊘/⚡/⟳/✓ |
| `DirectionArrow.vue` | CSS | ▲/▼ with numeric deviation |

### Frontend — View

| File | Purpose |
|---|---|
| `CommercialView.vue` | Orchestrator: fetch all data on mount, watch filters, layout grid |

**Layout (per TechSpec §6.1):**
```
[FilterBar]
[KPI1] [KPI2] [KPI3] [KPI4] [KPI5]           ← KpiStrip / 5 KpiCards
[Treemap  38%] [BlendedPITable  62%]          ← Row 4 top
[             ] [ProductDetailTable   ]        ← Row 4 bottom
[CoverageFunnel full width]                    ← Row 5
```

**Deliverable:** Interactive commercial dashboard. Click treemap → filters update → tables + funnel refresh.

---

## Phase 3: Master Data View ✅ DONE

**Goal:** Full action queue dashboard with filtering and AI match review.

**Ref:** TechSpec §4.2, §5.3, §6.2

### Backend — `routers/master_data.py`

| Endpoint | Response |
|---|---|
| `GET /api/master-data/action-summary` | 4 action type KPI counts |
| `GET /api/master-data/action-breakdown` | Actions by category (stacked bar data) |
| `GET /api/master-data/worklist?page=&page_size=` | Priority worklist (paginated) |
| `GET /api/master-data/ai-matches?page=&page_size=` | AI match candidates |
| `GET /api/master-data/staleness-heatmap` | Subcategory × days matrix |
| `GET /api/master-data/coverage-progress` | Coverage % trend line |
| `POST /api/master-data/ai-match/{id}/accept` | Accept (placeholder 501) |
| `POST /api/master-data/ai-match/{id}/reject` | Reject (placeholder 501) |

### Frontend — Components (TechSpec §5.3)

| Component | Tech |
|---|---|
| `ActionSummary.vue` | 4 KpiCards |
| `ActionBreakdown.vue` | ECharts stacked horizontal bar |
| `PriorityWorklist.vue` | TanStack Table |
| `AIMatchPanel.vue` | Scrollable match cards |
| `AIMatchCard.vue` | Single BF↔Talabat comparison |
| `StalenessHeatmap.vue` | ECharts heatmap |
| `CoverageProgress.vue` | ECharts line + 90% target |
| `WorklistActionButton.vue` | Inline action button |

### Frontend — Store + View

| File | Purpose |
|---|---|
| `src/stores/masterData.js` | State + fetch actions |
| `MasterDataView.vue` | Orchestrator |

**Deliverable:** Full action queue dashboard with filtering.

---

## Phase 4: Executive View ✅ DONE

**Goal:** Leadership dashboard — gauge, trends, category performance.

**Ref:** TechSpec §4.3, §5.4, §6.3

### Backend — `routers/executive.py`

| Endpoint | Response |
|---|---|
| `GET /api/executive/summary` | Overall PI, coverage, top/bottom 5, WoW deltas |
| `GET /api/executive/pi-trend` | 30-day blended PI time series |
| `GET /api/executive/coverage-trend` | 30-day coverage % time series |
| `GET /api/executive/category-performance` | PI by main category |
| `GET /api/executive/week-over-week` | WoW deltas for all key metrics |

### Frontend — Components (TechSpec §5.4)

| Component | Tech |
|---|---|
| `PIGauge.vue` | ECharts gauge (0.80–1.20 range) |
| `MiniKpiCard.vue` | Compact KPI with target + WoW delta |
| `TopBottomSubcats.vue` | Two-column ranked lists |
| `PITrendLine.vue` | ECharts line + 1.0 parity reference |
| `CategoryPerformance.vue` | ECharts diverging horizontal bar |
| `CoverageTrendLine.vue` | ECharts line + 90% target |
| `WoWDelta.vue` | Compact ▲/▼ delta indicator |

### Frontend — Store + View

| File | Purpose |
|---|---|
| `src/stores/executive.js` | State + fetch actions |
| `ExecutiveView.vue` | Orchestrator (no FilterBar) |

**Deliverable:** Executive summary with gauge, trends, and category performance.

---

## Phase 5: Shared Components + Polish ✅ DONE

**Goal:** Reusable utilities and cross-cutting UX.

**Ref:** TechSpec §5.1, §5.5

### Shared Components

| Component | Purpose |
|---|---|
| `KpiStrip.vue` | Horizontal row of KpiCards with dividers |
| `PageShell.vue` | Page wrapper with loading/error boundaries |
| `StarRating.vue` | ★★★★★ tier indicator |
| `SymbolLabel.vue` | Symbol + text label |
| `ExportButton.vue` | CSV export trigger |
| `EmptyState.vue` | Filtered-to-zero placeholder |
| `ConfirmModal.vue` | Accept/reject confirmation dialog |

### Composables

| File | Purpose |
|---|---|
| `useBlendedPI.js` | Blended PI formatting |
| `useActionType.js` | Action badge symbol/color mapping |
| `useTierRating.js` | Star rating rendering |
| `useExport.js` | CSV export from tables |

### Polish
- Loading skeleton states per component
- Error state handling per panel
- Brand compliance audit (font sizes, 0px gaps, sharp corners, no banned colors)

---

## Phase 6: Cross-View Interactivity + URL Sync ✅ PARTIAL

**Goal:** Deep linking, filter-to-URL sync, bookmarkable views.
**Done:** URL sync composable (filter state ↔ query params), CSV export endpoint.
**Remaining:** Sub-routes for drill-down views, 404 page, meta templates.

**Ref:** TechSpec §9

- **URL sync:** filter state ↔ URL query params via Vue Router (`pushState`)
- **Deep links:** `/commercial/subcategory/:slug`, `/commercial/product/:id`
- **Filter chips:** active filters shown as removable badges
- **Meta templates:** page titles per TechSpec §9.2
- **404 page:** navigation back to /commercial

### Additional Routes

| Route | View |
|---|---|
| `/commercial/subcategory/:id` | Subcategory drill-down |
| `/commercial/product/:id` | Product detail |
| `/master-data/ai-matches` | Dedicated AI review page |
| `/master-data/staleness` | Staleness monitor |
| `/executive/trends` | Trend analysis deep-dive |

### Backend — `routers/commercial.py` (additions)

| Endpoint | Purpose |
|---|---|
| `GET /api/commercial/export?format=csv&filters=` | CSV export of filtered products |

---

## Phase 7: Caching + Performance

**Goal:** Meet performance budgets from TechSpec §8.

**Ref:** TechSpec §8

### Backend
- `services/cache_service.py` — in-memory TTL cache (15 min), keyed by endpoint + filters
- Global exception handler middleware
- Streaming CSV response for large exports

### Frontend
- Debounce filter changes (300ms)
- `shallowRef` for large arrays
- Lazy-load ECharts (code splitting per view)
- AG Grid virtual scrolling (via TanStack Table virtualizer)

### Targets
| Metric | Target |
|---|---|
| API response (cached) | < 200ms |
| API response (cold) | < 2.0s |
| First Contentful Paint | < 1.5s |
| Total bundle (gzipped) | < 250 KB |

---

## Phase 8: BigQuery Integration

**Goal:** Switch from mock data to real BigQuery data.

- `services/bigquery_service.py` — implements same `PricingDataServiceInterface`
- Toggle via `DATA_SOURCE=bigquery` in `.env`
- Zero frontend changes required
- BQ materialized views for pre-aggregated subcategory metrics

---

## Phase 9: Auth + Infrastructure

**Goal:** Production-ready deployment.

**Ref:** TechSpec §7.3

### Auth
- Google OAuth2 SSO (Breadfast workspace)
- JWT token middleware
- `/auth/login`, `/auth/callback`, `/auth/me` endpoints
- `/login` view + route guard

### Infrastructure
| Layer | Service |
|---|---|
| Backend hosting | Google Cloud Run |
| Frontend hosting | Cloud Run (static) or Firebase Hosting |
| Cache | Cloud Memorystore (Redis) |
| CI/CD | Cloud Build (auto-deploy on merge to main) |
| Monitoring | Cloud Logging + Error Reporting |

### Additional
- Dockerfile for backend + frontend
- docker-compose for local dev
- `/settings` page (notification prefs, default filters)

---

## Component Inventory (34 total)

| Category | Components | Count |
|---|---|---|
| Layout | AppHeader, FilterBar, KpiCard, KpiStrip, PageShell, NavTabs | 6 |
| Commercial | SubcategoryTreemap, BlendedPITable, ProductDetailTable, CoverageFunnel, PIInlineBar, TierBadge, ActionBadge, DirectionArrow | 8 |
| Master Data | ActionSummary, ActionBreakdown, PriorityWorklist, AIMatchPanel, AIMatchCard, StalenessHeatmap, CoverageProgress, WorklistActionButton | 8 |
| Executive | PIGauge, MiniKpiCard, TopBottomSubcats, PITrendLine, CategoryPerformance, CoverageTrendLine, WoWDelta | 7 |
| Shared | StarRating, SymbolLabel, ExportButton, EmptyState, ConfirmModal | 5 |
| **Total** | | **34** |

---

## Verification Plan

After each phase:
1. Start backend: `python3 -m uvicorn backend.main:app --port 8001 --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:5174` and verify the phase deliverable
4. Test Swagger docs at `http://localhost:8001/docs`
5. Check browser console + terminal for errors
6. Test filter interactions across components
