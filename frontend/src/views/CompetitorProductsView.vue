<template>
  <PageShell :loading="store.loading" :error="store.error" @retry="store.fetchAll()">
    <div class="flex flex-col gap-4">
      <!-- ─── Command header ── -->
      <PageHeader
        eyebrow="Coverage & mapping"
        title="Competitor"
        accent="catalog"
        subtitle="Crawl coverage, price freshness, and the mapping that connects Breadfast products to each competitor."
      />

      <DefinitionsPanel :sections="definitions" storage-key="defs-competitor-products" />

      <!-- Local Filters -->
      <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 px-4 py-3 flex items-center gap-3 flex-wrap">
        <!-- Multi-select: Competitors -->
        <div class="relative" ref="compDropdownRef">
          <button
            @click="compDropdownOpen = !compDropdownOpen; if (compDropdownOpen) pendingCompetitors = [...store.competitorFilter]"
            class="text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary flex items-center gap-1.5 min-w-[140px]"
          >
            <span v-if="!store.competitorFilter.length" class="text-grey-500">All Competitors</span>
            <span v-else class="truncate max-w-[160px]">{{ store.competitorFilter.length }} selected</span>
            <ChevronDown class="w-3.5 h-3.5 text-grey-400 ml-auto shrink-0" />
          </button>
          <div v-if="compDropdownOpen" class="absolute z-20 mt-1 bg-white border border-grey-200 rounded-xl shadow-dropdown ring-1 ring-grey-200/70 w-56 max-h-64 flex flex-col">
            <div class="overflow-y-auto flex-1 p-2 space-y-0.5">
              <label
                v-for="c in store.filterOptions.competitors"
                :key="c"
                class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-grey-50 cursor-pointer text-body"
              >
                <input type="checkbox" :value="c" v-model="pendingCompetitors" class="rounded border-grey-300 text-brand-primary focus:ring-brand-primary" />
                <CompetitorLogo :name="c" />
                {{ c }}
              </label>
            </div>
            <div class="border-t border-grey-100 px-2 py-2 flex justify-between items-center">
              <button @click="pendingCompetitors = []; applyCompetitors()" class="text-caption text-grey-500 hover:text-grey-700">Clear</button>
              <button @click="applyCompetitors()" class="text-caption font-semibold text-white bg-brand-primary hover:bg-brand-dark rounded px-3 py-1">Apply</button>
            </div>
          </div>
        </div>

        <!-- Multi-select: Category L1 -->
        <div class="relative" ref="catDropdownRef">
          <button
            @click="catDropdownOpen = !catDropdownOpen; if (catDropdownOpen) pendingCategories = [...store.categoryL1Filter]"
            class="text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary flex items-center gap-1.5 min-w-[140px]"
          >
            <span v-if="!store.categoryL1Filter.length" class="text-grey-500">All Cat. L1</span>
            <span v-else class="truncate max-w-[160px]">L1: {{ store.categoryL1Filter.length }} sel.</span>
            <ChevronDown class="w-3.5 h-3.5 text-grey-400 ml-auto shrink-0" />
          </button>
          <div v-if="catDropdownOpen" class="absolute z-20 mt-1 bg-white border border-grey-200 rounded-xl shadow-dropdown ring-1 ring-grey-200/70 w-56 max-h-64 flex flex-col">
            <div class="overflow-y-auto flex-1 p-2 space-y-0.5">
              <label
                v-for="c in store.filterOptions.categories_l1"
                :key="c"
                class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-grey-50 cursor-pointer text-body"
              >
                <input type="checkbox" :value="c" v-model="pendingCategories" class="rounded border-grey-300 text-brand-primary focus:ring-brand-primary" />
                {{ c }}
              </label>
            </div>
            <div class="border-t border-grey-100 px-2 py-2 flex justify-between items-center">
              <button @click="pendingCategories = []; applyCategories()" class="text-caption text-grey-500 hover:text-grey-700">Clear</button>
              <button @click="applyCategories()" class="text-caption font-semibold text-white bg-brand-primary hover:bg-brand-dark rounded px-3 py-1">Apply</button>
            </div>
          </div>
        </div>

        <!-- Multi-select: Category L2 -->
        <div v-if="store.filterOptions.categories_l2.length" class="relative" ref="catL2DropdownRef">
          <button
            @click="catL2DropdownOpen = !catL2DropdownOpen; if (catL2DropdownOpen) pendingCategoriesL2 = [...store.categoryL2Filter]"
            class="text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary flex items-center gap-1.5 min-w-[140px]"
          >
            <span v-if="!store.categoryL2Filter.length" class="text-grey-500">All Cat. L2</span>
            <span v-else class="truncate max-w-[160px]">L2: {{ store.categoryL2Filter.length }} sel.</span>
            <ChevronDown class="w-3.5 h-3.5 text-grey-400 ml-auto shrink-0" />
          </button>
          <div v-if="catL2DropdownOpen" class="absolute z-20 mt-1 bg-white border border-grey-200 rounded-xl shadow-dropdown ring-1 ring-grey-200/70 w-56 max-h-64 flex flex-col">
            <div class="overflow-y-auto flex-1 p-2 space-y-0.5">
              <label
                v-for="c in store.filterOptions.categories_l2"
                :key="c"
                class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-grey-50 cursor-pointer text-body"
              >
                <input type="checkbox" :value="c" v-model="pendingCategoriesL2" class="rounded border-grey-300 text-brand-primary focus:ring-brand-primary" />
                {{ c }}
              </label>
            </div>
            <div class="border-t border-grey-100 px-2 py-2 flex justify-between items-center">
              <button @click="pendingCategoriesL2 = []; applyCategoriesL2()" class="text-caption text-grey-500 hover:text-grey-700">Clear</button>
              <button @click="applyCategoriesL2()" class="text-caption font-semibold text-white bg-brand-primary hover:bg-brand-dark rounded px-3 py-1">Apply</button>
            </div>
          </div>
        </div>

        <!-- Multi-select: Category L3 -->
        <div v-if="store.filterOptions.categories_l3.length" class="relative" ref="catL3DropdownRef">
          <button
            @click="catL3DropdownOpen = !catL3DropdownOpen; if (catL3DropdownOpen) pendingCategoriesL3 = [...store.categoryL3Filter]"
            class="text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary flex items-center gap-1.5 min-w-[140px]"
          >
            <span v-if="!store.categoryL3Filter.length" class="text-grey-500">All Cat. L3</span>
            <span v-else class="truncate max-w-[160px]">L3: {{ store.categoryL3Filter.length }} sel.</span>
            <ChevronDown class="w-3.5 h-3.5 text-grey-400 ml-auto shrink-0" />
          </button>
          <div v-if="catL3DropdownOpen" class="absolute z-20 mt-1 bg-white border border-grey-200 rounded-xl shadow-dropdown ring-1 ring-grey-200/70 w-56 max-h-64 flex flex-col">
            <div class="overflow-y-auto flex-1 p-2 space-y-0.5">
              <label
                v-for="c in store.filterOptions.categories_l3"
                :key="c"
                class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-grey-50 cursor-pointer text-body"
              >
                <input type="checkbox" :value="c" v-model="pendingCategoriesL3" class="rounded border-grey-300 text-brand-primary focus:ring-brand-primary" />
                {{ c }}
              </label>
            </div>
            <div class="border-t border-grey-100 px-2 py-2 flex justify-between items-center">
              <button @click="pendingCategoriesL3 = []; applyCategoriesL3()" class="text-caption text-grey-500 hover:text-grey-700">Clear</button>
              <button @click="applyCategoriesL3()" class="text-caption font-semibold text-white bg-brand-primary hover:bg-brand-dark rounded px-3 py-1">Apply</button>
            </div>
          </div>
        </div>

        <select
          v-model="store.mappingStatusFilter"
          class="text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary"
        >
          <option :value="null">All Mapping</option>
          <option value="Mapped">Mapped</option>
          <option value="Unmapped">Unmapped</option>
          <option value="AI Match">Potential Match</option>
        </select>

        <select
          v-model="store.freshnessFilter"
          class="text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary"
        >
          <option :value="null">All Freshness</option>
          <option value="Fresh">Fresh (≤7d)</option>
          <option value="Stale">Stale (>7d)</option>
        </select>

        <div class="flex items-center gap-1.5">
          <span class="text-caption text-grey-500 whitespace-nowrap">BF Updated:</span>
          <select
            :value="bfDatePreset"
            @change="onBfPresetChange($event.target.value)"
            class="text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary"
          >
            <option value="">All Time</option>
            <option value="1">Last Day</option>
            <option value="7">Last 7 Days</option>
            <option value="30">Last 30 Days</option>
            <option value="60">Last 60 Days</option>
            <option value="custom">Custom</option>
          </select>
          <template v-if="bfDatePreset === 'custom'">
            <input
              type="date"
              v-model="store.bfDateFrom"
              class="text-body border border-grey-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary w-[130px]"
              :max="store.bfDateTo || undefined"
            />
            <span class="text-caption text-grey-400">–</span>
            <input
              type="date"
              v-model="store.bfDateTo"
              class="text-body border border-grey-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary w-[130px]"
              :min="store.bfDateFrom || undefined"
            />
          </template>
        </div>

        <div class="flex items-center gap-1.5">
          <span class="text-caption text-grey-500 whitespace-nowrap">Comp. Updated:</span>
          <select
            :value="compDatePreset"
            @change="onCompPresetChange($event.target.value)"
            class="text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary"
          >
            <option value="">All Time</option>
            <option value="1">Last Day</option>
            <option value="7">Last 7 Days</option>
            <option value="30">Last 30 Days</option>
            <option value="60">Last 60 Days</option>
            <option value="custom">Custom</option>
          </select>
          <template v-if="compDatePreset === 'custom'">
            <input
              type="date"
              v-model="store.competitorDateFrom"
              class="text-body border border-grey-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary w-[130px]"
              :max="store.competitorDateTo || undefined"
            />
            <span class="text-caption text-grey-400">–</span>
            <input
              type="date"
              v-model="store.competitorDateTo"
              class="text-body border border-grey-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary w-[130px]"
              :min="store.competitorDateFrom || undefined"
            />
          </template>
        </div>

        <button
          v-if="hasActiveFilters"
          @click="clearFilters"
          class="text-caption text-brand-primary hover:text-brand-dark font-semibold px-2 py-1 rounded hover:bg-brand-50 transition-colors"
        >
          Clear filters
        </button>
      </div>

      <!-- KPI Cards -->
      <CrawlKpiCards :kpis="store.kpis" />

      <!-- Split Row: Category Breakdown + Mapping Summary -->
      <div ref="middleRef" class="flex gap-4" :class="{ 'animate-fade-in-up': middleVisible }">
        <CategoryMappingTable :data="store.categoryBreakdown" />
        <MappingSummaryTable :data="store.mappingSummary" />
      </div>

      <!-- Crawl Timeline Chart -->
      <div class="animate-fade-in-up" style="animation-delay: 0.1s">
        <CrawlTimeline :data="store.crawlTimeline" />
      </div>

      <!-- Product Explorer -->
      <div class="animate-fade-in-up" style="animation-delay: 0.2s">
        <CompetitorProductExplorer
          :items="store.products"
          :total="store.productsTotal"
          :page="store.currentPage"
          :page-size="store.pageSize"
          :search-query="store.searchQuery"
          :export-fetcher="exportProducts"
          @page="onPageChange"
          @search="onSearch"
        />
      </div>
    </div>
  </PageShell>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { useCompetitorProductsStore } from '../stores/competitorProducts'
import PageShell from '../components/shared/PageShell.vue'
import PageHeader from '../components/shared/PageHeader.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import CrawlKpiCards from '../components/competitor-products/CrawlKpiCards.vue'
import CrawlTimeline from '../components/competitor-products/CrawlTimeline.vue'
import CategoryMappingTable from '../components/competitor-products/CategoryMappingTable.vue'
import MappingSummaryTable from '../components/competitor-products/MappingSummaryTable.vue'
import CompetitorProductExplorer from '../components/competitor-products/CompetitorProductExplorer.vue'
import { useScrollReveal } from '../composables/useScrollReveal'
import { competitorProductsApi } from '../api/client'
import { Database, GitCompareArrows, CalendarClock, Percent, Layers, BrainCircuit, ChevronDown } from 'lucide-vue-next'
import { onClickOutside } from '@vueuse/core'
import CompetitorLogo from '../components/shared/CompetitorLogo.vue'

const store = useCompetitorProductsStore()
const { target: middleRef, isVisible: middleVisible } = useScrollReveal()

const definitions = [
  {
    title: 'Metrics',
    items: [
      { term: 'Total Crawled', description: 'Unique competitor products scraped across all competitors.', icon: Database },
      { term: 'Mapped to BF', description: 'Competitor products successfully matched to a Breadfast product.', icon: GitCompareArrows },
      { term: 'Mapping Rate', description: 'Percentage of crawled products that are mapped to BF.', icon: Percent },
      { term: 'Fresh ≤7d', description: 'Products whose competitor price was updated within the last 7 days.', icon: CalendarClock },
    ],
  },
  {
    title: 'Concepts',
    items: [
      { term: 'Category Breakdown', description: 'Treemap showing competitor category hierarchy. Size = product count, color = mapping rate.', icon: Layers },
      { term: 'Potential Match', description: 'Unmapped competitor products where AI found a likely BF match (similarity ≥ 85%).', icon: BrainCircuit },
    ],
  },
]

// Multi-select dropdowns
const compDropdownRef = ref(null)
const catDropdownRef = ref(null)
const catL2DropdownRef = ref(null)
const catL3DropdownRef = ref(null)
const compDropdownOpen = ref(false)
const catDropdownOpen = ref(false)
const catL2DropdownOpen = ref(false)
const catL3DropdownOpen = ref(false)
const pendingCompetitors = ref([...store.competitorFilter])
const pendingCategories = ref([...store.categoryL1Filter])
const pendingCategoriesL2 = ref([...store.categoryL2Filter])
const pendingCategoriesL3 = ref([...store.categoryL3Filter])

onClickOutside(compDropdownRef, () => { compDropdownOpen.value = false })
onClickOutside(catDropdownRef, () => { catDropdownOpen.value = false })
onClickOutside(catL2DropdownRef, () => { catL2DropdownOpen.value = false })
onClickOutside(catL3DropdownRef, () => { catL3DropdownOpen.value = false })

function applyCompetitors() {
  store.competitorFilter = [...pendingCompetitors.value]
  compDropdownOpen.value = false
}

function applyCategories() {
  store.categoryL1Filter = [...pendingCategories.value]
  catDropdownOpen.value = false
}

function applyCategoriesL2() {
  store.categoryL2Filter = [...pendingCategoriesL2.value]
  catL2DropdownOpen.value = false
}

function applyCategoriesL3() {
  store.categoryL3Filter = [...pendingCategoriesL3.value]
  catL3DropdownOpen.value = false
}

function daysAgo(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

const bfDatePreset = ref('')
const compDatePreset = ref('')

function onBfPresetChange(v) {
  bfDatePreset.value = v
  if (!v) {
    store.bfDateFrom = null
    store.bfDateTo = null
  } else if (v === 'custom') {
    if (!store.bfDateFrom) store.bfDateFrom = daysAgo(30)
    if (!store.bfDateTo) store.bfDateTo = todayStr()
  } else {
    store.bfDateFrom = daysAgo(Number(v))
    store.bfDateTo = todayStr()
  }
}

function onCompPresetChange(v) {
  compDatePreset.value = v
  if (!v) {
    store.competitorDateFrom = null
    store.competitorDateTo = null
  } else if (v === 'custom') {
    if (!store.competitorDateFrom) store.competitorDateFrom = daysAgo(30)
    if (!store.competitorDateTo) store.competitorDateTo = todayStr()
  } else {
    store.competitorDateFrom = daysAgo(Number(v))
    store.competitorDateTo = todayStr()
  }
}

const hasActiveFilters = computed(() => {
  return store.competitorFilter.length > 0 ||
    store.categoryL1Filter.length > 0 ||
    store.categoryL2Filter.length > 0 ||
    store.categoryL3Filter.length > 0 ||
    store.mappingStatusFilter !== null ||
    store.freshnessFilter !== null ||
    store.bfDateFrom !== null ||
    store.bfDateTo !== null ||
    store.competitorDateFrom !== null ||
    store.competitorDateTo !== null
})

function clearFilters() {
  bfDatePreset.value = ''
  compDatePreset.value = ''
  pendingCompetitors.value = []
  pendingCategories.value = []
  pendingCategoriesL2.value = []
  pendingCategoriesL3.value = []
  store.resetFilters()
  store.fetchAll()
}

onMounted(async () => {
  await store.fetchAll()
})

// Watch filter changes and refetch
watchDebounced(
  () => store.filterParams,
  async () => {
    store.currentPage = 1
    await store.fetchAll()
  },
  { debounce: 400, deep: true },
)

async function onPageChange(page) {
  await store.setPage(page)
}

function onSearch(query) {
  store.setSearch(query)
}

async function exportProducts() {
  const res = await competitorProductsApi.exportCSV(store.filterParams)
  return res.data
}
</script>
