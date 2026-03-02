<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-3 flex-wrap">
      <div class="flex items-center gap-2 shrink-0">
        <span class="text-subheading font-bold text-grey-900">Priority Worklist</span>
        <span class="text-caption text-grey-500">{{ total.toLocaleString() }} items</span>
      </div>
      <!-- Search -->
      <div class="relative flex-1 min-w-[180px]">
        <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-grey-400 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35m0 0A7 7 0 1010 17a7 7 0 006.65-4.35z"/></svg>
        <input
          v-model="search"
          type="text"
          placeholder="Search products..."
          class="w-full pl-8 pr-7 py-1.5 text-body border border-grey-200 rounded-lg bg-white focus:border-brand-primary focus:ring-1 focus:ring-brand-lightest outline-none transition-colors"
        />
        <button v-if="search" class="absolute right-2 top-1/2 -translate-y-1/2 text-grey-400 hover:text-grey-700 text-lg leading-none" @click="search = ''">&times;</button>
      </div>
      <ExportButton :fetcher="exportWorklist" filename="priority_worklist.csv" class="shrink-0" />
    </div>
    <div class="overflow-auto" style="max-height: 420px">
      <table class="w-full min-w-[900px]">
        <thead class="sticky top-0 bg-grey-50 z-10">
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-3 py-2.5 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide cursor-pointer hover:text-grey-900 border-b border-grey-200 select-none transition-colors whitespace-nowrap focus:outline-none focus-visible:bg-brand-50"
              :aria-sort="sortKey === col.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
              tabindex="0"
              @click="toggleSort(col.key)"
              @keyup.enter="toggleSort(col.key)"
            >
              <span class="inline-flex items-center gap-1">
                {{ col.label }}
                <span class="text-[10px] transition-colors" :class="sortKey === col.key ? 'text-brand-primary' : 'text-grey-400'">
                  {{ sortKey === col.key ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}
                </span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in sortedData"
            :key="row.product_id"
            class="border-b border-grey-100 hover:bg-brand-50 transition-colors"
          >
            <!-- Product name + badges -->
            <td class="px-3 py-2" style="max-width: 200px">
              <div class="text-body text-grey-900 truncate" :title="row.product_name">{{ row.product_name }}</div>
              <div class="flex items-center gap-1 mt-0.5 flex-wrap">
                <span v-if="row.eligible_product" class="inline-block px-1.5 py-px rounded-full text-micro font-medium bg-green-50 text-green-700 leading-tight">Eligible</span>
                <span v-if="row.used_product" class="inline-block px-1.5 py-px rounded-full text-micro font-medium bg-brand-50 text-brand-darkest leading-tight">Used</span>
                <span v-if="row.action_type && row.action_type !== 'Complete'" class="inline-block px-1.5 py-px rounded-full text-micro font-medium bg-amber-50 text-amber-700 leading-tight">{{ row.action_type }}</span>
              </div>
            </td>
            <td class="px-3 py-2 text-body text-grey-500" style="max-width: 110px">
              <span class="flex items-center gap-1 truncate">
                {{ row.brand_name }}
                <img v-if="isBreadfast(row.brand_name)" src="/breadfast-logo.png" alt="BF" class="h-3.5 shrink-0" />
              </span>
            </td>
            <td class="px-3 py-2 text-body text-grey-500 truncate" style="max-width: 100px">{{ row.sub_category_name }}</td>
            <td class="px-3 py-2"><TierBadge :tier="row.global_tier" /></td>
            <td class="px-3 py-2"><ActionBadge :action="row.action_type" /></td>
            <!-- Competitor Match -->
            <td class="px-3 py-2 text-body" style="max-width: 200px">
              <!-- Matched: show competitor name -->
              <div v-if="row.competitor_product_name" class="flex items-center gap-1.5" :title="row.competitor_product_name">
                <svg class="w-3.5 h-3.5 text-green-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>
                <span class="text-grey-900 truncate">{{ row.competitor_product_name }}</span>
              </div>
              <!-- Potential match: show name + similarity badge -->
              <div v-else-if="row.match_potential_product_name" class="flex items-center gap-1.5" :title="row.match_potential_product_name + (row.similarity_score ? ' (' + (row.similarity_score * 100).toFixed(0) + '% match)' : '')">
                <span v-if="row.similarity_score" class="inline-flex items-center px-1.5 py-0.5 rounded-full text-micro font-bold flex-shrink-0"
                  :class="row.similarity_score >= 0.9 ? 'bg-green-50 text-green-700' : row.similarity_score >= 0.8 ? 'bg-amber-50 text-amber-700' : 'bg-grey-100 text-grey-500'"
                >{{ (row.similarity_score * 100).toFixed(0) }}%</span>
                <span class="text-grey-500 truncate">{{ row.match_potential_product_name }}</span>
              </div>
              <!-- No match -->
              <span v-else class="text-grey-300">—</span>
            </td>
            <td class="px-3 py-2 text-body text-grey-700 text-right font-mono">{{ row.bf_sale_price?.toFixed(1) }}</td>
            <td class="px-3 py-2 text-body text-grey-700 text-right font-mono">{{ row.talabat_sale_price?.toFixed(1) ?? '—' }}</td>
            <!-- Stale — color-coded -->
            <td class="px-3 py-2 text-body text-right font-mono">
              <span v-if="row.days_since_update != null" :class="staleClass(row.days_since_update)">
                {{ row.days_since_update }}d
              </span>
              <span v-else class="text-grey-300">—</span>
            </td>
            <td class="px-3 py-2 text-body text-grey-700 text-right font-mono">{{ formatRevenue(row.total_revenue) }}</td>
            <td class="px-3 py-1.5 text-center">
              <button
                @click.stop="router.push({ path: '/commercial', query: { search: row.product_name } })"
                class="p-1 text-grey-400 hover:text-brand-primary transition-colors rounded"
                title="View in Commercial"
              >
                <ExternalLink class="w-3.5 h-3.5" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <EmptyState v-if="sortedData.length === 0" :icon="SearchIcon" title="No products found" message="No products match your search. Try a different keyword." />
    </div>
    <div v-if="totalPages > 1" class="px-4 py-2.5 border-t border-grey-100 flex items-center justify-between bg-grey-50 gap-3">
      <span class="text-caption text-grey-500 shrink-0">
        Showing {{ ((page - 1) * pageSize + 1).toLocaleString() }}&ndash;{{ Math.min(page * pageSize, total).toLocaleString() }} of {{ total.toLocaleString() }}
      </span>
      <div class="flex items-center gap-1">
        <button
          :disabled="page <= 1"
          class="text-caption px-2.5 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 transition-colors"
          @click="$emit('page', page - 1)"
        >&larr; Prev</button>
        <span class="text-caption text-grey-500 px-1">{{ page }} / {{ totalPages }}</span>
        <button
          :disabled="page >= totalPages"
          class="text-caption px-2.5 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 transition-colors"
          @click="$emit('page', page + 1)"
        >Next &rarr;</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import TierBadge from '../shared/TierBadge.vue'
import ActionBadge from '../shared/ActionBadge.vue'
import EmptyState from '../shared/EmptyState.vue'
import { Search as SearchIcon, ExternalLink } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'

const router = useRouter()

const props = defineProps({
  data: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 },
})

defineEmits(['page'])

const columns = [
  { key: 'product_name', label: 'Product' },
  { key: 'brand_name', label: 'Brand' },
  { key: 'sub_category_name', label: 'Subcategory' },
  { key: 'global_tier', label: 'Tier' },
  { key: 'action_type', label: 'Action' },
  { key: 'similarity_score', label: 'Competitor Match' },
  { key: 'bf_sale_price', label: 'BF Price' },
  { key: 'talabat_sale_price', label: 'Talabat' },
  { key: 'days_since_update', label: 'Stale' },
  { key: 'total_revenue', label: 'Revenue' },
  { key: '_link', label: '' },
]

const search = ref('')
const sortKey = ref('tier_order')
const sortDir = ref('desc')

const totalPages = computed(() => Math.ceil(props.total / props.pageSize))

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
}

const sortedData = computed(() => {
  let data = [...props.data]
  if (search.value) {
    const q = search.value.toLowerCase()
    data = data.filter(r =>
      r.product_name?.toLowerCase().includes(q) ||
      r.brand_name?.toLowerCase().includes(q)
    )
  }
  const dir = sortDir.value === 'asc' ? 1 : -1
  return data.sort((a, b) => {
    const va = a[sortKey.value] ?? -Infinity
    const vb = b[sortKey.value] ?? -Infinity
    if (va < vb) return -1 * dir
    if (va > vb) return 1 * dir
    return 0
  })
})

function staleClass(days) {
  if (days <= 7) return 'text-green-600'
  if (days <= 30) return 'text-amber-600'
  return 'text-red-600 font-bold'
}

function isBreadfast(brand) {
  return brand && brand.toLowerCase().includes('breadfast')
}

function formatRevenue(val) {
  if (val == null) return '--'
  if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`
  if (val >= 1000) return `${(val / 1000).toFixed(0)}K`
  return val.toFixed(0)
}

function exportWorklist() {
  return sortedData.value.map(r => ({
    product_name: r.product_name,
    brand_name: r.brand_name,
    sub_category_name: r.sub_category_name,
    global_tier: r.global_tier,
    action_type: r.action_type,
    bf_sale_price: r.bf_sale_price,
    talabat_sale_price: r.talabat_sale_price,
    days_since_update: r.days_since_update,
    total_revenue: r.total_revenue,
    similarity_score: r.similarity_score,
  }))
}
</script>
