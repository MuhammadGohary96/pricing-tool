# Breadfast Pricing Intelligence Tool
## Presentation Deck — 16 Slides

---

## Slide 1: Title

### Breadfast Pricing Intelligence Tool
**Turning Competitive Data into Pricing Decisions**

*Built by the Pricing & Data Engineering Team*
*Q2 2026*

> **Speaker Notes:**
> Welcome everyone. Today I'm presenting the Pricing Intelligence Tool — a platform we've built to give Breadfast a real-time, data-driven edge in competitive pricing. This tool replaces our previous spreadsheet-based approach with a unified system serving three teams: Commercial, Master Data, and Executive Leadership.

---

## Slide 2: The Problem

### Why We Built This

| Pain Point | Impact |
|---|---|
| **Scattered spreadsheets** | No single source of truth for competitor prices |
| **Manual tracking** | Hours spent collecting and comparing prices weekly |
| **No coverage visibility** | Unknown how much of our catalog is actually tracked |
| **Slow reaction time** | Days to identify and respond to competitor price changes |
| **No data quality metrics** | Stale prices and unmapped products went unnoticed |

**The core question we couldn't answer:**
> *"Are we competitively priced across our catalog — and where do we need to act?"*

> **Speaker Notes:**
> Before this tool, our commercial team relied on manually maintained Excel files to track competitor prices. There was no centralized view, no way to measure coverage gaps, and no prioritization of what to fix first. A commercial manager might spend half a day just figuring out where we stood against Talabat in a single category. We needed something that could answer that question instantly — and tell us exactly where to focus.

---

## Slide 3: The Solution

### One Platform, Three Dashboards

```
┌─────────────────────────────────────────────────────┐
│           Pricing Intelligence Platform              │
├──────────────┬──────────────┬────────────────────────┤
│  Executive   │  Commercial  │     Master Data        │
│  Dashboard   │  Dashboard   │     Dashboard          │
│              │              │                        │
│  Leadership  │  Pricing     │  Data Quality          │
│  Situational │  Analysis &  │  & Mapping             │
│  Awareness   │  Action      │  Workflow              │
│              │              │                        │
│  "How are    │  "Where do   │  "What do I            │
│   we doing?" │   we act?"   │   work on today?"      │
└──────────────┴──────────────┴────────────────────────┘
```

**Each dashboard is tailored to its audience's daily workflow and decision-making needs.**

> **Speaker Notes:**
> The solution is a single web platform with three purpose-built dashboards. The Executive Dashboard gives leadership a bird's-eye view of our competitive position. The Commercial Dashboard is the daily workbench where pricing managers analyze gaps and take action. And the Master Data Dashboard provides a prioritized queue of data quality tasks — mapping products, reviewing AI matches, and refreshing stale prices. All three share the same data pipeline and filter system, so everyone is looking at the same truth.

---

## Slide 4: Key Metric — Price Index (PI)

### The Language of Competitive Pricing

**Formula:**
```
Price Index (PI) = Competitor Price / Breadfast Price
```

| PI Value | Meaning | Color Code |
|----------|---------|------------|
| **PI > 1.0** | BF is **cheaper** than competitor | 🟢 Green |
| **PI = 1.0** | **Parity** — same price | 🟡 Yellow |
| **PI < 1.0** | BF is **more expensive** | 🔴 Red |

**Blended PI** = Quantity-weighted average across products
- Heavier-selling products influence the index more
- Calculated only from "Used" products (reliable, fresh data)

**Example:**
> If Talabat sells milk for EGP 55 and BF sells it for EGP 50 → PI = 55/50 = **1.10**
> BF is 10% cheaper on this product ✓

> **Speaker Notes:**
> The Price Index is the core metric powering everything in this tool. It's a simple ratio — competitor price divided by our price. Above 1 means we're cheaper, below 1 means we're more expensive. The beauty of the Blended PI is that it's quantity-weighted, so a product we sell 1,000 units of daily matters far more than one we sell 10 units of. And critically, we only calculate it from "Used" products — those with confirmed mappings and fresh prices — so the number is trustworthy.

---

## Slide 5: Coverage Funnel

### From Catalog to Calculation

```
  ALL PRODUCTS IN CATALOG
  ████████████████████████████████████  (100%)
           │
           ▼ Top 80% of subcategory revenue
  ELIGIBLE PRODUCTS
  ██████████████████████████████  (≈80%)
           │
           ▼ Matched to a competitor product
  MAPPED PRODUCTS
  █████████████████████  (varies)
           │
           ▼ Both BF + competitor prices updated within 7 days
  RECENTLY UPDATED
  ████████████████  (varies)
           │
           ▼ Eligible + Mapped + Updated
  USED PRODUCTS ← Feed Blended PI
  ████████████  (target: maximize)
```

**Why this matters:** PI is only as good as the data behind it. The funnel ensures we measure competitiveness using only reliable, business-critical products.

> **Speaker Notes:**
> This funnel is how we go from our full catalog down to the products that actually feed the PI calculation. We start with all products, narrow to the top 80% by revenue within each subcategory — these are "eligible" because they're worth tracking competitively. Then we filter to those mapped to a competitor equivalent, then to those with recent prices on both sides, and finally to "used" products. The key goal for the Master Data team is to push as many products as possible through this funnel. More used products means a more accurate, representative PI.

---

## Slide 6: Executive Dashboard

### Leadership Situational Awareness

```
┌─────────────────────────────────────────────────────────┐
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Blended PI   │  │ Active       │  │ Competitors  │  │
│  │   1.0234     │  │ Products     │  │ Tracked      │  │
│  │ ▲ 0.3% WoW  │  │   2,847      │  │     4        │  │
│  │ ~sparkline~  │  │ 1,923 elig.  │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ Competitor PI Table  │  │ Classification Breakdown │  │
│  │ Talabat    1.02 ▲   │  │ ● Mapped Not PL    45%  │  │
│  │ Carrefour  0.98 ▼   │  │ ● Mapped PL        12%  │  │
│  │ Kazyon     1.05 ▲   │  │ ● Potential Match   18%  │  │
│  │ ...                  │  │ ● No Match         25%  │  │
│  └─────────────────────┘  └──────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Mapping Progress by Competitor (stacked bars)     │   │
│  │ Talabat:   ████████████░░░░  78%                  │   │
│  │ Carrefour: ██████░░░░░░░░░░  42%                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  Category PI:  [Dairy 1.03] [Snacks 0.97] [Beverages…] │
└─────────────────────────────────────────────────────────┘
```

**Key features:** WoW trend badges · Per-competitor PI with deviation · Mapping progress · Category-level PI chips with click-to-explore

> **Speaker Notes:**
> The Executive Dashboard is designed for a 30-second scan. At the top, three KPI cards tell you our overall competitive position, catalog size, and competitor coverage. The Blended PI card includes a sparkline and week-over-week change. Below that, the Competitor PI table breaks down our position against each competitor, while the Classification Breakdown shows how healthy our product mapping is. The Mapping Progress chart tracks each competitor's coverage over time. And the Category PI chips at the bottom let leadership quickly spot which categories are competitive risks — click any chip to drill into the Commercial view.

---

## Slide 7: Commercial Dashboard — Overview

### The Daily Workbench for Pricing Managers

```
┌─────────────────────────────────────────────────────────┐
│  KPI Bar                                                │
│  [Total: 2,847] [Eligible: 1,923] [Used: 1,156]        │
│  [Avg PI: 1.02]  [Needs Action: 412]                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Subcategory Treemap                                    │
│  ┌────────────┬──────┬────────────────┐                 │
│  │ Dairy &    │Fresh │   Snacks &     │                 │
│  │ Eggs       │Juice │   Chips        │                 │
│  │  (green)   │(yel) │   (red)        │                 │
│  ├────────────┤      ├────────────────┤                 │
│  │ Beverages  │      │  Home Care     │                 │
│  │  (green)   │      │   (yellow)     │                 │
│  └────────────┴──────┴────────────────┘                 │
│  Size = Revenue · Color = PI Deviation                  │
│                                                         │
│  Blended PI Table (per subcategory × competitor)        │
│  Coverage & Mapping Funnels                             │
└─────────────────────────────────────────────────────────┘
```

> **Speaker Notes:**
> The Commercial Dashboard is where pricing managers spend most of their time. Five KPIs at the top give immediate context. The treemap is the visual centerpiece — each block is a subcategory, sized by its revenue contribution, and colored by PI deviation. Green means we're cheaper than the market, red means we're more expensive. Clicking any block filters the entire page to that subcategory. Below that, the Blended PI table shows subcategory-level PI broken down by each competitor, and the coverage funnels visualize our mapping and eligibility pipeline.

---

## Slide 8: Commercial Dashboard — Product Pivot Table

### The Power Tool

```
┌─────────────────────────────┬──────────────────────────────────────┐
│  FROZEN COLUMNS             │  SCROLLABLE COMPETITOR COLUMNS →     │
│  (always visible)           │  (alternating column tints)          │
├─────────┬──────┬─────┬──────┼────────────┬────────────┬────────────┤
│ Product │Brand │Tier │BF    │ Talabat    │ Carrefour  │ Kazyon     │
│ Name    │      │     │Price │ Price │ PI │ Price │ PI │ Price │ PI │
├─────────┼──────┼─────┼──────┼───────┼────┼───────┼────┼───────┼────┤
│ Milk 1L │Juha  │Top+ │50.00 │ 55.00 │1.10│ 48.00│0.96│  —   │ ⊘  │
│         │      │     │      │  ✓    │ 🟢 │  ✓   │ 🔴 │      │    │
├─────────┼──────┼─────┼──────┼───────┼────┼───────┼────┼───────┼────┤
│ Sugar2kg│Local │Top  │45.00 │ 44.00 │0.98│  —   │ ⚡ │ 46.50│1.03│
│         │      │     │      │  ✓    │ 🟡 │      │    │  ✓   │ 🟢 │
└─────────┴──────┴─────┴──────┴───────┴────┴───────┴────┴───────┴────┘

Action Badges: ✓ Used  ⊘ Needs Mapping  ⚡ Review Match  ⟳ Outdated
```

**Features:**
- **Frozen columns** — Product info stays visible while scrolling competitors
- **Inline price editing** — Click BF price to update; >10% change triggers safety confirmation
- **Compact "PI Only" mode** — Hides price columns, shows only PI values
- **Worst PI indicator** — Shows which competitor we're least competitive against (from used data only)
- **Search, sort, paginate** — Find any product instantly
- **CSV export** — Download filtered data for offline analysis

> **Speaker Notes:**
> This is the most feature-rich component in the tool. Each row is a product, and each competitor gets two columns — price and PI. The left columns are frozen so product info stays visible as you scroll horizontally through competitors. Action badges tell you the status of each product-competitor pair: green check for "Used" meaning reliable data, a circle-slash for unmapped, lightning bolt for AI matches needing review, and a refresh icon for stale prices. The Worst PI column shows which competitor we're least competitive against — and it only uses "Used" data so you can trust it. Commercial managers can edit BF prices inline, with a safety rail that asks for confirmation if the change exceeds 10%. There's also a compact "PI Only" mode that hides price columns when you just want to scan competitiveness.

---

## Slide 9: Master Data Dashboard

### The Daily Action Queue

```
┌─────────────────────────────────────────────────────────┐
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────┐ │
│  │ Total      │ │ Needs      │ │ Review     │ │Needs │ │
│  │ Needs      │ │ Mapping    │ │ AI Match   │ │Price │ │
│  │ Action     │ │            │ │            │ │Update│ │
│  │   412      │ │   187      │ │    89      │ │ 136  │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────┘ │
│                                                         │
│  Action Breakdown by Category (stacked bars)            │
│  Food & Bev:  ████ Mapping ███ Review ██ Update         │
│  Home Care:   ███ Mapping ██ Review █ Update            │
│  Personal:    ██ Mapping █ Review ██ Update             │
│                                                         │
│  Priority Worklist (sorted: Tier desc → Revenue desc)   │
│  ┌─────────────────────────────────────────────────┐    │
│  │ #1 Premium Milk 1L │ Top+ │ Needs Mapping │ →   │    │
│  │ #2 Olive Oil 500ml │ Top+ │ Review Match  │ →   │    │
│  │ #3 Detergent 2L    │ Top  │ Price Update  │ →   │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  Staleness Heatmap (subcategory × days since update)    │
│  ┌──────────┬─────┬──────┬───────┬───────┬──────┐      │
│  │          │ 0-7d│ 7-14d│ 14-21d│ 21-30d│ 30d+ │      │
│  │ Dairy    │ ░░  │  ░   │       │       │  ██  │      │
│  │ Snacks   │ ░░░ │  ░░  │  ░    │       │  █   │      │
│  └──────────┴─────┴──────┴───────┴───────┴──────┘      │
└─────────────────────────────────────────────────────────┘
```

> **Speaker Notes:**
> The Master Data Dashboard answers one question: "What should I work on today?" Four KPI cards summarize the backlog by action type. The Action Breakdown chart shows which categories carry the most outstanding tasks. The Priority Worklist is the core workflow tool — it's sorted by business impact, with Top+ tier and highest-revenue products at the top, so the team always works on what matters most. The AI Match Review panel shows ML-suggested competitor matches that need human confirmation. And the Staleness Heatmap highlights where prices are going dangerously out of date — dark cells in the 30d+ column mean urgent action needed.

---

## Slide 10: Multi-Competitor Support

### Beyond Single-Competitor Tracking

```
  Traditional Approach          Our Approach
  ──────────────────           ──────────────
  One spreadsheet              One platform
  per competitor               ALL competitors

  BF vs Talabat.xlsx           ┌─────────────────┐
  BF vs Carrefour.xlsx    →    │ Product Pivot    │
  BF vs Kazyon.xlsx            │ Table: all       │
  BF vs Spinneys.xlsx          │ competitors in   │
                               │ one view         │
                               └─────────────────┘
```

**How it works:**
- BigQuery query produces **one row per product × competitor**
- UI supports **toggling competitor visibility** (default: top 5, expandable)
- **Compare PI across all competitors** in a single pivot table row
- Filter by competitor to focus analysis
- Blended PI computed **per competitor** and **overall**

> **Speaker Notes:**
> A major architectural decision was to support multiple competitors from day one. The BigQuery query cross-joins our product catalog with a competitor registry, producing one row per product-competitor combination. This means when a commercial manager looks at a product, they see Talabat's price, Carrefour's price, Kazyon's price — all side by side. The competitor toggle defaults to showing the top 5 by coverage, with an option to expand to all. This is a fundamental shift from the old approach of maintaining separate spreadsheets per competitor.

---

## Slide 11: Smart Filtering System

### Filter Once, Explore Everywhere

```
┌─────────────────────────────────────────────────────────┐
│ 🔍 Filters                                             │
│                                                         │
│ [Categories ▼] [Subcategories ▼] [Tiers ▼] [Actions ▼] │
│ [Brands ▼]     [Competitor ▼]    ☑ Include Private Label│
│                                                         │
│ [📑 Views ▼]   [🔗 Copy Link]   [✕ Clear All]          │
│                                                         │
│ Filtered: [Dairy ×] [Top+ ×] [Talabat ×]               │
└─────────────────────────────────────────────────────────┘
```

**Capabilities:**
- **6 multi-select filters** with search — Category, Subcategory, Tier, Action, Brand, Competitor
- **Private Label toggle** — include/exclude Breadfast own-brand products
- **Saved Views** — 3 built-in presets + unlimited custom named views (persisted in browser)
- **URL sharing** — copy current filter state as a shareable link
- **Filter chips** — visual summary with one-click removal
- **Keyboard accessible** — Arrow keys, Enter, Escape (WCAG compliant)
- **Global state** — filters apply across all views simultaneously

> **Speaker Notes:**
> The filter system is shared across all three dashboards. When a commercial manager selects "Dairy" and "Top+ Tier," every component on every page respects that filter. Each dropdown supports search, select-all, and keyboard navigation. Saved Views let users bookmark their most common filter combinations — we ship three presets: "All Categories," "Top Tier Only," and "Needs Action." Users can also save custom views. The Copy Link button lets you share a filtered state with a colleague via URL. And filter chips at the bottom give a visual summary with one-click removal.

---

## Slide 12: Data Architecture

### From BigQuery to Browser

```
┌──────────────┐    Daily dbt     ┌──────────────────┐
│   BigQuery   │ ──────────────→  │ pricing_index_   │
│   Raw Data   │    pipeline      │ analysis table   │
└──────────────┘                  └────────┬─────────┘
                                           │
                              App startup  │  SQL query
                              (once)       │  (~10s)
                                           ▼
                                  ┌────────────────┐
                                  │   FastAPI       │
                                  │   In-Memory     │◄──── POST /reload
                                  │   DataFrame     │      (manual refresh)
                                  │   (Pandas)      │
                                  └───────┬────────┘
                                          │
                           ┌──────────────┼──────────────┐
                           ▼              ▼              ▼
                     /executive     /commercial    /master-data
                     (REST JSON)   (REST JSON)    (REST JSON)
                           │              │              │
                           └──────────────┼──────────────┘
                                          ▼
                                  ┌────────────────┐
                                  │   Vue 3 +      │
                                  │   Pinia Stores  │
                                  │   + ECharts     │
                                  └────────────────┘
                                          │
                              ┌───────────┼───────────┐
                              ▼           ▼           ▼
                         Executive   Commercial   Master Data
                         Dashboard   Dashboard    Dashboard
```

**Key design decisions:**
- **In-memory data** — No per-request BigQuery queries → sub-second API responses
- **Catalog API enrichment** — Live BF prices fetched from `catalog.breadfast.com`
- **Google OAuth** — JWT-based authentication for all endpoints
- **Session-cached filters** — Filter options cached 15 min to reduce API calls

> **Speaker Notes:**
> The architecture prioritizes speed. Instead of querying BigQuery on every request, we load the full dataset into memory at startup — about 10 seconds for the initial load. After that, every API call is just Pandas filtering and aggregation on an in-memory DataFrame, so responses are near-instant. The data is refreshed daily via the dbt pipeline, and there's a manual reload endpoint for ad-hoc refreshes. On the frontend, Pinia stores manage state reactively, ECharts powers our visualizations, and TanStack handles the complex pivot table. The Catalog API integration means we can pull live Breadfast prices when a user edits a price inline.

---

## Slide 13: UX & Design Philosophy

### Built for Speed and Clarity

| Feature | Why It Matters |
|---------|---------------|
| **Skeleton loading** | Perceived performance — users see structure instantly, data fills in |
| **Responsive layout** | Works on desktop and tablet; filter bar collapses on mobile |
| **Color-coded PI** | Instant visual scanning — green = good, red = needs attention |
| **Alternating column tints** | Easy to track competitor columns in wide pivot table |
| **Animated transitions** | Smooth state changes reduce cognitive load |
| **Definitions panel** | Collapsible glossary on every page — no guessing what metrics mean |
| **Sticky headers & columns** | Product info stays visible while scrolling large tables |
| **Action badges** | At-a-glance status: ✓ Used · ⊘ Needs Mapping · ⚡ Review · ⟳ Stale |

**Design language:** Clean, modern SaaS aesthetic with Breadfast brand magenta (#a3007c) as the primary accent.

> **Speaker Notes:**
> We invested heavily in UX because the tool is only valuable if people actually use it. Skeleton loaders show the page structure immediately while data loads in the background. Color coding is consistent everywhere — green PI means competitive, red means expensive. In the pivot table, alternating column tints help users track which competitor they're looking at across wide tables. Every page has a collapsible definitions panel that explains each metric in plain language. And the action badges — Used, Needs Mapping, Review Match, Outdated — give instant status at a glance without needing to read numbers.

---

## Slide 14: Business Impact

### Measurable Outcomes

```
  BEFORE                              AFTER
  ──────                              ─────

  Hours to identify                   Seconds to identify
  pricing gaps                        pricing gaps
  ████████████████                    ██

  Manual spreadsheet                  Automated, real-time
  per competitor                      all competitors in one view
  ████████████████                    ████

  No prioritization                   Tier × Revenue weighted
  of data tasks                       daily worklist
  ████████████████                    ████

  Unknown coverage                    Coverage funnel with
  gaps                                measurable targets
  ████████████████                    ████
```

**Key outcomes:**
- **Commercial:** Identify and act on pricing gaps in **minutes vs. hours**
- **Master Data:** Prioritized daily worklist → **work on what matters most first**
- **Leadership:** Real-time visibility → **faster strategic decisions**
- **Coverage:** Measurable improvement tracked via mapping progress charts
- **Efficiency:** Eliminated redundant manual competitor price collection

> **Speaker Notes:**
> The impact is tangible across all three teams. Commercial managers used to spend hours building ad-hoc comparisons in Excel — now they open the Commercial Dashboard and see everything instantly. The Master Data team no longer has to guess what to work on — the priority worklist sorts tasks by business impact automatically. Leadership gets a real-time pulse on competitive position instead of waiting for weekly reports. And the coverage funnel gives everyone a shared metric to improve: how many products can we push from "unmapped" to "used" in the PI calculation?

---

## Slide 15: Roadmap & Next Steps

### Where We're Going

| Phase | Feature | Status |
|-------|---------|--------|
| **Now** | Multi-competitor pivot table | ✅ Live |
| **Now** | Inline price editing + safety rails | ✅ Live |
| **Now** | Saved views & URL sharing | ✅ Live |
| **Next** | Historical PI trend analysis (30-day) | 🔧 Infrastructure ready |
| **Next** | Week-over-week automated alerts | 📋 Planned |
| **Next** | AI match auto-approval workflow | 📋 Planned |
| **Future** | Additional competitor onboarding | 📋 Planned |
| **Future** | Mobile-optimized views | 📋 Planned |
| **Future** | Price recommendation engine | 💡 Concept |

**Infrastructure already supports:**
- PI trend line charts (data pipeline needs historical snapshots)
- WoW delta badges (calculation logic implemented, awaiting historical data)
- Match review accept/reject actions (UI built, backend endpoint ready)

> **Speaker Notes:**
> We've built the foundation with room to grow. The immediate wins are live: multi-competitor support, inline editing with safety rails, saved views. The next phase focuses on time-series intelligence — historical PI trends and automated WoW alerts. The infrastructure is ready; we need the dbt pipeline to start capturing daily snapshots. The AI match workflow has its UI built and is awaiting backend integration for accept/reject actions. Longer term, we're exploring a price recommendation engine that could suggest optimal prices based on competitive position, margin targets, and demand elasticity.

---

## Slide 16: Thank You & Q&A

### Thank You

**Pricing Intelligence Tool**
*Turning Competitive Data into Pricing Decisions*

---

**Tech Stack Summary:**
Frontend: Vue 3 · Pinia · TailwindCSS · ECharts · TanStack
Backend: Python · FastAPI · Pandas · BigQuery
Auth: Google OAuth · JWT
Infra: GCP · dbt

---

*Questions?*

> **Speaker Notes:**
> Thank you for your time. I'm happy to give a live demo or answer any questions about the tool, the architecture, or the roadmap. If you'd like access, reach out and we'll get you set up with Google OAuth.

---

## Appendix: Slide Design Notes

### For the designer / person building slides:

**Brand Colors:**
- Primary: `#a3007c` (Breadfast magenta)
- Primary Light: `#f3e8f0`
- Green (competitive): `#059669`
- Red (expensive): `#DC2626`
- Yellow (parity): `#D97706`
- Grey text: `#6B7280`
- Dark text: `#111827`

**Font Recommendations:**
- Headings: Inter Bold or SF Pro Display
- Body: Inter Regular
- Code/Numbers: JetBrains Mono or SF Mono

**Icon Style:** Lucide (line icons, consistent stroke weight)

**Slide Backgrounds:** White with subtle grey (#F9FAFB) accent sections

**Charts to Mock Up:**
- Slide 5: Funnel diagram with progressive narrowing
- Slide 6: KPI cards + data table + stacked bar chart
- Slide 7: Treemap with color gradient (green → yellow → red)
- Slide 8: Table with frozen columns visual
- Slide 9: Heatmap grid + priority list
- Slide 12: Architecture flow diagram with arrows

**Suggested Tool:** Figma, Pitch, or Google Slides with a clean SaaS template
