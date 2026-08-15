<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2">
        <Tags class="w-4 h-4 text-brand-primary" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Gap by brand</span>
        <span class="text-caption text-grey-400 ml-1">
          showing {{ rows.length.toLocaleString() }} of {{ total.toLocaleString() }}
        </span>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <div class="flex items-center gap-1 bg-grey-50 rounded-lg p-0.5">
          <button
            v-for="opt in TYPES"
            :key="String(opt.value)"
            @click="$emit('type', opt.value)"
            class="px-2.5 py-1 rounded-md text-caption font-semibold transition-colors"
            :class="brandType === opt.value ? 'bg-white text-grey-900 shadow-sm' : 'text-grey-500 hover:text-grey-700'"
          >{{ opt.label }}</button>
        </div>
        <input
          v-model="search"
          type="search"
          placeholder="Filter brands…"
          class="text-body border border-grey-200 rounded-lg px-3 py-1.5 w-52 focus:outline-none focus:ring-1 focus:ring-brand-primary"
        />
        <ExportButton :fetcher="exportFetcher" label="Export Excel" filename="gap_by_brand.xlsx" />
      </div>
    </div>

    <p class="px-4 py-2 text-caption text-grey-500 bg-amber-50/60 border-b border-amber-100">
      <TriangleAlert class="w-3.5 h-3.5 inline -mt-0.5 text-amber-500" />
      Brand-name variants are not collapsed — <em>L'Oréal Paris</em>, <em>L'Oreal</em> and
      <em>Elvive</em> count as three brands. Treat "brands only they carry" as an upper bound.
    </p>

    <div v-if="filtered.length" class="overflow-x-auto max-h-[620px] overflow-y-auto">
      <table class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100 sticky top-0 z-10">
          <tr>
            <th :class="TH_L">Brand</th>
            <th :class="TH_L">Overlap</th>
            <th :class="TH_L">
              <span class="inline-flex items-center gap-1">Their brand
                <HelpTooltip text="Every distinct spelling this brand carries on their shelf, taken from the products we actually matched, biggest first. Two things show up here. A brand we label differently: we carry Froneri, the Nestlé ice-cream JV, and they shelve the same products as Nestle, Paradise, Oreo and a dozen more — that is the evidence behind a 'by match' overlap. And a brand we label the same but they spell several ways: 7Up, 7UP and 7up are three separate brands in their catalogue, which is why 'brands only they carry' is an upper bound." />
              </span>
            </th>
            <th :class="TH_R">Our SKUs</th>
            <th :class="TH_R">Mapped</th>
            <th :class="TH_C" style="min-width: 120px">Mapped %</th>
            <th :class="TH_R">No-match</th>
            <th :class="TH_R">Potential</th>
            <th :class="TH_R">They only</th>
            <th :class="TH_R">Our subcats</th>
            <th :class="TH_R">Their subcats</th>
            <th :class="TH_R">Revenue/day</th>
            <th :class="TH_R">Unmatched rev.</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in filtered" :key="row.brand_key" class="hover:bg-brand-50 transition-colors">
            <td class="px-4 py-3 text-body font-semibold text-grey-900">{{ row.brand_name }}</td>
            <td class="px-4 py-3">
              <span class="px-2 py-0.5 rounded-md text-caption font-semibold whitespace-nowrap"
                    :class="row.shared_by_match ? 'bg-green-50 text-green-700 ring-1 ring-green-200' : TYPE_STYLE[row.brand_type]"
                    :title="row.shared_by_match
                      ? 'The names do not match, but at least half of this brand\'s products are mapped here — so they stock it under another name.'
                      : undefined">
                {{ row.shared_by_match ? 'Shared — by match' : TYPE_LABEL[row.brand_type] }}
              </span>
            </td>
            <td class="px-4 py-3 text-caption text-grey-500 max-w-[220px]">
              <span v-if="variants(row).length" :title="variantTitle(row)" class="cursor-help">
                {{ variants(row).slice(0, 3).map(v => v.name).join(', ') }}
                <span v-if="variants(row).length > 3"
                      class="ml-1 px-1 py-px rounded-full bg-grey-100 text-grey-500 font-semibold">
                  +{{ variants(row).length - 3 }}
                </span>
              </span>
              <span v-else class="text-grey-300">—</span>
            </td>
            <td :class="TD_N">{{ n(row.bf_products) }}</td>
            <td :class="TD_N" class="text-green-600">{{ n(row.matched) }}</td>
            <td class="px-4 py-3">
              <div v-if="row.mapping_pct != null" class="flex items-center gap-2">
                <div class="flex-1 h-1.5 bg-grey-100 rounded-full overflow-hidden">
                  <div class="h-full rounded-full" :class="barColor(row.mapping_pct)" :style="{ width: `${row.mapping_pct}%` }"></div>
                </div>
                <span class="text-caption font-semibold w-11 text-right" :class="pctColor(row.mapping_pct)">{{ row.mapping_pct }}%</span>
              </div>
              <span v-else class="text-grey-300 text-caption">—</span>
            </td>
            <td :class="TD_N" class="text-grey-500">{{ n(row.confirmed_no_match) }}</td>
            <td :class="TD_N" class="text-amber-600">{{ n(row.potential_match) }}</td>
            <td :class="TD_N" class="text-amber-700 font-semibold">{{ n(row.comp_only_products) }}</td>
            <td :class="TD_N" class="text-grey-600">{{ n(row.bf_subcategories) }}</td>
            <td :class="TD_N" class="text-grey-600">{{ n(row.comp_subcategories) }}</td>
            <td :class="TD_N" class="text-grey-900 font-semibold">{{ n(row.daily_revenue) }}</td>
            <td :class="TD_N" class="text-red-500">{{ n(row.unmatched_revenue) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <EmptyState v-else message="No brands match the current scope" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Tags, TriangleAlert } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'
import EmptyState from '../shared/EmptyState.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  brandType: { type: String, default: null },
  exportFetcher: { type: Function, required: true },
})
defineEmits(['type'])

const TYPES = [
  { label: 'All', value: null },
  { label: 'Shared', value: 'shared' },
  // Not a brand type — an audit of the rule. These brands are also returned by
  // Shared, which is the point: they ARE shared, just established differently.
  { label: 'By match', value: 'by_match' },
  { label: 'Only ours', value: 'bf_only' },
  { label: 'Only theirs', value: 'comp_only' },
]
const TYPE_LABEL = { shared: 'Shared', bf_only: 'Only ours', comp_only: 'Only theirs' }
const TYPE_STYLE = {
  shared: 'bg-green-50 text-green-700',
  bf_only: 'bg-brand-50 text-brand-primary',
  comp_only: 'bg-amber-50 text-amber-700',
}

const TH_L = 'px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_R = 'px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_C = 'px-4 py-2 text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TD_N = 'px-4 py-3 text-right text-body font-mono'

// comp_brand_variants arrives as "Nestle:45|Paradise:39|Oreo:28", already ranked
// and capped at ten by the query. Encoded rather than sent as a nested array so
// it survives the BigQuery → Parquet → DuckDB → pandas path as a plain string.
function variants(row) {
  const raw = row.comp_brand_variants
  if (!raw) return []
  return String(raw).split('|').map(part => {
    const i = part.lastIndexOf(':')          // brand names can contain a colon
    // i <= 0 means the name half is blank — a competitor product with an empty
    // brand_name encodes as ":1". Drop it rather than render a bare count.
    return i <= 0 ? { name: '', n: null }
                  : { name: part.slice(0, i).trim(), n: Number(part.slice(i + 1)) || null }
  }).filter(v => v.name)
}

function variantTitle(row) {
  const v = variants(row)
  if (!v.length) return ''
  // Worth calling out when the only difference is spelling: it means the brand
  // is fragmented in their catalogue, not that they label it as something else.
  const spellingOnly = v.every(x =>
    x.name.toLowerCase().replace(/\s+/g, '') ===
    String(row.brand_name || '').toLowerCase().replace(/\s+/g, ''))
  return [
    `${row.brand_name} is shelved here as:`,
    '',
    ...v.map(x => `  ${x.name}${x.n ? ` — ${x.n} product${x.n === 1 ? '' : 's'}` : ''}`),
    v.length === 10 ? '\n(top 10 shown)' : '',
    spellingOnly && v.length > 1
      ? '\nSame brand, spelled several ways in their catalogue.'
      : '',
  ].filter(Boolean).join('\n')
}

const search = ref('')
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.rows
  return props.rows.filter(r => (r.brand_name || '').toLowerCase().includes(q))
})

function n(v) { return v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 }) }
function barColor(v) { return v >= 80 ? 'bg-green-500' : v >= 50 ? 'bg-amber-500' : 'bg-red-400' }
function pctColor(v) { return v >= 80 ? 'text-green-600' : v >= 50 ? 'text-amber-600' : 'text-red-500' }
</script>
