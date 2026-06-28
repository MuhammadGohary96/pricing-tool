<template>
  <!-- Secondary/overview surface: flat (no drop shadow) so the elevated Product Detail panel reads as primary -->
  <div class="bg-white rounded-xl ring-1 ring-grey-200/80 overflow-hidden flex flex-col">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3">
      <div class="flex items-center gap-1.5 min-w-0">
        <h2 class="text-subheading font-bold text-grey-900 tracking-tightish whitespace-nowrap">Blended PI by subcategory</h2>
        <HelpTooltip text="Quantity-weighted price index. Formula: Σ(sale_PI × avg_daily_quantity) ÷ Σ(avg_daily_quantity), filtered to used_product=TRUE (eligible + has price + recently updated). sale_PI = BF price ÷ Competitor price → PI > 1 = BF more expensive, PI < 1 = BF cheaper." />
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <span class="hidden sm:inline text-micro text-grey-400">Click a row to filter · a dot to jump to a product</span>
        <ExportButton :fetcher="exportData" filename="blended_pi.csv" class="shrink-0" />
      </div>
    </div>
    <!-- Refreshing indicator (in-place refetch on filter change) -->
    <div v-if="busy" class="h-[2px] bg-brand-lightest overflow-hidden shrink-0" role="status" aria-label="Updating results">
      <div class="h-full w-full bg-brand-primary animate-indeterminate"></div>
    </div>
    <div class="overflow-auto flex-1 min-h-0" :class="busy ? 'opacity-60 transition-opacity duration-200' : 'transition-opacity duration-200'">
      <table class="w-full">
        <thead class="sticky top-0 bg-grey-50 z-10">
          <tr>
            <!-- Fixed columns -->
            <th
              v-for="col in fixedColumns"
              :key="col.key"
              class="px-3 py-2 text-center text-caption font-semibold uppercase tracking-wide border-b border-grey-200 select-none transition-colors whitespace-nowrap"
              :class="[
                col.sortable !== false ? 'cursor-pointer hover:text-grey-900' : '',
                sortKey === col.key ? 'border-b-2 border-brand-primary text-brand-primary' : 'text-grey-500',
              ]"
              @click="col.sortable !== false && toggleSort(col.key)"
            >
              <span class="inline-flex items-center gap-1">
                {{ col.label }}
                <span
                  v-if="col.dynamicLabel && selectedCompetitor"
                  class="px-1.5 py-px rounded-full font-bold text-[9px] bg-brand-lightest text-brand-primary"
                >{{ selectedCompetitor }}</span>
                <component
                  v-if="col.sortable !== false"
                  :is="sortKey === col.key ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ChevronsUpDown"
                  class="w-3 h-3 transition-colors"
                  :class="sortKey === col.key ? 'text-brand-primary' : 'text-grey-300'"
                />
              </span>
            </th>
            <!-- Per-competitor PI columns -->
            <th
              v-for="comp in visibleCompetitors"
              :key="'comp-' + comp"
              class="px-2 py-2 text-center text-caption font-semibold uppercase tracking-wide border-b border-grey-200 whitespace-nowrap cursor-pointer select-none transition-colors"
              :class="selectedCompetitor === comp ? 'text-brand-primary bg-brand-50' : 'text-grey-500 hover:text-grey-900'"
              @click="toggleCompetitor(comp)"
            >
              <span class="inline-flex flex-col items-center gap-0.5">
                <CompetitorLogo :name="comp" />
                <span class="inline-flex items-center gap-0.5">{{ comp }}<Check v-if="selectedCompetitor === comp" class="w-3 h-3" /></span>
              </span>
            </th>
            <!-- Remaining fixed columns -->
            <th
              v-for="col in trailingColumns"
              :key="col.key"
              class="px-3 py-2 text-center text-caption font-semibold uppercase tracking-wide border-b border-grey-200 select-none transition-colors whitespace-nowrap"
              :class="[
                col.sortable !== false ? 'cursor-pointer hover:text-grey-900' : '',
                sortKey === col.key ? 'border-b-2 border-brand-primary text-brand-primary' : 'text-grey-500',
              ]"
              @click="col.sortable !== false && toggleSort(col.key)"
            >
              <span class="inline-flex items-center gap-1">
                {{ col.label }}
                <component
                  v-if="col.sortable !== false"
                  :is="sortKey === col.key ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ChevronsUpDown"
                  class="w-3 h-3 transition-colors"
                  :class="sortKey === col.key ? 'text-brand-primary' : 'text-grey-300'"
                />
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
            <td class="px-3 py-1.5 text-center font-mono text-body font-bold" :class="piTextClass(rowMinPI(row))">
              <span class="text-[10px] mr-0.5 opacity-70">{{ piArrow(rowMinPI(row)) }}</span>{{ rowMinPI(row)?.toFixed(2) ?? '—' }}
            </td>
            <td class="px-3 py-1.5 text-center font-mono text-body font-bold" :class="piTextClass(rowMaxPI(row))">
              <span class="text-[10px] mr-0.5 opacity-70">{{ piArrow(rowMaxPI(row)) }}</span>{{ rowMaxPI(row)?.toFixed(2) ?? '—' }}
            </td>
            <td class="px-3 py-1.5 text-center" style="min-width: 180px">
              <PIStripPlot
                :points="stripPlotPoints(row)"
                :blended-pi="stripPlotBlendedPi(row)"
                :subcategory="row.sub_category_name"
                @select-product="(payload) => $emit('select-product', payload)"
              />
            </td>
            <!-- Per-competitor blended PI cells -->
            <td
              v-for="comp in visibleCompetitors"
              :key="'val-' + comp"
              class="px-2 py-1.5 text-center font-mono text-body font-bold whitespace-nowrap"
              :class="[compPiClass(row.competitor_blended_pis?.[comp]), selectedCompetitor === comp ? 'bg-brand-50' : '']"
            ><span v-if="row.competitor_blended_pis?.[comp] != null" class="text-[10px] mr-0.5 opacity-70">{{ piArrow(row.competitor_blended_pis[comp]) }}</span>{{ row.competitor_blended_pis?.[comp]?.toFixed(2) ?? '—' }}</td>
            <!-- Trailing columns -->
            <td class="px-3 py-1.5 text-body text-grey-700 text-center font-mono">{{ row.total_product_count }}</td>
            <td class="px-3 py-1.5 text-body text-center font-mono">
              <span class="text-green-700">{{ row.eligible_product_count }}</span>
            </td>
            <td class="px-3 py-1.5 text-body text-center font-mono">
              <span class="text-brand-darkest">{{ rowUsed(row) }}</span>
            </td>
            <td class="px-3 py-1.5 text-body text-center font-mono">
              <span v-if="rowActions(row) > 0" class="text-amber-600">{{ rowActions(row) }}</span>
              <span v-else class="text-grey-300">0</span>
            </td>
            <td class="px-3 py-1.5 text-body text-grey-700 text-center font-mono" :title="row.total_revenue != null ? row.total_revenue.toLocaleString() + ' EGP' : ''">{{ formatRevenue(row.total_revenue) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <!-- Pagination -->
    <div class="px-4 py-2 border-t border-grey-100 flex items-center justify-between bg-grey-50 shrink-0">
      <span class="text-caption text-grey-500 tabular-nums">
        Showing <span class="font-medium text-grey-700">{{ ((page - 1) * pageSize + 1) }}-{{ Math.min(page * pageSize, totalRows) }}</span> of {{ totalRows }} subcategories
      </span>
      <div v-if="totalPages > 1" class="flex items-center gap-1">
        <button
          :disabled="page <= 1"
          class="inline-flex items-center gap-1 text-caption pl-2 pr-2.5 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 disabled:hover:bg-white transition-colors"
          @click="page--"
        ><ChevronLeft class="w-3.5 h-3.5" /> Prev</button>
        <button
          v-for="pg in pageNumbers"
          :key="pg"
          class="text-caption w-7 py-1 rounded-lg border tabular-nums transition-colors"
          :class="pg === page
            ? 'bg-brand-primary text-white border-brand-primary font-bold'
            : 'border-grey-200 bg-white hover:bg-grey-100 text-grey-700'"
          @click="page = pg"
        >{{ pg }}</button>
        <button
          :disabled="page >= totalPages"
          class="inline-flex items-center gap-1 text-caption pl-2.5 pr-2 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 disabled:hover:bg-white transition-colors"
          @click="page++"
        >Next <ChevronRight class="w-3.5 h-3.5" /></button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, watchEffect } from 'vue'
import PIStripPlot from '../shared/PIStripPlot.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'
import ExportButton from '../shared/ExportButton.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import { ChevronLeft, ChevronRight, ArrowUp, ArrowDown, ChevronsUpDown, Check } from 'lucide-vue-next'
import { piTextClass, piArrow } from '../../utils/piColor'

const props = defineProps({
  data: { type: Array, default: () => [] },
  competitors: { type: Array, default: () => [] },
  selectedCompetitors: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
})

defineEmits(['select', 'select-product'])

watch(() => props.data, () => { page.value = 1 })

const visibleCompetitors = computed(() => {
  if (props.selectedCompetitors.length > 0) {
    return props.competitors.filter(c => props.selectedCompetitors.includes(c))
  }
  return props.competitors
})

// Default selectedCompetitor to Talabat (or first available competitor), persisted in localStorage
const LS_KEY = 'bf_selected_competitor_blended'
const selectedCompetitor = ref(null)
watchEffect(() => {
  const comps = visibleCompetitors.value
  if (!comps.length) { selectedCompetitor.value = null; return }
  // If current selection is no longer visible, reset to preferred default
  if (!selectedCompetitor.value || !comps.includes(selectedCompetitor.value)) {
    const stored = localStorage.getItem(LS_KEY)
    selectedCompetitor.value = (stored && comps.includes(stored))
      ? stored
      : (comps.find(c => c.toLowerCase().includes('talabat')) ?? comps[0])
  }
})

function toggleCompetitor(comp) {
  const next = selectedCompetitor.value === comp ? null : comp
  selectedCompetitor.value = next
  if (next) localStorage.setItem(LS_KEY, next)
  else localStorage.removeItem(LS_KEY)
}

// Strip plot: show competitor-specific PIs when a competitor header is clicked
function stripPlotPoints(row) {
  if (selectedCompetitor.value && row.competitor_product_pis?.[selectedCompetitor.value]) {
    return row.competitor_product_pis[selectedCompetitor.value]
  }
  return row.product_pis || []
}

function stripPlotBlendedPi(row) {
  if (selectedCompetitor.value && row.competitor_blended_pis?.[selectedCompetitor.value] != null) {
    return row.competitor_blended_pis[selectedCompetitor.value]
  }
  return row.blended_pi
}

// Columns split around competitor PI columns
const fixedColumns = [
  { key: 'sub_category_name', label: 'Subcategory' },
  { key: 'min_pi', label: 'Min PI' },
  { key: 'max_pi', label: 'Max PI' },
  { key: 'product_pis', label: 'PI Distribution', sortable: false, dynamicLabel: true },
]

const trailingColumns = [
  { key: 'total_product_count', label: 'Total' },
  { key: 'eligible_product_count', label: 'Eligible' },
  { key: 'used_product_count', label: 'Used' },
  { key: 'needs_action_count', label: 'Actions' },
  { key: 'total_revenue', label: 'Revenue' },
]

const sortKey = ref('max_pi')
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

function rowMinPI(row) {
  const vals = Object.values(row.competitor_blended_pis || {}).filter(v => v != null)
  return vals.length ? Math.min(...vals) : null
}

function rowMaxPI(row) {
  const vals = Object.values(row.competitor_blended_pis || {}).filter(v => v != null)
  return vals.length ? Math.max(...vals) : null
}

function rowUsed(row) {
  if (selectedCompetitor.value)
    return row.competitor_used_counts?.[selectedCompetitor.value] ?? 0
  return row.used_product_count
}

function rowActions(row) {
  if (selectedCompetitor.value)
    return row.competitor_needs_action_counts?.[selectedCompetitor.value] ?? 0
  return row.needs_action_count
}

const allSortedData = computed(() => {
  const data = [...props.data]
  const dir = sortDir.value === 'asc' ? 1 : -1
  return data.sort((a, b) => {
    let va, vb
    if (sortKey.value === 'min_pi') {
      va = rowMinPI(a) ?? -Infinity
      vb = rowMinPI(b) ?? -Infinity
    } else if (sortKey.value === 'max_pi') {
      va = rowMaxPI(a) ?? -Infinity
      vb = rowMaxPI(b) ?? -Infinity
    } else {
      va = a[sortKey.value] ?? -Infinity
      vb = b[sortKey.value] ?? -Infinity
    }
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

function compPiClass(val) {
  if (val == null) return 'text-grey-300'
  return piTextClass(val)
}

function formatRevenue(val) {
  if (val == null) return '--'
  if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`
  if (val >= 1000) return `${(val / 1000).toFixed(0)}K`
  return val.toFixed(0)
}

function exportData() {
  return allSortedData.value.map(row => {
    const out = {
      subcategory: row.sub_category_name,
      min_pi: rowMinPI(row),
      max_pi: rowMaxPI(row),
      total_products: row.total_product_count,
      eligible: row.eligible_product_count,
      revenue: row.total_revenue,
    }
    for (const c of props.competitors) out[`${c}_pi`] = row.competitor_blended_pis?.[c] ?? null
    return out
  })
}
</script>
