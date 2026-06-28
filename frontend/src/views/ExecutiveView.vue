<template>
  <PageShell :loading="store.loading" :error="store.error" @retry="store.fetchAll()">
    <!-- Executive skeleton -->
    <template #skeleton>
      <div class="flex flex-col gap-4 animate-fade-in-up">
        <div class="grid grid-cols-3 gap-3">
          <div v-for="i in 3" :key="i" class="bg-white rounded-xl shadow-panel px-4 py-3">
            <div class="skeleton-shimmer h-3 w-24 rounded mb-2"></div>
            <div class="skeleton-shimmer h-8 w-20 rounded mb-1"></div>
            <div class="skeleton-shimmer h-2.5 w-32 rounded"></div>
          </div>
        </div>
        <div class="bg-white rounded-2xl shadow-panel p-4">
          <div class="skeleton-shimmer h-[200px] rounded"></div>
        </div>
        <div class="flex gap-4">
          <div class="w-1/2 bg-white rounded-2xl shadow-panel p-4">
            <div class="skeleton-shimmer h-[240px] rounded"></div>
          </div>
          <div class="w-1/2 bg-white rounded-2xl shadow-panel p-4">
            <div class="skeleton-shimmer h-[240px] rounded"></div>
          </div>
        </div>
      </div>
    </template>

    <div class="flex flex-col gap-4">

      <!-- ─── Command header: identity + the verdict leadership scans for ── -->
      <section v-if="kpis" class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden animate-fade-in-up">
        <!-- Title band -->
        <div class="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 px-6 lg:px-7 pt-6 pb-5 border-b border-grey-100">
          <div class="min-w-0">
            <h1 class="text-[1.75rem] leading-none font-semibold text-grey-900 tracking-tight">Executive overview</h1>
            <p class="text-body text-grey-500 mt-2">Where Breadfast stands against the market this week, at a glance.</p>
          </div>
          <span
            v-if="store.lastFetchedAt"
            class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-grey-50 ring-1 ring-grey-200/70 text-caption font-medium text-grey-600 shrink-0 tabular-nums"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" aria-hidden="true"></span>
            Updated {{ formatTime(store.lastFetchedAt) }}
          </span>
        </div>

        <!-- Verdict + subordinate stats -->
        <div class="grid lg:grid-cols-[1.4fr_1fr]">
          <div class="p-6 lg:p-7 lg:border-r border-grey-100">
            <div class="flex items-center gap-2 mb-3">
              <span class="text-caption font-semibold uppercase tracking-wide text-grey-500">Blended price index</span>
            </div>
            <span class="font-mono font-black leading-[0.82] tabular-nums inline-flex items-start gap-1" style="font-size:52px" :class="piTextClass(kpis.blended_pi)">
              <span v-if="kpis.blended_pi != null" class="text-[0.42em] mt-1">{{ piArrow(kpis.blended_pi) }}</span>
              {{ kpis.blended_pi != null ? kpis.blended_pi.toFixed(2) : '—' }}
            </span>
            <p class="text-body font-semibold mt-3.5 max-w-[44ch]" :class="piTextClass(kpis.blended_pi)">{{ piInterpretation }}</p>
            <p class="text-caption text-grey-500 mt-1 max-w-[48ch]">Quantity-weighted Breadfast price ÷ competitor price, across every tracked competitor.</p>
          </div>

          <!-- Subordinate stats -->
          <dl class="grid grid-cols-2 gap-px bg-grey-100">
            <div class="bg-white p-5 lg:p-6 flex flex-col justify-center gap-1.5">
              <dt class="text-caption text-grey-500 font-medium">Active products</dt>
              <dd class="font-mono text-[26px] font-bold text-grey-900 tabular-nums leading-none"><AnimatedNumber :value="kpis.total_products" /></dd>
              <dd class="text-micro text-grey-500">{{ kpis.eligible_products?.toLocaleString() }} eligible ({{ kpis.eligible_pct }}%)</dd>
            </div>
            <div class="bg-white p-5 lg:p-6 flex flex-col justify-center gap-1.5">
              <dt class="text-caption text-grey-500 font-medium">Competitors tracked</dt>
              <dd class="font-mono text-[26px] font-bold text-grey-900 tabular-nums leading-none"><AnimatedNumber :value="competitorCount" /></dd>
              <dd class="text-micro text-grey-500">with live price data</dd>
            </div>
          </dl>
        </div>
      </section>

      <!-- Definitions -->
      <DefinitionsPanel :sections="definitions" storage-key="defs-executive" class="animate-fade-in-up stagger-1" />

      <!-- Filters -->
      <FilterBar :loading="store.loading" class="animate-fade-in-up stagger-2" />

      <!-- PI legend — teaches "both tails bad" before the PI-colored tables below -->
      <div class="flex justify-end animate-fade-in-up stagger-3">
        <PILegend />
      </div>

      <!-- ─── Row 1: Competitor PI Table + Classification + Category PI ── -->
      <div class="flex flex-col xl:flex-row gap-4 animate-fade-in-up stagger-3">
        <div class="xl:w-[60%] min-w-0">
          <CompetitorPITable
            :data="enrichedCompetitorPI"
            @select-competitor="navigateToCompetitor"
          />
        </div>
        <div class="xl:w-[40%] min-w-0 flex flex-col gap-4">
          <ClassificationBreakdown
            :data="store.dashboard?.classification_breakdown"
            :mapping-progress="store.dashboard?.mapping_progress || []"
            @navigate="navigateToAction"
          />
          <!-- Category PI -->
          <div v-if="store.categoryPerformance?.length" class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
            <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2">
              <Layers class="w-4 h-4 text-brand-primary" />
              <span class="text-subheading font-bold text-grey-900 tracking-tightish">Category PI</span>
              <span class="text-caption text-grey-400 ml-1">click to explore</span>
            </div>
            <div class="flex flex-wrap gap-2 px-4 py-3">
              <button
                v-for="cat in store.categoryPerformance"
                :key="cat.category_name"
                class="flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all hover:shadow-panel-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-lightest"
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

      <!-- ─── Geographic exposure: blended PI by FP × competitor ── -->
      <GeographicExposure
        v-if="store.fpCompetitorPi"
        :data="store.fpCompetitorPi"
        class="animate-fade-in-up stagger-4"
        @select-fp="onSelectFp"
      />

      <!-- ─── Row 2: Mapping Progress (full width) ──────────────── -->
      <MappingProgressChart :data="store.dashboard?.mapping_progress || []" class="animate-fade-in-up stagger-4" />

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
import GeographicExposure from '../components/executive/GeographicExposure.vue'
import PageShell from '../components/shared/PageShell.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import { piTextClass, piBgClass, piToHex, piTreatment, piArrow } from '../utils/piColor'
import PILegend from '../components/shared/PILegend.vue'
import AnimatedNumber from '../components/shared/AnimatedNumber.vue'
import {
  Gauge, Package, Users, Clock, Layers, ArrowUp, ArrowDown,
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
    filters.fpNames,
    filters.includePrivateLabel,
    filters.priceFallback,
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

// Click an FP (summary or grid) → scope the whole Executive view to it.
// filters.fpNames is watched above, so this refetches the dashboard + this panel.
function onSelectFp(fp) {
  filters.setFilter('fpNames', [fp])
}

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

// pi_deviation = sale_PI - 1, so PI = 1 + dev. Drive deviation chrome straight
// from piColor so it follows the "both tails bad" orientation: pricier (dev > 0)
// = warm, cheaper (dev < 0) = cool, near-parity = green.
function _piFromDev(dev) {
  return dev == null ? null : 1 + dev
}

function deviationTextClass(dev) {
  return piTextClass(_piFromDev(dev))
}

function deviationBgClass(dev) {
  return piBgClass(_piFromDev(dev))
}

function deviationBorderClass(dev) {
  const border = {
    cheaper: 'border-blue-200 bg-blue-50 hover:border-blue-400',
    pricier: 'border-orange-200 bg-orange-50 hover:border-orange-400',
    parity: 'border-green-200 bg-green-50 hover:border-green-400',
    none: 'border-grey-200 bg-grey-50 hover:border-grey-300',
  }
  return border[piTreatment(_piFromDev(dev)).dir]
}

// ─── Definitions ────────────────────────────────────────────────
const definitions = [
  {
    title: 'Key Metrics',
    items: [
      { term: 'Blended PI', description: 'Weighted Price Index = BF price ÷ Competitor price, weighted by daily sales quantity. PI > 1 means BF is more expensive. PI < 1 means BF is cheaper.', icon: Scale },
      { term: 'Eligible Products', description: 'Products in the top 80% of revenue within their subcategory, worth tracking competitively.', icon: Target },
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

