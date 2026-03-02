<template>
  <PageShell :loading="store.loading" :error="store.error" @retry="store.fetchAll()">
    <div class="flex flex-col gap-4">
      <DefinitionsPanel :sections="definitions" storage-key="defs-executive" />

      <!-- Export row + data freshness -->
      <div class="flex items-center justify-between">
        <span v-if="store.lastFetchedAt" class="text-micro text-grey-400 flex items-center gap-1">
          <Clock class="w-3 h-3" />
          Data as of {{ formatDate(store.lastFetchedAt) }}
        </span>
        <span v-else></span>
        <ExportButton :fetcher="exportSummary" filename="executive_summary.csv" />
      </div>

      <!-- Top Row: PI Gauge + Mini KPIs -->
      <div class="flex gap-4">
        <div class="w-7/12 min-w-0">
          <PIGauge :value="store.summary?.overall_blended_pi" />
        </div>
        <div class="w-5/12 min-w-0">
          <MiniKpiCards :summary="store.summary" />
        </div>
      </div>

      <!-- Middle Row: Top/Bottom + Category Performance -->
      <div class="flex gap-4">
        <div class="w-1/2">
          <TopBottomSubcats
            :cheapest="store.summary?.top_5_cheapest || []"
            :expensive="store.summary?.top_5_expensive || []"
          />
        </div>
        <div class="w-1/2">
          <CategoryPerformance :data="store.categoryPerformance" />
        </div>
      </div>

      <!-- Top Revenue Items Needing Action -->
      <div v-if="store.topActions.length" class="bg-white rounded-xl shadow-card overflow-hidden">
        <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2">
          <AlertCircle class="w-4 h-4 text-amber-500" />
          <span class="text-subheading font-bold text-grey-900">Top Revenue Items Needing Action</span>
          <span class="text-caption text-grey-500 bg-grey-100 px-2 py-0.5 rounded-full ml-1">{{ store.topActions.length }}</span>
        </div>
        <div class="divide-y divide-grey-50">
          <div
            v-for="(item, i) in store.topActions"
            :key="item.product_id"
            class="flex items-center gap-3 px-4 py-2.5 hover:bg-brand-50 transition-colors cursor-pointer group"
            @click="navigateToProduct(item)"
          >
            <div class="w-6 h-6 rounded-full bg-amber-50 flex items-center justify-center text-micro font-bold text-amber-700 shrink-0">
              {{ i + 1 }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-body text-grey-900 truncate">{{ item.product_name }}</div>
              <div class="text-micro text-grey-500">{{ item.sub_category_name }}</div>
            </div>
            <span class="inline-block px-1.5 py-px rounded-full text-micro font-medium bg-amber-50 text-amber-700 shrink-0">{{ item.action_type }}</span>
            <span class="text-caption text-grey-500 font-mono shrink-0">EGP {{ formatRevenue(item.total_revenue) }}</span>
            <ChevronRight class="w-3.5 h-3.5 text-grey-300 group-hover:text-brand-primary transition-colors shrink-0" />
          </div>
        </div>
      </div>
    </div>
  </PageShell>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useExecutiveStore } from '../stores/executive'
import PIGauge from '../components/executive/PIGauge.vue'
import MiniKpiCards from '../components/executive/MiniKpiCards.vue'
import TopBottomSubcats from '../components/executive/TopBottomSubcats.vue'
import CategoryPerformance from '../components/executive/CategoryPerformance.vue'
import PageShell from '../components/shared/PageShell.vue'
import ExportButton from '../components/shared/ExportButton.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import { Gauge, ShieldCheck, BarChart3, Activity, ArrowUpDown, TrendingUp, Clock, AlertCircle, ChevronRight } from 'lucide-vue-next'

const router = useRouter()
const store = useExecutiveStore()

const definitions = [
  {
    title: 'Key Metrics',
    items: [
      { term: 'Overall Blended PI', description: 'Single number summarizing BF\u2019s competitive pricing position across all categories. Target: close to 1.00.', icon: Gauge },
      { term: 'Coverage Rate', description: 'Percentage of eligible products that are fully matched and have fresh prices. Higher = more reliable PI.', icon: ShieldCheck },
      { term: 'Category Performance', description: 'Blended PI broken down by category \u2014 identifies which categories are most/least competitive.', icon: BarChart3 },
    ],
  },
  {
    title: 'How to Read',
    items: [
      { term: 'PI Gauge', description: 'The large gauge shows the overall blended PI. Needle at 1.0 = perfect parity. Right (green) = BF cheaper, Left (red) = BF more expensive.', icon: Activity },
      { term: 'Top/Bottom Tables', description: 'The 5 cheapest and 5 most expensive subcategories \u2014 quick view of best and worst performers.', icon: ArrowUpDown },
      { term: 'Drill Down', description: 'Click any subcategory in the top/bottom lists to view detailed pricing in the Commercial dashboard.', icon: TrendingUp },
    ],
  },
]

onMounted(async () => {
  await store.fetchAll()
})

function formatDate(date) {
  if (!date) return ''
  const d = date instanceof Date ? date : new Date(date)
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

function navigateToProduct(item) {
  router.push({ path: '/commercial', query: { search: item.product_name } })
}

function formatRevenue(val) {
  if (val == null) return '--'
  if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`
  if (val >= 1000) return `${(val / 1000).toFixed(0)}K`
  return val.toFixed(0)
}

function exportSummary() {
  const s = store.summary
  if (!s) return []
  const rows = [
    { metric: 'Overall Blended PI', value: s.overall_blended_pi },
    { metric: 'Coverage Rate (%)', value: s.coverage_pct },
    { metric: 'Eligible Products', value: s.eligible_products },
    { metric: 'Used Products', value: s.used_products },
    { metric: 'Needs Action', value: s.needs_action },
  ]
  ;(store.categoryPerformance || []).forEach(c => {
    rows.push({ metric: `PI - ${c.main_category}`, value: c.blended_pi })
  })
  return rows
}
</script>
