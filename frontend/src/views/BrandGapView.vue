<template>
  <PageShell :loading="store.loading" :error="store.error" @retry="store.fetchAll()">
    <div class="flex flex-col gap-4">
      <PageHeader
        eyebrow="Assortment & matching"
        title="Gap"
        accent="analysis"
        subtitle="Per brand and per subcategory, against one competitor: how much of our range is matched, how much can be, which brands we share, and what they sell that we don't."
      />

      <DefinitionsPanel :sections="definitions" storage-key="defs-brand-gap" />

      <!-- ─── Controls ─── -->
      <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 px-4 py-3 flex items-center gap-3 flex-wrap">
        <!-- Competitor: single-select on purpose. Every number here is
             "against whom" — unioning competitors would double-count. -->
        <div class="flex items-center gap-1.5">
          <span class="text-caption text-grey-500 whitespace-nowrap">Compared with</span>
          <select
            v-model="store.competitor"
            class="text-body border border-grey-200 rounded-lg px-3 py-1.5 font-semibold focus:outline-none focus:ring-1 focus:ring-brand-primary"
          >
            <option v-for="c in store.filterOptions.competitors" :key="c.name" :value="c.name">
              {{ c.name }}{{ c.has_catalogue ? '' : ' (no catalogue)' }}
            </option>
          </select>
        </div>

        <span class="h-5 w-px bg-grey-200" aria-hidden="true"></span>

        <label class="flex items-center gap-2 text-body cursor-pointer select-none">
          <input type="checkbox" v-model="store.excludeBeautyPL"
                 class="rounded border-grey-300 text-brand-primary focus:ring-brand-primary" />
          Exclude beauty &amp; private label
        </label>

        <label class="flex items-center gap-2 text-body cursor-pointer select-none"
               :class="store.excludeBeautyPL ? '' : 'opacity-40 pointer-events-none'">
          <input type="checkbox" v-model="store.includePrivateLabel"
                 class="rounded border-grey-300 text-brand-primary focus:ring-brand-primary" />
          …but keep private label
        </label>

        <span class="h-5 w-px bg-grey-200" aria-hidden="true"></span>

        <!-- Category / subcategory narrowing -->
        <div class="relative" ref="catRef">
          <button @click="toggleCat" :class="DROPDOWN_BTN">
            <span v-if="!store.mainCategoryFilter.length" class="text-grey-500">All categories</span>
            <span v-else class="truncate max-w-[150px]">{{ store.mainCategoryFilter.length }} categories</span>
            <ChevronDown class="w-3.5 h-3.5 text-grey-400 ml-auto shrink-0" />
          </button>
          <div v-if="catOpen" :class="DROPDOWN_PANEL">
            <div class="overflow-y-auto flex-1 p-2 space-y-0.5">
              <label v-for="c in store.filterOptions.main_categories" :key="c" :class="DROPDOWN_ITEM">
                <input type="checkbox" :value="c" v-model="pendingCats"
                       class="rounded border-grey-300 text-brand-primary focus:ring-brand-primary" />
                {{ c }}
              </label>
            </div>
            <div class="border-t border-grey-100 px-2 py-2 flex justify-between items-center">
              <button @click="pendingCats = []; applyCats()" class="text-caption text-grey-500 hover:text-grey-700">Clear</button>
              <button @click="applyCats()" class="text-caption font-semibold text-white bg-brand-primary hover:bg-brand-dark rounded px-3 py-1">Apply</button>
            </div>
          </div>
        </div>

        <div class="relative" ref="subRef">
          <button @click="toggleSub" :class="DROPDOWN_BTN">
            <span v-if="!store.subCategoryFilter.length" class="text-grey-500">All subcategories</span>
            <span v-else class="truncate max-w-[150px]">{{ store.subCategoryFilter.length }} subcategories</span>
            <ChevronDown class="w-3.5 h-3.5 text-grey-400 ml-auto shrink-0" />
          </button>
          <div v-if="subOpen" :class="DROPDOWN_PANEL">
            <input v-model="subSearch" type="search" placeholder="Search…"
                   class="m-2 text-body border border-grey-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-brand-primary" />
            <div class="overflow-y-auto flex-1 p-2 space-y-0.5">
              <label v-for="c in visibleSubs" :key="c" :class="DROPDOWN_ITEM">
                <input type="checkbox" :value="c" v-model="pendingSubs"
                       class="rounded border-grey-300 text-brand-primary focus:ring-brand-primary" />
                {{ c }}
              </label>
            </div>
            <div class="border-t border-grey-100 px-2 py-2 flex justify-between items-center">
              <button @click="pendingSubs = []; applySubs()" class="text-caption text-grey-500 hover:text-grey-700">Clear</button>
              <button @click="applySubs()" class="text-caption font-semibold text-white bg-brand-primary hover:bg-brand-dark rounded px-3 py-1">Apply</button>
            </div>
          </div>
        </div>

        <button v-if="hasActiveFilters" @click="clearFilters"
                class="text-caption text-brand-primary hover:text-brand-dark font-semibold px-2 py-1 rounded hover:bg-brand-50 transition-colors ml-auto">
          Reset
        </button>
      </div>

      <!-- ─── Data-quality disclosures ─── -->
      <div v-if="store.competitorHasNoCatalogue"
           class="rounded-2xl ring-1 ring-red-200 bg-red-50/70 px-4 py-3 flex items-start gap-2.5">
        <TriangleAlert class="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
        <p class="text-body text-red-800">
          <strong>{{ store.competitor }} has no live catalogue.</strong>
          Nothing has been crawled into the product list in the last 7 days, so the
          "they carry, we don't" side and every brand-overlap count are empty —
          that is a collection gap, not a real assortment gap. Our own matching
          figures below are still valid.
        </p>
      </div>

      <div v-if="store.hasBeautyBlindSpot"
           class="rounded-2xl ring-1 ring-amber-200 bg-amber-50/70 px-4 py-3 flex items-start gap-2.5">
        <Info class="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
        <p class="text-body text-amber-900">
          {{ store.competitor }} files its whole beauty range under one flat category, so
          "exclude beauty" cannot reliably remove their beauty products from the
          competitor-only counts. Our side is filtered correctly.
        </p>
      </div>

      <!-- ─── KPIs ─── -->
      <GapKpiCards :kpis="store.kpis" />

      <!-- ─── View switch ─── -->
      <div class="flex items-center gap-1 bg-white rounded-xl shadow-panel ring-1 ring-grey-200/70 p-1 self-start">
        <button v-for="v in VIEWS" :key="v.value" @click="store.setView(v.value)"
                class="px-4 py-1.5 rounded-lg text-body font-semibold transition-colors flex items-center gap-2"
                :class="store.view === v.value ? 'bg-brand-primary text-white' : 'text-grey-600 hover:bg-grey-50'">
          <component :is="v.icon" class="w-4 h-4" />
          {{ v.label }}
        </button>
      </div>

      <GapSubcategoryTable
        v-if="store.view === 'subcategories'"
        :rows="store.subcategories"
        :export-fetcher="() => exportRows('subcategories')"
      />

      <GapBrandTable
        v-else-if="store.view === 'brands'"
        :rows="store.brands"
        :total="store.brandsTotal"
        :brand-type="store.brandTypeFilter"
        :export-fetcher="() => exportRows('brands')"
        @type="store.setBrandType($event)"
      />

      <GapProductExplorer
        v-else
        :items="store.products"
        :total="store.productsTotal"
        :page="store.currentPage"
        :page-size="store.pageSize"
        :side="store.productSide"
        :search-query="store.searchQuery"
        :export-fetcher="() => exportRows('products')"
        @page="store.setPage($event)"
        @search="store.setSearch($event)"
        @side="store.setProductSide($event)"
        @sort="store.setSort($event)"
      />
    </div>
  </PageShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { watchDebounced, onClickOutside } from '@vueuse/core'
import { useGapStore } from '../stores/gap'
import { gapApi } from '../api/client'
import PageShell from '../components/shared/PageShell.vue'
import PageHeader from '../components/shared/PageHeader.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import GapKpiCards from '../components/gap/GapKpiCards.vue'
import GapSubcategoryTable from '../components/gap/GapSubcategoryTable.vue'
import GapBrandTable from '../components/gap/GapBrandTable.vue'
import GapProductExplorer from '../components/gap/GapProductExplorer.vue'
import {
  ChevronDown, TriangleAlert, Info, Layers, Tags, PackageSearch,
  GitCompareArrows, Target, Handshake, Scale, Sparkles,
} from 'lucide-vue-next'

const store = useGapStore()

const VIEWS = [
  { label: 'Subcategories', value: 'subcategories', icon: Layers },
  { label: 'Brands', value: 'brands', icon: Tags },
  { label: 'Products', value: 'products', icon: PackageSearch },
]

const DROPDOWN_BTN = 'text-body border border-grey-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-primary flex items-center gap-1.5 min-w-[160px]'
const DROPDOWN_PANEL = 'absolute z-20 mt-1 bg-white border border-grey-200 rounded-xl shadow-dropdown ring-1 ring-grey-200/70 w-64 max-h-72 flex flex-col'
const DROPDOWN_ITEM = 'flex items-center gap-2 px-2 py-1.5 rounded hover:bg-grey-50 cursor-pointer text-body'

const definitions = [
  {
    title: 'Gap metrics',
    items: [
      { term: 'Matched %', description: 'Our products linked to a competitor product, over all our products in scope. Linkage — not whether we managed to price it in a given fulfillment point.', icon: GitCompareArrows },
      { term: 'Addressable %', description: 'Matched ÷ (our products − confirmed no-match). Products the matcher has positively rejected are removed from the denominator, so this is the honest ceiling.', icon: Target },
      { term: 'Shared-brand %', description: 'Matched % counting only brands the competitor also carries. A brand they do not stock can never be matched, so this separates a matching backlog from a genuine assortment difference.', icon: Handshake },
      { term: 'Confirmed no-match', description: 'The matcher looked and positively rejected every candidate — a real assortment gap, not a backlog item.', icon: Scale },
      { term: 'Potential match', description: 'Unmatched, with an AI candidate scoring ≥ 85% similarity that is still in the competitor portfolio. Ready for review.', icon: Sparkles },
    ],
  },
  {
    title: 'Reading the numbers',
    items: [
      { term: 'Blended PI', description: 'Quantity-weighted Breadfast price ÷ competitor price. Above 1.00 means BREADFAST IS MORE EXPENSIVE; below 1.00 means we are cheaper. Both tails matter.', icon: Scale },
      { term: 'Coverage %', description: 'Products with a fresh usable price on both sides, over the eligible set (the products making up our top 80% of revenue).', icon: Target },
      { term: 'They carry, we don\'t', description: 'Competitor products with no link to anything of ours, placed into one of our subcategories by learning from where already-matched products in the same competitor category landed. Never sum this across subcategories — one product can bridge to several.', icon: PackageSearch },
      { term: 'Scope', description: 'Beauty and private label are excluded by default: in those ranges "we don\'t carry it" is usually a deliberate assortment decision rather than a gap.', icon: Layers },
    ],
  },
]

// ── dropdowns ────────────────────────────────────────────────
const catRef = ref(null)
const subRef = ref(null)
const catOpen = ref(false)
const subOpen = ref(false)
const pendingCats = ref([])
const pendingSubs = ref([])
const subSearch = ref('')

onClickOutside(catRef, () => { catOpen.value = false })
onClickOutside(subRef, () => { subOpen.value = false })

function toggleCat() {
  catOpen.value = !catOpen.value
  if (catOpen.value) pendingCats.value = [...store.mainCategoryFilter]
}
function toggleSub() {
  subOpen.value = !subOpen.value
  if (subOpen.value) pendingSubs.value = [...store.subCategoryFilter]
}
function applyCats() {
  store.mainCategoryFilter = [...pendingCats.value]
  catOpen.value = false
}
function applySubs() {
  store.subCategoryFilter = [...pendingSubs.value]
  subOpen.value = false
}

const visibleSubs = computed(() => {
  const q = subSearch.value.trim().toLowerCase()
  const all = store.filterOptions.sub_categories || []
  return q ? all.filter(s => s.toLowerCase().includes(q)) : all
})

const hasActiveFilters = computed(() =>
  store.mainCategoryFilter.length > 0 ||
  store.subCategoryFilter.length > 0 ||
  !store.excludeBeautyPL ||
  store.includePrivateLabel ||
  store.brandTypeFilter !== null)

function clearFilters() {
  pendingCats.value = []
  pendingSubs.value = []
  store.resetFilters()
  store.fetchAll()
}

async function exportRows(view) {
  const params = { ...store.filterParams, view }
  if (view === 'products') params.side = store.productSide
  const res = await gapApi.exportRows(params)
  return res.data
}

onMounted(() => store.init())

watchDebounced(
  () => store.filterParams,
  () => { store.currentPage = 1; store.fetchAll() },
  { debounce: 350, deep: true },
)
</script>
