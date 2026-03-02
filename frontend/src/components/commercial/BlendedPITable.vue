<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden flex flex-col">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between">
      <div class="flex items-center gap-1.5">
        <span class="text-subheading font-bold text-grey-900">Blended PI by Subcategory</span>
        <HelpTooltip text="Weighted price index = Competitor price \u00F7 BF price for eligible products. PI > 1 = BF cheaper, PI < 1 = BF more expensive." />
      </div>
      <div class="flex items-center gap-2">
        <span class="text-micro px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary font-medium">Click row to filter</span>
        <span class="text-micro px-2 py-0.5 rounded-full bg-grey-100 text-grey-600 font-medium">Click dot for product</span>
      </div>
    </div>
    <div class="overflow-auto flex-1 min-h-0">
      <table class="w-full">
        <thead class="sticky top-0 bg-grey-50 z-10">
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-3 py-2 text-center text-caption font-semibold text-grey-500 uppercase tracking-wide border-b border-grey-200 select-none transition-colors whitespace-nowrap"
              :class="col.sortable !== false ? 'cursor-pointer hover:text-grey-900' : ''"
              @click="col.sortable !== false && toggleSort(col.key)"
            >
              <span class="inline-flex items-center gap-1">
                {{ col.label }}
                <span
                  v-if="col.sortable !== false"
                  class="text-[10px] transition-colors"
                  :class="sortKey === col.key ? 'text-brand-primary' : 'text-grey-300'"
                >{{ sortKey === col.key ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in sortedData"
            :key="row.sub_category_name"
            class="border-b border-grey-100 hover:bg-brand-50 cursor-pointer transition-colors"
            @click="$emit('select', row.sub_category_name)"
          >
            <td class="px-3 py-1.5 text-body text-grey-900 text-center truncate" style="max-width: 180px" :title="row.sub_category_name">
              {{ row.sub_category_name }}
            </td>
            <td class="px-3 py-1.5 text-center" style="min-width: 140px">
              <PIInlineBar :value="row.blended_pi" />
            </td>
            <td class="px-3 py-1.5 text-center" style="min-width: 180px">
              <PIStripPlot
                :points="row.product_pis || []"
                :blended-pi="row.blended_pi"
                :subcategory="row.sub_category_name"
                @select-product="(payload) => $emit('select-product', payload)"
              />
            </td>
            <td class="px-3 py-1.5 text-center">
              <DirectionArrow :deviation="row.pi_deviation" />
            </td>
            <td class="px-3 py-1.5 text-body text-grey-700 text-center font-mono">{{ row.total_product_count }}</td>
            <td class="px-3 py-1.5 text-body text-center font-mono">
              <span class="text-green-700">{{ row.eligible_product_count }}</span>
            </td>
            <td class="px-3 py-1.5 text-body text-center font-mono">
              <span class="text-brand-darkest">{{ row.used_product_count }}</span>
            </td>
            <td class="px-3 py-1.5 text-body text-center font-mono">
              <span v-if="row.needs_action_count > 0" class="text-amber-600">{{ row.needs_action_count }}</span>
              <span v-else class="text-grey-300">0</span>
            </td>
            <td class="px-3 py-1.5 text-body text-grey-700 text-center font-mono">{{ formatRevenue(row.total_revenue) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <!-- Pagination -->
    <div class="px-4 py-2 border-t border-grey-100 flex items-center justify-between bg-grey-50 shrink-0">
      <span class="text-caption text-grey-500">
        Showing {{ ((page - 1) * pageSize + 1) }}–{{ Math.min(page * pageSize, totalRows) }} of {{ totalRows }} subcategories
      </span>
      <div v-if="totalPages > 1" class="flex items-center gap-1">
        <button
          :disabled="page <= 1"
          class="text-caption px-2 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 transition-colors"
          @click="page--"
        >← Prev</button>
        <button
          v-for="pg in pageNumbers"
          :key="pg"
          class="text-caption w-7 py-1 rounded-lg border transition-colors"
          :class="pg === page
            ? 'bg-brand-primary text-white border-brand-primary font-bold'
            : 'border-grey-200 bg-white hover:bg-grey-100 text-grey-700'"
          @click="page = pg"
        >{{ pg }}</button>
        <button
          :disabled="page >= totalPages"
          class="text-caption px-2 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 transition-colors"
          @click="page++"
        >Next →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import PIInlineBar from '../shared/PIInlineBar.vue'
import PIStripPlot from '../shared/PIStripPlot.vue'
import DirectionArrow from '../shared/DirectionArrow.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

defineEmits(['select', 'select-product'])

watch(() => props.data, () => { page.value = 1 })

const columns = [
  { key: 'sub_category_name', label: 'Subcategory' },
  { key: 'blended_pi', label: 'Blended PI' },
  { key: 'product_pis', label: 'PI Distribution', sortable: false },
  { key: 'pi_deviation', label: 'Direction' },
  { key: 'total_product_count', label: 'Total' },
  { key: 'eligible_product_count', label: 'Eligible' },
  { key: 'used_product_count', label: 'Used' },
  { key: 'needs_action_count', label: 'Actions' },
  { key: 'total_revenue', label: 'Revenue' },
]

const sortKey = ref('blended_pi')
const sortDir = ref('desc')
const page = ref(1)
const pageSize = 20

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
  page.value = 1
}

const allSortedData = computed(() => {
  const data = [...props.data]
  const dir = sortDir.value === 'asc' ? 1 : -1
  return data.sort((a, b) => {
    const va = a[sortKey.value] ?? -Infinity
    const vb = b[sortKey.value] ?? -Infinity
    if (va < vb) return -1 * dir
    if (va > vb) return 1 * dir
    return 0
  })
})

const totalRows = computed(() => allSortedData.value.length)
const totalPages = computed(() => Math.ceil(totalRows.value / pageSize))
const pageNumbers = computed(() => {
  const total = totalPages.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const cur = page.value
  const pageSet = new Set([1, total, cur, cur - 1, cur + 1].filter(p => p >= 1 && p <= total))
  return [...pageSet].sort((a, b) => a - b)
})

const sortedData = computed(() => {
  const start = (page.value - 1) * pageSize
  return allSortedData.value.slice(start, start + pageSize)
})

function formatRevenue(val) {
  if (val == null) return '--'
  if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`
  if (val >= 1000) return `${(val / 1000).toFixed(0)}K`
  return val.toFixed(0)
}
</script>
