<template>
  <PageShell :loading="store.loading" :error="store.error" @retry="store.fetchAll()">
    <!-- Tailored skeleton matching the real stacked layout -->
    <template #skeleton>
      <div class="flex flex-col gap-4">
        <div class="flex items-end justify-between gap-8 pt-1">
          <div class="flex flex-col gap-2">
            <div class="skeleton-shimmer h-6 w-72 rounded-lg"></div>
            <div class="skeleton-shimmer h-3.5 w-96 max-w-full rounded"></div>
          </div>
          <div class="hidden sm:flex gap-6">
            <div v-for="i in 3" :key="i" class="flex flex-col gap-2 items-end">
              <div class="skeleton-shimmer h-7 w-16 rounded"></div>
              <div class="skeleton-shimmer h-2.5 w-20 rounded"></div>
            </div>
          </div>
        </div>
        <div class="skeleton-shimmer h-10 rounded-xl"></div>
        <div class="bg-white rounded-2xl shadow-panel p-4">
          <div class="skeleton-shimmer h-7 w-56 rounded mb-3"></div>
          <div class="skeleton-shimmer h-[300px] rounded-lg"></div>
        </div>
        <div class="bg-white rounded-2xl shadow-panel p-4">
          <div class="skeleton-shimmer h-7 w-64 rounded mb-3"></div>
          <div class="skeleton-shimmer h-[340px] rounded-lg"></div>
        </div>
      </div>
    </template>

    <div class="flex flex-col gap-4">
      <!-- ─── Command header: identity + scope ── -->
      <PageHeader
        eyebrow="Category workspace"
        title="Commercial"
        accent="workspace"
        subtitle="Track the price index by subcategory and product, and act on the gaps that move revenue."
      >
        <template #stats>
          <dl class="grid grid-cols-3 gap-px bg-grey-100">
            <div class="bg-white p-5 lg:p-6 flex flex-col gap-1.5">
              <dt class="text-caption text-grey-500 font-medium">Subcategories</dt>
              <dd class="font-mono text-[26px] leading-none font-bold text-grey-900 tabular-nums"><AnimatedNumber :value="subcatCount" /></dd>
            </div>
            <div class="bg-white p-5 lg:p-6 flex flex-col gap-1.5">
              <dt class="text-caption text-grey-500 font-medium">Products tracked</dt>
              <dd class="font-mono text-[26px] leading-none font-bold text-grey-900 tabular-nums"><AnimatedNumber :value="productCount" /></dd>
            </div>
            <div class="bg-white p-5 lg:p-6 flex flex-col gap-1.5">
              <dt class="text-caption text-grey-500 font-medium">Competitors</dt>
              <dd class="font-mono text-[26px] leading-none font-bold text-grey-900 tabular-nums"><AnimatedNumber :value="competitorCount" /></dd>
            </div>
          </dl>
        </template>
      </PageHeader>

      <DefinitionsPanel :sections="definitions" storage-key="defs-commercial" class="animate-fade-in-up stagger-1" />
      <FilterBar :loading="store.loading" hide-competitor class="animate-fade-in-up stagger-2" />

      <!-- Competitor visibility pills (left-aligned) -->
      <CompetitorToggle
        v-if="allCompetitors.length > 0"
        :competitors="allCompetitors"
        v-model="selectedCompetitors"
        :default-limit="5"
        class="animate-fade-in-up stagger-2"
      />

      <!-- Drill-down context -->
      <Transition name="filter" mode="out-in">
        <DrilldownBreadcrumb
          v-if="filters.subCategory.length === 1"
          :subcategory="filters.subCategory[0]"
          @clear="filters.setFilter('subCategory', [])"
          class="animate-fade-in-up"
        />
      </Transition>

      <!-- PI legend — both-tails-bad key for the PI-colored tables below -->
      <div class="flex justify-end animate-fade-in-up stagger-3">
        <PILegend />
      </div>

      <!-- Blended PI Table -->
      <BlendedPITable
        class="animate-fade-in-up stagger-3"
        :data="store.blendedPI"
        :competitors="store.blendedCompetitors"
        :selected-competitors="selectedCompetitors"
        :busy="store.refreshingBlended"
        :group-by="store.blendedGroupBy"
        style="max-height: 420px;"
        @select="onSubcategorySelect"
        @select-category="onCategorySelect"
        @select-product="onSelectProduct"
        @set-group-by="store.setBlendedGroupBy"
      />

      <!-- Pivoted Product Table -->
      <div class="flex-1 overflow-hidden product-panel animate-fade-in-up stagger-4">
        <ProductPivotTable
          :data="store.pivotedProducts"
          :total="store.pivotedTotal"
          :page="store.currentPage"
          :page-size="store.pageSize"
          :competitors="filteredPivotCompetitors"
          :needs-action-only="store.needsActionOnly"
          :compact-mode="compactMode"
          :busy="store.refreshingPivot"
          class="h-full"
          @page="onPageChange"
          @toggle-needs-action="onToggleNeedsAction"
          @toggle-compact="compactMode = !compactMode"
        />
      </div>
    </div>
  </PageShell>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { useFiltersStore } from '../stores/filters'
import { useCommercialStore } from '../stores/commercial'
import FilterBar from '../components/layout/FilterBar.vue'
import BlendedPITable from '../components/commercial/BlendedPITable.vue'
import ProductPivotTable from '../components/commercial/ProductPivotTable.vue'
import CompetitorToggle from '../components/shared/CompetitorToggle.vue'
import DrilldownBreadcrumb from '../components/commercial/DrilldownBreadcrumb.vue'
import PageShell from '../components/shared/PageShell.vue'
import PageHeader from '../components/shared/PageHeader.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import PILegend from '../components/shared/PILegend.vue'
import AnimatedNumber from '../components/shared/AnimatedNumber.vue'
import { Scale, Target, CheckCircle, AlertTriangle, SlidersHorizontal, Table2, PencilLine, Palette } from 'lucide-vue-next'
import { useUrlSync } from '../composables/useUrlSync'

const route = useRoute()
const filters = useFiltersStore()
useUrlSync()
const store = useCommercialStore()

const selectedCompetitors = ref([])
const compactMode = ref(false)
const allCompetitors = computed(() => {
  const set = new Set([...store.pivotedCompetitors, ...store.blendedCompetitors])
  return [...set].sort()
})
const filteredPivotCompetitors = computed(() => {
  if (selectedCompetitors.value.length === 0) return store.pivotedCompetitors
  return store.pivotedCompetitors.filter(c => selectedCompetitors.value.includes(c))
})

// At-a-glance summary — derived from data already in the store (no extra API calls)
const subcatCount = computed(() => store.pivotedSubcatCount)
const productCount = computed(() => store.pivotedTotal)
const competitorCount = computed(() => allCompetitors.value.length)

onMounted(async () => {
  if (route.query.search) store.search = route.query.search
  if (route.query.main_category) filters.setFilter('mainCategory', [route.query.main_category])
  await filters.fetchFilterOptions()
  // Explicitly call both fetches to be resilient to Pinia HMR state
  await Promise.all([store.fetchBlendedPI(), store.fetchPivotedProducts()])
})

watchDebounced(
  () => [
    filters.mainCategory,
    filters.subCategory,
    filters.globalTier,
    filters.subcatTier,
    filters.actionType,
    filters.brand,
    filters.competitor,
    filters.fpNames,
    filters.vertical,
    filters.includePrivateLabel,
    filters.priceFallback,
  ],
  async () => {
    store.currentPage = 1
    try {
      await Promise.all([store.fetchBlendedPI(), store.fetchPivotedProducts()])
    } catch (err) {
      console.error('[CommercialView] filter fetch failed:', err)
    }
  },
  { debounce: 400, deep: true }
)

function onSubcategorySelect(subCategory) {
  filters.setFilter('subCategory', subCategory ? [subCategory] : [])
}

// Category roll-up drill: filter to that commercial category (the app's
// "main_category" filter, which maps to commercial_category_name) and let the
// cascade reset + reload subcategory options.
function onCategorySelect(commercialCategory) {
  filters.setFilter('mainCategory', commercialCategory ? [commercialCategory] : [])
}

function onSelectProduct({ productName, subcategory }) {
  store.search = productName
  filters.setFilter('subCategory', subcategory ? [subcategory] : [])
}

async function onPageChange(page) {
  await store.setPage(page)
}

async function onToggleNeedsAction(val) {
  await store.setNeedsActionOnly(val)
}

const definitions = [
  {
    title: 'Key Metrics',
    items: [
      { term: 'Blended PI', description: 'Weighted Price Index = BF price ÷ Competitor price, weighted by daily quantity. PI < 1 = BF cheaper, PI > 1 = BF more expensive.', icon: Scale },
      { term: 'Worst PI', description: 'The highest PI a product has across all competitors. Identifies where BF is most overpriced vs any single competitor.', icon: AlertTriangle },
      { term: 'Eligible Products', description: 'Products in the top 80% of revenue within their subcategory, worth tracking competitively.', icon: Target },
      { term: 'Used Products', description: 'Eligible products matched to a competitor with a recently updated price. These feed the Blended PI.', icon: CheckCircle },
    ],
  },
  {
    title: 'How to Use',
    items: [
      { term: 'Filter', description: 'Use dropdowns to narrow by category, subcategory, tier, or brand. Press Escape to clear all.', icon: SlidersHorizontal },
      { term: 'Blended PI Table', description: 'Click a row to filter to that subcategory. Dots show individual product PIs; click to jump to the product.', icon: Table2 },
      { term: 'BF Price', description: 'The Breadfast regular and sale price for the current scope, read-only. Inline price editing was removed; prices are sourced from BigQuery.', icon: PencilLine },
      { term: 'Addr %', description: 'Addressable: matched over what CAN be matched, i.e. our products minus those the matcher positively rejected. A subcategory at 30% mapped but 100% addressable is finished, not behind. Resolved per product across competitors, so "no-match" here means nobody carries an equivalent.', icon: Table2 },
      { term: 'They only', description: 'Competitor products with no link to anything of ours, placed into this subcategory by the category bridge. Rows with no matched product now appear with a blank PI instead of being hidden, because those are the biggest gaps.', icon: Table2 },
      { term: 'Include Private Label', description: 'Unchecking this excludes Breadfast own-brand products. The exclusion is approximate and not yet identical across views: brands named exactly "Breadfast" always drop, while sub-brands such as "Breadfast Bakery" may still be counted on some panels.', icon: SlidersHorizontal },
      { term: 'Color Coding', description: 'Cells are shaded by PI: PI < 0.95, near parity (0.95–1.05), and PI > 1.05. Lower PI = BF cheaper, higher PI = BF more expensive. Worst PI column shows your biggest competitive gap.', icon: Palette },
    ],
  },
]
</script>

<style scoped>
.product-panel {
  min-height: 420px;
  height: calc(100vh - 560px);
}
</style>
