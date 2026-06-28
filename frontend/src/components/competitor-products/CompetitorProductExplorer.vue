<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Search class="w-4 h-4 text-brand-primary" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Product Explorer</span>
        <span class="text-caption text-grey-400 ml-1">{{ total.toLocaleString() }} products</span>
      </div>
      <div class="flex items-center gap-3">
        <div class="relative">
          <Search class="w-3.5 h-3.5 text-grey-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            :value="searchQuery"
            @input="$emit('search', $event.target.value)"
            type="text"
            placeholder="Search products..."
            class="text-body pl-8 pr-3 py-1.5 border border-grey-200 rounded-lg w-56 focus:outline-none focus:ring-1 focus:ring-brand-primary focus:border-brand-primary"
          />
        </div>
        <ExportButton :fetcher="exportFetcher" filename="competitor_products.csv" />
      </div>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100">
          <tr>
            <th class="px-3 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide">Competitor</th>
            <th class="px-3 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide" style="min-width: 200px">Product Name</th>
            <th class="px-3 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide">Category</th>
            <th class="px-3 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Price</th>
            <th class="px-3 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide">Last Crawled</th>
            <th class="px-3 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide" style="min-width: 160px">BF Product</th>
            <th class="px-3 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">BF Price</th>
            <th class="px-3 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">PI</th>
            <th class="px-3 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide">Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in items" :key="row.competitor_product_id" class="hover:bg-brand-50 transition-colors">
            <td class="px-3 py-2.5">
              <div class="flex items-center gap-1.5">
                <CompetitorLogo :name="row.competitor_name" />
                <span class="text-body text-grey-700">{{ row.competitor_name }}</span>
              </div>
            </td>
            <td class="px-3 py-2.5">
              <div class="text-body text-grey-900 font-medium truncate max-w-[240px]" :title="row.competitor_product_name">
                {{ row.competitor_product_name || '—' }}
              </div>
            </td>
            <td class="px-3 py-2.5">
              <span class="text-caption text-grey-500">{{ row.category_level_1 }}</span>
              <span v-if="row.category_level_2" class="text-caption text-grey-400"> / {{ row.category_level_2 }}</span>
            </td>
            <td class="px-3 py-2.5 text-right text-body font-mono text-grey-900">
              {{ row.competitor_sale_price != null ? `${row.competitor_sale_price.toFixed(2)}` : '—' }}
            </td>
            <td class="px-3 py-2.5">
              <span
                class="inline-flex items-center gap-1 text-caption font-medium px-2 py-0.5 rounded-full"
                :class="freshnessBadge(row.days_since_crawl)"
              >
                {{ row.days_since_crawl != null ? `${row.days_since_crawl}d ago` : '—' }}
              </span>
            </td>
            <td class="px-3 py-2.5">
              <div v-if="row.bf_product_name" class="text-body text-grey-700 truncate max-w-[180px]" :title="row.bf_product_name">
                {{ row.bf_product_name }}
              </div>
              <div v-else-if="row.match_potential" class="flex items-center gap-1.5">
                <span class="text-body text-amber-600 italic truncate max-w-[140px]" :title="row.match_potential_product_name">
                  {{ row.match_potential_product_name || 'potential match' }}
                </span>
                <span v-if="row.similarity_score != null" class="shrink-0 inline-flex items-center px-1.5 py-px rounded-full text-micro font-bold bg-amber-50 text-amber-700 border border-amber-200">
                  {{ Math.round(row.similarity_score * 100) }}%
                </span>
              </div>
              <span v-else class="text-caption text-grey-400">—</span>
            </td>
            <td class="px-3 py-2.5 text-right text-body font-mono text-grey-600">
              {{ row.bf_sale_price != null ? `${row.bf_sale_price.toFixed(2)}` : '—' }}
            </td>
            <td class="px-3 py-2.5 text-right">
              <span v-if="row.sale_PI != null" class="text-body font-mono font-semibold" :class="piClass(row.sale_PI)">
                <span class="text-[10px] mr-0.5 opacity-70">{{ piArrow(row.sale_PI) }}</span>{{ row.sale_PI.toFixed(2) }}
              </span>
              <span v-else class="text-caption text-grey-400">—</span>
            </td>
            <td class="px-3 py-2.5">
              <span
                class="inline-flex items-center text-caption font-semibold px-2 py-0.5 rounded-full"
                :class="statusBadge(row)"
              >
                {{ statusLabel(row) }}
              </span>
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="9" class="px-4 py-8 text-center text-grey-400 text-body">No products found</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="px-4 py-3 border-t border-grey-100 flex items-center justify-between">
      <span class="text-caption text-grey-500">
        Showing {{ (page - 1) * pageSize + 1 }}–{{ Math.min(page * pageSize, total) }} of {{ total.toLocaleString() }}
      </span>
      <div class="flex gap-1">
        <button
          class="px-3 py-1 text-caption rounded border border-grey-200 hover:bg-grey-100 disabled:opacity-40"
          :disabled="page <= 1"
          @click="$emit('page', page - 1)"
        >Prev</button>
        <button
          class="px-3 py-1 text-caption rounded border border-grey-200 hover:bg-grey-100 disabled:opacity-40"
          :disabled="page * pageSize >= total"
          @click="$emit('page', page + 1)"
        >Next</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Search } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import { piTextClass, piArrow } from '../../utils/piColor'

defineProps({
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 },
  searchQuery: { type: String, default: '' },
  exportFetcher: { type: Function, required: true },
})

defineEmits(['page', 'search'])

function freshnessBadge(days) {
  if (days == null) return 'bg-grey-100 text-grey-500'
  if (days <= 7) return 'bg-green-50 text-green-700'
  if (days <= 30) return 'bg-amber-50 text-amber-700'
  return 'bg-red-50 text-red-700'
}

// Delegate to the shared "both tails bad" system (PI = BF ÷ Comp): cheaper = cool,
// parity = green, pricier = warm. Replaces the old inverted high-PI-is-green logic.
function piClass(pi) {
  return piTextClass(pi)
}

function statusBadge(row) {
  if (row.has_PI) return 'bg-green-50 text-green-700'
  if (row.match_potential) return 'bg-amber-50 text-amber-700'
  return 'bg-grey-100 text-grey-600'
}

function statusLabel(row) {
  if (row.has_PI) return 'Mapped'
  if (row.match_potential) return 'Potential Match'
  return 'Unmapped'
}
</script>
