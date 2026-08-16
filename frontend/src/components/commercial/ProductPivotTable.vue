<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden flex flex-col relative">
    <!-- Header -->
    <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2.5 flex-wrap shrink-0">
      <div class="flex items-center gap-2 shrink-0">
        <h2 class="text-subheading font-bold text-grey-900 tracking-tightish">Product detail</h2>
        <span class="text-micro font-semibold tabular-nums text-grey-500 bg-grey-100 px-2 py-0.5 rounded-full">{{ total.toLocaleString() }}</span>
      </div>
      <!-- Search -->
      <div class="relative flex-1 min-w-[180px]">
        <SearchIcon class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-grey-400 pointer-events-none" />
        <input
          ref="searchInput"
          v-model="search"
          type="text"
          placeholder="Search products    /"
          aria-keyshortcuts="/"
          class="w-full pl-8 pr-7 py-1.5 text-body border border-grey-200 rounded-lg bg-grey-50 focus:bg-white focus:border-brand-primary focus:ring-2 focus:ring-brand-lightest outline-none transition-all duration-150"
        />
        <button
          v-if="search"
          class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-grey-400 hover:text-grey-700 hover:bg-grey-100 transition-colors"
          aria-label="Clear search"
          @click="search = ''"
        ><X class="w-3.5 h-3.5" /></button>
      </div>
      <!-- Needs Action Only toggle -->
      <button
        type="button"
        :aria-pressed="needsActionOnly"
        class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-caption font-medium transition-colors shrink-0"
        :class="needsActionOnly
          ? 'border-brand-primary bg-brand-50 text-brand-primary'
          : 'border-grey-200 bg-white text-grey-600 hover:border-grey-300'"
        @click="$emit('toggleNeedsAction', !needsActionOnly)"
      >
        <ListFilter class="w-3.5 h-3.5" /> Needs action
      </button>
      <!-- Density segmented control -->
      <div class="inline-flex items-center rounded-lg border border-grey-200 bg-grey-50 p-0.5 shrink-0 text-caption font-medium" role="group" aria-label="Table density">
        <button
          class="px-2.5 py-1 rounded-md transition-colors"
          :class="!compactMode ? 'bg-white text-grey-900 shadow-sm' : 'text-grey-500 hover:text-grey-700'"
          @click="compactMode && $emit('toggle-compact')"
        >Full</button>
        <button
          class="px-2.5 py-1 rounded-md transition-colors"
          :class="compactMode ? 'bg-white text-grey-900 shadow-sm' : 'text-grey-500 hover:text-grey-700'"
          @click="!compactMode && $emit('toggle-compact')"
        >PI only</button>
      </div>
      <ExportButton :fetcher="exportData" label="Export Excel" filename="Products_Price_Position.xlsx" class="shrink-0" />
    </div>

    <!-- Refreshing indicator (in-place refetch on filter/sort/search) -->
    <div v-if="busy" class="h-[2px] bg-brand-lightest overflow-hidden shrink-0" role="status" aria-label="Updating results">
      <div class="h-full w-full bg-brand-primary animate-indeterminate"></div>
    </div>

    <!-- Table -->
    <div ref="tableContainerRef" class="overflow-auto flex-1 min-h-0" :class="busy ? 'opacity-60 transition-opacity duration-200' : 'transition-opacity duration-200'">
      <table class="w-full border-separate border-spacing-0">
        <!-- Grouped header: fixed cols + one group per competitor -->
        <thead>
          <!-- Row 1: group labels -->
          <tr class="bg-grey-100">
            <th
              :colspan="frozenColsCount"
              class="px-3 py-1.5 border-b border-r border-grey-200 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide whitespace-nowrap bg-grey-100"
              style="position: sticky; top: 0; z-index: 40;"
            >Product Info</th>
            <th
              :colspan="nonFrozenFixedCount"
              class="px-3 py-1.5 border-b border-r border-grey-200 bg-grey-100 sticky top-0 z-40"
            ></th>
            <th
              v-for="comp in competitors"
              :key="comp"
              :class="['px-3 py-1.5 border-b border-r border-grey-200 text-center text-caption font-semibold text-grey-700 uppercase tracking-wide whitespace-nowrap sticky top-0 z-40', compIdx(comp) % 2 ? 'bg-[#EFEFEF]' : 'bg-grey-100']"
              :colspan="compactMode ? 1 : 2"
            ><span class="inline-flex items-center gap-1 justify-center"><CompetitorLogo :name="comp" /> {{ comp }}</span></th>
            <th class="px-2 py-1.5 border-b border-grey-200 w-9 sticky top-0 z-40 bg-grey-100"></th>
          </tr>
          <!-- Row 2: column headers -->
          <tr class="bg-grey-50">
            <th
              v-for="col in fixedCols"
              :key="col.key"
              :style="frozenThStyle(col)"
              :class="[
                'px-3 py-2 text-left text-caption font-semibold uppercase tracking-wide cursor-pointer hover:text-grey-900 border-b border-r border-grey-200 whitespace-nowrap select-none transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-lightest',
                col.frozen ? 'bg-grey-50' : '',
                sortKey === col.key ? 'border-b-2 border-brand-primary text-brand-primary' : 'text-grey-500',
              ]"
              tabindex="0"
              :aria-sort="sortKey === col.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
              @click="toggleSort(col.key)"
              @keydown.enter.prevent="toggleSort(col.key)"
              @keydown.space.prevent="toggleSort(col.key)"
            >
              <span class="inline-flex items-center gap-1">
                {{ col.label }}
                <component :is="sortKey === col.key ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ChevronsUpDown" class="w-3 h-3 transition-colors" :class="sortKey === col.key ? 'text-brand-primary' : 'text-grey-400'" />
              </span>
            </th>
            <template v-for="comp in competitors" :key="comp">
              <th v-if="!compactMode" class="px-3 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide border-b border-grey-200 whitespace-nowrap" :style="[row2StickyStyle, compIdx(comp) % 2 ? { background: '#F5F5F5' } : {}]">Price</th>
              <th
                class="px-3 py-2 text-right text-caption font-semibold uppercase tracking-wide cursor-pointer hover:text-grey-900 border-b border-r border-grey-200 whitespace-nowrap select-none transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-lightest"
                :class="sortKey === `${comp}_pi` ? 'border-b-2 border-brand-primary text-brand-primary' : 'text-grey-500'"
                :style="[row2StickyStyle, compIdx(comp) % 2 ? { background: '#F5F5F5' } : {}]"
                tabindex="0"
                :aria-sort="sortKey === `${comp}_pi` ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
                @click="toggleSort(`${comp}_pi`)"
                @keydown.enter.prevent="toggleSort(`${comp}_pi`)"
                @keydown.space.prevent="toggleSort(`${comp}_pi`)"
              >
                <span class="inline-flex items-center gap-1 justify-end">
                  PI
                  <component :is="sortKey === `${comp}_pi` ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ChevronsUpDown" class="w-3 h-3" :class="sortKey === `${comp}_pi` ? 'text-brand-primary' : 'text-grey-400'" />
                </span>
              </th>
            </template>
            <th class="px-2 py-2 border-b border-grey-200 w-9" :style="row2StickyStyle"></th>
          </tr>
        </thead>

        <tbody class="stagger-rows-fade">
          <tr
            v-for="row in data"
            :key="row.product_id"
            class="border-b border-grey-100 hover:bg-brand-50/70 transition-colors duration-150"
          >
            <!-- Product (frozen) -->
            <td class="px-3 py-2 border-r border-grey-100" :style="frozenTdStyle(fixedCols[0])" style="width: 200px; min-width: 200px">
              <button
                type="button"
                class="block w-full text-left text-body text-grey-900 truncate font-medium hover:text-brand-primary transition-colors"
                :title="`${row.product_name}: view FP × competitor pricing`"
                @click="openDetail(row)"
              >{{ row.product_name }}</button>
              <div class="flex items-center gap-1 mt-0.5 flex-wrap">
                <span v-if="row.eligible_product" class="inline-block px-1.5 py-px rounded-full text-micro font-medium bg-green-50 text-green-700 leading-tight">Eligible</span>
              </div>
            </td>
            <!-- Tier (frozen) -->
            <td class="px-3 py-2 border-r border-grey-100" :style="frozenTdStyle(fixedCols[1])" style="width: 80px; min-width: 80px"><TierBadge :tier="row.global_tier" /></td>
            <!-- Action (frozen) -->
            <td class="px-3 py-2 border-r border-grey-100" :style="frozenTdStyle(fixedCols[2])" style="width: 120px; min-width: 120px">
              <div class="flex items-center gap-1 flex-wrap">
                <span
                  v-for="(count, action) in effectiveActionCounts(row)"
                  :key="action"
                  class="inline-flex items-center gap-0.5 px-1.5 py-px rounded-full font-bold leading-tight whitespace-nowrap"
                  style="font-size: 10px;"
                  :style="ACTION_STYLE[action]"
                >{{ ACTION_SHORT[action] || action }} ×{{ count }}</span>
              </div>
            </td>
            <!-- BF Price — editable (frozen, last) -->
            <td
              class="px-3 py-2 text-right"
              :style="[frozenTdStyle(fixedCols[3]), { width: '100px', minWidth: '100px', borderRight: '2px solid #E5E7EB', boxShadow: '2px 0 6px -2px rgba(40,16,48,0.12)', background: flashId === row.product_id ? '#dcfce7' : 'white', transition: 'background-color 0.7s' }]"
            >
              <div class="inline-flex flex-col items-end">
                <!-- Regular price (BQ): shown struck-through when above sale -->
                <span
                  v-if="displayRegularPrice(row) != null && displayRegularPrice(row) !== displaySalePrice(row)"
                  class="text-grey-400 font-mono line-through"
                  style="font-size: 10px;"
                >{{ displayRegularPrice(row).toFixed(2) }}</span>
                <!-- Sale price (BQ) -->
                <span class="text-grey-900 font-mono">{{ displaySalePrice(row)?.toFixed(2) ?? '—' }}</span>
              </div>
            </td>
            <!-- Worst PI (dynamic: max across visible competitors) -->
            <td
              class="px-3 py-2 border-r border-grey-100 text-right font-mono font-bold"
              :class="[piBgClass(effectiveWorstPI(row)), piTextClass(effectiveWorstPI(row))]"
            >
              <div class="flex flex-col items-end gap-0.5">
                <span><span v-if="effectiveWorstPI(row) != null" class="text-[10px] mr-0.5 opacity-70">{{ piArrow(effectiveWorstPI(row)) }}</span>{{ effectiveWorstPI(row)?.toFixed(2) ?? '—' }}</span>
                <button
                  v-if="worstCompetitorName(row)"
                  class="text-micro text-grey-400 hover:text-brand-primary transition-colors font-sans font-normal"
                  @click.stop="scrollToCompetitor(worstCompetitorName(row))"
                >vs {{ worstCompetitorName(row) }}</button>
              </div>
            </td>
            <!-- Score (combined_score_global) -->
            <td class="px-3 py-2 border-r border-grey-100 text-right text-body text-grey-600 font-mono">{{ row.weighted_score?.toFixed(3) ?? '—' }}</td>
            <!-- Revenue -->
            <td class="px-3 py-2 border-r border-grey-100 text-right text-body text-grey-600 font-mono" :title="row.total_revenue != null ? row.total_revenue.toLocaleString() + ' EGP' : ''">{{ formatRevenue(row.total_revenue) }}</td>

            <!-- Competitor columns -->
            <template v-for="comp in competitors" :key="comp">
              <td v-if="!compactMode" class="px-3 py-2 text-right text-body text-grey-600 font-mono whitespace-nowrap" :title="`${comp} price`" :style="compIdx(comp) % 2 ? { background: '#FAFAFA' } : {}">
                <div class="flex flex-col items-end gap-0.5">
                  <span>{{ row[`${comp}_price`]?.toFixed(2) ?? '—' }}</span>
                  <span
                    v-if="row[`${comp}_action`]"
                    class="inline-block px-1.5 py-px rounded-full font-bold leading-tight"
                    style="font-size: 9px;"
                    :style="compBadge(row, comp).style"
                  >{{ compBadge(row, comp).label }}</span>
                </div>
              </td>
              <td
                class="px-3 py-2 text-right font-mono font-bold border-r border-grey-100 whitespace-nowrap"
                :title="`${comp} PI`"
                :style="compIdx(comp) % 2 ? { background: '#FAFAFA' } : {}"
                :class="row[`${comp}_pi`] != null
                  ? [piBgClass(row[`${comp}_pi`]), piTextClass(row[`${comp}_pi`])]
                  : 'text-grey-300'"
              >
                <div class="flex flex-col items-end gap-0.5">
                  <span><span v-if="row[`${comp}_pi`] != null" class="text-[10px] mr-0.5 opacity-70">{{ piArrow(row[`${comp}_pi`]) }}</span>{{ row[`${comp}_pi`]?.toFixed(2) ?? '—' }}</span>
                  <span
                    v-if="compactMode && row[`${comp}_action`]"
                    class="inline-block px-1.5 py-px rounded-full font-bold leading-tight"
                    style="font-size: 9px;"
                    :style="compBadge(row, comp).style"
                  >{{ compBadge(row, comp).label }}</span>
                </div>
              </td>
            </template>

            <!-- Saving indicator -->
            <td class="px-2 py-2 text-center w-9">
              <Loader2 v-if="saving === row.product_id" class="w-3.5 h-3.5 animate-spin text-brand-primary mx-auto" />
            </td>
          </tr>
        </tbody>
      </table>
      <EmptyState v-if="!data.length" :icon="SearchIcon" title="No products found" message="No products match your search or filters." :hint="emptyHint" />
    </div>

    <!-- Pagination -->
    <div class="px-4 py-2.5 border-t border-grey-100 flex items-center justify-between bg-grey-50 gap-3 shrink-0">
      <span class="text-caption text-grey-500 shrink-0 tabular-nums">
        Showing <span class="font-medium text-grey-700">{{ ((page - 1) * pageSize + 1).toLocaleString() }}-{{ Math.min(page * pageSize, total).toLocaleString() }}</span> of {{ total.toLocaleString() }}
      </span>
      <div v-if="totalPages > 1" class="flex items-center gap-1">
        <button :disabled="page <= 1" class="inline-flex items-center gap-1 text-caption pl-2 pr-2.5 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 disabled:hover:bg-white transition-colors" @click="$emit('page', page - 1)"><ChevronLeft class="w-3.5 h-3.5" /> Prev</button>
        <template v-for="pg in pageNumbers" :key="pg ?? ('e-' + Math.random())">
          <span v-if="pg === null" class="text-caption text-grey-400 px-1">…</span>
          <button v-else class="text-caption w-8 py-1 rounded-lg border tabular-nums transition-colors"
            :class="pg === page ? 'bg-brand-primary text-white border-brand-primary font-bold' : 'border-grey-200 bg-white hover:bg-grey-100 text-grey-700'"
            @click="$emit('page', pg)"
          >{{ pg }}</button>
        </template>
        <button :disabled="page >= totalPages" class="inline-flex items-center gap-1 text-caption pl-2.5 pr-2 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 disabled:hover:bg-white transition-colors" @click="$emit('page', page + 1)">Next <ChevronRight class="w-3.5 h-3.5" /></button>
      </div>
    </div>

    <!-- Per-product FP × competitor pricing matrix -->
    <ProductPricingDetailModal :product-id="detailProductId" @close="detailProductId = null" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import TierBadge from '../shared/TierBadge.vue'
import EmptyState from '../shared/EmptyState.vue'
import ExportButton from '../shared/ExportButton.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import ProductPricingDetailModal from './ProductPricingDetailModal.vue'
import { Search as SearchIcon, Loader2, X, ChevronLeft, ChevronRight, ListFilter, ArrowUp, ArrowDown, ChevronsUpDown } from 'lucide-vue-next'
import { piTextClass, piBgClass, piArrow } from '../../utils/piColor'
import { useCommercialStore } from '../../stores/commercial'
import { useFiltersStore } from '../../stores/filters'
import { commercialApi } from '../../api/client'
import { asDownload } from '../../utils/workbook'

const props = defineProps({
  data: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 },
  competitors: { type: Array, default: () => [] },
  needsActionOnly: { type: Boolean, default: false },
  compactMode: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits(['page', 'toggleNeedsAction', 'toggle-compact'])

const store = useCommercialStore()
const filters = useFiltersStore()

const emptyHint = computed(() => {
  if (!filters.hasActiveFilters) return ''
  const names = []
  if (filters.mainCategory.length) names.push('Category')
  if (filters.subCategory.length) names.push('Subcategory')
  if (filters.globalTier.length) names.push('Tier')
  if (filters.brand.length) names.push('Brand')
  if (filters.actionType.length) names.push('Action')
  if (filters.competitor.length) names.push('Competitor')
  if (names.length === 0) return 'Try adjusting your filters'
  return `Try clearing ${names.slice(0, 2).join(' or ')} filters`
})

const fixedCols = [
  { key: 'product_name',   label: 'Product',  width: 200, frozen: true  },
  { key: 'global_tier',    label: 'Tier',     width: 80,  frozen: true  },
  { key: 'action_type',    label: 'Action',   width: 120, frozen: true  },
  { key: 'bf_sale_price',  label: 'BF Price', width: 100, frozen: true  },
  { key: 'worst_pi',       label: 'Worst PI', width: 80,  frozen: false },
  { key: 'weighted_score', label: 'Score',    width: 70,  frozen: false },
  { key: 'total_revenue',  label: 'Revenue',  width: 80,  frozen: false },
]

const frozenOffset = (() => {
  const map = {}
  let left = 0
  for (const col of fixedCols) {
    if (col.frozen) { map[col.key] = left; left += col.width }
  }
  return map
})()

const frozenColsCount = fixedCols.filter(c => c.frozen).length
const nonFrozenFixedCount = fixedCols.filter(c => !c.frozen).length
const row2StickyStyle = { position: 'sticky', top: '29px', zIndex: 40, background: '#F9FAFB' }

function frozenThStyle(col) {
  const style = { position: 'sticky', top: '29px', zIndex: col.frozen ? 41 : 40, background: '#F9FAFB' }
  if (col.frozen) style.left = frozenOffset[col.key] + 'px'
  return style
}

function frozenTdStyle(col) {
  if (!col.frozen) return {}
  return { position: 'sticky', left: frozenOffset[col.key] + 'px', zIndex: 10, background: 'white' }
}

function compIdx(comp) { return props.competitors.indexOf(comp) }

const tableContainerRef = ref(null)

// Product pricing-detail modal (FP × competitor matrix)
const detailProductId = ref(null)
function openDetail(row) {
  detailProductId.value = row.product_id
}

function worstCompetitorName(row) {
  let best = null, bestVal = -Infinity
  for (const c of props.competitors) {
    if (row[`${c}_action`] !== 'Complete') continue
    const pi = row[`${c}_pi`]
    if (pi != null && pi > bestVal) { bestVal = pi; best = c }
  }
  return best
}

function scrollToCompetitor(comp) {
  const idx = props.competitors.indexOf(comp)
  if (idx < 0 || !tableContainerRef.value) return
  tableContainerRef.value.scrollTo({ left: 500 + idx * 180, behavior: 'smooth' })
}

const sortKey = computed(() => store.sortBy)
const sortDir = computed(() => store.sortDir)
const totalPages = computed(() => Math.ceil(props.total / props.pageSize))

const pageNumbers = computed(() => {
  const total = totalPages.value
  const cur = props.page
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pageSet = new Set([1, total, cur, cur - 1, cur + 1].filter(p => p >= 1 && p <= total))
  const sorted = [...pageSet].sort((a, b) => a - b)
  const result = []
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) result.push(null)
    result.push(sorted[i])
  }
  return result
})

function toggleSort(key) {
  const newDir = sortKey.value === key && sortDir.value === 'desc' ? 'asc' : 'desc'
  store.setSort(key, newDir)
}

// Search with debounce
const search = ref(store.search || '')
watchDebounced(search, (val) => { store.setSearch(val) }, { debounce: 400 })

// Press "/" anywhere (outside a field) to jump to product search
const searchInput = ref(null)
function onGlobalKey(e) {
  if (e.key !== '/') return
  const el = document.activeElement
  if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return
  e.preventDefault()
  searchInput.value?.focus()
  searchInput.value?.select?.()
}
onMounted(() => window.addEventListener('keydown', onGlobalKey))
onUnmounted(() => window.removeEventListener('keydown', onGlobalKey))

// Price editing was removed — prices are read-only (sourced from BigQuery).
// `saving` / `flashId` are retained inert so the table's spinner column and
// row-flash style keep their bindings without restructuring the table.
const saving = ref(null)
const flashId = ref(null)

// Normalize "Review AI Match" → "Review Match" on the fly
function normAction(action) {
  return action === 'Review AI Match' ? 'Review Match' : action
}

// Action column: multi-badge styles & short labels (includes Complete)
// Mirrors shared/ActionBadge.vue (the single source). "Needs Price Update" uses
// brand magenta, not blue, so it never collides with the PI cheaper-tail in the grid.
const ACTION_STYLE = {
  'Needs Mapping':      'background:#FEE2E2;color:#DC2626',
  'Review Match':       'background:#FEF3C7;color:#D97706',
  'Needs Price Update': 'background:#FDF2F9;color:#a3007c',
  'Complete':           'background:#D1FAE5;color:#059669',
}
const ACTION_SHORT = {
  'Needs Mapping':      'Unmapped',
  'Review Match':       'Review Match',
  'Needs Price Update': 'Outdated',
  'Complete':           'Complete',
}

// Dynamic action counts from visible competitors only
function effectiveActionCounts(row) {
  const counts = {}
  for (const comp of props.competitors) {
    const action = normAction(row[`${comp}_action`] || 'Complete')
    counts[action] = (counts[action] || 0) + 1
  }
  return counts
}

// Dynamic worst PI from visible competitors only (used/complete only)
function effectiveWorstPI(row) {
  const pis = props.competitors
    .filter(c => row[`${c}_action`] === 'Complete')
    .map(c => row[`${c}_pi`])
    .filter(v => v != null)
  return pis.length > 0 ? Math.max(...pis) : null
}

// BF Price display: prefer catalog API prices (now_*), fall back to BigQuery prices
function displaySalePrice(row) {
  return row.now_sale_price ?? row.bf_sale_price
}
function displayRegularPrice(row) {
  return row.now_price ?? row.bf_regular_price
}

// Per-competitor action badge
const COMP_ACTION_MAP = {
  'Needs Mapping':      { label: 'Unmapped', style: 'background:#FEE2E2;color:#DC2626' },
  'Review Match':       { label: 'Review Match', style: 'background:#FEF3C7;color:#D97706' },
  'Needs Price Update': { label: 'Outdated', style: 'background:#FDF2F9;color:#a3007c' },
  'Complete':           { label: 'Used', style: 'background:#D1FAE5;color:#059669' },
}
// Per-competitor badge: resolves label + style from action + eligibility +
// classification (so 'Complete' splits into Used/Updated, and the unmapped
// case splits into the decided "No Match" vs the weak "No Potential Match").
// Single-accent + semantic only: no blue/teal (they would collide with the PI
// cheaper-tail). used = green, updated = lighter green (same "fresh" family),
// outdated = brand magenta (matches ActionBadge "Needs Price Update").
const BADGE_STYLE = {
  used:         'background:#D1FAE5;color:#059669',  // green        — eligible + fresh price
  updated:      'background:#ECFDF5;color:#047857',  // light green  — fresh price, not eligible
  no_match:     'background:#F3F4F6;color:#6B7280',  // grey         — master-data decided no match (resolved)
  no_potential: 'background:#FEE2E2;color:#DC2626',  // red          — only weak candidates (<0.85)
  unmapped:     'background:#FEE2E2;color:#DC2626',  // red          — fallback
  review:       'background:#FEF3C7;color:#D97706',  // amber        — strong AI candidate to review
  outdated:     'background:#FDF2F9;color:#a3007c',  // brand        — mapped, stale price
}
function compBadge(row, comp) {
  const raw = row[`${comp}_action`]
  if (!raw) return { label: '', style: '' }
  const action = normAction(raw)
  const cls = row[`${comp}_classification`] || ''
  if (action === 'Complete') {
    return row.eligible_product
      ? { label: 'Used', style: BADGE_STYLE.used }
      : { label: 'Updated', style: BADGE_STYLE.updated }
  }
  if (action === 'Needs Mapping') {
    if (cls.endsWith('No Match')) return { label: 'No Match', style: BADGE_STYLE.no_match }
    if (cls.includes('No Potential')) return { label: 'No Potential', style: BADGE_STYLE.no_potential }
    return { label: 'Unmapped', style: BADGE_STYLE.unmapped }
  }
  if (action === 'Review Match') return { label: 'Review Match', style: BADGE_STYLE.review }
  if (action === 'Needs Price Update') {
    const days = row[`${comp}_days_stale`]
    return { label: days != null ? `Outdated ${days}d` : 'Outdated', style: BADGE_STYLE.outdated }
  }
  const m = COMP_ACTION_MAP[action]
  return { label: m?.label ?? action, style: m?.style ?? '' }
}

function formatRevenue(val) {
  if (val == null) return '—'
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`
  if (val >= 1_000) return `${(val / 1_000).toFixed(0)}K`
  return val.toFixed(0)
}

// Built by the backend — see utils/workbook.js. Two things change besides the
// styling: the file now holds EVERY product in scope rather than the 50 on the
// current page, and the sort/search on screen are passed through so it comes out
// in the order you are looking at.
function exportData() {
  return asDownload(
    commercialApi.workbook({
      ...store._params(),
      sheets: 'products',
      competitors: props.competitors.join(','),
      sort_by: store.sortBy,
      sort_dir: store.sortDir,
      ...(store.search ? { search: store.search } : {}),
    }),
    'Products_Price_Position.xlsx',
  )
}
</script>

<style scoped>
.slide-up-enter-active, .slide-up-leave-active { transition: opacity 0.2s, transform 0.2s; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(8px); }
</style>
