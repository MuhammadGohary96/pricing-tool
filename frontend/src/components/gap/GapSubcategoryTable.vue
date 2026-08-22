<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2">
        <Layers class="w-4 h-4 text-brand-primary" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Gap by subcategory</span>
        <span class="text-caption text-grey-400 ml-1">{{ rows.length }} subcategories · sorted by revenue</span>
      </div>
      <div class="flex items-center gap-2">
        <input
          v-model="search"
          type="search"
          placeholder="Filter subcategories…"
          class="text-body border border-grey-200 rounded-lg px-3 py-1.5 w-56 focus:outline-none focus:ring-1 focus:ring-brand-primary"
        />
        <ExportButton :fetcher="exportFetcher" label="Export Excel" filename="gap_by_subcategory.xlsx" />
      </div>
    </div>

    <div v-if="filtered.length" class="overflow-x-auto">
      <table class="w-full">
        <!-- Tint the middle group: Pricing position is the odd one out (a ratio,
             not a count), so the eye needs to know when it has crossed into it
             and back out. Same device as the scorecard's shared-brand band. -->
        <colgroup>
          <col />
          <col span="7" />
          <col span="2" class="col-pricing" />
          <col span="6" />
        </colgroup>
        <thead class="bg-grey-50 border-b border-grey-100">
          <tr>
            <th :class="TH_L" rowspan="2" class="align-bottom">Subcategory</th>
            <th :class="GROUP" colspan="7">Mapping coverage</th>
            <th :class="[GROUP, 'border-l-2 border-grey-300']" colspan="2">Pricing position</th>
            <th :class="[GROUP, 'border-l-2 border-grey-300']" colspan="6">Assortment gap</th>
          </tr>
          <tr>
            <th :class="TH_R">Our SKUs</th>
            <th :class="TH_R">Mapped</th>
            <th :class="TH_C" style="min-width: 130px">Mapped %</th>
            <th :class="TH_C" style="min-width: 130px">
              <span class="inline-flex items-center gap-1">
                Mapped Shared-brand %
                <HelpTooltip text="Mapped % counting only brands the competitor also carries — the realistic ceiling, since a brand they don't stock can never be matched." />
              </span>
            </th>
            <th :class="TH_R">No-match</th>
            <th :class="TH_C" style="min-width: 130px">
              <span class="inline-flex items-center gap-1">
                Mapping Addressable %
                <HelpTooltip text="Mapped ÷ (our SKUs − confirmed no-match), the column to its left. Products the matcher positively rejected leave the denominator." />
              </span>
            </th>
            <th :class="TH_R">Potential</th>

            <th :class="[TH_R, 'border-l-2 border-grey-300']">
              <span class="inline-flex items-center gap-1">
                Blended PI
                <HelpTooltip text="Quantity-weighted Breadfast ÷ competitor across fulfillment points. Above 1.00 means Breadfast is MORE expensive." />
              </span>
            </th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">
                Confidence %
                <HelpTooltip text="Products with a usable fresh price on both sides, over the eligible set (top 80% of revenue)." />
              </span>
            </th>

            <th :class="[TH_R, 'border-l-2 border-grey-300']">
              <span class="inline-flex items-center gap-1">Their catalogue
                <HelpTooltip text="Their catalogue attributable to this row — Mapped live plus They only. It will not equal Mapped + They only, because Mapped counts OUR products and this counts theirs." />
              </span>
            </th>
            <!-- Our SKUs repeats here on purpose: it is the denominator of Ours
                 only, and the assortment group is unreadable without the size of
                 our own side in view. -->
            <th :class="TH_R">Our SKUs</th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Mapped live
                <HelpTooltip text="Their products ours are matched to that they still list. Counted on THEIR side, so smaller than Mapped. This plus They only is exactly Their catalogue." />
              </span>
            </th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">
                They only
                <HelpTooltip text="Competitor products we do not carry, placed here by the category bridge. Never sum this column — one competitor product can bridge to several subcategories." />
              </span>
            </th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Ours only
                <HelpTooltip text="Our SKUs minus Mapped — the mirror of They only. A CEILING, not a work queue: what they do not stock together with what we failed to match." />
              </span>
            </th>
            <th :class="TH_C" style="min-width: 178px">
              <span class="inline-flex items-center gap-1">Brands (shared · by match / ours / theirs)
                <HelpTooltip text="Brands we share here, of which proved BY MATCH — a subset, not a fourth bucket. Then only-ours and only-theirs. Sets are WITHIN-subcategory." />
              </span>
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in filtered" :key="row.sub_category_name" class="hover:bg-brand-50 transition-colors">
            <td class="px-4 py-3">
              <div class="text-body font-semibold text-grey-900">{{ row.sub_category_name }}</div>
              <div class="text-caption text-grey-400 truncate max-w-[220px]">{{ row.commercial_category_name || '—' }}</div>
            </td>

            <td :class="TD_N">{{ n(row.bf_products) }}</td>
            <td :class="TD_N" class="text-green-600">{{ n(row.matched) }}</td>
            <td class="px-4 py-3"><Bar :pct="row.mapping_pct" /></td>
            <td class="px-4 py-3"><Bar :pct="row.mapping_pct_shared" /></td>
            <td :class="TD_N" class="text-grey-500">{{ n(row.confirmed_no_match) }}</td>
            <td class="px-4 py-3"><Bar :pct="row.addressable_pct" /></td>
            <td :class="TD_N" class="text-amber-600">{{ n(row.potential_match) }}</td>

            <td class="px-4 py-3 text-center border-l-2 border-grey-200">
              <span v-if="row.blended_pi != null"
                    class="inline-block px-2 py-0.5 rounded-md text-body font-mono font-semibold"
                    :class="piClass(row.blended_pi)"
                    :title="piTitle(row.blended_pi)">
                {{ row.blended_pi.toFixed(3) }}
              </span>
              <span v-else class="text-grey-300">—</span>
            </td>
            <td :class="TD_N" class="text-grey-600">{{ pct(row.coverage_pct) }}</td>

            <td :class="[TD_N, 'border-l-2 border-grey-200']" class="text-grey-600" :title="catalogueTitle(row)">{{ n(row.comp_catalogue) }}</td>
            <td :class="TD_N" class="text-grey-500">{{ n(row.bf_products) }}</td>
            <td :class="TD_N" class="text-green-700">{{ n(row.comp_mapped_live) }}</td>
            <td :class="TD_N" class="text-amber-700 font-semibold">{{ n(row.comp_only_products) }}</td>
            <td :class="TD_N" class="text-brand-primary font-semibold" :title="oursOnlyTitle(row)">{{ n(oursOnly(row)) }}</td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-1 text-caption font-mono">
                <span class="px-1.5 py-0.5 rounded bg-green-50 text-green-700" :title="titleList('Shared', row.shared_brand_list)">{{ row.shared_brands }}</span>
                <!-- Middle dot, not a slash: this sits inside the number to its
                     left, and a slash would read as a fourth bucket. -->
                <span class="text-grey-300">·</span>
                <span class="px-1.5 py-0.5 rounded ring-1 ring-green-200 text-green-700"
                      :title="`${row.shared_by_match_brands} of those ${row.shared_brands} shared brands are named differently on each side — proved by matching products, not by the label.`">{{ row.shared_by_match_brands }}</span>
                <span class="text-grey-300">/</span>
                <span class="px-1.5 py-0.5 rounded bg-brand-50 text-brand-primary" :title="titleList('Only ours', row.bf_only_brand_list)">{{ row.bf_only_brands }}</span>
                <span class="text-grey-300">/</span>
                <span class="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700" :title="titleList('Only theirs', row.comp_only_brand_list)">{{ row.comp_only_brands }}</span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <EmptyState v-else message="No subcategories match the current scope" />
  </div>
</template>

<script setup>
import { computed, ref, h } from 'vue'
import { Layers } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'
import EmptyState from '../shared/EmptyState.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'

const GROUP = 'px-4 py-1.5 text-center text-micro font-bold uppercase tracking-wide text-grey-400'

// Same bar the Mapped % column always had, now shared by the two rate columns
// beside it -- a percentage rendered as bare text next to one drawn as a bar
// reads as a lesser number, which these are not.
const Bar = (p) => {
  const v = p.pct
  return h('div', { class: 'flex items-center gap-2' }, [
    h('div', { class: 'flex-1 h-1.5 bg-grey-100 rounded-full overflow-hidden' }, [
      h('div', { class: `h-full rounded-full transition-all duration-500 ${barColor(v)}`,
                 style: { width: `${v || 0}%` } }),
    ]),
    h('span', { class: `text-caption font-semibold w-11 text-right ${pctColor(v)}` }, pct(v)),
  ])
}

// Ours only is an exact identity on this grain -- our SKUs minus the mapped ones
// -- so it is derived rather than carried as another column on the wire.
function oursOnly(row) {
  return Math.max(0, (row.bf_products || 0) - (row.matched || 0))
}
function oursOnlyTitle(row) {
  return `${oursOnly(row).toLocaleString()} of our ${(row.bf_products || 0).toLocaleString()} SKUs here have no match.\n`
       + `Confirmed not stocked: ${(row.confirmed_no_match || 0).toLocaleString()} · `
       + `strong candidate waiting: ${(row.potential_match || 0).toLocaleString()}`
}

const props = defineProps({
  rows: { type: Array, default: () => [] },
  exportFetcher: { type: Function, required: true },
})

const TH_L = 'px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_R = 'px-4 py-2 text-center text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_C = 'px-4 py-2 text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TD_N = 'px-4 py-3 text-center text-body font-mono'

const search = ref('')
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.rows
  return props.rows.filter(r =>
    (r.sub_category_name || '').toLowerCase().includes(q) ||
    (r.commercial_category_name || '').toLowerCase().includes(q))
})

// The column does not equal Mapped + They only and visibly should, so the
// breakdown belongs on the number itself rather than in a paragraph nobody
// reads at the moment they notice the discrepancy.
function catalogueTitle(row) {
  const theyOnly = row.comp_only_products || 0
  const paired = (row.comp_catalogue || 0) - theyOnly
  return [
    `${(row.comp_catalogue || 0).toLocaleString()} of their products land in this row:`,
    '',
    `  ${paired.toLocaleString()} matched to ours and still listed by them`,
    `  ${theyOnly.toLocaleString()} they carry that we do not`,
    '',
    `Mapped reads ${(row.matched || 0).toLocaleString()} because it counts OUR products —`,
    'several of ours can share one of their listings, and a match to a product',
    'they have since delisted is not in their catalogue any more.',
  ].join('\n')
}

function n(v) { return v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 }) }
function pct(v) { return v == null ? '—' : `${v}%` }

function barColor(v) {
  if (v == null) return 'bg-grey-200'
  if (v >= 80) return 'bg-green-500'
  if (v >= 50) return 'bg-amber-500'
  return 'bg-red-400'
}
function pctColor(v) {
  if (v == null) return 'text-grey-300'
  if (v >= 80) return 'text-green-600'
  if (v >= 50) return 'text-amber-600'
  return 'text-red-500'
}

// sale_PI = Breadfast ÷ competitor. Above 1 = we are the expensive one.
// Both tails are a problem, so the scale is symmetric around parity.
function piClass(v) {
  if (v > 1.05) return 'bg-red-50 text-red-700'
  if (v < 0.95) return 'bg-blue-50 text-blue-700'
  return 'bg-green-50 text-green-700'
}
function piTitle(v) {
  if (v > 1.05) return `Breadfast is ${((v - 1) * 100).toFixed(1)}% more expensive`
  if (v < 0.95) return `Breadfast is ${((1 - v) * 100).toFixed(1)}% cheaper`
  return 'At parity (within ±5%)'
}
function titleList(label, list) {
  if (!list || !list.length) return `${label}: none`
  const shown = list.slice(0, 40).join(', ')
  return `${label} (${list.length}): ${shown}${list.length > 40 ? ', …' : ''}`
}
</script>

<style scoped>
.col-pricing { background-color: rgb(248 250 252); }
</style>
