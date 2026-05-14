<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden flex flex-col relative">
    <!-- Header -->
    <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-3 flex-wrap shrink-0">
      <div class="flex items-center gap-2 shrink-0">
        <span class="text-subheading font-bold text-grey-900">Product Detail</span>
        <span class="text-caption text-grey-500 bg-grey-100 px-2 py-0.5 rounded-full">{{ total.toLocaleString() }}</span>
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
      <!-- Needs Action Only toggle -->
      <label class="flex items-center gap-1.5 shrink-0 cursor-pointer select-none">
        <input
          type="checkbox"
          :checked="needsActionOnly"
          class="w-3.5 h-3.5 rounded border-grey-300 accent-brand-primary cursor-pointer"
          @change="$emit('toggleNeedsAction', $event.target.checked)"
        />
        <span class="text-body text-grey-700">Needs Action Only</span>
      </label>
      <ExportButton :fetcher="exportData" filename="pivot_products.csv" class="shrink-0" />
      <button
        class="text-caption px-2.5 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 shrink-0 transition-colors"
        @click="$emit('toggle-compact')"
      >{{ compactMode ? 'Full View' : 'PI Only' }}</button>
    </div>

    <!-- Table -->
    <div ref="tableContainerRef" class="overflow-auto flex-1 min-h-0">
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
                'px-3 py-2 text-left text-caption font-semibold uppercase tracking-wide cursor-pointer hover:text-grey-900 border-b border-r border-grey-200 whitespace-nowrap select-none transition-colors',
                col.frozen ? 'bg-grey-50' : '',
                sortKey === col.key ? 'border-b-2 border-brand-primary text-brand-primary' : 'text-grey-500',
              ]"
              :aria-sort="sortKey === col.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
              @click="toggleSort(col.key)"
            >
              <span class="inline-flex items-center gap-1">
                {{ col.label }}
                <span class="text-[10px] transition-colors" :class="sortKey === col.key ? 'text-brand-primary' : 'text-grey-400'">
                  {{ sortKey === col.key ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}
                </span>
              </span>
            </th>
            <template v-for="comp in competitors" :key="comp">
              <th v-if="!compactMode" class="px-3 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide border-b border-grey-200 whitespace-nowrap" :style="[row2StickyStyle, compIdx(comp) % 2 ? { background: '#F5F5F5' } : {}]">Price</th>
              <th
                class="px-3 py-2 text-right text-caption font-semibold uppercase tracking-wide cursor-pointer hover:text-grey-900 border-b border-r border-grey-200 whitespace-nowrap select-none transition-colors"
                :class="sortKey === `${comp}_pi` ? 'border-b-2 border-brand-primary text-brand-primary' : 'text-grey-500'"
                :style="[row2StickyStyle, compIdx(comp) % 2 ? { background: '#F5F5F5' } : {}]"
                @click="toggleSort(`${comp}_pi`)"
              >
                <span class="inline-flex items-center gap-1 justify-end">
                  PI
                  <span class="text-[10px]" :class="sortKey === `${comp}_pi` ? 'text-brand-primary' : 'text-grey-400'">
                    {{ sortKey === `${comp}_pi` ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}
                  </span>
                </span>
              </th>
            </template>
            <th class="px-2 py-2 border-b border-grey-200 w-9" :style="row2StickyStyle"></th>
          </tr>
        </thead>

        <tbody>
          <tr
            v-for="row in data"
            :key="row.product_id"
            class="border-b border-grey-100 hover:bg-brand-50 transition-colors"
          >
            <!-- Product (frozen) -->
            <td class="px-3 py-2 border-r border-grey-100" :style="frozenTdStyle(fixedCols[0])" style="width: 200px; min-width: 200px">
              <div class="text-body text-grey-900 truncate font-medium" :title="row.product_name">{{ row.product_name }}</div>
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
              :style="[frozenTdStyle(fixedCols[3]), { width: '100px', minWidth: '100px', borderRight: '2px solid #d1d5db', boxShadow: '2px 0 6px -2px rgba(0,0,0,0.12)', background: flashId === row.product_id ? '#dcfce7' : 'white', transition: 'background-color 0.7s' }]"
            >
              <div v-if="editingId === row.product_id" class="flex items-center justify-end gap-1">
                <input
                  ref="editInput"
                  type="number" step="0.01"
                  class="w-20 text-right border-2 border-brand-primary rounded-lg px-2 py-1 text-body outline-none bg-white font-mono"
                  v-model.number="editValue"
                  @keyup.enter="saveEdit(row)"
                  @keyup.escape="cancelEdit"
                />
                <button class="px-2 py-1 bg-brand-primary text-white rounded-lg text-caption font-bold hover:bg-brand-dark transition-colors" @click="saveEdit(row)">✓</button>
                <button class="px-2 py-1 bg-grey-100 text-grey-600 rounded-lg text-caption hover:bg-grey-200 transition-colors" @click="cancelEdit">✕</button>
              </div>
              <div
                v-else
                class="inline-flex flex-col items-end cursor-pointer group/edit"
                @click="startEdit(row)"
              >
                <!-- Regular price: catalog now_price if available, else bf_regular_price -->
                <span
                  v-if="displayRegularPrice(row) != null && displayRegularPrice(row) !== displaySalePrice(row)"
                  class="text-grey-400 font-mono line-through"
                  style="font-size: 10px;"
                >{{ displayRegularPrice(row).toFixed(2) }}</span>
                <span class="inline-flex items-center gap-1">
                  <!-- Sale price: catalog now_sale_price if available, else bf_sale_price -->
                  <span class="text-grey-900 font-mono group-hover/edit:text-brand-primary transition-colors">
                    {{ displaySalePrice(row)?.toFixed(2) ?? '—' }}
                  </span>
                  <svg class="w-3 h-3 text-grey-300 group-hover/edit:text-brand-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
                </span>
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
                    :style="compActionStyle(row[`${comp}_action`])"
                  >{{ compActionLabel(row[`${comp}_action`], row[`${comp}_days_stale`]) }}</span>
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
                    :style="compActionStyle(row[`${comp}_action`])"
                  >{{ compActionLabel(row[`${comp}_action`], row[`${comp}_days_stale`]) }}</span>
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

    <!-- Price change confirmation banner -->
    <Transition name="slide-up">
      <div v-if="confirmPending" class="absolute inset-x-4 bottom-14 z-50 bg-amber-50 border border-amber-300 rounded-lg px-4 py-3 flex items-center justify-between gap-3 shadow-lg">
        <span class="text-body text-amber-800">
          <b>{{ (confirmPending.pct * 100).toFixed(0) }}% change:</b>
          {{ confirmPending.oldPrice?.toFixed(2) }} → {{ confirmPending.newPrice?.toFixed(2) }}
        </span>
        <div class="flex gap-2 shrink-0">
          <button class="px-3 py-1.5 bg-amber-600 text-white rounded-lg text-caption font-bold hover:bg-amber-700" @click="confirmSave">Confirm</button>
          <button class="px-3 py-1.5 bg-white border rounded-lg text-caption hover:bg-grey-50" @click="confirmPending = null">Cancel</button>
        </div>
      </div>
    </Transition>

    <!-- Pagination -->
    <div class="px-4 py-2.5 border-t border-grey-100 flex items-center justify-between bg-grey-50 gap-3 shrink-0">
      <span class="text-caption text-grey-500 shrink-0">
        Showing {{ ((page - 1) * pageSize + 1).toLocaleString() }}–{{ Math.min(page * pageSize, total).toLocaleString() }} of {{ total.toLocaleString() }}
      </span>
      <div v-if="totalPages > 1" class="flex items-center gap-1">
        <button :disabled="page <= 1" class="text-caption px-2.5 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 transition-colors" @click="$emit('page', page - 1)">← Prev</button>
        <template v-for="pg in pageNumbers" :key="pg ?? ('e-' + Math.random())">
          <span v-if="pg === null" class="text-caption text-grey-400 px-1">…</span>
          <button v-else class="text-caption w-8 py-1 rounded-lg border transition-colors"
            :class="pg === page ? 'bg-brand-primary text-white border-brand-primary font-bold' : 'border-grey-200 bg-white hover:bg-grey-100 text-grey-700'"
            @click="$emit('page', pg)"
          >{{ pg }}</button>
        </template>
        <button :disabled="page >= totalPages" class="text-caption px-2.5 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 transition-colors" @click="$emit('page', page + 1)">Next →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import TierBadge from '../shared/TierBadge.vue'
import EmptyState from '../shared/EmptyState.vue'
import ExportButton from '../shared/ExportButton.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import { Search as SearchIcon, Loader2 } from 'lucide-vue-next'
import { piTextClass, piBgClass, piArrow } from '../../utils/piColor'
import { useCommercialStore } from '../../stores/commercial'
import { useFiltersStore } from '../../stores/filters'
import { useToast } from '../../composables/useToast'

const props = defineProps({
  data: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 },
  competitors: { type: Array, default: () => [] },
  needsActionOnly: { type: Boolean, default: false },
  compactMode: { type: Boolean, default: false },
})

const emit = defineEmits(['page', 'toggleNeedsAction', 'toggle-compact'])

const store = useCommercialStore()
const filters = useFiltersStore()
const toast = useToast()

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

const confirmPending = ref(null)

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

// Inline price edit
const editingId = ref(null)
const editValue = ref(null)
const saving = ref(null)
const editInput = ref(null)
const flashId = ref(null)

function startEdit(row) {
  if (saving.value) return
  editingId.value = row.product_id
  editValue.value = displaySalePrice(row)
  nextTick(() => {
    const el = Array.isArray(editInput.value) ? editInput.value[0] : editInput.value
    el?.focus()
    el?.select()
  })
}

function cancelEdit() {
  editingId.value = null
  editValue.value = null
}

async function saveEdit(row) {
  if (saving.value) return
  const nowPrice = editValue.value !== row.bf_sale_price ? editValue.value : undefined
  if (nowPrice === undefined) { cancelEdit(); return }
  const oldPrice = displaySalePrice(row)
  if (oldPrice && Math.abs((nowPrice - oldPrice) / oldPrice) > 0.10) {
    editingId.value = null
    confirmPending.value = { row, newPrice: nowPrice, oldPrice, pct: Math.abs((nowPrice - oldPrice) / oldPrice) }
    return
  }
  await doSave(row, nowPrice, oldPrice)
}

async function doSave(row, nowPrice, oldPrice) {
  saving.value = row.product_id
  editingId.value = null
  try {
    const result = await store.updateProductPrice(row.product_id, nowPrice, undefined)
    if (result.catalog_synced) {
      toast.success('Updated in BF Catalog', `${row.product_name}: ${oldPrice?.toFixed(2)} → ${nowPrice.toFixed(2)}`, {
        duration: 5000,
        action: { label: 'Undo', fn: () => { row.bf_sale_price = oldPrice; row.now_sale_price = null } },
      })
    } else {
      toast.warning('Saved locally (no catalog access)', result.catalog_error ? 'No write access to Catalog API' : 'Price saved in-memory only')
    }
    row.bf_sale_price = nowPrice
    flashId.value = row.product_id
    setTimeout(() => { if (flashId.value === row.product_id) flashId.value = null }, 2000)
  } catch (err) {
    toast.error('Update failed', err.response?.data?.error || err.message)
  } finally {
    saving.value = null
  }
}

async function confirmSave() {
  const { row, newPrice, oldPrice } = confirmPending.value
  confirmPending.value = null
  await doSave(row, newPrice, oldPrice)
}

// Normalize "Review AI Match" → "Review Match" on the fly
function normAction(action) {
  return action === 'Review AI Match' ? 'Review Match' : action
}

// Action column: multi-badge styles & short labels (includes Complete)
const ACTION_STYLE = {
  'Needs Mapping':      'background:#FEE2E2;color:#DC2626',
  'Review Match':       'background:#FEF3C7;color:#D97706',
  'Needs Price Update': 'background:#DBEAFE;color:#2563EB',
  'Complete':           'background:#D1FAE5;color:#059669',
}
const ACTION_SHORT = {
  'Needs Mapping':      'No Match',
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
  'Needs Mapping':      { label: 'No Match', style: 'background:#FEE2E2;color:#DC2626' },
  'Review Match':       { label: 'Review Match', style: 'background:#FEF3C7;color:#D97706' },
  'Needs Price Update': { label: 'Outdated', style: 'background:#DBEAFE;color:#2563EB' },
  'Complete':           { label: 'Used', style: 'background:#D1FAE5;color:#059669' },
}
function compActionLabel(action, daysStale) {
  const norm = normAction(action)
  const base = COMP_ACTION_MAP[norm]?.label ?? norm
  if (norm === 'Needs Price Update' && daysStale != null) return `${base} ${daysStale}d`
  return base
}
function compActionStyle(action) { return COMP_ACTION_MAP[normAction(action)]?.style ?? '' }

function formatRevenue(val) {
  if (val == null) return '—'
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`
  if (val >= 1_000) return `${(val / 1_000).toFixed(0)}K`
  return val.toFixed(0)
}

function exportData() {
  return props.data.map(row => {
    const out = {
      product_name: row.product_name,
      brand_name: row.brand_name,
      sub_category_name: row.sub_category_name,
      global_tier: row.global_tier,
      action_type: row.action_type,
      bf_sale_price: row.bf_sale_price,
      worst_pi: row.worst_pi,
      total_revenue: row.total_revenue,
    }
    for (const comp of props.competitors) {
      out[`${comp}_price`] = row[`${comp}_price`]
      out[`${comp}_pi`] = row[`${comp}_pi`]
    }
    return out
  })
}
</script>

<style scoped>
.slide-up-enter-active, .slide-up-leave-active { transition: opacity 0.2s, transform 0.2s; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(8px); }
</style>
