<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden flex flex-col">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-3 flex-wrap">
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
      <span class="text-micro px-2 py-0.5 rounded-full bg-red-50 text-red-500 font-medium shrink-0">Red rows = BF overpriced</span>

      <!-- Column toggle -->
      <div ref="colMenuRef" class="relative shrink-0">
        <button
          class="p-1.5 rounded-lg border border-grey-200 bg-grey-50 hover:bg-grey-100 text-grey-500 hover:text-grey-700 transition-colors"
          title="Toggle columns"
          @click="colMenuOpen = !colMenuOpen"
        >
          <Columns3 class="w-4 h-4" />
        </button>
        <Transition name="dropdown">
          <div v-if="colMenuOpen" class="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-grey-200 z-50 w-48 py-1">
            <label
              v-for="col in ALL_COLUMNS"
              :key="col.key"
              class="flex items-center gap-2 px-3 py-1.5 hover:bg-brand-50 cursor-pointer transition-colors text-body"
              :class="col.pinned ? 'opacity-50 cursor-default' : ''"
            >
              <input
                type="checkbox"
                :checked="visibleColKeys.includes(col.key)"
                :disabled="col.pinned"
                class="w-3.5 h-3.5 rounded border-grey-300 text-brand-primary accent-[var(--brand-primary)]"
                @change="toggleColumn(col.key)"
              />
              <span class="text-grey-700">{{ col.label }}</span>
            </label>
            <div class="border-t border-grey-100 px-3 py-1.5 mt-1">
              <button class="text-micro text-grey-500 hover:text-brand-primary font-medium" @click="resetColumns">Reset All</button>
            </div>
          </div>
        </Transition>
      </div>
    </div>
    <div class="overflow-auto flex-1 min-h-0">
      <table class="w-full">
        <thead class="sticky top-0 bg-grey-50 z-10">
          <tr>
            <!-- Select All -->
            <th class="px-3 py-2.5 border-b border-grey-200 w-9">
              <input
                type="checkbox"
                :checked="allSelected"
                :indeterminate.prop="someSelected"
                class="w-3.5 h-3.5 cursor-pointer accent-brand-primary"
                aria-label="Select all"
                @change="toggleSelectAll"
              />
            </th>
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-3 py-2.5 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide cursor-pointer hover:text-grey-900 border-b border-grey-200 whitespace-nowrap select-none transition-colors"
              :aria-sort="sortKey === col.key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
              @click="toggleSort(col.key)"
            >
              <span class="inline-flex items-center gap-1">
                {{ col.label }}
                <span
                  class="text-[10px] transition-colors"
                  :class="sortKey === col.key ? 'text-brand-primary' : 'text-grey-400'"
                >{{ sortKey === col.key ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}</span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in sortedData"
            :key="row.product_id"
            class="border-b border-grey-100 transition-colors"
            :class="[
              row.sale_PI != null && row.sale_PI < 0.90 ? 'bg-red-50 hover:bg-red-100' : 'hover:bg-brand-50',
              selectedIds.has(row.product_id) ? 'ring-1 ring-inset ring-brand-light' : '',
            ]"
          >
            <!-- Row checkbox -->
            <td class="px-3 py-2 w-9">
              <input
                type="checkbox"
                :checked="selectedIds.has(row.product_id)"
                class="w-3.5 h-3.5 cursor-pointer accent-brand-primary"
                :aria-label="`Select ${row.product_name}`"
                @change="toggleSelect(row.product_id)"
              />
            </td>
            <td class="px-3 py-2" style="max-width: 220px">
              <div class="text-body text-grey-900 truncate" :title="row.product_name">{{ row.product_name }}</div>
              <div class="flex items-center gap-1 mt-0.5 flex-wrap">
                <span v-if="row.eligible_product" class="inline-block px-1.5 py-px rounded-full text-micro font-medium bg-green-50 text-green-700 leading-tight">Eligible</span>
                <span v-if="row.used_product" class="inline-block px-1.5 py-px rounded-full text-micro font-medium bg-brand-50 text-brand-darkest leading-tight">Used</span>
                <span v-if="row.action_type && row.action_type !== 'Complete'" class="inline-block px-1.5 py-px rounded-full text-micro font-medium bg-amber-50 text-amber-700 leading-tight">{{ row.action_type }}</span>
              </div>
            </td>
            <td v-if="visibleSet.has('brand_name')" class="px-3 py-2 text-body text-grey-500 truncate" style="max-width: 120px">
              <span class="inline-flex items-center gap-1">
                {{ row.brand_name }}
                <img v-if="isBreadfast(row.brand_name)" src="/breadfast-logo.png" alt="BF" class="h-3.5 shrink-0" />
              </span>
            </td>
            <td v-if="visibleSet.has('bf_sale_price')" class="px-3 py-2 text-body text-grey-700 text-right font-mono">{{ row.bf_sale_price?.toFixed(2) }}</td>

            <!-- Now Price — editable -->
            <td v-if="visibleSet.has('now_price')" class="px-3 py-2 text-body text-right">
              <div v-if="editingId === row.product_id" class="flex items-center justify-end gap-1">
                <input
                  ref="nowPriceInput"
                  type="number"
                  step="0.01"
                  class="w-20 text-right border-2 border-brand-primary rounded-lg px-2 py-1 text-body outline-none bg-white font-mono"
                  v-model.number="editNowPrice"
                  @keyup.enter="saveEdit(row)"
                  @keyup.escape="cancelEdit"
                />
              </div>
              <div v-else-if="saving === row.product_id" class="inline-flex items-center gap-1 text-brand-primary text-caption">
                <Loader2 class="w-3 h-3 animate-spin" /> Saving...
              </div>
              <div
                v-else
                class="inline-flex items-center gap-1.5 cursor-pointer group/edit"
                @click="startEdit(row)"
              >
                <span class="text-grey-900 group-hover/edit:text-brand-primary font-mono transition-colors">{{ row.now_price?.toFixed(2) ?? '—' }}</span>
                <svg class="w-3 h-3 text-grey-300 group-hover/edit:text-brand-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
              </div>
            </td>

            <!-- Now Sale Price — editable -->
            <td v-if="visibleSet.has('now_sale_price')" class="px-3 py-2 text-body text-right">
              <div v-if="editingId === row.product_id" class="flex items-center justify-end gap-1">
                <input
                  type="number"
                  step="0.01"
                  class="w-20 text-right border-2 border-brand-primary rounded-lg px-2 py-1 text-body outline-none bg-white font-mono"
                  v-model.number="editNowSalePrice"
                  @keyup.enter="saveEdit(row)"
                  @keyup.escape="cancelEdit"
                />
                <button
                  class="px-2 py-1 bg-brand-primary text-white rounded-lg text-caption font-bold hover:bg-brand-dark transition-colors"
                  @click="saveEdit(row)"
                  title="Save (Enter)"
                >Save</button>
                <button
                  class="px-2 py-1 bg-grey-100 text-grey-600 rounded-lg text-caption hover:bg-grey-200 transition-colors"
                  @click="cancelEdit"
                  title="Cancel (Esc)"
                >Cancel</button>
              </div>
              <div
                v-else
                class="inline-flex items-center gap-1.5 cursor-pointer group/edit"
                :class="saving === row.product_id ? 'opacity-50' : ''"
                @click="startEdit(row)"
              >
                <span class="text-grey-900 group-hover/edit:text-brand-primary font-mono transition-colors">{{ row.now_sale_price?.toFixed(2) ?? '—' }}</span>
                <svg class="w-3 h-3 text-grey-300 group-hover/edit:text-brand-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
              </div>
            </td>

            <td v-if="visibleSet.has('talabat_sale_price')" class="px-3 py-2 text-body text-grey-700 text-right font-mono">{{ row.talabat_sale_price?.toFixed(2) ?? '—' }}</td>
            <td v-if="visibleSet.has('sale_PI')" class="px-3 py-2 text-body font-bold text-right font-mono" :class="piClass(row.sale_PI)">
              {{ row.sale_PI?.toFixed(2) ?? '—' }}
            </td>
            <td v-if="visibleSet.has('global_tier')" class="px-3 py-2"><TierBadge :tier="row.global_tier" /></td>
            <td v-if="visibleSet.has('subcat_tier')" class="px-3 py-2"><TierBadge :tier="row.subcat_tier" /></td>
            <td v-if="visibleSet.has('action_type')" class="px-3 py-2"><ActionBadge :action="row.action_type" /></td>
            <!-- Competitor Match -->
            <td v-if="visibleSet.has('similarity_score')" class="px-3 py-2 text-body" style="max-width: 200px">
              <!-- Matched: show competitor name -->
              <div v-if="row.competitor_product_name" class="flex items-center gap-1.5" :title="row.competitor_product_name">
                <svg class="w-3.5 h-3.5 text-green-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>
                <span class="text-grey-900 truncate">{{ row.competitor_product_name }}</span>
              </div>
              <!-- Potential match: show name + similarity badge -->
              <div v-else-if="row.match_potential_product_name" class="flex items-center gap-1.5" :title="row.match_potential_product_name + ' (' + (row.similarity_score * 100).toFixed(0) + '% match)'">
                <span class="inline-flex items-center px-1.5 py-0.5 rounded-full text-micro font-bold flex-shrink-0"
                  :class="row.similarity_score >= 0.9 ? 'bg-green-50 text-green-700' : row.similarity_score >= 0.8 ? 'bg-amber-50 text-amber-700' : 'bg-grey-100 text-grey-500'"
                >{{ (row.similarity_score * 100).toFixed(0) }}%</span>
                <span class="text-grey-500 truncate">{{ row.match_potential_product_name }}</span>
              </div>
              <!-- No match -->
              <span v-else class="text-grey-300">—</span>
            </td>
            <!-- Edit status -->
            <td v-if="visibleSet.has('edit_status')" class="px-3 py-2 text-center">
              <span
                v-if="store.editedProducts[row.product_id]"
                class="inline-flex items-center gap-1 text-caption font-bold px-2 py-0.5 rounded-full"
                :class="store.editedProducts[row.product_id].catalog_synced
                  ? 'text-green-700 bg-green-50'
                  : 'text-amber-700 bg-amber-50'"
                :title="store.editedProducts[row.product_id].catalog_synced ? 'Synced to Catalog API' : 'Saved locally'"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
                {{ store.editedProducts[row.product_id].catalog_synced ? 'Synced' : 'Local' }}
              </span>
              <span v-else class="text-grey-300">—</span>
            </td>
          </tr>
        </tbody>
      </table>
      <EmptyState v-if="sortedData.length === 0" :icon="SearchIcon" title="No products found" message="No products match your search. Try a different keyword." />
    </div>

    <!-- Floating bulk action bar -->
    <Transition name="slide-up">
      <div
        v-if="selectedIds.size > 0"
        class="border-t-2 border-brand-primary bg-brand-50 px-4 py-2.5 flex items-center justify-between gap-3"
      >
        <span class="text-body font-semibold text-brand-darkest">
          {{ selectedIds.size }} product{{ selectedIds.size > 1 ? 's' : '' }} selected
        </span>
        <div class="flex gap-2">
          <button
            class="text-caption px-3 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 text-grey-600 transition-colors"
            @click="selectedIds = new Set()"
          >Deselect All</button>
          <button
            class="text-caption px-3 py-1.5 rounded-lg bg-brand-primary text-white font-semibold hover:bg-brand-dark transition-colors"
            @click="openBulkModal"
          >✎ Bulk Edit Prices</button>
        </div>
      </div>
    </Transition>

    <!-- Bulk Edit Modal -->
    <Teleport to="body">
      <div v-if="bulkModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="closeBulkModal">
        <div class="bg-white rounded-xl shadow-card-hover p-6 w-96 max-w-[90vw]">
          <h3 class="text-heading font-bold text-grey-900 mb-1">Bulk Edit Prices</h3>
          <p class="text-body text-grey-500 mb-4">{{ selectedIds.size }} products selected. Leave blank to keep existing price.</p>
          <div class="flex flex-col gap-3">
            <label class="flex flex-col gap-1">
              <span class="text-caption font-semibold text-grey-600">Now Price (EGP)</span>
              <input
                type="number" step="0.01" v-model.number="bulkNowPrice"
                class="border border-grey-200 rounded-lg px-3 py-2 text-body outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-lightest transition-colors"
                placeholder="Leave blank to skip"
              />
            </label>
            <label class="flex flex-col gap-1">
              <span class="text-caption font-semibold text-grey-600">Now Sale Price (EGP)</span>
              <input
                type="number" step="0.01" v-model.number="bulkNowSalePrice"
                class="border border-grey-200 rounded-lg px-3 py-2 text-body outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-lightest transition-colors"
                placeholder="Leave blank to skip"
              />
            </label>
          </div>
          <div v-if="bulkProgress > 0" class="mt-4">
            <div class="h-2 bg-grey-100 rounded-full overflow-hidden">
              <div class="h-full bg-brand-primary rounded-full transition-all duration-300" :style="{ width: bulkProgress + '%' }"></div>
            </div>
            <p class="text-caption text-grey-500 mt-1">{{ Math.round(bulkProgress) }}% complete...</p>
          </div>
          <div class="flex gap-2 mt-5">
            <button
              class="flex-1 py-2 rounded-lg text-body font-semibold bg-brand-primary text-white hover:bg-brand-dark transition-colors disabled:opacity-40"
              :disabled="bulkSaving || (bulkNowPrice == null && bulkNowSalePrice == null)"
              @click="saveBulkEdit"
            >{{ bulkSaving ? 'Saving...' : 'Apply to All' }}</button>
            <button
              class="px-4 py-2 rounded-lg text-body text-grey-600 bg-grey-100 hover:bg-grey-200 transition-colors"
              :disabled="bulkSaving"
              @click="closeBulkModal"
            >Cancel</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Bulk Edit Confirm -->
    <ConfirmModal
      :visible="bulkConfirmVisible"
      title="Confirm Bulk Price Edit"
      :message="`Update prices for ${selectedIds.size} product${selectedIds.size > 1 ? 's' : ''}? This will set ${bulkNowPrice != null ? 'Now Price to EGP ' + bulkNowPrice : ''}${bulkNowPrice != null && bulkNowSalePrice != null ? ' and ' : ''}${bulkNowSalePrice != null ? 'Now Sale Price to EGP ' + bulkNowSalePrice : ''} for all selected products.`"
      confirm-label="Update All"
      @confirm="executeBulkEdit"
      @cancel="bulkConfirmVisible = false"
    />

    <div class="px-4 py-2.5 border-t border-grey-100 flex items-center justify-between bg-grey-50 gap-3 shrink-0">
      <!-- Showing range -->
      <span class="text-caption text-grey-500 shrink-0">
        Showing {{ ((page - 1) * pageSize + 1).toLocaleString() }}–{{ Math.min(page * pageSize, total).toLocaleString() }} of {{ total.toLocaleString() }}
      </span>
      <!-- Page buttons -->
      <div v-if="totalPages > 1" class="flex items-center gap-1">
        <button
          :disabled="page <= 1"
          class="text-caption px-2.5 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 transition-colors"
          @click="$emit('page', page - 1)"
        >← Prev</button>
        <template v-for="pg in pageNumbers" :key="pg ?? ('ellipsis-' + Math.random())">
          <span v-if="pg === null" class="text-caption text-grey-400 px-1">…</span>
          <button
            v-else
            class="text-caption w-8 py-1 rounded-lg border transition-colors"
            :class="pg === page
              ? 'bg-brand-primary text-white border-brand-primary font-bold'
              : 'border-grey-200 bg-white hover:bg-grey-100 text-grey-700'"
            @click="$emit('page', pg)"
          >{{ pg }}</button>
        </template>
        <button
          :disabled="page >= totalPages"
          class="text-caption px-2.5 py-1 rounded-lg border border-grey-200 bg-white hover:bg-grey-100 disabled:opacity-40 transition-colors"
          @click="$emit('page', page + 1)"
        >Next →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import TierBadge from '../shared/TierBadge.vue'
import ActionBadge from '../shared/ActionBadge.vue'
import ConfirmModal from '../shared/ConfirmModal.vue'
import { useCommercialStore } from '../../stores/commercial'
import { useToast } from '../../composables/useToast'
import EmptyState from '../shared/EmptyState.vue'
import { Search as SearchIcon, Loader2, Columns3 } from 'lucide-vue-next'
import { piTextClass } from '../../utils/piColor'

const props = defineProps({
  data: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 },
  highlight: { type: String, default: null },
})

defineEmits(['page'])

const store = useCommercialStore()
const toast = useToast()

const ALL_COLUMNS = [
  { key: 'product_name', label: 'Product', pinned: true },
  { key: 'brand_name', label: 'Brand' },
  { key: 'bf_sale_price', label: 'BF Price' },
  { key: 'now_price', label: 'Now Price' },
  { key: 'now_sale_price', label: 'Now Sale' },
  { key: 'talabat_sale_price', label: 'Talabat' },
  { key: 'sale_PI', label: 'PI' },
  { key: 'global_tier', label: 'Tier' },
  { key: 'subcat_tier', label: 'Sub Tier' },
  { key: 'action_type', label: 'Action' },
  { key: 'similarity_score', label: 'Competitor Match' },
  { key: 'edit_status', label: 'Status' },
]

// Column visibility with localStorage persistence
const STORAGE_KEY = 'pdt-visible-cols'
const defaultVisible = ALL_COLUMNS.map(c => c.key)

function loadVisibleCols() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return JSON.parse(stored)
  } catch {}
  return defaultVisible
}

const visibleColKeys = ref(loadVisibleCols())
const colMenuOpen = ref(false)
const colMenuRef = ref(null)

const columns = computed(() =>
  ALL_COLUMNS.filter(c => c.pinned || visibleColKeys.value.includes(c.key))
)

const visibleSet = computed(() => new Set(columns.value.map(c => c.key)))

function toggleColumn(key) {
  const col = ALL_COLUMNS.find(c => c.key === key)
  if (col?.pinned) return
  const idx = visibleColKeys.value.indexOf(key)
  if (idx >= 0) visibleColKeys.value.splice(idx, 1)
  else visibleColKeys.value.push(key)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(visibleColKeys.value))
}

function resetColumns() {
  visibleColKeys.value = [...defaultVisible]
  localStorage.removeItem(STORAGE_KEY)
}

function handleColMenuClickOutside(e) {
  if (colMenuRef.value && !colMenuRef.value.contains(e.target)) {
    colMenuOpen.value = false
  }
}

onMounted(() => document.addEventListener('mousedown', handleColMenuClickOutside))
onUnmounted(() => document.removeEventListener('mousedown', handleColMenuClickOutside))

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

// Search — server-side with debounce
const search = ref(store.search || '')

// When a product is highlighted (e.g. from dot click in BlendedPITable), set search
watch(() => props.highlight, (val) => {
  if (val) search.value = val
})

// Debounce search to avoid excessive API calls
watchDebounced(search, (val) => {
  store.setSearch(val)
}, { debounce: 400 })

// Bulk selection
const selectedIds = ref(new Set())

const allSelected = computed(() =>
  sortedData.value.length > 0 && sortedData.value.every(r => selectedIds.value.has(r.product_id))
)
const someSelected = computed(() =>
  sortedData.value.some(r => selectedIds.value.has(r.product_id)) && !allSelected.value
)

function toggleSelect(productId) {
  const s = new Set(selectedIds.value)
  if (s.has(productId)) s.delete(productId)
  else s.add(productId)
  selectedIds.value = s
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(sortedData.value.map(r => r.product_id))
  }
}

// Bulk edit modal
const bulkModal = ref(false)
const bulkNowPrice = ref(null)
const bulkNowSalePrice = ref(null)
const bulkProgress = ref(0)
const bulkSaving = ref(false)

function openBulkModal() {
  bulkNowPrice.value = null
  bulkNowSalePrice.value = null
  bulkProgress.value = 0
  bulkModal.value = true
}

function closeBulkModal() {
  if (!bulkSaving.value) bulkModal.value = false
}

const bulkConfirmVisible = ref(false)

function saveBulkEdit() {
  // Show confirmation before executing
  bulkConfirmVisible.value = true
}

async function executeBulkEdit() {
  bulkConfirmVisible.value = false
  const ids = [...selectedIds.value]
  bulkSaving.value = true
  bulkProgress.value = 0
  let done = 0
  let errors = 0
  for (const id of ids) {
    try {
      await store.updateProductPrice(
        id,
        bulkNowPrice.value ?? undefined,
        bulkNowSalePrice.value ?? undefined,
      )
    } catch { errors++ }
    done++
    bulkProgress.value = (done / ids.length) * 100
  }
  bulkSaving.value = false
  bulkModal.value = false
  selectedIds.value = new Set()
  if (errors > 0) {
    toast.warning('Bulk edit partial', `${done - errors} updated, ${errors} failed`)
  } else {
    toast.success('Bulk edit complete', `${ids.length} products updated`)
  }
}

// Inline editing state
const editingId = ref(null)
const editNowPrice = ref(null)
const editNowSalePrice = ref(null)
const saving = ref(null)
const nowPriceInput = ref(null)

function startEdit(row) {
  if (saving.value) return
  editingId.value = row.product_id
  editNowPrice.value = row.now_price
  editNowSalePrice.value = row.now_sale_price
  nextTick(() => {
    if (nowPriceInput.value) {
      const el = Array.isArray(nowPriceInput.value) ? nowPriceInput.value[0] : nowPriceInput.value
      el?.focus()
      el?.select()
    }
  })
}

function cancelEdit() {
  editingId.value = null
  editNowPrice.value = null
  editNowSalePrice.value = null
}

async function saveEdit(row) {
  if (saving.value) return
  const nowPrice = editNowPrice.value !== row.now_price ? editNowPrice.value : undefined
  const nowSalePrice = editNowSalePrice.value !== row.now_sale_price ? editNowSalePrice.value : undefined
  if (nowPrice === undefined && nowSalePrice === undefined) {
    cancelEdit()
    return
  }
  saving.value = row.product_id
  editingId.value = null
  try {
    const result = await store.updateProductPrice(row.product_id, nowPrice, nowSalePrice)
    const undoAction = { label: 'Undo', fn: () => store.undoLastEdit() }
    if (result.catalog_synced) {
      toast.success('Price updated', `${row.product_name} synced`, { duration: 5000, action: undoAction })
    } else {
      toast.warning('Saved locally', result.catalog_error ? 'Catalog API: no write access' : 'Price saved in-memory only', { duration: 5000, action: undoAction })
    }
  } catch (err) {
    console.error('Price update failed:', err)
    toast.error('Update failed', err.response?.data?.error || err.message)
  } finally {
    saving.value = null
  }
}

function toggleSort(key) {
  const newDir = sortKey.value === key && sortDir.value === 'desc' ? 'asc' : 'desc'
  store.setSort(key, newDir)
}

// Client-side filter for instant feedback; server-side search handles cross-page results
const sortedData = computed(() => {
  if (!search.value) return props.data
  const q = search.value.toLowerCase()
  return props.data.filter(r =>
    r.product_name?.toLowerCase().includes(q) ||
    r.brand_name?.toLowerCase().includes(q)
  )
})

function isBreadfast(brand) {
  return brand && brand.toLowerCase().includes('breadfast')
}

function piClass(pi) {
  return piTextClass(pi)
}

</script>

<style scoped>
.slide-up-enter-active, .slide-up-leave-active { transition: all 0.2s ease; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(8px); }
.dropdown-enter-active, .dropdown-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
