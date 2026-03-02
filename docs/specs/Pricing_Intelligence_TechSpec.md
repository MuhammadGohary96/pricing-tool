# Breadfast Pricing Intelligence — Technical Specification

**Web Application**

Architecture, Data Models, Components & Implementation Guide

| | |
|---|---|
| **Stack** | FastAPI + Vue.js 3 + Google BigQuery |
| **Version** | 1.0 |
| **Date** | February 2026 |
| **Author** | Mohamed El Gohary, Analytics Team |
| **Status** | Planning |

---

## Table of Contents

1. [Site Map](#1-site-map)
2. [User Flows](#2-user-flows)
3. [Data Models](#3-data-models)
4. [API Requirements](#4-api-requirements)
5. [Component Inventory](#5-component-inventory)
6. [Page Templates](#6-page-templates)
7. [Technical Stack](#7-technical-stack)
8. [Performance Budgets](#8-performance-budgets)
9. [SEO & URL Structure](#9-seo--url-structure)
10. [Appendix: Design Tokens](#appendix-design-tokens)

---

## 1. Site Map

Complete page hierarchy for the Pricing Intelligence web application. All routes are prefixed with the app base URL.

| Route | Page Name | View | Description |
|---|---|---|---|
| `/` | Landing / Redirect | N/A | Redirects to /commercial (default view) |
| `/login` | Login | Auth | Google SSO via Breadfast workspace |
| `/commercial` | Commercial Dashboard | Commercial | Main pricing intelligence view for commercial team |
| `/commercial/subcategory/:id` | Subcategory Drill-down | Commercial | Deep-dive into single subcategory products |
| `/commercial/product/:id` | Product Detail | Commercial | Single product pricing history and match detail |
| `/master-data` | Action Queue | Master Data | Prioritized worklist for master data team |
| `/master-data/ai-matches` | AI Match Review | Master Data | Dedicated AI match accept/reject workflow |
| `/master-data/staleness` | Staleness Monitor | Master Data | Heatmap view of stale prices by subcategory |
| `/executive` | Executive Summary | Executive | High-level PI, coverage, trends for leadership |
| `/executive/trends` | Trend Analysis | Executive | 30/60/90 day PI and coverage trend deep-dive |
| `/settings` | User Settings | Shared | Notification preferences, default filters, export settings |
| `/api/docs` | API Documentation | System | Auto-generated FastAPI Swagger/OpenAPI docs |

**Site map hierarchy:**

```
app.breadfast.com/
  ├── /login
  ├── /commercial
  │   ├── /subcategory/:id
  │   └── /product/:id
  ├── /master-data
  │   ├── /ai-matches
  │   └── /staleness
  ├── /executive
  │   └── /trends
  └── /settings
```

---

## 2. User Flows

Three primary user journeys mapped to the core audiences of the tool.

### Flow 1: Commercial Manager — Subcategory Price Investigation

**Goal:** Identify an overpriced subcategory and drill down to specific products to take pricing action.

1. Login via Google SSO → lands on /commercial (default view)
2. Scans KPI bar: spots Avg Blended PI at 1.07 and 2,282 products needing action
3. Examines treemap: notices Frozen Foods cell is light-colored (PI 0.91 — BF is 9% more expensive)
4. Clicks Frozen Foods cell in treemap → all panels filter to that subcategory
5. Blended PI table confirms: Frozen Foods ranked lowest, direction ▼ -0.09
6. Product Detail table shows individual products: sorts by Sale PI ascending to find worst offenders
7. Identifies 3 Top+ tier frozen products priced 15-20% above Talabat
8. Exports filtered product list to CSV for pricing team action
9. Checks Coverage Funnel: only 68% of Frozen subcategory products are Used (mapped + updated)

### Flow 2: Master Data Analyst — Daily Mapping & Review Workflow

**Goal:** Work through the daily action queue, prioritizing high-impact products first.

1. Login → navigates to /master-data
2. Scans Action Summary KPIs: 1,140 Needs Mapping, 485 Review AI Match, 657 Needs Update
3. Checks Action Breakdown chart: Dairy has the most actions (342) — clicks to filter
4. Priority Worklist shows Dairy products sorted by tier (Top+ first) then revenue
5. Sees 12 Top+ Dairy products marked ⚡ Review AI Match with scores 0.89–0.96
6. Clicks to open AI Match Review panel: sees BF product alongside suggested Talabat match
7. Reviews match: Juhayna Full Cream 1L ↔ Juhayna Fresh Milk 1L (score 0.93) → clicks Accept
8. Continues through queue: accepts 8 matches, rejects 2 poor matches, flags 2 for manual review
9. Switches Action Type filter to ⟳ Needs Update: sees Staleness Heatmap showing 45 Dairy products stale >21 days
10. Exports stale products list and sends to scraping team for price refresh

### Flow 3: VP Commercial — Weekly Executive Review

**Goal:** Assess overall competitive position and coverage health in under 2 minutes.

1. Login → navigates to /executive
2. Reads Overall Blended PI gauge: 1.07 — BF is 7% cheaper overall. WoW: ▲ +0.02 (improving)
3. Checks Coverage: 47.5% of products are Used. WoW: +1.2 percentage points (improving)
4. Scans Top 5 / Bottom 5: Cleaning is best (PI 1.15), Frozen is worst (PI 0.91)
5. Views PI Trend line: steady upward trajectory over last 30 days, parity line clearly exceeded
6. Views PI by Main Category bar chart: Home Care strongest, Food & Beverage near parity
7. Reviews Coverage Progress trend: on track to reach 60% by end of quarter but far from 90% target
8. Navigates to /executive/trends for 90-day view: confirms positive momentum but flags Frozen for commercial team attention

---

## 3. Data Models

Pydantic models used across the FastAPI backend. These map directly to the BigQuery source table and computed metrics.

### 3.1 Product Model

| Field | Type | Source | Description |
|---|---|---|---|
| `product_id` | str | BQ column | Breadfast product identifier |
| `product_name` | str | BQ column | Display name |
| `brand_name` | str | BQ column | Product brand |
| `main_category_name` | str | BQ column | Top-level category |
| `commercial_category_name` | str | BQ column | Commercial grouping |
| `sub_category_name` | str | BQ column | Granular subcategory (180 values) |
| `total_revenue` | float | BQ column | Cumulative revenue (EGP) |
| `avg_daily_quantity` | float | BQ column | Average daily units sold |
| `weighted_score` | float | BQ column | norm_rev × 0.5 + norm_qty × 0.5 |
| `global_tier` | str | BQ column | Top+, Top, Medium, Low, Very Low |
| `subcat_tier` | str | BQ column | Tier within subcategory peers |
| `eligible_product` | bool | BQ column | Within top 80% cumulative subcat revenue |
| `bf_sale_price` | float | BQ column | Breadfast sale price (EGP) |
| `talabat_sale_price` | float \| None | BQ column | Talabat sale price (EGP), null if unmapped |
| `sale_PI` | float \| None | BQ column | talabat_sale / bf_sale |
| `has_PI` | bool | BQ column | Has confirmed competitor match |
| `updated` | bool | BQ column | Talabat price refreshed within 7 days |
| `similarity_score` | float \| None | BQ column | AI match confidence (0–1) |
| `match_potential` | bool | BQ column | similarity_score >= 0.85 |
| `used_product` | bool | BQ column | eligible AND has_PI AND updated |
| `action_type` | str | Computed | Needs Mapping / Review AI / Needs Update / Complete |
| `pi_deviation` | float \| None | Computed | sale_PI - 1 |
| `days_since_update` | int \| None | Computed | Days since talabat_price_updated_at |

### 3.2 Subcategory Blended PI Model

| Field | Type | Description |
|---|---|---|
| `sub_category_name` | str | Subcategory identifier |
| `blended_pi` | float | Σ(PI × qty) / Σ(qty) for used products |
| `used_product_count` | int | Count of used products in subcategory |
| `total_revenue` | float | Total revenue across used products |
| `pi_deviation` | float | blended_pi - 1 |
| `direction` | str | ▲ (>0), ▼ (<0), or — (=0) |
| `tier_distribution` | dict | Count per tier within subcategory |

### 3.3 Coverage Funnel Model

| Field | Type | Description |
|---|---|---|
| `stage_name` | str | All Products / Eligible / Mapped / Updated / Used |
| `count` | int | Product count at this stage |
| `pct` | float | Percentage of All Products |
| `symbol` | str | 📦 / ★ / 🔗 / ⏱ / ✔ |
| `drop_off` | int \| None | Products lost from previous stage |

### 3.4 Executive Summary Model

| Field | Type | Description |
|---|---|---|
| `overall_blended_pi` | float | Grand qty-weighted PI across all subcategories |
| `coverage_pct` | float | used_products / total_products × 100 |
| `total_products` | int | All BF products |
| `used_products` | int | Eligible + mapped + updated |
| `needs_action` | int | Eligible products not Complete |
| `wow_pi_delta` | float | Week-over-week change in blended PI |
| `wow_coverage_delta` | float | WoW change in coverage % |
| `wow_actions_delta` | int | WoW change in needs_action count |
| `top_5_cheapest` | list[SubcatPI] | Subcategories where BF is cheapest |
| `top_5_expensive` | list[SubcatPI] | Subcategories where BF is most expensive |
| `pi_trend_30d` | list[DailyPI] | Daily blended PI for last 30 days |
| `coverage_trend_30d` | list[DailyCoverage] | Daily coverage % for last 30 days |

---

## 4. API Requirements

RESTful JSON API served by FastAPI. All endpoints prefixed with `/api/v1`. Authentication via Google OAuth2 JWT tokens.

### 4.1 Commercial Endpoints

| Method | Endpoint | Response | Cache TTL |
|---|---|---|---|
| GET | `/commercial/kpis` | KPI summary (5 metrics) | 15 min |
| GET | `/commercial/treemap` | Subcategory treemap data | 15 min |
| GET | `/commercial/blended-pi?sort=&order=` | Blended PI ranking table | 15 min |
| GET | `/commercial/products?subcat=&tier=&action=&page=&limit=` | Paginated product table | 5 min |
| GET | `/commercial/funnel?category=&subcat=` | Coverage funnel counts | 15 min |
| GET | `/commercial/export?format=csv&filters=` | CSV export of filtered products | No cache |

### 4.2 Master Data Endpoints

| Method | Endpoint | Response | Cache TTL |
|---|---|---|---|
| GET | `/master-data/action-summary` | Action type KPI cards (4 counts) | 15 min |
| GET | `/master-data/action-breakdown?group_by=` | Actions by category (stacked bar) | 15 min |
| GET | `/master-data/worklist?action=&tier=&page=&limit=` | Priority worklist (paginated) | 5 min |
| GET | `/master-data/ai-matches?page=&limit=` | AI match candidates | 5 min |
| POST | `/master-data/ai-match/{product_id}/accept` | Accept AI match | Invalidate |
| POST | `/master-data/ai-match/{product_id}/reject` | Reject AI match | Invalidate |
| GET | `/master-data/staleness-heatmap` | Staleness by subcat × days | 15 min |
| GET | `/master-data/coverage-progress?days=30` | Coverage % trend line | 15 min |

### 4.3 Executive Endpoints

| Method | Endpoint | Response | Cache TTL |
|---|---|---|---|
| GET | `/executive/summary` | Overall PI, coverage, top/bottom 5, WoW deltas | 15 min |
| GET | `/executive/pi-trend?days=30` | Daily blended PI trend | 15 min |
| GET | `/executive/coverage-trend?days=30` | Daily coverage % trend | 15 min |
| GET | `/executive/category-performance` | PI by main category (bar chart) | 15 min |
| GET | `/executive/week-over-week` | WoW delta for all key metrics | 15 min |

### 4.4 Shared Endpoints

| Method | Endpoint | Response | Cache TTL |
|---|---|---|---|
| GET | `/filters/categories` | Distinct main categories | 1 hour |
| GET | `/filters/subcategories?main=` | Subcategories for a main category | 1 hour |
| GET | `/filters/tiers` | Available tier values | 1 hour |
| GET | `/health` | Health check + BQ connectivity | No cache |
| GET | `/auth/login` | Google OAuth2 redirect | N/A |
| GET | `/auth/callback` | OAuth2 callback handler | N/A |
| GET | `/auth/me` | Current user profile | No cache |

---

## 5. Component Inventory

30+ Vue.js components organized by domain. All components use the Breadfast design tokens and TailwindCSS utility classes.

### 5.1 Layout Components (6)

| Component | Props | Description |
|---|---|---|
| `AppHeader.vue` | activeView, user | Top bar: title, nav tabs (Commercial/MD/Exec), toolbar icons, logo |
| `FilterBar.vue` | filters, options, onUpdate | Horizontal filter chips with dropdowns; shared across all views |
| `KpiCard.vue` | icon, value, label, subtitle, color, delta | Reusable KPI metric card with icon, value, delta indicator |
| `KpiStrip.vue` | kpis[] | Horizontal row of 4-5 KpiCards with dividers |
| `PageShell.vue` | title, loading, error | Standard page wrapper with loading states and error boundaries |
| `NavTabs.vue` | tabs[], active | Tab-style navigation switcher with brand active state |

### 5.2 Commercial View Components (8)

| Component | Props | Description |
|---|---|---|
| `SubcategoryTreemap.vue` | data[], onSelect | ECharts treemap: size=revenue, color=PI, click to filter |
| `BlendedPITable.vue` | data[], sortBy, order | AG Grid table with inline PI bars, tier badges, direction arrows |
| `ProductDetailTable.vue` | data[], filters, onExport | AG Grid table with sortable columns, action badges, CSV export |
| `CoverageFunnel.vue` | stages[] | Horizontal 5-stage funnel with progressive brand shading |
| `PIInlineBar.vue` | value, max | Small inline horizontal bar showing PI magnitude |
| `TierBadge.vue` | tier | Styled badge: brand shading for Top+/Top, grey for others |
| `ActionBadge.vue` | action | Color-coded action label: ⊘/⚡/⟳/✓ with brand palette |
| `DirectionArrow.vue` | deviation | ▲/▼ with numeric deviation, brand-colored |

### 5.3 Master Data View Components (8)

| Component | Props | Description |
|---|---|---|
| `ActionSummary.vue` | counts{} | Four KPI cards: Total Actions, Mapping, AI, Update |
| `ActionBreakdown.vue` | data[], groupBy | ECharts stacked horizontal bar: actions by category |
| `PriorityWorklist.vue` | data[], filters, onAction | AG Grid priority-sorted table with action buttons per row |
| `AIMatchPanel.vue` | matches[], onAccept, onReject | Side-by-side BF↔Talabat comparison with score bar |
| `AIMatchCard.vue` | bfProduct, talabatMatch, score | Single match card: product names, score, accept/reject buttons |
| `StalenessHeatmap.vue` | data[] | ECharts heatmap: subcategory × days-since-update |
| `CoverageProgress.vue` | data[], target | ECharts line chart with 90% target goal line |
| `WorklistActionButton.vue` | action, productId | Inline action trigger button with confirmation modal |

### 5.4 Executive View Components (7)

| Component | Props | Description |
|---|---|---|
| `PIGauge.vue` | value, wowDelta | Large center gauge/dial showing overall blended PI |
| `MiniKpiCard.vue` | label, value, target, delta | Compact KPI with target comparison and WoW change |
| `TopBottomSubcats.vue` | cheapest[], expensive[] | Side-by-side ranked lists: Top 5 / Bottom 5 |
| `PITrendLine.vue` | data[], parityLine | ECharts line chart: 30d PI trend with 1.0 reference |
| `CategoryPerformance.vue` | data[] | ECharts horizontal diverging bar centered on parity |
| `CoverageTrendLine.vue` | data[], target | ECharts line chart: coverage % with 90% target |
| `WoWDelta.vue` | value, direction | Compact ▲/▼ delta indicator with magnitude |

### 5.5 Shared / Utility Components (5)

| Component | Props | Description |
|---|---|---|
| `StarRating.vue` | tier | ★★★★★ / ★☆☆☆☆ visual tier indicator |
| `SymbolLabel.vue` | symbol, text, color | Generic symbol + text label (used for funnel stages, actions) |
| `ExportButton.vue` | onExport, format | CSV/Excel export trigger with loading state |
| `EmptyState.vue` | icon, message | Placeholder for filtered-to-zero or loading-error states |
| `ConfirmModal.vue` | title, message, onConfirm | Confirmation dialog for accept/reject actions |

**Total component count: 34 components**

---

## 6. Page Templates

Wireframe descriptions for each primary view, suitable for Figma Make implementation.

### 6.1 Commercial View Template

Full-width 1200px dashboard. Tiled container layout, no rounded corners, sharp brand dividers.

- **Row 1:** AppHeader (full width) — title left, NavTabs center, toolbar + logo right
- **Row 2:** FilterBar (full width) — filter icon + 6 dropdown chips, date selector right-aligned
- **Row 3:** KpiStrip (full width) — 5 KpiCards with icons, separated by 1px grey borders
- **Row 4 Left (38% width, full row height):** SubcategoryTreemap — 180 cells, sized by revenue, colored by PI
- **Row 4 Right Top (62% width, 50% row height):** BlendedPITable — scrollable sorted subcategory table
- **Row 4 Right Bottom (62% width, 50% row height):** ProductDetailTable — filterable product rows
- **Row 5:** CoverageFunnel (full width) — 5 stages horizontal with progressive brand shading

### 6.2 Master Data View Template

- **Row 1:** AppHeader (Master Data tab active)
- **Row 2:** FilterBar (Category, Subcat, Action Type, Tier, Staleness)
- **Row 3:** ActionSummary — 4 KpiCards in a row with action symbols and counts
- **Row 4:** ActionBreakdown (full width) — stacked horizontal bar chart, clickable segments
- **Row 5:** PriorityWorklist (full width) — large scrollable table, primary workhorse component
- **Row 6 Left (50%):** AIMatchPanel — scrollable cards with accept/reject inline
- **Row 6 Right (50%):** StalenessHeatmap — subcategory × days grid

### 6.3 Executive View Template

- **Row 1:** AppHeader (Executive tab active)
- **Row 2 Center:** PIGauge (large) — overall 1.07, interpretation text, WoW delta
- **Row 2 Right:** 3 MiniKpiCards — Coverage %, Products Used, Actions Remaining
- **Row 3:** PITrendLine (full width) — 30-day trend with 1.0 parity reference line
- **Row 4 Left (50%):** TopBottomSubcats — two ranked lists side by side
- **Row 4 Right (50%):** CategoryPerformance — diverging horizontal bar chart
- **Row 5:** CoverageTrendLine (full width) — 30-day coverage % with 90% target line

---

## 7. Technical Stack

### 7.1 Backend

| Technology | Version | Purpose |
|---|---|---|
| FastAPI | >=0.104 | Async REST API framework with auto-generated OpenAPI docs |
| Uvicorn | >=0.24 | ASGI server (production: Gunicorn + Uvicorn workers) |
| google-cloud-bigquery | >=3.13 | BigQuery client (same pattern as SubareaForecaster) |
| Pandas | >=2.1 | Data manipulation and metric computation |
| NumPy | >=1.25 | Numerical operations for PI calculations |
| Pydantic | >=2.5 | Request/response validation and serialization |
| Redis | >=5.0 | Distributed cache (TTL-based, 15min default) |
| Python | 3.11+ | Runtime (matches existing Breadfast analytics stack) |

### 7.2 Frontend

| Technology | Version | Purpose |
|---|---|---|
| Vue.js | 3.4+ | Reactive UI framework (Composition API) |
| Vite | 5.0+ | Build tool and dev server |
| Vue Router | 4.2+ | Client-side routing (3 main views + sub-routes) |
| Pinia | 2.1+ | State management (one store per view + shared filters) |
| Axios | 1.6+ | HTTP client for API calls |
| Apache ECharts | 5.4+ | Treemap, heatmap, line charts, bar charts, gauge |
| AG Grid Community | 31+ | Sortable/filterable data tables with virtual scrolling |
| TailwindCSS | 3.4+ | Utility-first CSS with Breadfast design tokens |
| VueUse | 10.7+ | Utility composables (debounce, localStorage, etc.) |

### 7.3 Infrastructure

| Layer | Service | Notes |
|---|---|---|
| Data Warehouse | Google BigQuery | Source: dbt_gohary.pricing_index_analysis (daily refresh) |
| Backend Hosting | Google Cloud Run | Auto-scaling, pay-per-request, connects to BQ via IAM |
| Frontend Hosting | Cloud Run (static) | Or Firebase Hosting / Cloud CDN for static assets |
| Cache | Cloud Memorystore (Redis) | Shared cache for multi-instance backend |
| Auth | Google OAuth2 | Breadfast workspace SSO, JWT tokens |
| CI/CD | Cloud Build | Auto-deploy on merge to main |
| Monitoring | Cloud Logging + Error Reporting | Structured logging, API latency tracking |

---

## 8. Performance Budgets

### 8.1 Frontend Targets

| Metric | Target | Measurement |
|---|---|---|
| First Contentful Paint (FCP) | < 1.5s | Lighthouse on 4G throttle |
| Largest Contentful Paint (LCP) | < 2.5s | Lighthouse on 4G throttle |
| Time to Interactive (TTI) | < 3.0s | Lighthouse on 4G throttle |
| Cumulative Layout Shift (CLS) | < 0.1 | Lighthouse |
| Total Bundle Size (gzipped) | < 250 KB | Initial JS + CSS |
| Treemap Render | < 1.0s | 180 subcategories, client-side |
| AG Grid Render (1000 rows) | < 500ms | Virtual scrolling enabled |

### 8.2 Backend Targets

| Metric | Target | Notes |
|---|---|---|
| API Response (cached) | < 200ms | Redis cache hit, no BQ call |
| API Response (cold) | < 2.0s | First call after cache expiry, BQ round-trip |
| BigQuery Query Time | < 5.0s | Most complex aggregation query |
| Concurrent Users | 50+ | Cloud Run auto-scaling, 4 instances min |
| Cache TTL | 15 min | Acceptable staleness for daily-refreshed data |
| CSV Export (10K rows) | < 3.0s | Streaming response, no timeout |

### 8.3 Optimization Strategies

- BigQuery materialized views for pre-aggregated subcategory metrics
- Redis caching with 15-minute TTL (data refreshes daily, so aggressive caching is safe)
- AG Grid virtual scrolling for tables with 1000+ rows (no DOM rendering of off-screen rows)
- ECharts lazy loading: treemap and heatmap data fetched only when tab is active
- Code splitting per view: /commercial, /master-data, /executive loaded as separate chunks
- Static assets on CDN with immutable cache headers (365-day max-age for hashed files)

---

## 9. SEO & URL Structure

Since this is an internal tool (authenticated access only), SEO is focused on internal discoverability, bookmarkability, and link-sharing within the organization.

### 9.1 URL Patterns

| Pattern | Example | Purpose |
|---|---|---|
| `/commercial` | `/commercial` | Default landing, bookmarkable |
| `/commercial/subcategory/:slug` | `/commercial/subcategory/dairy-eggs` | Shareable subcategory deep-link |
| `/commercial/product/:id` | `/commercial/product/12345` | Direct product reference for Slack sharing |
| `/master-data?action=:type` | `/master-data?action=needs-mapping` | Pre-filtered worklist for daily assignments |
| `/master-data/ai-matches` | `/master-data/ai-matches` | Dedicated AI review page |
| `/executive` | `/executive` | Leadership bookmark |
| `/executive/trends?range=90d` | `/executive/trends?range=90d` | Quarterly trend view for board reports |

### 9.2 Meta Templates

| Page | Title Template | Description |
|---|---|---|
| Commercial | PI Dashboard — Commercial \| Breadfast | Blended Price Index by subcategory and product |
| Subcategory | {Subcat} Price Index \| Breadfast | PI analysis for {subcategory_name} |
| Master Data | Action Queue \| Breadfast | Prioritized product mapping and update worklist |
| AI Matches | AI Match Review \| Breadfast | Review and approve AI-suggested product matches |
| Executive | Executive Summary \| Breadfast | High-level pricing position and coverage health |
| Trends | Trend Analysis \| Breadfast | PI and coverage trends over {range} |

### 9.3 Deep Linking & Sharing

- All filter states serialized to URL query parameters for bookmarkable, shareable views
- Subcategory slugs use kebab-case normalized names (dairy-eggs, frozen-foods)
- Product detail pages use numeric IDs for stability across name changes
- OpenGraph meta tags for link previews in Slack: title + description + Breadfast logo
- Browser history correctly updated on filter changes (pushState, not replaceState)
- 404 page with navigation back to /commercial for broken deep links

---

## Appendix: Design Tokens

Complete Breadfast brand design system for implementation in TailwindCSS config.

### Color Palette

| Token | Hex | Usage |
|---|---|---|
| brand-primary | `#AB0184` | Primary actions, active states, PI bars |
| brand-dark | `#7A015E` | Dark emphasis, hover states |
| brand-darkest | `#4A0038` | Maximum contrast, Needs Mapping badge |
| brand-light | `#D4A1C7` | Light fills, Needs Update badge, secondary bars |
| brand-lightest | `#F3E4EF` | Background tints, Complete badge, hover backgrounds |
| grey-900 | `#333333` | Primary text, headings |
| grey-700 | `#555555` | Body text, table content |
| grey-500 | `#999999` | Labels, captions, secondary text |
| grey-300 | `#CCCCCC` | Borders, dividers |
| grey-100 | `#F5F5F5` | Alternate row backgrounds, subtle fills |

### Typography

| Element | Font | Size | Weight | Color |
|---|---|---|---|---|
| Dashboard Title | Lato | 18px | 700 (Bold) | #333333 |
| Section Headers | Lato | 14px | 700 (Bold) | #333333 |
| Panel Headers | Lato | 12px | 700 (Bold) | #555555 + uppercase |
| Table Headers | Lato | 9px | 700 (Bold) | #999999 + uppercase |
| Body / Cells | Lato | 10px | 400 (Regular) | #555555 |
| Labels / Caption | Lato | 9px | 400 (Regular) | #999999 |
| Code / Formulas | Consolas | 9px | 400 (Regular) | #7A015E |
| KPI Values | Lato | 28px | 900 (Black) | #333333 or #AB0184 |

### Symbol Reference

| Context | Symbols Used |
|---|---|
| Direction (PI > 1) | ▲ + positive number (color: #4A0038) |
| Direction (PI < 1) | ▼ + negative number (color: #AB0184) |
| Direction (parity) | — neutral (color: #999999) |
| Action: Needs Mapping | ⊘ dark badge (#4A0038 bg, white text) |
| Action: Review AI Match | ⚡ brand badge (#AB0184 bg, white text) |
| Action: Needs Update | ⟳ light badge (#D4A1C7 bg, dark text) |
| Action: Complete | ✓ lightest badge (#F3E4EF bg, brand text) |
| Tier: Top+ | ★★★★★ |
| Tier: Top | ★★★★☆ |
| Tier: Medium | ★★★☆☆ |
| Tier: Low | ★★☆☆☆ |
| Tier: Very Low | ★☆☆☆☆ |
| Funnel Stages | 📦 All → ★ Eligible → 🔗 Mapped → ⏱ Updated → ✔ Used |

---

*End of Technical Specification*
