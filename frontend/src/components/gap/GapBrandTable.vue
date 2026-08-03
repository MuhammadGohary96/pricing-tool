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
        <ExportButton :fetcher="exportFetcher" filename="gap_by_brand.csv" />
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
            <th :class="TH_R">Our SKUs</th>
            <th :class="TH_R">Matched</th>
            <th :class="TH_C" style="min-width: 120px">Matched %</th>
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
              <span class="px-2 py-0.5 rounded-md text-caption font-semibold" :class="TYPE_STYLE[row.brand_type]">
                {{ TYPE_LABEL[row.brand_type] }}
              </span>
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
