<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2">
        <TriangleAlert class="w-4 h-4 text-amber-600" aria-hidden="true" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Pack-size review</span>
        <HelpTooltip text="Fruits & Vegetables pairs whose pack sizes cannot be compared: weights more than 5× apart, or different piece counts. Their PI is left per pack (never normalized), so fix the size or the mapping here." />
      </div>
      <span class="text-micro px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-medium">
        {{ total.toLocaleString() }} flagged
      </span>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100">
          <tr class="text-micro font-bold uppercase tracking-wide text-grey-500">
            <th class="text-left px-4 py-2">Our product</th>
            <th class="text-left px-4 py-2">Competitor product</th>
            <th class="text-center px-4 py-2">Sizes (ours · theirs)</th>
            <th class="text-center px-4 py-2">PI (per pack)</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in items" :key="`${row.product_id}|${row.competitor_name}`" class="hover:bg-amber-50/40 transition-colors">
            <td class="px-4 py-2.5">
              <div class="text-body font-medium text-grey-900 max-w-[320px] truncate" :title="row.product_name">{{ row.product_name }}</div>
              <div class="text-caption text-grey-400">{{ row.sub_category_name }}</div>
            </td>
            <td class="px-4 py-2.5">
              <div class="flex items-center gap-1.5 max-w-[320px]">
                <CompetitorLogo :name="row.competitor_name" size="sm" />
                <span class="text-body text-grey-700 truncate" :title="row.competitor_product_name">{{ row.competitor_product_name || '—' }}</span>
              </div>
            </td>
            <td class="px-4 py-2.5">
              <div class="flex items-center justify-center gap-1.5">
                <SizeChip :value="row.bf_size_value" :unit="row.bf_size_unit" title="Our pack size" />
                <span class="text-grey-300 text-micro">vs</span>
                <SizeChip :value="row.comp_size_value" :unit="row.comp_size_unit" :title="`${row.competitor_name} pack size`" flagged />
              </div>
            </td>
            <td class="px-4 py-2.5 text-center">
              <span v-if="row.sale_PI != null" class="font-mono text-body font-bold" :class="piTextClass(row.sale_PI)">
                {{ row.sale_PI.toFixed(2) }}
              </span>
              <span v-else class="text-grey-300">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="total > items.length" class="px-4 py-2 text-micro text-grey-400 border-t border-grey-100">
      Showing the {{ items.length }} highest-revenue of {{ total.toLocaleString() }}.
    </div>
  </div>
</template>

<script setup>
import { TriangleAlert } from 'lucide-vue-next'
import HelpTooltip from '../shared/HelpTooltip.vue'
import SizeChip from '../shared/SizeChip.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import { piTextClass } from '../../utils/piColor'

defineProps({
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
})
</script>
