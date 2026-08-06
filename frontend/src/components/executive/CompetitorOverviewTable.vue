<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2">
        <LayoutList class="w-4 h-4 text-brand-primary" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Competitor overview</span>
        <span class="text-caption text-grey-400 ml-1">
          matching &amp; assortment coverage · {{ rows.length }} competitors
        </span>
      </div>
      <ExportButton :fetcher="exportData" filename="competitor_overview.csv" />
    </div>

    <!-- The workbook this mirrors is built excluding beauty; say so rather than
         adding a second scope control that competes with the filter bar. -->
    <p v-if="!isSupermarket" class="px-4 py-2 text-caption text-grey-500 bg-grey-50/70 border-b border-grey-100">
      <Info class="w-3.5 h-3.5 inline -mt-0.5 text-grey-400" />
      Showing all verticals. Set <strong>Vertical → Supermarket</strong> above to match the
      <em>excl. beauty</em> workbook.
    </p>

    <div v-if="rows.length" class="overflow-x-auto">
      <table class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100">
          <tr>
            <th :class="TH_L" class="sticky left-0 bg-grey-50 z-10">Competitor</th>
            <th :class="TH_R">Our SKUs</th>
            <th :class="TH_R">Matched</th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Fresh
                <HelpTooltip text="Matched AND the competitor product was seen in the last 7 days. A match whose competitor side has gone quiet is a benchmark that is quietly rotting." />
              </span>
            </th>
            <th :class="TH_C" style="min-width: 128px">Matched %</th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Shared-brand %
                <HelpTooltip text="Matched % counting only products whose brand the competitor also carries — the realistic ceiling, since a brand they don't stock can never be matched." />
              </span>
            </th>
            <th :class="TH_R">No-match</th>
            <th :class="TH_R">Addressable</th>
            <th :class="TH_C" style="min-width: 128px">
              <span class="inline-flex items-center gap-1">Addressable %
                <HelpTooltip text="Matched / (our SKUs - confirmed no-match). Products the matcher positively rejected leave the denominator, so this is the honest ceiling rather than a backlog." />
              </span>
            </th>
            <th :class="TH_R">Potential</th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Their catalogue (all)
                <HelpTooltip text="The competitor's ENTIRE live catalogue, across every category. This is the one column the vertical and category filters do not narrow, so for a beauty-heavy competitor it reads much larger than the rest of the row. Compare 'They only' for the in-scope figure." />
              </span>
            </th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">They only
                <HelpTooltip text="Their products with no link to anything of ours. Never sum this across views — one competitor product can bridge to several of our subcategories." />
              </span>
            </th>
            <th :class="TH_C" style="min-width: 140px">Brands (shared / ours / theirs)</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in rows" :key="row.competitor_name"
              class="hover:bg-brand-50 transition-colors"
              :class="{ 'opacity-70': !row.has_catalogue }">
            <td class="px-4 py-3 sticky left-0 bg-white z-10">
              <div class="flex items-center gap-2">
                <CompetitorLogo :name="row.competitor_name" />
                <span class="text-body font-semibold text-grey-900">{{ row.competitor_name }}</span>
                <!-- Without this, 0 / 0 reads as "no assortment gap" when the
                     truth is "nothing was crawled". -->
                <span v-if="!row.has_catalogue"
                      class="px-1.5 py-0.5 rounded text-caption font-semibold bg-red-50 text-red-600 whitespace-nowrap"
                      title="No products crawled into the catalogue in the last 7 days. The competitor-side columns are a collection gap, not an assortment gap — our matching figures are still valid.">
                  no catalogue
                </span>
              </div>
            </td>
            <td :class="TD_N">{{ n(row.bf_products) }}</td>
            <td :class="[TD_N, 'text-green-600']">{{ n(row.matched) }}</td>
            <td :class="[TD_N, row.matched_fresh === 0 && row.matched > 0 ? 'text-red-500 font-semibold' : 'text-grey-600']"
                :title="staleTitle(row)">{{ n(row.matched_fresh) }}</td>
            <td class="px-4 py-3"><Bar :pct="row.mapping_pct" /></td>
            <td :class="[TD_N, pctColor(row.mapping_pct_shared)]">{{ pct(row.mapping_pct_shared) }}</td>
            <td :class="[TD_N, 'text-grey-500']">{{ n(row.confirmed_no_match) }}</td>
            <td :class="[TD_N, 'text-grey-700']">{{ n(row.addressable) }}</td>
            <td class="px-4 py-3"><Bar :pct="row.addressable_pct" /></td>
            <td :class="[TD_N, 'text-amber-600']">{{ n(row.potential_match) }}
              <span class="text-caption text-grey-400">{{ row.potential_pct != null ? `(${row.potential_pct}%)` : '' }}</span>
            </td>
            <td :class="[TD_N, 'text-grey-600']">{{ n(row.comp_products) }}</td>
            <td :class="[TD_N, 'text-amber-700 font-semibold']">{{ n(row.comp_only_products) }}</td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-1 text-caption font-mono">
                <span class="px-1.5 py-0.5 rounded bg-green-50 text-green-700" title="Brands both of us carry">{{ row.shared_brands }}</span>
                <span class="text-grey-300">/</span>
                <span class="px-1.5 py-0.5 rounded bg-brand-50 text-brand-primary" title="Brands only we carry">{{ row.bf_only_brands }}</span>
                <span class="text-grey-300">/</span>
                <span class="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700" title="Brands only they carry (name variants are not collapsed, so this is an upper bound)">{{ row.comp_only_brands }}</span>
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

const props = defineProps({
  data: { type: Array, default: () => [] },
  vertical: { type: String, default: '' },
})

const TH_L = 'px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_R = 'px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_C = 'px-4 py-2 text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TD_N = 'px-4 py-3 text-right text-body font-mono'

const rows = computed(() => props.data || [])
const isSupermarket = computed(() => String(props.vertical).toLowerCase() === 'supermarket')

function n(v) { return v == null ? '—' : Number(v).toLocaleString() }
function pct(v) { return v == null ? '—' : `${v}%` }
function pctColor(v) {
  if (v == null) return 'text-grey-300'
  if (v >= 80) return 'text-green-600'
  if (v >= 50) return 'text-amber-600'
  return 'text-red-500'
}
function staleTitle(row) {
  if (!row.matched) return 'Nothing matched'
  const stale = row.matched - row.matched_fresh
  if (stale <= 0) return 'Every match was seen in the last 7 days'
  return `${stale.toLocaleString()} of ${row.matched.toLocaleString()} matches have not been seen in 7 days`
}

// Inline bar — a local render function rather than a new shared component,
// since it is only two elements and used twice on this panel.
const Bar = (p) => {
  const v = p.pct
  const color = v == null ? 'bg-grey-200' : v >= 80 ? 'bg-green-500' : v >= 50 ? 'bg-amber-500' : 'bg-red-400'
  const text = v == null ? 'text-grey-300' : v >= 80 ? 'text-green-600' : v >= 50 ? 'text-amber-600' : 'text-red-500'
  return h('div', { class: 'flex items-center gap-2' }, [
    h('div', { class: 'flex-1 h-1.5 bg-grey-100 rounded-full overflow-hidden' }, [
      h('div', { class: `h-full rounded-full transition-all duration-500 ${color}`, style: { width: `${v || 0}%` } }),
    ]),
    h('span', { class: `text-caption font-semibold w-11 text-right ${text}` }, v == null ? '—' : `${v}%`),
  ])
}

function exportData() {
  return rows.value.map(r => ({
    COMPETITOR: r.competitor_name,
    'BF PRODUCTS': r.bf_products,
    MATCHED: r.matched,
    'MATCHED FRESH': r.matched_fresh,
    'MAPPING %': r.mapping_pct,
    'MAPPING % (SHARED BRANDS)': r.mapping_pct_shared,
    'CONFIRMED NO-MATCH': r.confirmed_no_match,
    ADDRESSABLE: r.addressable,
    'ADDRESSABLE %': r.addressable_pct,
    'POTENTIAL MATCH': r.potential_match,
    'POTENTIAL %': r.potential_pct,
    'COMP PRODUCTS (ALL CATEGORIES)': r.comp_products,
    'COMP-ONLY PRODUCTS': r.comp_only_products,
    'SHARED BRANDS': r.shared_brands,
    'BF-ONLY BRANDS': r.bf_only_brands,
    'COMP-ONLY BRANDS': r.comp_only_brands,
    'HAS CATALOGUE': r.has_catalogue,
  }))
}
</script>
