<template>
  <PageShell :loading="store.loading" :error="store.error" @retry="store.fetchAll()">
    <div class="flex flex-col gap-4">
      <DefinitionsPanel :sections="definitions" storage-key="defs-commercial" />
      <FilterBar :loading="store.loading" />

      <!-- KPI Strip -->
      <div class="flex gap-3" v-if="store.kpis">
        <KpiCard :value="store.kpis.total_products" label="Total Products" subtitle="Across all categories" :icon="Package" icon-bg="bg-grey-100 text-grey-600" :stagger-index="0" />
        <KpiCard :value="store.kpis.eligible_products" label="Eligible Products" subtitle="Top 80% revenue" :icon="Target" icon-bg="bg-green-50 text-green-600" :stagger-index="1" />
        <KpiCard :value="store.kpis.used_products" label="Used Products" subtitle="Eligible + Matched + Fresh" :icon="CheckCircle" icon-bg="bg-brand-50 text-brand-primary" :stagger-index="2" />
        <KpiCard :value="store.kpis.avg_blended_pi" label="Avg Blended PI" format="pi" :highlight="true" :icon="TrendingUp" icon-bg="bg-brand-50 text-brand-primary" :stagger-index="3" />
        <KpiCard :value="store.kpis.needs_action" label="Need Action" :icon="AlertTriangle" icon-bg="bg-red-50 text-red-500" :stagger-index="4" />
        <div class="flex items-center">
          <ExportButton :fetcher="exportProducts" filename="pricing_products.csv" />
        </div>
      </div>

      <!-- Blended PI Table — full width -->
      <BlendedPITable
        :data="store.blendedPI"
        style="max-height: 420px;"
        @select="onTreemapSelect"
        @select-product="onSelectProduct"
      />

      <!-- Tabbed Panel: Products / Coverage Map -->
      <div class="flex flex-col overflow-hidden product-panel">
        <!-- Tab header -->
        <div class="flex border-b border-grey-200 bg-white rounded-t-lg px-1 shrink-0">
          <button
            v-for="tab in tabs"
            :key="tab"
            @click="activeTab = tab"
            class="px-4 py-2.5 text-body font-medium border-b-2 transition-colors -mb-px"
            :class="activeTab === tab
              ? 'border-brand-primary text-brand-primary'
              : 'border-transparent text-grey-500 hover:text-grey-700'"
          >{{ tab }}</button>
        </div>

        <!-- Tab content -->
        <div class="flex-1 overflow-hidden flex flex-col min-h-0">
          <ProductDetailTable
            v-show="activeTab === 'Products'"
            class="flex-1 min-h-0"
            :data="store.products"
            :total="store.productsTotal"
            :page="store.currentPage"
            :page-size="store.pageSize"
            :highlight="highlightProduct"
            @page="onPageChange"
          />
          <div v-show="activeTab === 'Coverage Map'" class="flex gap-4 p-4 flex-1 min-h-0 overflow-y-auto">
            <div class="w-1/2 min-w-0 self-stretch">
              <SubcategoryTreemap
                :data="store.treemap"
                :selected="filters.subCategory.length === 1 ? filters.subCategory[0] : null"
                class="h-full"
                @select="onTreemapSelect"
                @clear-filters="filters.clearAll()"
              />
            </div>
            <div class="w-1/2 min-w-0 flex flex-col gap-4">
              <CoverageFunnel title="Mapping Funnel" :stages="store.funnelMapping" class="flex-1" />
              <CoverageFunnel title="Coverage Funnel" :stages="store.funnelCoverage" class="flex-1" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </PageShell>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { useFiltersStore } from '../stores/filters'
import { useCommercialStore } from '../stores/commercial'
import FilterBar from '../components/layout/FilterBar.vue'
import KpiCard from '../components/layout/KpiCard.vue'
import SubcategoryTreemap from '../components/commercial/SubcategoryTreemap.vue'
import BlendedPITable from '../components/commercial/BlendedPITable.vue'
import ProductDetailTable from '../components/commercial/ProductDetailTable.vue'
import CoverageFunnel from '../components/commercial/CoverageFunnel.vue'
import ExportButton from '../components/shared/ExportButton.vue'
import PageShell from '../components/shared/PageShell.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import { commercialApi } from '../api/client'
import { useUrlSync } from '../composables/useUrlSync'
import {
  Scale, Target, CheckCircle, AlertTriangle, SlidersHorizontal, Table2, PencilLine, Palette,
  Package, TrendingUp,
} from 'lucide-vue-next'

const route = useRoute()
const filters = useFiltersStore()
useUrlSync()
const store = useCommercialStore()

const tabs = ['Products', 'Coverage Map']
const activeTab = ref('Products')

onMounted(async () => {
  // Pick up ?search= from cross-view navigation
  if (route.query.search) {
    store.search = route.query.search
    highlightProduct.value = route.query.search
  }
  // Pick up ?main_category= from category performance click
  if (route.query.main_category) {
    filters.setFilter('mainCategory', [route.query.main_category])
  }
  await filters.fetchFilterOptions()
  await store.fetchAll()
})

watchDebounced(() => filters.activeFilters, async () => {
  store.currentPage = 1
  await store.fetchAll()
}, { debounce: 400, deep: true })

const definitions = [
  {
    title: 'Key Metrics',
    items: [
      { term: 'Blended PI', description: 'Weighted Price Index = Competitor price \u00F7 BF price, weighted by daily sales quantity. PI > 1 = BF cheaper (green), PI < 1 = BF more expensive (red), PI \u2248 1 = parity (yellow).', icon: Scale },
      { term: 'Eligible Products', description: 'Products in the top 80% of revenue within their subcategory \u2014 the ones worth tracking competitively.', icon: Target },
      { term: 'Used Products', description: 'Eligible products that are also matched to a competitor and have a recently updated price. These feed the Blended PI calculation.', icon: CheckCircle },
      { term: 'Needs Action', description: 'Eligible products missing a competitor match, needing match review, or with stale prices.', icon: AlertTriangle },
    ],
  },
  {
    title: 'How to Use',
    items: [
      { term: 'Filter', description: 'Use the dropdowns to narrow by category, subcategory, tier, or action type. Press Escape to clear all.', icon: SlidersHorizontal },
      { term: 'Blended PI Table', description: 'Click a row to filter to that subcategory. Hover dots in the strip plot to see individual product PIs; click a dot to jump to that product.', icon: Table2 },
      { term: 'Product Detail', description: 'Search by name, sort any column. Click the pencil icon to edit Now Price / Now Sale Price. Select rows for bulk price edits.', icon: PencilLine },
      { term: 'Color Coding', description: 'Red = BF overpriced (PI < 0.95), Green = BF cheaper (PI > 1.05), Yellow = near parity (0.95\u20131.05). Applies to all charts and indicators.', icon: Palette },
    ],
  },
]

const highlightProduct = ref(null)

function onTreemapSelect(subCategory) {
  highlightProduct.value = null
  filters.setFilter('subCategory', subCategory ? [subCategory] : [])
}

function onSelectProduct({ productName, subcategory }) {
  highlightProduct.value = productName
  filters.setFilter('subCategory', subcategory ? [subcategory] : [])
}

async function onPageChange(page) {
  await store.setPage(page)
}

async function exportProducts() {
  const res = await commercialApi.exportCSV(filters.activeFilters)
  const blob = new Blob([res.data], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'pricing_products.csv'
  a.click()
  URL.revokeObjectURL(url)
  return []
}
</script>

<style scoped>
.product-panel {
  height: calc(100vh - 420px);
  min-height: 320px;
}
</style>
