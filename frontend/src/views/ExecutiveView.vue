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
      <PageHeader
        v-if="kpis"
        eyebrow="Price intelligence"
        title="Executive"
        accent="overview"
        subtitle="Where Breadfast stands against the market this week, at a glance."
      >
        <template #actions>
          <span
            v-if="store.lastFetchedAt"
            :title="syncTitle"
            class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-grey-50 ring-1 ring-grey-200/70 text-caption font-medium text-grey-600 shrink-0"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" aria-hidden="true"></span>
            {{ syncLabel }}
          </span>
        </template>

        <template #stats>
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
              <!-- Was the flat claim "with live price data", which is untrue for a
                   competitor whose catalogue was never crawled. -->
              <dd class="text-micro text-grey-500">
                {{ withCatalogueCount != null ? `${withCatalogueCount} with a live catalogue` : 'benchmarked' }}
              </dd>
            </div>
          </dl>
        </div>
        </template>
      </PageHeader>

      <!-- Definitions -->
      <DefinitionsPanel :sections="definitions" storage-key="defs-executive" class="animate-fade-in-up stagger-1" />

      <!-- Filters -->
      <FilterBar :loading="store.loading" hide-competitor class="animate-fade-in-up stagger-2" />

      <!-- Competitor visibility pills (left-aligned), same as Commercial -->
      <CompetitorToggle
        v-if="allCompetitors.length > 0"
        :competitors="allCompetitors"
        v-model="selectedCompetitors"
        :default-limit="5"
        class="animate-fade-in-up stagger-2"
      />

      <!-- ═══ TIER 2 · Pricing position — the PI drill: competitor ▸ category ▸ location ═══ -->
      <div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 mt-1 animate-fade-in-up stagger-3">
        <div class="flex items-baseline gap-2.5 min-w-0">
          <h2 class="text-caption font-semibold uppercase tracking-wide text-grey-500">Pricing position</h2>
          <span class="text-micro text-grey-400 truncate">where we stand, by competitor, category, and location</span>
        </div>
        <PILegend />
      </div>

      <!-- One table per competitor: price position and assortment coverage, which
           were two separate panels at opposite ends of this page. Same grain, so
           the same row now answers "are we priced right against them" and "how
           much of our range can we even compare". -->
      <CompetitorScorecard
        v-if="visibleOverview.length"
        :data="visibleOverview"
        :mapping-progress="store.dashboard?.mapping_progress || []"
        :vertical="filters.vertical"
        class="animate-fade-in-up stagger-3"
        @select-competitor="navigateToCompetitor"
      />

      <!-- Classification donut keeps its place in this tier, now paired with the
           category strip (also a pricing-position panel) so neither sits alone. -->
      <div class="flex flex-col xl:flex-row gap-4 items-start animate-fade-in-up stagger-3">
        <div class="w-full xl:w-[42%] min-w-0">
          <ClassificationBreakdown
            :data="store.dashboard?.classification_breakdown"
            :mapping-progress="store.dashboard?.mapping_progress || []"
            @navigate="navigateToAction"
          />
        </div>
        <div
          v-if="store.categoryPerformance?.length"
          class="w-full xl:w-[58%] min-w-0 bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden"
        >
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
            </button>
          </div>
        </div>
      </div>

      <!-- By location: blended PI by FP × competitor (widest grain, full width) -->
      <GeographicExposure
        v-if="geoData"
        :data="geoData"
        class="animate-fade-in-up stagger-4"
        @select-fp="onSelectFp"
      />

      <!-- ═══ TIER 3 · Data coverage — how complete the mapping behind these numbers is ═══ -->
      <div class="flex items-baseline gap-2.5 mt-3 animate-fade-in-up stagger-5">
        <h2 class="text-caption font-semibold uppercase tracking-wide text-grey-500">Data coverage</h2>
        <span class="text-micro text-grey-400">how much of the catalog is mapped per competitor, and the reachable headroom</span>
      </div>
      <MappingProgressChart :data="store.dashboard?.mapping_progress || []" class="animate-fade-in-up stagger-5" />

    </div>
  </PageShell>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { useFiltersStore } from '../stores/filters'
import { useExecutiveStore } from '../stores/executive'
import { dataApi } from '../api/client'
import KpiCard from '../components/layout/KpiCard.vue'
import FilterBar from '../components/layout/FilterBar.vue'
import CompetitorToggle from '../components/shared/CompetitorToggle.vue'
import MappingProgressChart from '../components/executive/MappingProgressChart.vue'
import ClassificationBreakdown from '../components/executive/ClassificationBreakdown.vue'
import GeographicExposure from '../components/executive/GeographicExposure.vue'
import CompetitorScorecard from '../components/executive/CompetitorScorecard.vue'
import PageShell from '../components/shared/PageShell.vue'
import PageHeader from '../components/shared/PageHeader.vue'
import DefinitionsPanel from '../components/shared/DefinitionsPanel.vue'
import { piTextClass, piTreatment, piArrow } from '../utils/piColor'
import PILegend from '../components/shared/PILegend.vue'
import AnimatedNumber from '../components/shared/AnimatedNumber.vue'
import {
  Gauge, Package, Users, Clock, Layers, ArrowUp, ArrowDown,
  Scale, AlertTriangle, Target, CheckCircle, BarChart2 as BarChart2Icon, PieChart,
} from 'lucide-vue-next'

const router = useRouter()
const filters = useFiltersStore()
const store = useExecutiveStore()

// Header badge reflects the backend's last BigQuery sync, NOT the client fetch
// time. Two distinct backend timestamps:
//   data_synced_at  — when the data ITSELF was last pulled/changed (real freshness)
//   last_checked_at — when freshness was last verified (advances even on a
//                     no-change check, so it is NOT the same as a real sync)
// The label uses data_synced_at so a mere re-check is never mislabeled as a sync;
// the tooltip shows both. We re-poll so that if new data lands while the page is
// open, data_synced_at advances and the badge updates instead of going stale.
const dataSyncedAt = ref(null)
const lastCheckedAt = ref(null)
const now = ref(Date.now())
let clockTimer = null
let pollTimer = null

async function refreshSyncTime() {
  try {
    const { data } = await dataApi.getStatus()
    dataSyncedAt.value = data.data_synced_at ? new Date(data.data_synced_at) : null
    lastCheckedAt.value = data.last_checked_at ? new Date(data.last_checked_at) : null
  } catch { /* non-critical — badge falls back to a generic label */ }
}

function ago(ms) {
  const diffMin = Math.floor((now.value - ms) / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin === 1) return '1 min ago'
  if (diffMin < 60) return `${diffMin} mins ago`
  const h = Math.floor(diffMin / 60)
  if (h < 24) return h === 1 ? '1 hr ago' : `${h} hrs ago`
  const days = Math.floor(h / 24)
  return days === 1 ? '1 day ago' : `${days} days ago`
}

const syncLabel = computed(() =>
  dataSyncedAt.value ? `Synced ${ago(dataSyncedAt.value.getTime())}` : 'Data synced'
)

const syncTitle = computed(() => {
  const parts = []
  if (dataSyncedAt.value) parts.push(`Data last synced from BigQuery: ${dataSyncedAt.value.toLocaleString()}`)
  if (lastCheckedAt.value) parts.push(`Freshness last checked: ${lastCheckedAt.value.toLocaleString()}`)
  return parts.length ? parts.join(' · ') : 'Data sync status'
})

onMounted(() => {
  store.fetchAll()
  refreshSyncTime()
  // Advance the relative clock often so "X mins ago" stays accurate, but only
  // re-poll the backend status every 10 minutes (it changes at most hourly).
  clockTimer = setInterval(() => { now.value = Date.now() }, 60000)
  pollTimer = setInterval(refreshSyncTime, 600000)
})
onUnmounted(() => {
  if (clockTimer) { clearInterval(clockTimer); clockTimer = null }
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
})

watchDebounced(
  () => [
    filters.mainCategory,
    filters.subCategory,
    filters.globalTier,
    filters.subcatTier,
    filters.brand,
    filters.competitor,
    filters.fpNames,
    filters.vertical,
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

// withCatalogueCount powers the header caption "N with a live catalogue"; the
// Addressable / freshness summaries now live inside CompetitorScorecard, beside
// the table they describe.
const overview = computed(() => store.competitorOverview || [])
const withCatalogueCount = computed(() =>
  overview.value.length ? overview.value.filter(r => r.has_catalogue).length : null)

// ─── Competitor visibility (client-side, same UX as Commercial) ──
// Empty selection = show all. The pills filter the Competitor PI table and the
// Geographic-exposure grid client-side; they don't change the backend query.
const selectedCompetitors = ref([])
const allCompetitors = computed(() => {
  const set = new Set()
  for (const r of store.dashboard?.competitor_pi || []) if (r.competitor_name) set.add(r.competitor_name)
  for (const c of store.fpCompetitorPi?.competitors || []) set.add(c)
  return [...set].sort()
})
function compVisible(name) {
  return selectedCompetitors.value.length === 0 || selectedCompetitors.value.includes(name)
}

// Geographic-exposure data with the competitor selection applied.
const geoData = computed(() => {
  const d = store.fpCompetitorPi
  if (!d) return null
  if (selectedCompetitors.value.length === 0) return d
  return {
    ...d,
    competitors: (d.competitors || []).filter(compVisible),
    cells: (d.cells || []).filter(c => compVisible(c.competitor_name)),
  }
})
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

// The competitor pills are visibility-only on this view, so they filter the
// scorecard's rows client-side without changing any number.
const visibleOverview = computed(() =>
  (store.competitorOverview || []).filter(r => compVisible(r.competitor_name)))

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
// pi_deviation = sale_PI - 1, so PI = 1 + dev. Drive the category chip's border
// straight from piColor so it follows the "both tails bad" orientation: pricier
// (dev > 0) = warm, cheaper (dev < 0) = cool, near-parity = green.
function _piFromDev(dev) {
  return dev == null ? null : 1 + dev
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
      { term: 'Competitor PI', description: 'Blended PI per competitor, ranked. Click any row to open the Commercial view filtered for that competitor.', icon: BarChart2Icon },
      { term: 'Category PI', description: 'Blended PI per category. Click a category to explore it in the Commercial view.', icon: Layers },
      { term: 'Classification', description: 'Donut of product x competitor pairs by mapping status. Use the competitor pills to filter; click a segment to navigate.', icon: PieChart },
      { term: 'Mapping Progress', description: 'Stacked bar of product status per competitor. Shows coverage now, plus the reachable headroom from potential matches.', icon: BarChart2Icon },
      { term: 'Competitor Overview', description: 'Matching and assortment coverage per competitor — the live version of the Brand Portfolio workbook sheet. Set Vertical to Supermarket to match that sheet, which excludes beauty.', icon: BarChart2Icon },
    ],
  },
  {
    title: 'Coverage & matchability',
    items: [
      { term: 'Addressable %', description: 'Matched divided by (our products minus confirmed no-match). Products the matcher positively rejected leave the denominator, so this is the honest ceiling rather than a backlog. Pooled across product x competitor pairs.', icon: Target },
      { term: 'Confirmed no-match', description: 'The matcher looked and rejected every candidate — a real assortment difference, not a queue item.', icon: PieChart },
      { term: 'Benchmark freshness', description: 'Share of our matches whose competitor product was seen in the last 7 days. A match that has gone quiet is a price benchmark quietly going stale.', icon: BarChart2Icon },
      { term: 'They only', description: "Competitor products with no link to anything of ours. A competitor with no crawled catalogue shows zero here — that is a collection gap, not an assortment gap, and the row is flagged.", icon: Layers },
      { term: 'Include Private Label', description: 'Unchecking this excludes Breadfast own-brand products. Be aware the exclusion is approximate and not yet identical across views: brands named exactly "Breadfast" always drop, while sub-brands such as "Breadfast Bakery" may still be counted on some panels. Treat small differences between screens as this, not as a data error.', icon: Scale },
    ],
  },
]
</script>

