<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2 min-w-0">
        <LayoutList class="w-4 h-4 text-brand-primary shrink-0" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">By competitor</span>
        <span class="text-caption text-grey-400">price position &amp; assortment coverage</span>
      </div>

      <div class="flex items-center gap-4 flex-wrap">
        <!-- Summaries OF this table, so they live with it rather than competing
             with the blended-PI hero above. Pooled over product x competitor
             pairs, the grain MappingProgressChart already pools on. -->
        <div v-if="addressablePct != null" class="flex items-baseline gap-1.5">
          <span class="text-caption text-grey-500">Addressable</span>
          <span class="font-mono text-body font-bold text-grey-900 tabular-nums">{{ addressablePct }}%</span>
          <HelpTooltip text="Matched over what CAN be matched, pooled across every competitor. Products the matcher positively rejected leave the denominator." />
        </div>
        <div v-if="freshPct != null" class="flex items-baseline gap-1.5">
          <span class="text-caption text-grey-500">Benchmark freshness</span>
          <span class="font-mono text-body font-bold tabular-nums"
                :class="freshPct < 80 ? 'text-amber-600' : 'text-grey-900'">{{ freshPct }}%</span>
          <HelpTooltip text="Share of our matches whose competitor product was seen in the last 7 days. A match that has gone quiet is a benchmark quietly going stale." />
        </div>
        <ExportButton :fetcher="exportData" filename="competitor_scorecard.csv" />
      </div>
    </div>

    <p v-if="!isSupermarket" class="px-4 py-2 text-caption text-grey-500 bg-grey-50/70 border-b border-grey-100">
      <Info class="w-3.5 h-3.5 inline -mt-0.5 text-grey-400" />
      Showing all verticals. Set <strong>Vertical → Supermarket</strong> above to match the
      <em>excl. beauty</em> brand-portfolio workbook.
    </p>

    <div v-if="rows.length" class="overflow-x-auto">
      <table class="w-full">
        <thead>
          <!-- Grouped header: three questions, read left to right. -->
          <tr class="bg-grey-50 border-b border-grey-100">
            <th :class="TH_L" rowspan="2" class="sticky left-0 bg-grey-50 z-10 align-bottom">Competitor</th>
            <th :class="GROUP" colspan="3">Price position</th>
            <th :class="[GROUP, 'border-l border-grey-200']" colspan="6">Match coverage</th>
            <th :class="[GROUP, 'border-l border-grey-200']" colspan="4">Assortment overlap</th>
          </tr>
          <tr class="bg-grey-50 border-b border-grey-100">
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Blended PI
                <HelpTooltip text="Quantity-weighted Breadfast price divided by competitor price. Above 1.00 means BREADFAST IS MORE EXPENSIVE. Both tails matter." />
              </span>
            </th>
            <th :class="TH_R">vs Parity</th>
            <!-- Named "Priced" until it turned out to be the same number Commercial
                 already showed as "Util %" — identical to the decimal for all seven
                 competitors. One metric, one name, across both views. -->
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Util %
                <HelpTooltip text="Used ÷ Eligible. The share of our eligible range (top 80% of revenue) that has a usable fresh price against this competitor. The denominator is the eligible set as a whole and is the same for every competitor, because BigQuery emits every product×competitor pair — so read it as how much of our priced-worthy range is benchmarked here, not as a per-competitor utilisation rate. Same figure as Util % in Commercial." />
              </span>
            </th>
            <th :class="[TH_R, 'border-l border-grey-200']">Our SKUs</th>
            <th :class="TH_R">Matched</th>
            <th :class="TH_C" style="min-width: 118px">Matched %</th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Fresh
                <HelpTooltip text="Matched AND the competitor product was seen in the last 7 days." />
              </span>
            </th>
            <th :class="TH_C" style="min-width: 118px">
              <span class="inline-flex items-center gap-1">Addressable %
                <HelpTooltip text="Matched divided by (our SKUs minus confirmed no-match). The honest ceiling: a competitor at 30% matched but 100% addressable is finished, not behind." />
              </span>
            </th>
            <th :class="TH_R">Potential</th>
            <th :class="[TH_R, 'border-l border-grey-200']">
              <span class="inline-flex items-center gap-1">Their catalogue
                <HelpTooltip :text="catalogueHelp" />
              </span>
              <!-- The basis has to be on the header, not only in a tooltip: the
                   number changes by up to 4x between the two and the columns
                   either side of it are always category-scoped. -->
              <span class="block text-micro font-normal normal-case tracking-normal"
                    :class="isNarrowed ? 'text-brand-primary' : 'text-grey-400'">
                {{ catalogueBasis }}
              </span>
            </th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">They only
                <HelpTooltip text="Their products with no link to anything in our tracked range. That last phrase is doing work: a few of these ARE matched, but only to Breadfast products the tool does not track — bundles and long-tail SKUs outside the top 80% of revenue — and from here those count as products we do not carry. Never sum across views: one competitor product can bridge to several of our subcategories." />
              </span>
            </th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Ours only
                <HelpTooltip text="Our SKUs with no match at this competitor — Our SKUs minus Matched. The mirror of 'They only'. Read it as a CEILING: it counts what they genuinely do not stock TOGETHER WITH what we simply failed to match. Hover a row for the split into confirmed-not-stocked, likely matching miss, and never ruled either way." />
              </span>
            </th>
            <th :class="TH_C" style="min-width: 132px">Brands s / ours / theirs</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr
            v-for="row in rows"
            :key="row.competitor_name"
            class="hover:bg-brand-50 transition-colors cursor-pointer"
            :class="{ 'opacity-70': !row.has_catalogue }"
            :title="rowTitle(row)"
            @click="$emit('select-competitor', row.competitor_name)"
          >
            <td class="px-4 py-3 sticky left-0 bg-white z-10">
              <div class="flex items-center gap-2">
                <CompetitorLogo :name="row.competitor_name" />
                <span class="text-body font-semibold text-grey-900">{{ row.competitor_name }}</span>
                <span v-if="!row.has_catalogue"
                      class="px-1.5 py-0.5 rounded text-caption font-semibold bg-red-50 text-red-600 whitespace-nowrap"
                      title="Nothing crawled into the catalogue in the last 7 days. The competitor-side columns are a collection gap, not an assortment gap; our matching figures are still valid.">
                  no catalogue
                </span>
              </div>
            </td>

            <!-- Price position -->
            <td class="px-4 py-3 text-right">
              <span v-if="row.blended_pi != null"
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-mono text-body font-bold"
                    :class="piBgClass(row.blended_pi)">
                <span :class="piTextClass(row.blended_pi)">{{ piArrow(row.blended_pi) }}</span>
                {{ row.blended_pi.toFixed(2) }}
              </span>
              <span v-else class="text-grey-300">—</span>
            </td>
            <td :class="[TD_N, devClass(row.pi_deviation)]">{{ dev(row.pi_deviation) }}</td>
            <td class="px-4 py-3"><Bar :pct="row.priced_pct" /></td>

            <!-- Match coverage -->
            <td :class="[TD_N, 'border-l border-grey-100 text-grey-700']">{{ n(row.bf_products) }}</td>
            <td :class="[TD_N, 'text-green-600']">{{ n(row.matched) }}</td>
            <td class="px-4 py-3"><Bar :pct="row.mapping_pct" /></td>
            <td :class="[TD_N, row.matched_fresh === 0 && row.matched > 0 ? 'text-red-500 font-semibold' : 'text-grey-600']"
                :title="staleTitle(row)">{{ n(row.matched_fresh) }}</td>
            <td class="px-4 py-3"><Bar :pct="row.addressable_pct" /></td>
            <td :class="[TD_N, 'text-amber-600']">{{ n(row.potential_match) }}</td>

            <!-- Assortment overlap -->
            <td :class="[TD_N, 'border-l border-grey-100 text-grey-600']"
                :title="catalogueTitle(row)">{{ n(catalogueVal(row)) }}</td>
            <td :class="[TD_N, 'text-amber-700 font-semibold']">{{ n(row.comp_only_products) }}</td>
            <td :class="[TD_N, 'text-brand-primary font-semibold']" :title="ourOnlyTitle(row)">{{ n(row.our_only_products) }}</td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-1 text-caption font-mono">
                <span class="px-1.5 py-0.5 rounded bg-green-50 text-green-700" title="Brands both of us carry">{{ row.shared_brands }}</span>
                <span class="text-grey-300">/</span>
                <span class="px-1.5 py-0.5 rounded bg-brand-50 text-brand-primary" title="Brands only we carry">{{ row.bf_only_brands }}</span>
                <span class="text-grey-300">/</span>
                <span class="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700" title="Brands only they carry. Name variants are not collapsed, so this is an upper bound.">{{ row.comp_only_brands }}</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <EmptyState v-else message="No competitor data for the current filters" />
  </div>
</template>

<script setup>
import { computed, h } from 'vue'
import { LayoutList, Info } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'
import EmptyState from '../shared/EmptyState.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import { piTextClass, piBgClass, piArrow } from '../../utils/piColor'

const props = defineProps({
  data: { type: Array, default: () => [] },
  /** mapping_progress rows, keyed by competitor, for the hover breakdown. */
  mappingProgress: { type: Array, default: () => [] },
  vertical: { type: String, default: '' },
  /** '' | 'shared' — switches the catalogue column onto the shared-brand basis. */
  brandScope: { type: String, default: '' },
})
defineEmits(['select-competitor'])

const GROUP = 'px-4 py-1.5 text-center text-micro font-bold uppercase tracking-wide text-grey-400'
const TH_L = 'px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_R = 'px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_C = 'px-4 py-2 text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TD_N = 'px-4 py-3 text-right text-body font-mono'

const rows = computed(() => props.data || [])
const isSupermarket = computed(() => String(props.vertical).toLowerCase() === 'supermarket')

const mappingByComp = computed(() =>
  Object.fromEntries((props.mappingProgress || []).map(m => [m.competitor_name, m])))

function pooled(numKey, denFn) {
  const r = rows.value
  if (!r.length) return null
  const num = r.reduce((s, x) => s + (x[numKey] || 0), 0)
  const den = r.reduce((s, x) => s + (denFn(x) || 0), 0)
  return den > 0 ? Math.round((num / den) * 1000) / 10 : null
}
const addressablePct = computed(() => pooled('matched', r => r.addressable))
const freshPct = computed(() => pooled('matched_fresh', r => r.matched))

function n(v) { return v == null ? '—' : Number(v).toLocaleString() }
function dev(v) { return v == null ? '—' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}%` }
function devClass(v) {
  if (v == null) return 'text-grey-300'
  if (Math.abs(v) <= 0.005) return 'text-grey-500'
  // Same convention as piColor: pricier = warm, cheaper = cool.
  return v > 0 ? 'text-red-600' : 'text-blue-600'
}
const sharedOnly = computed(() => props.brandScope === 'shared')

// Their catalogue is now counted from the filtered rows — the paired half off our
// side, the unpaired half off theirs — so it narrows like every other column. No
// prop is needed to know whether it has: if the scoped count is below the
// competitor-level total, a filter is biting.
function catalogueVal(row) {
  return row.comp_products_in_scope ?? row.comp_products
}
const isNarrowed = computed(() => rows.value.some(r =>
  r.comp_products_in_scope != null && r.comp_products > 0
  && r.comp_products_in_scope < r.comp_products))

const catalogueBasis = computed(() => {
  if (!isNarrowed.value) return 'all brands'
  return sharedOnly.value ? 'shared brands, in scope' : 'in current scope'
})

const catalogueHelp = computed(() => isNarrowed.value
  ? 'Their live catalogue as narrowed by the filters above: the products of theirs we matched, plus the products of theirs we did not, both counted inside the current scope. Products of theirs that the category bridge cannot attribute to one of our subcategories are excluded as soon as you filter by category or subcategory — they cannot be placed, so counting them would inflate whichever categories you happened to pick. Hover a row for how many were excluded.'
  : 'Their ENTIRE live catalogue, across every category and brand. Filter by category, subcategory or brand scope and this narrows with everything else.')

function catalogueTitle(row) {
  const all = row.comp_products || 0
  const scope = row.comp_products_in_scope ?? all
  if (!all) return `Nothing crawled for ${row.competitor_name}`
  const pct = v => `${Math.round((v / all) * 1000) / 10}%`
  // Deliberately NOT showing comp_products_shared alongside the scoped count.
  // The two disagree by up to 413 products because they ask different questions:
  // the BigQuery scalar tests THEIR product's brand label against our brand list,
  // while the scoped count's matched half tests OUR product's brand, and the two
  // brand strings do not always survive a match intact. The scoped count is the
  // one that composes with every other filter, so it is the one on screen; the
  // scalar stays in the export where its column name can say what it is.
  const lines = [
    `${row.competitor_name} live catalogue`,
    `All brands, all categories: ${all.toLocaleString()}`,
  ]
  if (scope !== all) {
    lines.push(`In the current scope: ${scope.toLocaleString()} (${pct(scope)})`)
    lines.push('', `${(all - scope).toLocaleString()} excluded — outside the filters, or with no`,
               'category mapping to attribute them to one of our subcategories.')
  } else {
    // Worth stating plainly: with no filter this equals their true catalogue,
    // because the matched and unmatched halves partition it exactly.
    lines.push('', 'Matched and unmatched halves account for all of it.')
  }
  return lines.join('\n')
}

// "Ours only" is one number covering three very different situations, and the
// mix is what decides whether it is an assortment story or a matching backlog.
// The three are disjoint and exhaustive by construction: confirmed no-match is
// (rejected candidates), potential is (not confirmed AND similarity >= 0.85),
// and the remainder is everything the matcher never ruled either way.
function ourOnlyTitle(row) {
  const only = row.our_only_products || 0
  if (!only) return `Every one of our SKUs is matched at ${row.competitor_name}`
  const confirmed = row.confirmed_no_match || 0
  const potential = row.potential_match || 0
  const unresolved = Math.max(0, only - confirmed - potential)
  return [
    `${only.toLocaleString()} of our SKUs have no match at ${row.competitor_name}`,
    '',
    `They confirmably do not stock it: ${confirmed.toLocaleString()}`,
    `Likely a matching miss (similarity ≥ 0.85): ${potential.toLocaleString()}`,
    `Never ruled either way: ${unresolved.toLocaleString()}`,
  ].join('\n')
}
function staleTitle(row) {
  if (!row.matched) return 'Nothing matched'
  const stale = row.matched - row.matched_fresh
  return stale <= 0
    ? 'Every match was seen in the last 7 days'
    : `${stale.toLocaleString()} of ${row.matched.toLocaleString()} matches have not been seen in 7 days`
}

// Carried over from the table this replaces: the classification split was only
// ever available on hover there, and it is still the quickest way to see why the
// unmatched remainder is what it is.
function rowTitle(row) {
  const m = mappingByComp.value[row.competitor_name]
  const head = `${row.competitor_name} — click to open Commercial filtered to this competitor`
  if (!m) return head
  const mapped = (m.mapped_not_pl || 0) + (m.mapped_pl || 0)
  const potential = (m.potential_not_pl || 0) + (m.potential_pl || 0)
  const noPotential = (m.no_potential_not_pl || 0) + (m.no_potential_pl || 0)
  const noMatch = (m.no_match_not_pl || 0) + (m.no_match_pl || 0)
  return [
    head,
    '',
    `Mapped: ${mapped.toLocaleString()}`,
    `Potential match: ${potential.toLocaleString()}`,
    `No likely match: ${noPotential.toLocaleString()}`,
    `Confirmed no match: ${noMatch.toLocaleString()}`,
    m.potential_reach_pct != null ? `Potential reach: ${m.potential_reach_pct}%` : '',
  ].filter(Boolean).join('\n')
}

const Bar = (p) => {
  const v = p.pct
  const color = v == null ? 'bg-grey-200' : v >= 80 ? 'bg-green-500' : v >= 50 ? 'bg-amber-500' : 'bg-red-400'
  const text = v == null ? 'text-grey-300' : v >= 80 ? 'text-green-600' : v >= 50 ? 'text-amber-600' : 'text-red-500'
  return h('div', { class: 'flex items-center gap-2' }, [
    h('div', { class: 'flex-1 h-1.5 bg-grey-100 rounded-full overflow-hidden' }, [
      h('div', { class: `h-full rounded-full transition-all duration-500 ${color}`, style: { width: `${v || 0}%` } }),
    ]),
    h('span', { class: `text-caption font-semibold w-10 text-right ${text}` }, v == null ? '—' : `${v}%`),
  ])
}

function exportData() {
  return rows.value.map(r => ({
    COMPETITOR: r.competitor_name,
    'BLENDED PI': r.blended_pi,
    'VS PARITY': r.pi_deviation,
    'UTILIZATION %': r.priced_pct,
    'USED PRODUCTS': r.used_products,
    'ELIGIBLE PRODUCTS': r.eligible_products,
    'BF PRODUCTS': r.bf_products,
    MATCHED: r.matched,
    'MATCHED %': r.mapping_pct,
    'MATCHED FRESH': r.matched_fresh,
    'MAPPING % (SHARED BRANDS)': r.mapping_pct_shared,
    'CONFIRMED NO-MATCH': r.confirmed_no_match,
    ADDRESSABLE: r.addressable,
    'ADDRESSABLE %': r.addressable_pct,
    'POTENTIAL MATCH': r.potential_match,
    'POTENTIAL %': r.potential_pct,
    'COMP PRODUCTS (ALL CATEGORIES)': r.comp_products,
    'COMP PRODUCTS (THEIR BRAND IN OUR RANGE)': r.comp_products_shared,
    'COMP PRODUCTS (CURRENT SCOPE)': r.comp_products_in_scope,
    'COMP-ONLY PRODUCTS': r.comp_only_products,
    'OURS-ONLY PRODUCTS (UNMATCHED)': r.our_only_products,
    'SHARED BRANDS': r.shared_brands,
    'BF-ONLY BRANDS': r.bf_only_brands,
    'COMP-ONLY BRANDS': r.comp_only_brands,
    'HAS CATALOGUE': r.has_catalogue,
  }))
}
</script>
