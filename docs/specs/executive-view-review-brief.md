# Brief: assess and redesign the Executive view

**For:** one senior Business Analyst and one senior UI/UX designer-developer, working together.
**Product:** Breadfast Pricing Intelligence Tool — an internal web app that compares Breadfast's
prices and assortment against seven Egyptian grocery competitors.
**Scope of this brief:** the Executive view only (`/executive`), in the context of the two views
it feeds into.

---

## 1. What you are assessing

The Executive view is the landing screen. Top to bottom it currently contains:

| # | Panel | What it shows |
|---|---|---|
| 1 | **Page header** | Blended PI as a 52px hero number, a one-line interpretation, plus Active products and Competitors tracked |
| 2 | **Definitions panel** | Collapsible glossary of every metric on the page |
| 3 | **Filter bar** | Vertical, category, subcategory, tier, brand, brand scope (3 states), private label, price fallback. Competitor is deliberately hidden here |
| 4 | **Competitor pills** | Multi-select. Normally cosmetic — dims what you are not looking at. Under a brand scope they also decide which competitors count, and say so on a badge |
| 5 | **Competitor scorecard** | One row per competitor, **16 columns** under a two-row grouped header: Price position (3), Match coverage (8), Assortment overlap (4). Clicking a row opens Commercial filtered to that competitor |
| 6 | **Classification donut** | Split of products by mapping state |
| 7 | **Category PI strip** | One clickable chip per commercial category (17–22 of them) with its blended PI |
| 8 | **Geographic exposure** | Blended PI by fulfillment point × competitor |
| 9 | **Mapping progress** | How much of the catalogue is mapped per competitor |

Sections 5–8 sit under a "Pricing position" heading, section 9 under "Data coverage".

---

## 2. The central question

**This page currently serves two audiences at once, and we want you to resolve that
explicitly rather than average across it.**

- A **leadership scan**: someone who opens it to learn "are we priced right, is anything on
  fire" and leaves inside a minute.
- A **working console**: category and pricing managers who live in it, filter it, and drill
  from it into the Commercial and Gap Analysis views.

The 16-column scorecard is the sharpest expression of the conflict: indispensable to the
second reader, plausibly hostile to the first. Decide whether the page should pick one
audience, tier harder within one page, or split into two surfaces — and justify it.

---

## 3. Constraints

**UI and information architecture only, using data the API already returns.** You may
reorganise, remove, merge, relabel, re-rank, change defaults and change interactions. You may
*not* assume new metrics, new columns or pipeline work. If you find yourself wanting data that
does not exist, list it separately as a wish, clearly marked, and design without it.

Everything you propose should be implementable in days, not weeks.

---

## 4. Domain facts you must internalise before recommending anything

These are non-obvious and have already cost real mistakes. Recommendations that contradict
them will be rejected.

1. **PI = Breadfast price ÷ competitor price. Above 1.00 means WE ARE MORE EXPENSIVE.**
   Internal decks use the inverted convention. Never re-derive a cheaper/more-expensive label
   from memory; read it off this rule.
2. **Two populations, never mixable.** Our products (one row per product, national grain) and
   competitor-only products (their catalogue, deduped). Counts from one side cannot be added
   to the other, and "one competitor product can map to several of our subcategories" means
   competitor-side counts must never be summed across rows.
3. **Eligible reads the same number on every scorecard row** (e.g. 4,743) and this is correct,
   not a rendering fault: the eligible set does not depend on which competitor you look at.
   Any redesign must keep that legible or stop showing it.
4. **Carrefour has no crawled catalogue.** Its competitor-side columns are zero and the row is
   flagged. That is a *collection* gap, not an assortment gap, and the design must keep those
   two readings apart.
5. **Some metrics are ceilings, not facts.** "Ours only" counts products we failed to match
   together with products they genuinely do not stock. "Brands only they carry" is an upper
   bound because their name variants are not collapsed. The UI currently carries these caveats
   in tooltips; assess whether that is honest enough or merely deniable.
6. **Brand overlap is partly inferred.** A brand counts as shared when the names match OR when
   at least half its products are matched at that competitor (our "Froneri" is their "Nestle",
   "Paradise", "Oreo"). The scorecard shows the evidence-based subset as a separate figure.
7. **Data drifts between refreshes.** Product counts move by tens or hundreds day to day. The
   page should not imply more precision than that supports.
8. **Vocabulary was just unified** across the three views: Mapped (not Matched), Confidence % (not
   Priced or Coverage %). Do not reintroduce synonyms.

---

## 5. What to produce

**Part A — Critique.** Panel by panel and page as a whole:

- What job does each panel do, and who for? Which panels earn their space and which do not?
- Where does the eye go first, and is that the right place?
- Is the tiering (Pricing position → Data coverage) the right spine, or an artefact?
- Where does the page make a reader do arithmetic, hold state in their head, or scroll to
  compare two things that belong together?
- Which numbers are likely to be *misread*, and how? Be specific — name the column and the
  wrong conclusion.
- What is missing that the existing data could already answer?

**Part B — Redesign.** A concrete proposed layout, panel by panel, with described or ASCII
wireframes. For every change state: what it fixes, what it costs, and what a reader loses.
Include what you would **remove** — a redesign that only adds is not a redesign.

Rank everything in Part B by impact against effort, and mark anything that changes what a
number *means* (as opposed to how it looks), because those need separate sign-off.

---

## 6. How your work will be judged

- **Specific over general.** "Reduce cognitive load" is worthless; "move Eligible and Used
  behind a disclosure because they exist to explain Confidence %, which is the number people act on"
  is useful.
- **Reasoned trade-offs.** Every removal costs someone something. Say who and what.
- **Honest about uncertainty.** Where you are guessing at user behaviour, say so and name the
  question that would settle it, rather than asserting it.
- **No invented data.** If a recommendation needs a number the API does not return, it belongs
  in the wish list, not the design.
- **Respect what is already correct.** A great deal of care has gone into making these numbers
  agree across three views. Do not propose changes that would quietly break that agreement.
