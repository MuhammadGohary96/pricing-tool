<template>
  <PageShell :loading="store.loading" :error="store.error" @retry="store.fetchAll()">
    <div class="flex flex-col gap-4">
      <DefinitionsPanel :sections="definitions" storage-key="defs-commercial" />
      <FilterBar :loading="store.loading" hide-competitor />

      <!-- Competitor visibility toggle -->
      <CompetitorToggle
        v-if="allCompetitors.length > 0"
        :competitors="allCompetitors"
        v-model="selectedCompetitors"
      />

      <!-- Blended PI Table -->
      <BlendedPITable
        :data="store.blendedPI"
        :competitors="store.blendedCompetitors"
        :selected-competitors="selectedCompetitors"
        style="max-height: 420px;"
        @select="onSubcategorySelect"
        @select-product="onSelectProduct"
      />

      <!-- Pivoted Product Table -->
      <div class="flex-1 overflow-hidden product-panel">
        <ProductPivotTable
          :data="store.pivotedProducts"
          :total="store.pivotedTotal"
          :page="store.currentPage"
          :page-size="store.pageSize"
          :competitors="filteredPivotCompetitors"
          :needs-action-only="store.needsActionOnly"
          class="h-full"
          @page="onPageChange"
          @toggle-needs-action="onToggleNeedsAction"
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
import CompetitorToggle from '../components/commercial/CompetitorToggle.vue'
import PageShell from '../components/shared/PageShell.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import { Scale, Target, CheckCircle, AlertTriangle, SlidersHorizontal, Table2, PencilLine, Palette } from 'lucide-vue-next'
import { useUrlSync } from '../composables/useUrlSync'

const route = useRoute()
const filters = useFiltersStore()
useUrlSync()
const store = useCommercialStore()

const selectedCompetitors = ref([])
const allCompetitors = computed(() => {
  const set = new Set([...store.pivotedCompetitors, ...store.blendedCompetitors])
  return [...set].sort()
})
const filteredPivotCompetitors = computed(() => {
  if (selectedCompetitors.value.length === 0) return store.pivotedCompetitors
  return store.pivotedCompetitors.filter(c => selectedCompetitors.value.includes(c))
})

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
    filters.includePrivateLabel,
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
      { term: 'Blended PI', description: 'Weighted Price Index = Competitor price ÷ BF price, weighted by daily quantity. PI > 1 = BF cheaper (green), PI < 1 = BF more expensive (red).', icon: Scale },
      { term: 'Worst PI', description: 'The highest PI a product has across all competitors — identifies where BF is most overpriced vs any single competitor.', icon: AlertTriangle },
      { term: 'Eligible Products', description: 'Products in the top 80% of revenue within their subcategory — worth tracking competitively.', icon: Target },
      { term: 'Used Products', description: 'Eligible products matched to a competitor with a recently updated price. These feed the Blended PI.', icon: CheckCircle },
    ],
  },
  {
    title: 'How to Use',
    items: [
      { term: 'Filter', description: 'Use dropdowns to narrow by category, subcategory, tier, or brand. Press Escape to clear all.', icon: SlidersHorizontal },
      { term: 'Blended PI Table', description: 'Click a row to filter to that subcategory. Dots show individual product PIs; click to jump to the product.', icon: Table2 },
      { term: 'Edit Price', description: 'Click any BF Price cell to edit the now price inline. Saves to Catalog API if you have write access.', icon: PencilLine },
      { term: 'Color Coding', description: 'Red = BF overpriced (PI < 0.95), Green = BF cheaper (PI > 1.05), Yellow = near parity. Worst PI column shows your biggest competitive gap.', icon: Palette },
    ],
  },
]
</script>

<style scoped>
.product-panel {
  min-height: 400px;
  height: calc(100vh - 480px);
}
</style>
