<template>
  <PageShell :loading="store.loading" :error="store.error" @retry="store.fetchAll()">
    <!-- Executive skeleton -->
    <template #skeleton>
      <div class="flex flex-col gap-4 animate-fade-in-up">
        <div class="grid grid-cols-3 gap-3">
          <div v-for="i in 3" :key="i" class="bg-white rounded-lg shadow-card px-4 py-3">
            <div class="skeleton-shimmer h-3 w-24 rounded mb-2"></div>
            <div class="skeleton-shimmer h-8 w-20 rounded mb-1"></div>
            <div class="skeleton-shimmer h-2.5 w-32 rounded"></div>
          </div>
        </div>
        <div class="bg-white rounded-lg shadow-card p-4">
          <div class="skeleton-shimmer h-[200px] rounded"></div>
        </div>
        <div class="flex gap-4">
          <div class="w-1/2 bg-white rounded-lg shadow-card p-4">
            <div class="skeleton-shimmer h-[240px] rounded"></div>
          </div>
          <div class="w-1/2 bg-white rounded-lg shadow-card p-4">
            <div class="skeleton-shimmer h-[240px] rounded"></div>
          </div>
        </div>
      </div>
    </template>

    <div class="flex flex-col gap-4">

      <!-- Header row -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-heading font-bold text-grey-900">Pricing Intelligence</h1>
          <p class="text-caption text-grey-400">Executive Dashboard · {{ today }}</p>
        </div>
        <span v-if="store.lastFetchedAt" class="text-micro text-grey-400 flex items-center gap-1">
          <Clock class="w-3 h-3" />
          Updated {{ formatTime(store.lastFetchedAt) }}
        </span>
      </div>

      <!-- Definitions -->
      <DefinitionsPanel :sections="definitions" storage-key="defs-executive" />

      <!-- Filters -->
      <FilterBar :loading="store.loading" />

      <!-- ─── KPI Cards ─────────────────────────────────────────────── -->
      <div v-if="kpis" class="grid grid-cols-3 gap-3">

        <!-- 1. Overall Blended PI (bespoke card) -->
        <div
          class="bg-white rounded-lg shadow-card px-4 py-3 flex flex-col gap-1 card-interactive animate-fade-in-up border-l-[3px] border-brand-primary relative overflow-hidden kpi-card-wrap"
        >
          <div class="kpi-accent-bar"></div>
          <div class="flex items-center justify-between">
            <span class="text-caption text-grey-500 font-semibold uppercase tracking-wide">Overall Blended PI</span>
            <div class="w-8 h-8 rounded-full bg-brand-50 flex items-center justify-center">
              <Gauge class="w-4 h-4 text-brand-primary" />
            </div>
          </div>
          <div class="flex items-baseline gap-2">
            <span class="text-kpi font-black" :class="piTextClass(kpis.blended_pi)">
              {{ kpis.blended_pi != null ? kpis.blended_pi.toFixed(4) : '—' }}
            </span>
            <!-- WoW trend badge -->
            <span
              v-if="wowPI"
              class="inline-flex items-center gap-0.5 text-micro font-bold px-1.5 py-0.5 rounded"
              :class="wowPI.delta > 0 ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-700'"
            >
              {{ wowPI.delta > 0 ? '▲' : '▼' }} {{ Math.abs(wowPI.delta * 100).toFixed(1) }}% WoW
            </span>
          </div>
          <div class="text-caption" :class="piTextClass(kpis.blended_pi)">{{ piInterpretation }}</div>
          <!-- PI Sparkline -->
          <svg v-if="sparklinePath" width="120" height="28" class="mt-1 opacity-50">
            <polyline :points="sparklinePath" fill="none" :stroke="piToHex(kpis.blended_pi)" stroke-width="1.5" stroke-linejoin="round" />
          </svg>
        </div>

        <!-- 2. Active Products -->
        <KpiCard
          :value="kpis.total_products"
          label="Active Products"
          :subtitle="`${kpis.eligible_products?.toLocaleString()} eligible (${kpis.eligible_pct}%)`"
          :icon="Package"
          icon-bg="bg-grey-100 text-grey-600"
          :stagger-index="1"
          :highlight="true"
          :trend="wowUsed"
        />

        <!-- 3. Competitors Tracked -->
        <KpiCard
          :value="competitorCount"
          label="Competitors Tracked"
          subtitle="with live price data"
          :icon="Users"
          icon-bg="bg-blue-50 text-blue-600"
          :stagger-index="2"
          :highlight="true"
        />
      </div>

      <!-- ─── Row 1: Competitor PI Table + Classification + Category PI ── -->
      <div class="flex gap-4">
        <div class="w-[60%] min-w-0">
          <CompetitorPITable
            :data="enrichedCompetitorPI"
            @select-competitor="navigateToCompetitor"
          />
        </div>
        <div class="w-[40%] min-w-0 flex flex-col gap-4">
          <ClassificationBreakdown
            :data="store.dashboard?.classification_breakdown"
            :mapping-progress="store.dashboard?.mapping_progress || []"
            @navigate="navigateToAction"
          />
          <!-- Category PI -->
          <div v-if="store.categoryPerformance?.length" class="bg-white rounded-lg shadow-card overflow-hidden">
            <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2">
              <Layers class="w-4 h-4 text-brand-primary" />
              <span class="text-subheading font-bold text-grey-900">Category PI</span>
              <span class="text-caption text-grey-400 ml-1">click to explore</span>
            </div>
            <div class="flex flex-wrap gap-2 px-4 py-3">
              <button
                v-for="cat in store.categoryPerformance"
                :key="cat.category_name"
                class="flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all hover:shadow-card-hover"
                :class="deviationBorderClass(cat.pi_deviation)"
                @click="navigateToCategory(cat.category_name)"
              >
                <span class="text-body text-grey-800 font-medium">{{ cat.category_name }}</span>
                <span class="font-mono text-body font-bold" :class="piTextClass(cat.blended_pi)">
                  {{ cat.blended_pi?.toFixed(2) ?? '—' }}
                </span>
                <span
                  class="inline-block px-1.5 py-0.5 rounded text-micro font-bold"
                  :class="[deviationTextClass(cat.pi_deviation), deviationBgClass(cat.pi_deviation)]"
                >
                  {{ formatDeviation(cat.pi_deviation) }}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Row 2: Mapping Progress (full width) ──────────────── -->
      <MappingProgressChart :data="store.dashboard?.mapping_progress || []" />

    </div>
  </PageShell>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { useFiltersStore } from '../stores/filters'
import { useExecutiveStore } from '../stores/executive'
import KpiCard from '../components/layout/KpiCard.vue'
import FilterBar from '../components/layout/FilterBar.vue'
import CompetitorPITable from '../components/executive/CompetitorPITable.vue'
import MappingProgressChart from '../components/executive/MappingProgressChart.vue'
import ClassificationBreakdown from '../components/executive/ClassificationBreakdown.vue'
import PageShell from '../components/shared/PageShell.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import { piTextClass, piToHex } from '../utils/piColor'
import {
  Gauge, Package, Users, Clock, Layers,
  Scale, AlertTriangle, Target, CheckCircle, BarChart2 as BarChart2Icon, PieChart,
} from 'lucide-vue-next'

const router = useRouter()
const filters = useFiltersStore()
const store = useExecutiveStore()

onMounted(() => store.fetchAll())

watchDebounced(
  () => [
    filters.mainCategory,
    filters.subCategory,
    filters.globalTier,
    filters.subcatTier,
    filters.brand,
    filters.competitor,
    filters.includePrivateLabel,
  ],
  async () => {
    try {
      await store.fetchAll()
    } catch (err) {
      console.error('[ExecutiveView] filter fetch failed:', err)
    }
  },
  { debounce: 400, deep: true }
)

const kpis = computed(() => store.dashboard?.kpis ?? null)
const competitorCount = computed(() => store.dashboard?.competitor_pi?.length ?? 0)
const today = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })

// ─── Week-over-Week helpers ─────────────────────────────────────
const wowMap = computed(() => {
  if (!store.weekOverWeek) return {}
  const map = {}
  for (const item of store.weekOverWeek) map[item.metric_name] = item
  return map
})

const wowPI = computed(() => wowMap.value['Blended PI'] || null)

const wowUsed = computed(() => {
  const w = wowMap.value['Used Products']
  if (!w) return null
  return { direction: w.delta > 0 ? 'up' : 'down', value: `${Math.abs(Math.round(w.delta)).toLocaleString()} WoW` }
})

const wowCoverage = computed(() => {
  const w = wowMap.value['Coverage %']
  if (!w) return null
  return { direction: w.delta > 0 ? 'up' : 'down', value: `${Math.abs(w.delta).toFixed(1)}% WoW` }
})

// ─── wowCoverage kept but card removed; keep for possible reuse ─

// ─── PI interpretation ──────────────────────────────────────────
const piInterpretation = computed(() => {
  const pi = kpis.value?.blended_pi
  if (pi == null) return ''
  const pct = Math.abs((pi - 1) * 100).toFixed(1)
  if (pi > 1.001) return `BF is ${pct}% more expensive overall`
  if (pi < 0.999) return `BF is ${pct}% cheaper overall`
  return 'At parity with market'
})

// ─── PI Sparkline (SVG polyline) ────────────────────────────────
const sparklinePath = computed(() => {
  const values = store.piTrend?.map(p => p.value) || []
  if (values.length < 2) return ''
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 0.01
  const w = 120, h = 28
  return values.map((v, i) => {
    const x = (i / (values.length - 1)) * w
    const y = h - ((v - min) / range) * (h - 2) - 1
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})

// ─── Enriched competitor PI (merge mapping data for tooltips) ───
const enrichedCompetitorPI = computed(() => {
  const pi = store.dashboard?.competitor_pi || []
  const progress = store.dashboard?.mapping_progress || []
  const progressMap = Object.fromEntries(progress.map(p => [p.competitor_name, p]))
  return pi.map(row => ({
    ...row,
    _mapping: progressMap[row.competitor_name] || null,
  }))
})

// ─── Navigation helpers ─────────────────────────────────────────
function navigateToCompetitor(name) {
  router.push({ path: '/commercial', query: { competitor: name } })
}

function navigateToAction(filters) {
  router.push({ path: '/commercial', query: filters })
}

function navigateToCategory(categoryName) {
  router.push({ path: '/commercial', query: { main_category: categoryName } })
}

// ─── Formatting helpers ─────────────────────────────────────────
function formatTime(date) {
  if (!date) return ''
  const d = date instanceof Date ? date : new Date(date)
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

function formatDeviation(dev) {
  if (dev == null) return '—'
  const sign = dev > 0 ? '+' : ''
  return `${sign}${(dev * 100).toFixed(1)}%`
}

function deviationTextClass(dev) {
  if (dev == null) return 'text-grey-400'
  if (dev > 0.005) return 'text-green-700'
  if (dev < -0.005) return 'text-red-700'
  return 'text-grey-500'
}

function deviationBgClass(dev) {
  if (dev == null) return 'bg-grey-50'
  if (dev > 0.005) return 'bg-green-50'
  if (dev < -0.005) return 'bg-red-50'
  return 'bg-grey-50'
}

function deviationBorderClass(dev) {
  if (dev == null) return 'border-grey-200 bg-grey-50'
  if (dev > 0.005) return 'border-green-200 bg-green-50 hover:border-green-400'
  if (dev < -0.005) return 'border-red-200 bg-red-50 hover:border-red-400'
  return 'border-grey-200 bg-grey-50 hover:border-grey-300'
}

// ─── Definitions ────────────────────────────────────────────────
const definitions = [
  {
    title: 'Key Metrics',
    items: [
      { term: 'Blended PI', description: 'Weighted Price Index = Competitor price / BF price, weighted by daily sales quantity. PI > 1 means BF is MORE EXPENSIVE. PI < 1 means BF is cheaper.', icon: Scale },
      { term: 'Eligible Products', description: 'Products in the top 80% of revenue within their subcategory — worth tracking competitively.', icon: Target },
      { term: 'Used Products', description: 'Eligible products matched to a competitor with a recently updated price. These feed the Blended PI calculation.', icon: CheckCircle },
      { term: 'Mapped', description: 'Products successfully matched to a competitor equivalent. Not PL = non-private-label; PL = Breadfast own-brand.', icon: AlertTriangle },
    ],
  },
  {
    title: 'Charts & Tables',
    items: [
      { term: 'Competitor Table', description: 'Click any row to navigate to the Commercial view filtered for that competitor. Coverage bar shows mapped/eligible ratio per competitor.', icon: BarChart2Icon },
      { term: 'Mapping Progress', description: 'Stacked bar showing product status per competitor. Diamond marker = Potential Reach if all potential matches were mapped.', icon: BarChart2Icon },
      { term: 'Classification', description: 'Donut chart of product x competitor pairs by mapping status. Use competitor pills to filter. Click a segment to navigate.', icon: PieChart },
    ],
  },
]
</script>

<style scoped>
.kpi-accent-bar {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: #a3007c;
  border-radius: 8px 8px 0 0;
  opacity: 0;
  transition: opacity 0.2s;
}
.kpi-card-wrap:hover .kpi-accent-bar {
  opacity: 1;
}
</style>
