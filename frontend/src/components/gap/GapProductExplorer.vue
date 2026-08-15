<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2">
        <PackageSearch class="w-4 h-4 text-brand-primary" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Products</span>
        <span class="text-caption text-grey-400 ml-1">{{ total.toLocaleString() }} rows</span>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <div class="flex items-center gap-1 bg-grey-50 rounded-lg p-0.5">
          <button
            v-for="opt in SIDES"
            :key="opt.value"
            @click="$emit('side', opt.value)"
            class="px-2.5 py-1 rounded-md text-caption font-semibold transition-colors"
            :class="side === opt.value ? 'bg-white text-grey-900 shadow-sm' : 'text-grey-500 hover:text-grey-700'"
          >{{ opt.label }}</button>
        </div>
        <input
          :value="searchQuery"
          @input="onSearch($event.target.value)"
          type="search"
          :placeholder="side === 'competitor' ? 'Search their products…' : 'Search our products…'"
          class="text-body border border-grey-200 rounded-lg px-3 py-1.5 w-56 focus:outline-none focus:ring-1 focus:ring-brand-primary"
        />
        <ExportButton :fetcher="exportFetcher" label="Export Excel" :filename="`gap_products_${side}.xlsx`" />
      </div>
    </div>

    <div v-if="items.length" class="overflow-x-auto">
      <!-- ── Their products we don't carry ───────────────────────── -->
      <table v-if="side === 'competitor'" class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100">
          <tr>
            <th :class="TH_L">Their product</th>
            <th :class="TH_L">Brand</th>
            <th :class="TH_L">Their category path</th>
            <th :class="TH_L">
              <span class="inline-flex items-center gap-1">
                Placed in our subcategory
                <HelpTooltip text="Inferred from where already-matched products in the same competitor category landed on our side. Confidence is the share of that evidence pointing here." />
              </span>
            </th>
            <th :class="TH_R">Confidence</th>
            <th :class="TH_L">Brand overlap</th>
            <th :class="TH_R">Last seen</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in items" :key="row.competitor_product_key" class="hover:bg-brand-50 transition-colors">
            <td class="px-4 py-3">
              <div class="text-body font-semibold text-grey-900 max-w-[300px] truncate" :title="row.product_name">{{ row.product_name }}</div>
              <div class="text-caption text-grey-400">{{ row.classification }}</div>
            </td>
            <td class="px-4 py-3 text-body text-grey-700">{{ row.brand_name || '—' }}</td>
            <td class="px-4 py-3 text-caption text-grey-500 max-w-[240px] truncate"
                :title="path(row)">{{ path(row) }}</td>
            <td class="px-4 py-3">
              <div v-if="row.sub_category_name" class="text-body text-grey-900">{{ row.sub_category_name }}</div>
              <div v-else class="text-caption text-grey-400 italic">not placed</div>
              <div v-if="row.mapped_bf_sub_categories_all && row.mapped_bf_sub_categories_all !== row.sub_category_name"
                   class="text-caption text-grey-400 truncate max-w-[220px]"
                   :title="row.mapped_bf_sub_categories_all">also: {{ row.mapped_bf_sub_categories_all }}</div>
            </td>
            <td class="px-4 py-3 text-right">
              <span v-if="row.mapped_pct_of_comp_category != null"
                    class="text-caption font-mono px-1.5 py-0.5 rounded"
                    :class="confClass(row.mapped_pct_of_comp_category, row.bridge_level)">
                {{ Math.round(row.mapped_pct_of_comp_category * 100) }}%
              </span>
              <span v-else class="text-grey-300">—</span>
              <div v-if="row.bridge_level === 'parent_l3_fallback'" class="text-caption text-grey-400">via parent</div>
            </td>
            <td class="px-4 py-3">
              <span class="px-2 py-0.5 rounded-md text-caption font-semibold"
                    :class="row.is_shared_brand ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'">
                {{ row.is_shared_brand ? 'We carry this brand' : 'New brand' }}
              </span>
            </td>
            <td class="px-4 py-3 text-right text-caption font-mono text-grey-500">{{ row.comp_last_seen || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- ── Our products and their match state ──────────────────── -->
      <table v-else class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100">
          <tr>
            <th :class="TH_L">Our product</th>
            <th :class="TH_L">Brand</th>
            <th :class="TH_L">Subcategory</th>
            <th :class="TH_L">Tier</th>
            <th :class="TH_L">Match state</th>
            <th :class="TH_R">Best similarity</th>
            <th :class="TH_R" class="cursor-pointer select-none" @click="$emit('sort', 'total_revenue')">Revenue/day</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in items" :key="row.product_id" class="hover:bg-brand-50 transition-colors">
            <td class="px-4 py-3">
              <div class="text-body font-semibold text-grey-900 max-w-[320px] truncate" :title="row.product_name">{{ row.product_name }}</div>
              <div class="text-caption text-grey-400">{{ row.commercial_category_name }}</div>
            </td>
            <td class="px-4 py-3 text-body text-grey-700">
              {{ row.brand_name || '—' }}
              <span v-if="!row.is_shared_brand" class="ml-1 text-caption text-amber-600" title="The competitor does not carry this brand at all">·&nbsp;brand not stocked</span>
            </td>
            <td class="px-4 py-3 text-body text-grey-700">{{ row.sub_category_name }}</td>
            <td class="px-4 py-3"><TierBadge v-if="row.global_tier" :tier="row.global_tier" /></td>
            <td class="px-4 py-3">
              <span class="px-2 py-0.5 rounded-md text-caption font-semibold" :class="stateStyle(row)">{{ stateLabel(row) }}</span>
            </td>
            <td class="px-4 py-3 text-right text-body font-mono text-grey-600">
              {{ row.best_similarity != null ? `${Math.round(row.best_similarity * 100)}%` : '—' }}
            </td>
            <td class="px-4 py-3 text-right text-body font-mono text-grey-900">{{ n(row.total_revenue) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <EmptyState v-else message="No products match the current scope" />

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="px-4 py-3 border-t border-grey-100 flex items-center justify-between">
      <span class="text-caption text-grey-500">
        {{ ((page - 1) * pageSize + 1).toLocaleString() }}–{{ Math.min(page * pageSize, total).toLocaleString() }}
        of {{ total.toLocaleString() }}
      </span>
      <div class="flex items-center gap-1">
        <button :disabled="page <= 1" @click="$emit('page', page - 1)" :class="PAGE_BTN">Previous</button>
        <span class="text-caption text-grey-600 px-2">Page {{ page }} / {{ totalPages }}</span>
        <button :disabled="page >= totalPages" @click="$emit('page', page + 1)" :class="PAGE_BTN">Next</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { PackageSearch } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'
import EmptyState from '../shared/EmptyState.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'
import TierBadge from '../shared/TierBadge.vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 },
  side: { type: String, default: 'competitor' },
  searchQuery: { type: String, default: '' },
  exportFetcher: { type: Function, required: true },
})
const emit = defineEmits(['page', 'search', 'side', 'sort'])

const SIDES = [
  { label: "They carry, we don't", value: 'competitor' },
  { label: 'Our products', value: 'breadfast' },
]
const TH_L = 'px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_R = 'px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide'
const PAGE_BTN = 'px-3 py-1 text-caption font-semibold rounded-lg border border-grey-200 text-grey-700 hover:bg-grey-50 disabled:opacity-40 disabled:cursor-not-allowed'

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

let searchTimer = null
function onSearch(v) {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => emit('search', v), 350)
}

function n(v) { return v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 }) }
function path(row) {
  return [row.category_level_1, row.category_level_2, row.category_level_3].filter(Boolean).join(' › ') || '—'
}
function confClass(v, level) {
  if (level === 'parent_l3_fallback') return 'bg-grey-100 text-grey-600'
  if (v >= 0.7) return 'bg-green-50 text-green-700'
  if (v >= 0.4) return 'bg-amber-50 text-amber-700'
  return 'bg-grey-100 text-grey-600'
}
function stateLabel(row) {
  if (row.is_mapped) return row.matched_comp_active_7d ? 'Matched' : 'Matched · stale'
  if (row.is_confirmed_no_match) return 'Confirmed no match'
  if (row.is_potential_match) return 'Potential match'
  return 'Unmatched'
}
function stateStyle(row) {
  if (row.is_mapped) return row.matched_comp_active_7d ? 'bg-green-50 text-green-700' : 'bg-grey-100 text-grey-600'
  if (row.is_confirmed_no_match) return 'bg-grey-100 text-grey-500'
  if (row.is_potential_match) return 'bg-amber-50 text-amber-700'
  return 'bg-red-50 text-red-600'
}
</script>
