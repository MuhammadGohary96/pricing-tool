# Wireframe & Workflow Design Prompt

Use this prompt with Claude, ChatGPT, Figma AI, or any design tool.

---

## THE PROMPT

You are a senior product designer specializing in B2B SaaS dashboards, data-heavy analytics platforms, and pricing intelligence tools. I need you to create detailed wireframe designs and user workflow diagrams for a **Pricing Intelligence Web Application** used by a grocery delivery company (Breadfast, Egypt) to monitor and manage competitive pricing against their main competitor (Talabat).

---

### PRODUCT CONTEXT

**Company**: Breadfast — Egypt's leading grocery delivery app
**Problem**: The commercial team manually tracks ~9,000+ product prices against Talabat. They need to identify which products are overpriced, underpriced, unmapped to competitor products, or have stale pricing data.
**Users**: Three distinct personas with different needs:

1. **Commercial Analyst** (daily user, 70% of usage)
   - Goal: Find products where Breadfast is more expensive than Talabat, update prices
   - Needs: Filter by category/tier, see price index by subcategory, edit prices inline
   - Key metric: "Blended Price Index" (quantity-weighted ratio of competitor/our price — above 1.0 means we're cheaper)

2. **Master Data Specialist** (daily user, 20% of usage)
   - Goal: Map unmapped products to competitor equivalents, review AI-suggested matches, refresh stale prices
   - Needs: Prioritized worklist sorted by revenue impact, AI match review cards, staleness heatmap
   - Key metric: Coverage % (how many products have confirmed competitor matches)

3. **Executive / VP Commercial** (weekly user, 10% of usage)
   - Goal: 30-second overview of competitive position and team progress
   - Needs: Single PI gauge, coverage %, top/bottom performing categories
   - Key metric: Overall Blended PI and week-over-week trend

---

### CURRENT APPLICATION STRUCTURE

The app has 3 main views accessible via top navigation tabs:

#### VIEW 1: COMMERCIAL DASHBOARD
Components (top to bottom):
- **Filter Bar**: Dropdowns for Main Category, Subcategory, Global Tier (Top+ → Very Low), Action Type (Needs Mapping, Review AI Match, Needs Price Update, Complete)
- **KPI Strip**: 5 cards in a row — Total Products, Eligible Products (top 80% revenue), Used Products (eligible + matched + fresh), Average Blended PI (4 decimal places), Products Needing Action
- **Two-column layout**:
  - Left (38%): **Subcategory Treemap** — size = revenue, color = PI deviation from parity (green = cheaper, red = expensive). Clicking a cell filters the whole page.
  - Right (62%): **Blended PI Ranking Table** — subcategories sorted by PI, with inline PI bars, direction arrows (▲/▼), and counts (Total/Eligible/Used/Actions/Revenue)
- **Product Detail Table** (full width, paginated 50/page):
  - Columns: Product name + status badges (Eligible/Used/Action), Brand, BF Price, Now Price (editable), Now Sale Price (editable), Talabat Price, Sale PI, Tier badge (★★★★★), Action badge (⊘/⚡/⟳/✓), Competitor match name, Days since update
  - Inline editing: click price cell → input field → save syncs to backend API
- **Coverage Funnel** (full width): 5 progressive stages: All Products → Eligible → Mapped → Recently Updated → Used Products. Each stage shows count and percentage.
- **Export CSV button** in KPI strip area

#### VIEW 2: MASTER DATA DASHBOARD
Components:
- **Same Filter Bar** as Commercial
- **Action Summary**: 4 KPI cards — Total Needs Action, Needs Mapping (⊘), Review AI Match (⚡), Needs Price Update (⟳)
- **Action Breakdown Chart**: Stacked horizontal bar chart showing action type distribution by main category. Clicking a category filters the worklist.
- **Priority Worklist Table** (paginated 50/page): Product name + badges, Brand, Subcategory, Tier, Action type, Competitor match (if mapped), AI match candidate (if unmapped) + similarity %, BF Price, Talabat Price, Days since update (color-coded: green ≤7d, amber 8-30d, red >30d), Revenue
- **Two-column layout (50/50)**:
  - Left: **AI Match Review Panel** — scrollable cards showing: BF product ↔ Suggested Talabat product, similarity score bar, Accept/Reject buttons
  - Right: **Staleness Heatmap** — X: days buckets (0-7d, 7-14d, 14-21d, 21d+), Y: subcategories, color intensity = product count

#### VIEW 3: EXECUTIVE DASHBOARD
Components (no filter bar):
- **Large PI Gauge**: Big number "1.07" with interpretation "Breadfast is 7% cheaper overall"
- **3 Mini KPI Cards** (stacked vertically): Coverage %, Products Used, Actions Remaining
- **Top/Bottom 5 Subcategories**: Two columns — "Where we're cheapest" (highest PI) and "Where we're most expensive" (lowest PI)
- **Category Performance Chart**: Diverging horizontal bar — main categories on Y-axis, PI on X-axis centered at parity (1.0)

---

### DESIGN SYSTEM

**Brand Colors**:
- Primary: `#7C3AED` (purple)
- Darkest: `#4C1D95`
- Light: `#C4B5FD`
- Lightest: `#EDE9FE`
- Background: `#F9FAFB` (light grey)
- Cards: `#FFFFFF` with subtle shadow

**Typography**: Inter font family
- Heading: 18px bold
- Subheading: 14px bold
- Body: 13px regular
- Caption: 12px
- Micro: 11px

**Component Style**:
- Cards: White background, 8px border-radius, subtle shadow
- Tables: Compact rows, sticky headers, hover highlight (brand-50)
- Badges: Rounded-full, small text, color-coded backgrounds
- Buttons: Rounded-lg, brand-primary background

---

### WHAT I NEED YOU TO DESIGN

#### 1. HIGH-FIDELITY WIREFRAMES (for each of the 3 views)
For each view, create:
- Desktop layout (1440px wide) showing exact component placement
- Component spacing, sizing, and proportions
- Real data examples in tables and charts (use Egyptian grocery products: Juhayna Milk, Persil Detergent, Pampers Diapers, etc.)
- Show interaction states: hover, active filter, selected row, editing mode
- Show empty states and loading skeletons
- Mobile-responsive adaptation (if applicable)

#### 2. USER WORKFLOW DIAGRAMS
Create flow diagrams for these key workflows:

**Workflow A: "Find and fix overpriced products"** (Commercial Analyst)
```
Login → See KPIs → Notice low PI in treemap → Click subcategory →
Table filters → Sort by Sale PI ascending → Find product where PI < 1 →
Click price cell → Enter new price → Save → See "Synced" confirmation →
Export updated list as CSV
```

**Workflow B: "Review AI-suggested matches"** (Master Data Specialist)
```
Login → Navigate to Master Data → See "87 Review AI Match" →
Filter by action = "Review AI Match" → Scroll AI Match Panel →
See BF product ↔ Talabat suggestion with 92% score →
Click Accept → Product moves to "Complete" status →
Check staleness heatmap for next priority area
```

**Workflow C: "Weekly competitive check"** (Executive)
```
Login → See PI Gauge (1.07 = 7% cheaper) →
Check coverage (47.5%) → See "Baby Care" is most expensive →
Navigate to Commercial → Filter main_category = "Baby Care" →
See specific products → Forward to team with action items
```

**Workflow D: "First-time login & data loading"**
```
Open app → See login screen → Sign in with Google (@breadfast.com) →
See startup progress (loading BigQuery data) →
See enrichment progress (fetching live catalog prices) →
Dashboard ready → All data loaded
```

#### 3. INTERACTION PATTERNS
Design micro-interactions for:
- **Treemap click → filter cascade**: How the page transitions when a subcategory is selected
- **Inline price editing**: Click cell → expand to input → validation → save animation → success/error feedback
- **Filter application**: How applying a filter visually updates all components simultaneously
- **Table sorting**: Header click → arrow indicator → smooth re-sort animation
- **Pagination**: Page navigation with loading state
- **Toast notifications**: Slide-in from bottom-right, auto-dismiss

#### 4. COMPONENT LIBRARY SHEET
Create a reference sheet showing all reusable UI components:
- KPI Card (3 variants: default, PI format, percentage)
- Tier Badge (5 levels: Top+ through Very Low, with star ratings)
- Action Badge (4 types: Needs Mapping, Review AI Match, Needs Price Update, Complete)
- Direction Arrow (up/down/neutral with deviation value)
- PI Inline Bar (horizontal bar 0.70–1.30 scale with gradient)
- Filter Dropdown (with selected state, clear button)
- Table Row (normal, hover, selected, editing states)
- Toast Notification (success, error, info variants)
- Funnel Stage (with progressive width and count/percentage)
- Empty State (icon + message + optional retry button)
- Loading Skeleton (for cards, tables, charts)

#### 5. INFORMATION ARCHITECTURE
Create a sitemap/IA diagram showing:
- Navigation structure (3 tabs + login/logout)
- Data hierarchy: Main Category → Subcategory → Product
- Filter relationships: How selecting one filter constrains others
- Cross-view navigation: How clicking items in one view can navigate to another

---

### BEST PRACTICES TO INCORPORATE

Research and apply best practices from these reference products:
- **Prisync** (competitor pricing intelligence)
- **Competera** (retail pricing platform)
- **Intelligence Node** (retail analytics)
- **Tableau/Looker** dashboard patterns
- **Linear/Notion** for clean B2B SaaS aesthetics
- **Stripe Dashboard** for data-dense yet clean layouts

Specifically incorporate:
1. **Progressive disclosure**: Show summary first, drill down on demand
2. **Contextual actions**: Actions appear where data is, not in separate pages
3. **Visual encoding**: Use color, size, position consistently to encode data meaning
4. **Glanceable KPIs**: Executive should understand status in <5 seconds
5. **Keyboard shortcuts**: Power users should be able to navigate without mouse
6. **Batch operations**: Allow selecting multiple products for bulk price updates
7. **Undo/redo**: For price edits, allow reverting within session
8. **Comparison mode**: Side-by-side BF vs Talabat product comparison
9. **Alerts/notifications**: Highlight products with >10% price discrepancy
10. **Collaborative features**: Show who last edited a price and when

---

### OUTPUT FORMAT

For wireframes: Provide ASCII wireframes, or describe layouts in precise detail with exact positioning, sizing, and spacing that can be directly implemented. Include annotations explaining design decisions.

For workflows: Use flowchart notation with decision points, user actions, system responses, and error paths.

For the component library: Show each component in all its states (default, hover, active, disabled, loading, error) with exact color codes, typography, and spacing specifications.

---

### ADDITIONAL CONTEXT

- The app runs in a web browser, optimized for 1440px+ desktop screens
- Primary users work 8+ hours/day on this tool — optimize for efficiency and reduced eye strain
- Data refreshes daily from BigQuery; live prices from Catalog API on login
- Average dataset: 9,000 products, 180 subcategories, 7 main categories
- Target: Commercial team should be able to identify and fix a pricing issue in under 60 seconds
