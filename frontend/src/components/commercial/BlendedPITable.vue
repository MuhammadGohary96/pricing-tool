<template>
  <!-- Secondary/overview surface: flat (no drop shadow) so the elevated Product Detail panel reads as primary -->
  <div class="bg-white rounded-xl ring-1 ring-grey-200/80 overflow-hidden flex flex-col">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-1.5 min-w-0">
        <h2 class="text-subheading font-bold text-grey-900 tracking-tightish whitespace-nowrap">{{ title }}</h2>
        <HelpTooltip text="Quantity-weighted price index. Formula: Σ(sale_PI × avg_daily_quantity) ÷ Σ(avg_daily_quantity), filtered to used_product=TRUE (eligible + has price + recently updated). sale_PI = BF price ÷ Competitor price → PI > 1 = BF more expensive, PI < 1 = BF cheaper." />
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <!-- Grain toggle: roll up to commercial category or drop to subcategory -->
        <div class="inline-flex items-center rounded-lg border border-grey-200 overflow-hidden text-caption font-medium">
          <button
            type="button"
            class="px-2.5 py-1 transition-colors"
            :class="groupBy === 'sub_category' ? 'bg-brand-primary text-white' : 'bg-white text-grey-600 hover:bg-grey-50'"
            @click="$emit('set-group-by', 'sub_category')"
          >Subcategory</button>
          <button
            type="button"
            class="px-2.5 py-1 border-l border-grey-200 transition-colors"
            :class="groupBy === 'commercial_category' ? 'bg-brand-primary text-white' : 'bg-white text-grey-600 hover:bg-grey-50'"
            @click="$emit('set-group-by', 'commercial_category')"
          >Commercial category</button>
        </div>
        <span class="hidden sm:inline text-micro text-grey-400">Click a row to filter · a dot to jump to a product</span>
        <ExportButton :fetcher="exportData" label="Export Excel" filename="blended_pi.xlsx" class="shrink-0" />
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
            :key="row.group_key"
            class="border-b border-grey-100 hover:bg-brand-50 cursor-pointer transition-colors"
            @click="onRowClick(row)"
          >
            <td
              class="px-3 py-1.5 text-body text-center truncate"
              :class="groupBy === 'commercial_category' ? 'text-grey-900' : 'text-grey-600'"
              style="max-width: 180px"
              :title="row.commercial_category_name || ''"
            >
              {{ row.commercial_category_name || '—' }}
            </td>
            <td v-if="groupBy === 'sub_category'" class="px-3 py-1.5 text-body text-grey-900 text-center truncate" style="max-width: 180px" :title="row.sub_category_name">
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
                :subcategory="row.sub_category_name || row.commercial_category_name"
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
              <span class="text-grey-800">{{ rowMapped(row) }}</span>
            </td>
            <td class="px-3 py-1.5 text-body text-center font-mono">
              <span :class="rowMappingPct(row) == null ? 'text-grey-300' : 'text-grey-700'">{{ rowMappingPct(row) != null ? rowMappingPct(row) + '%' : '—' }}</span>
            </td>
            <td class="px-3 py-1.5 text-body text-center font-mono">
              <span :class="rowUtilizationPct(row) == null ? 'text-grey-300' : 'text-grey-700'">{{ rowUtilizationPct(row) != null ? rowUtilizationPct(row) + '%' : '—' }}</span>
            </td>
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
  // 'sub_category' (default) | 'commercial_category' — the row grain.
  groupBy: { type: String, default: 'sub_category' },
})

const emit = defineEmits(['select', 'select-product', 'select-category', 'set-group-by'])

const title = computed(() =>
  props.groupBy === 'commercial_category' ? 'Blended PI by commercial category' : 'Blended PI by subcategory'
)

// Row click drills: subcategory → subcategory filter; commercial category →
// commercial-category filter (handled by the parent view).
function onRowClick(row) {
  if (props.groupBy === 'commercial_category') emit('select-category', row.commercial_category_name)
  else emit('select', row.sub_category_name)
}

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

// Columns split around competitor PI columns. The Subcategory column only
// exists in subcategory grain; the category roll-up drops it.
const fixedColumns = computed(() => {
  const cols = [{ key: 'commercial_category_name', label: 'Commercial category' }]
  if (props.groupBy === 'sub_category') cols.push({ key: 'sub_category_name', label: 'Subcategory' })
  cols.push(
    { key: 'min_pi', label: 'Min PI' },
    { key: 'max_pi', label: 'Max PI' },
    { key: 'product_pis', label: 'PI Distribution', sortable: false, dynamicLabel: true },
  )
  return cols
})

const trailingColumns = [
  { key: 'total_product_count', label: 'Total' },
  { key: 'eligible_product_count', label: 'Eligible' },
  { key: 'used_product_count', label: 'Used' },
  { key: 'mapped_product_count', label: 'Mapped' },
  { key: 'mapping_pct', label: 'Map %' },
  { key: 'utilization_pct', label: 'Util %' },
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

function rowMapped(row) {
  if (selectedCompetitor.value)
    return row.competitor_mapped_counts?.[selectedCompetitor.value] ?? 0
  return row.mapped_product_count ?? 0
}

// Mapping % = mapped / total tracked; Utilization % = used / eligible.
function rowMappingPct(row) {
  const total = row.total_product_count || 0
  return total ? Math.round((rowMapped(row) / total) * 100) : null
}

function rowUtilizationPct(row) {
  const eligible = row.eligible_product_count || 0
  return eligible ? Math.round((rowUsed(row) / eligible) * 100) : null
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
    } else if (sortKey.value === 'mapping_pct') {
      va = rowMappingPct(a) ?? -Infinity
      vb = rowMappingPct(b) ?? -Infinity
    } else if (sortKey.value === 'utilization_pct') {
      va = rowUtilizationPct(a) ?? -Infinity
      vb = rowUtilizationPct(b) ?? -Infinity
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

// One worksheet per currently-visible competitor. Each row is a table row at
// the active grain (commercial category, or + subcategory) with that
// competitor's PI and coverage. Falls back to a single combined sheet if no
// competitors are visible.
function exportData() {
  const rows = allSortedData.value
  const isSubcat = props.groupBy === 'sub_category'

  const baseCols = (row) => {
    const o = { 'Commercial category': row.commercial_category_name ?? '' }
    if (isSubcat) o['Subcategory'] = row.sub_category_name ?? ''
    return o
  }

  const comps = visibleCompetitors.value
  if (!comps.length) {
    return {
      filename: 'blended_pi.xlsx',
      sheets: [{
        name: 'Blended PI',
        rows: rows.map(row => ({
          ...baseCols(row),
          'Blended PI': row.blended_pi ?? null,
          'Total': row.total_product_count,
          'Eligible': row.eligible_product_count,
        })),
      }],
    }
  }

  const sheets = comps.map(comp => ({
    name: comp,
    rows: rows.map(row => {
      const pi = row.competitor_blended_pis?.[comp] ?? null
      const used = row.competitor_used_counts?.[comp] ?? 0
      const mapped = row.competitor_mapped_counts?.[comp] ?? 0
      const total = row.total_product_count || 0
      const eligible = row.eligible_product_count || 0
      return {
        ...baseCols(row),
        'Blended PI': pi,
        'Total': total,
        'Eligible': eligible,
        'Used': used,
        'Mapped': mapped,
        'Mapping %': total ? Math.round((mapped / total) * 100) : null,
        'Utilization %': eligible ? Math.round((used / eligible) * 100) : null,
      }
    }),
  }))

  return { filename: 'blended_pi.xlsx', sheets }
}
</script>
