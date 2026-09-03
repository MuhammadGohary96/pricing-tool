<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2">
        <Tags class="w-4 h-4 text-brand-primary" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Gap by brand</span>
        <span class="text-caption text-grey-400 ml-1">
          {{ filtered.length.toLocaleString() }} of {{ total.toLocaleString() }} brands
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
        <!-- Top pager: same controls as the footer, so long lists navigate
             without scrolling to the bottom first. -->
        <div v-if="totalPages > 1" class="flex items-center gap-1">
          <button :disabled="page <= 1" @click="page--" :class="PAGE_BTN">Previous</button>
          <span class="text-caption text-grey-600 px-1 whitespace-nowrap">{{ page }} / {{ totalPages }}</span>
          <button :disabled="page >= totalPages" @click="page++" :class="PAGE_BTN">Next</button>
        </div>
        <ExportButton :fetcher="exportFetcher" label="Export Excel" filename="gap_by_brand.xlsx" />
      </div>
    </div>

    <div v-if="filtered.length" class="overflow-x-auto max-h-[620px] overflow-y-auto">
      <table class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100 sticky top-0 z-10">
          <tr>
<th :class="TH_L" rowspan="2" class="align-bottom">Brand</th>
<th :class="TH_L" rowspan="2" class="align-bottom">Overlap</th>
<th :class="TH_L" rowspan="2" class="align-bottom">
              <span class="inline-flex items-center gap-1">Their brand
                <HelpTooltip text="Every spelling this brand has on their shelf, from products we actually matched, biggest first. Our Froneri is their Nestle; their 7Up/7UP/7up count as three brands, which is why 'only theirs' is an upper bound." />
              </span>
            </th>
            <th :class="GROUP" colspan="6">Mapping coverage</th>
            <th :class="[GROUP, 'border-l-2 border-grey-300']" colspan="7">Assortment gap</th>
          </tr>
          <tr>
            <th :class="TH_R">Our SKUs</th>
            <th :class="TH_R">Mapped</th>
            <th :class="TH_C" style="min-width: 120px">Mapped %</th>
            <th :class="TH_R">No-match</th>
            <th :class="TH_C" style="min-width: 130px">
              <span class="inline-flex items-center gap-1">Mapping Addressable %
                <HelpTooltip text="Mapped ÷ (our SKUs − confirmed no-match), the column to its left. Products the matcher positively rejected leave the denominator." />
              </span>
            </th>
            <th :class="TH_R">Potential</th>

            <th :class="[TH_R, 'border-l-2 border-grey-300']">
              <span class="inline-flex items-center gap-1">Their catalogue
                <HelpTooltip text="Their catalogue attributable to this brand — Mapped live plus They only. It will not equal Mapped + They only, because Mapped counts OUR products and this counts theirs." />
              </span>
            </th>
            <!-- Our SKUs repeats here: it is the denominator of Ours only, and
                 the assortment group cannot be read without our own side's size. -->
            <th :class="TH_R">Our SKUs</th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Mapped live
                <HelpTooltip text="Their products ours are matched to that they still list. Counted on THEIR side, so smaller than Mapped. This plus They only is exactly Their catalogue." />
              </span>
            </th>
            <th :class="TH_R">They only</th>
            <th :class="TH_R">
              <span class="inline-flex items-center gap-1">Ours only
                <HelpTooltip text="Our SKUs of this brand minus Mapped — the mirror of They only. A CEILING, not a proven gap: what they do not stock plus what we failed to match. No-match is the confirmed subset." />
              </span>
            </th>
            <th :class="TH_R">Our subcats</th>
            <th :class="TH_R">Their subcats</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in paged" :key="row.brand_key" class="hover:bg-brand-50 transition-colors">
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
            <td class="px-4 py-3"><Bar :pct="row.addressable_pct" /></td>
            <td :class="TD_N" class="text-amber-600">{{ n(row.potential_match) }}</td>
            <td :class="[TD_N, 'border-l-2 border-grey-200']" class="text-grey-600" :title="catalogueTitle(row)">{{ n(row.comp_catalogue) }}</td>
            <td :class="TD_N" class="text-grey-500">{{ n(row.bf_products) }}</td>
            <td :class="TD_N" class="text-green-700">{{ n(row.comp_mapped_live) }}</td>
            <td :class="TD_N" class="text-amber-700 font-semibold">{{ n(row.comp_only_products) }}</td>
            <td :class="TD_N" class="text-brand-primary font-semibold">{{ n(row.our_only_products) }}</td>
                                                            <td :class="TD_N" class="text-grey-600">{{ n(row.bf_subcategories) }}</td>
            <td :class="TD_N" class="text-grey-600">{{ n(row.comp_subcategories) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <EmptyState v-else message="No brands match the current scope" />

    <!-- Pagination (client-side: the full brand list is already loaded) -->
    <div v-if="totalPages > 1" class="px-4 py-3 border-t border-grey-100 flex items-center justify-between">
      <span class="text-caption text-grey-500">
        {{ ((page - 1) * PAGE_SIZE + 1).toLocaleString() }}–{{ Math.min(page * PAGE_SIZE, filtered.length).toLocaleString() }}
        of {{ filtered.length.toLocaleString() }}
      </span>
      <div class="flex items-center gap-1">
        <button :disabled="page <= 1" @click="page--" :class="PAGE_BTN">Previous</button>
        <span class="text-caption text-grey-600 px-2">Page {{ page }} / {{ totalPages }}</span>
        <button :disabled="page >= totalPages" @click="page++" :class="PAGE_BTN">Next</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, h } from 'vue'
import { Tags } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'
import EmptyState from '../shared/EmptyState.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'

// Shared by Mapped % and Mapping Addressable %: a rate drawn as bare text
// beside one drawn as a bar reads as the lesser number.
const Bar = (p) => {
  const v = p.pct
  if (v == null) return h('span', { class: 'text-grey-300' }, '—')
  return h('div', { class: 'flex items-center gap-2' }, [
    h('div', { class: 'flex-1 h-1.5 bg-grey-100 rounded-full overflow-hidden' }, [
      h('div', { class: `h-full rounded-full ${barColor(v)}`, style: { width: `${v}%` } }),
    ]),
    h('span', { class: `text-caption font-semibold w-11 text-right ${pctColor(v)}` }, `${v}%`),
  ])
}

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

const GROUP = 'px-4 py-1.5 text-center text-micro font-bold uppercase tracking-wide text-grey-400'
const TH_L = 'px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_R = 'px-4 py-2 text-center text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_C = 'px-4 py-2 text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TD_N = 'px-4 py-3 text-center text-body font-mono'

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

// Client-side pagination over the filtered set: search first, then page.
const PAGE_SIZE = 50
const page = ref(1)
const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const paged = computed(() => filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))
const PAGE_BTN = 'px-3 py-1 text-caption font-semibold rounded-lg border border-grey-200 text-grey-700 hover:bg-grey-50 disabled:opacity-40 disabled:cursor-not-allowed'
// New search, type filter, or data → back to page 1.
watch([search, () => props.brandType, () => props.rows], () => { page.value = 1 })

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
function barColor(v) { return v >= 80 ? 'bg-green-500' : v >= 50 ? 'bg-amber-500' : 'bg-red-400' }
function pctColor(v) { return v >= 80 ? 'text-green-600' : v >= 50 ? 'text-amber-600' : 'text-red-500' }
</script>
