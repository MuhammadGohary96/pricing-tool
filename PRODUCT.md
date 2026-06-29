# Product

## Register

product

## Users

Breadfast's commercial decision-makers, primarily:

- **Commercial / category managers** — the primary users. They set and adjust Breadfast prices against competitors, working subcategory by subcategory and product by product, and act on the price-index (PI) gaps that move revenue. Their context is a daily/weekly working session: filter to a category, read the competitive position, edit prices inline, move on.
- **Executives / leadership** — monitor overall competitiveness, week-over-week movement, and mapping coverage at a glance (the Executive view). Their context is a quick scan for "are we winning or exposed, and where."

The job to be done: turn competitor price data into confident pricing decisions, fast, without leaving the tool to act.

## Product Purpose

A pricing-intelligence tool that tracks Breadfast's quantity-weighted Price Index against every tracked competitor, across categories, subcategories, and individual products, and lets commercial teams act on it (inline and bulk price edits synced to the Catalog API). Success looks like: a category manager can spot where Breadfast is overpriced versus a specific competitor, trust the number, and correct the price in the same screen.

## Brand Personality

Confident, precise, calm. The voice is expert and plain: it states the competitive position directly and never decorates a number it can't defend. It should feel like a senior analyst's working surface, not a marketing dashboard. Emotional goal: trust and control, not excitement.

## Anti-references

- **Generic AI SaaS template** — purple/blue gradients, three identical icon-cards, glassmorphism, system-font blandness, decoration standing in for hierarchy.
- **Legacy enterprise BI** (SAP / Oracle / old-Excel dashboards) — gray chrome, cramped grids, no visual hierarchy, every cell shouting at the same volume.

## Design Principles

1. **The tool disappears into the decision.** Clarity over decoration; the fastest path from "what's the gap" to "price changed" wins.
2. **Confident, not loud.** Restraint signals expertise. One accent (brand magenta), calm surfaces, color used to encode state (PI good/bad, action status), never for flourish.
3. **Every number is trustworthy and traceable.** Make data integrity visible: synced-vs-local edits, mapping coverage, price staleness, eligible/used counts. A figure the user can't trust is worse than no figure.
4. **Act where you analyze.** Drill-downs, inline edits, and bulk actions live next to the data, not behind a report. No dead-end views.
5. **Earned familiarity, consistent across views.** Same table, badge, filter, and pagination vocabulary on Executive and Commercial. Density is welcome when the user needs it; motion conveys state, not spectacle.

## Accessibility & Inclusion

WCAG AA throughout: body text and PI/status colors meet AA contrast against their surfaces, all interactive elements have visible focus, and color is never the sole carrier of meaning (status also uses labels/icons). Full `prefers-reduced-motion` support — staggered entrances, count-ups, and chart animation collapse to instant/crossfade.

Note: the product register's default is to avoid orchestrated page-load motion. This project intentionally overrides that with restrained, reduced-motion-safe entrance animation at the explicit request of the product owner ("modern, animated; tasteful motion"). Motion stays in the 150-250ms band and never gates content visibility.
