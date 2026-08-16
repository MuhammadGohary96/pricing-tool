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
      <!-- The same filter bar as Executive and Commercial, so one filter state
           carries across all three. Tier and FP are hidden: this screen's
           competitor-only rows are national and carry no tier of ours, so those
           two could only ever narrow half the table. -->
      <FilterBar :loading="store.loading" hide-competitor hide-tier hide-fp
                 class="animate-fade-in-up stagger-2" />

      <!-- Competitor: single-select, because every number here is "against
           whom". Same widget as the other two views, squarer shape to signal
           that it selects rather than merely dims. -->
      <CompetitorToggle
        v-if="competitorNames.length"
        :competitors="competitorNames"
        :model-value="store.competitor"
        :without-catalogue="competitorsWithoutCatalogue"
        single
        class="animate-fade-in-up stagger-2"
        @update:model-value="store.setCompetitor($event)"
      />

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
      <div class="flex items-center justify-between gap-3 flex-wrap">
        <div class="flex items-center gap-1 bg-white rounded-xl shadow-panel ring-1 ring-grey-200/70 p-1">
          <button v-for="v in VIEWS" :key="v.value" @click="store.setView(v.value)"
                  class="px-4 py-1.5 rounded-lg text-body font-semibold transition-colors flex items-center gap-2"
                  :class="store.view === v.value ? 'bg-brand-primary text-white' : 'text-grey-600 hover:bg-grey-50'">
            <component :is="v.icon" class="w-4 h-4" />
            {{ v.label }}
          </button>
        </div>

        <!-- The whole file, not just the table on screen: the per-table buttons
             below export one sheet each, this one builds the workbook. -->
        <div class="flex items-center gap-2">
          <span class="text-caption text-grey-400 hidden sm:inline">
            Overview + Brands + Subcategories + Portfolio
          </span>
          <ExportButton
            :fetcher="exportWorkbook"
            label="Export workbook"
            :filename="`${compFile()}_Brand_Portfolio.xlsx`"
          />
        </div>
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
import { computed, onMounted } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { useGapStore } from '../stores/gap'
import { useFiltersStore } from '../stores/filters'
import { useUrlSync } from '../composables/useUrlSync'
import { gapApi } from '../api/client'
import { asDownload } from '../utils/workbook'
import ExportButton from '../components/shared/ExportButton.vue'
import PageShell from '../components/shared/PageShell.vue'
import PageHeader from '../components/shared/PageHeader.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import FilterBar from '../components/layout/FilterBar.vue'
import CompetitorToggle from '../components/shared/CompetitorToggle.vue'
import GapKpiCards from '../components/gap/GapKpiCards.vue'
import GapSubcategoryTable from '../components/gap/GapSubcategoryTable.vue'
import GapBrandTable from '../components/gap/GapBrandTable.vue'
import GapProductExplorer from '../components/gap/GapProductExplorer.vue'
import {
  TriangleAlert, Info, Layers, Tags, PackageSearch,
  GitCompareArrows, Target, Handshake, Scale, Sparkles,
} from 'lucide-vue-next'

const store = useGapStore()
const filters = useFiltersStore()
useUrlSync()

const competitorNames = computed(() => store.filterOptions.competitors.map(c => c.name))
const competitorsWithoutCatalogue = computed(() =>
  store.filterOptions.competitors.filter(c => !c.has_catalogue).map(c => c.name))

const VIEWS = [
  { label: 'Subcategories', value: 'subcategories', icon: Layers },
  { label: 'Brands', value: 'brands', icon: Tags },
  { label: 'Products', value: 'products', icon: PackageSearch },
]

const definitions = [
  {
    title: 'Gap metrics',
    items: [
      { term: 'Mapped %', description: 'Our products linked to a competitor product, over all our products in scope. Linkage — not whether we managed to price it in a given fulfillment point.', icon: GitCompareArrows },
      { term: 'Addressable %', description: 'Mapped ÷ (our products − confirmed no-match). Products the matcher has positively rejected are removed from the denominator, so this is the honest ceiling.', icon: Target },
      { term: 'Shared-brand %', description: 'Matched % counting only brands the competitor also carries. A brand they do not stock can never be matched, so this separates a matching backlog from a genuine assortment difference.', icon: Handshake },
      { term: 'Confirmed no-match', description: 'The matcher looked and positively rejected every candidate — a real assortment gap, not a backlog item.', icon: Scale },
      { term: 'Potential match', description: 'Unmatched, with an AI candidate scoring ≥ 85% similarity that is still in the competitor portfolio. Ready for review.', icon: Sparkles },
    ],
  },
  {
    title: 'Reading the numbers',
    items: [
      { term: 'Blended PI', description: 'Quantity-weighted Breadfast price ÷ competitor price. Above 1.00 means BREADFAST IS MORE EXPENSIVE; below 1.00 means we are cheaper. Both tails matter.', icon: Scale },
      { term: 'Util %', description: 'Products with a fresh usable price on both sides, over the eligible set (the products making up our top 80% of revenue). Used ÷ Eligible — the same figure Executive and Commercial both label Util %; it was called Coverage % here until the three views were reconciled.', icon: Target },
      { term: 'They carry, we don\'t', description: 'Competitor products with no link to anything of ours, placed into one of our subcategories by learning from where already-matched products in the same competitor category landed. Never sum this across subcategories — one product can bridge to several.', icon: PackageSearch },
      { term: 'Brands: All / Shared only', description: 'Shared only keeps just the products whose brand the competitor also carries. A brand they do not stock can never be matched, so this turns every mapping rate on screen into the achievable ceiling instead of a target nobody can hit. On the competitor side it means "of the brands we both carry, what do they have that we do not".', icon: Handshake },
      { term: 'Scope', description: 'Use Vertical and Include Private Label in the filter bar to narrow this view. Setting Vertical to Supermarket and unchecking private label is often what you want, because in beauty and private label "we don\'t carry it" is usually a deliberate assortment decision rather than a gap. Note that private-label exclusion is approximate and can differ slightly between views.', icon: Layers },
    ],
  },
]

const compFile = () => (store.competitor || 'Competitor').replace(/[^A-Za-z0-9]+/g, '')

// Both exports are rendered by the backend. A browser-built workbook cannot
// carry the house style at all — the community build of SheetJS writes values
// but no fills, fonts or number formats — so the styling, threshold colours and
// frozen headers all come from openpyxl on the server.
function downloadWorkbook(sheets) {
  return asDownload(
    gapApi.workbook({ ...store.filterParams, sheets }),
    `${compFile()}_${sheets === 'all' ? 'Brand_Portfolio' : sheets}.xlsx`,
  )
}

/** One table, styled the same way, for grabbing just what is on screen. */
const exportRows = view => downloadWorkbook(view)

/** The whole file: Overview + Brands + Subcategories + Portfolio. */
const exportWorkbook = () => downloadWorkbook('all')

onMounted(() => store.init())

// One watcher over the merged params: the shared FilterBar commits atomically on
// Apply, and the competitor bar is view-local, so both land here as one refetch.
watchDebounced(
  () => store.filterParams,
  () => { store.currentPage = 1; store.fetchAll() },
  { debounce: 350, deep: true },
)
</script>
