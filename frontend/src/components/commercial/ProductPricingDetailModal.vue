<template>
  <Teleport to="body">
    <Transition name="modal-fade">
    <div v-if="productId != null" class="fixed inset-0 z-50 flex items-start justify-center px-6 pt-16 pb-6">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-brand-darkest/30" @click="$emit('close')" />

      <!-- Modal card -->
      <div
        class="relative z-10 flex flex-col w-full max-w-[980px] bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden animate-scale-in"
        style="max-height: min(840px, calc(100vh - 5.5rem));"
        role="dialog"
        aria-modal="true"
        :aria-label="`Pricing detail for ${data?.product?.product_name || 'product'}`"
      >
        <!-- ============ HEADER ============ -->
        <div class="flex items-start gap-4 px-6 pt-5 pb-4 border-b border-grey-100 shrink-0">
          <div class="flex-1 min-w-0">
            <div v-if="data?.product" class="flex items-center gap-2 text-micro font-medium text-grey-500 mb-1.5 flex-wrap">
              <span class="font-semibold text-grey-700">{{ data.product.brand_name }}</span>
              <span class="text-grey-300">·</span>
              <span>{{ data.product.main_category_name }}</span>
              <span v-if="data.product.sub_category_name" class="text-grey-300">›</span>
              <span>{{ data.product.sub_category_name }}</span>
            </div>
            <h2 class="text-lg leading-tight font-bold text-grey-900 tracking-tightish text-pretty">
              {{ data?.product?.product_name || 'Pricing detail' }}
            </h2>
            <div v-if="data?.product" class="flex items-baseline gap-3 mt-2.5 flex-wrap">
              <div class="flex items-baseline gap-1.5">
                <span class="text-micro font-semibold text-grey-500 uppercase tracking-wide">BF Price</span>
                <span class="font-mono text-2xl font-bold text-grey-900">{{ fmt(data.product.bf_sale_price) }}</span>
                <span class="text-caption text-grey-500">EGP</span>
                <span
                  v-if="data.product.bf_regular_price && data.product.bf_regular_price !== data.product.bf_sale_price"
                  class="font-mono text-caption text-grey-400 line-through"
                >{{ fmt(data.product.bf_regular_price) }}</span>
              </div>
              <span v-if="data.product.bf_price_updated_at" class="inline-flex items-center gap-1.5 text-micro text-grey-400">
                <span class="w-1.5 h-1.5 rounded-full bg-green-500" />
                Updated {{ relTime(data.product.bf_price_updated_at) }}
              </span>
            </div>
          </div>
          <button
            aria-label="Close"
            class="shrink-0 w-8 h-8 inline-flex items-center justify-center border border-grey-200 bg-white rounded-lg text-grey-500 hover:bg-grey-100 hover:text-grey-900 transition-colors"
            @click="$emit('close')"
          ><X class="w-4 h-4" /></button>
        </div>

        <!-- ============ MIN / MAX PI vs competitors (aggregated over filtered FPs) ============ -->
        <div v-if="isLoaded" class="flex items-stretch gap-3 px-6 py-3.5 border-b border-grey-100 shrink-0 flex-wrap">
          <div
            v-for="chip in summaryChips"
            :key="chip.label"
            class="flex items-center gap-3.5 px-4 py-3 rounded-xl border"
            :class="[chipColors(chip.c.agg_pi).bg, chipColors(chip.c.agg_pi).border]"
          >
            <div>
              <div class="text-micro font-semibold text-grey-500 uppercase tracking-wide mb-0.5">{{ chip.label }}</div>
              <div class="flex items-baseline gap-2">
                <span class="font-mono text-3xl font-extrabold leading-none" :class="chipColors(chip.c.agg_pi).text">{{ chip.c.agg_pi.toFixed(2) }}</span>
                <span class="text-base font-bold" :class="chipColors(chip.c.agg_pi).text">{{ piArrow(chip.c.agg_pi) }}</span>
              </div>
            </div>
            <div class="w-px self-stretch" :class="chipColors(chip.c.agg_pi).divider" />
            <div class="min-w-0">
              <div class="flex items-center gap-1.5">
                <CompetitorLogo :name="chip.c.competitor_name" />
                <span class="text-caption font-bold text-grey-800 truncate">{{ chip.c.competitor_name }}</span>
              </div>
              <div class="text-micro text-grey-500 mt-0.5"><span class="font-mono">{{ fmt(chip.c.agg_price) }}</span> EGP</div>
            </div>
          </div>
          <div v-if="!summaryChips.length" class="text-caption text-grey-500 py-2 self-center">No fresh competitor prices to compare across these fulfillment points.</div>
        </div>

        <!-- ============ BODY ============ -->

        <!-- LOADED: matrix -->
        <template v-if="isLoaded">
          <div class="flex-1 min-h-0 overflow-auto">
            <table class="border-separate border-spacing-0 w-full" style="min-width: 720px;">
              <thead>
                <tr>
                  <th class="text-left px-4 py-2.5 text-micro font-semibold text-grey-500 uppercase tracking-wide border-b border-r border-grey-200 bg-grey-50"
                      style="position: sticky; top: 0; left: 0; z-index: 40; min-width: 156px; width: 156px;">Fulfillment Point</th>
                  <th class="text-right px-4 py-2.5 text-micro font-bold uppercase tracking-wide border-b border-grey-200 bg-brand-lightest text-brand-dark"
                      style="position: sticky; top: 0; z-index: 30; min-width: 104px; border-right: 2px solid #E5E7EB;">BF Price</th>
                  <th v-for="comp in data.competitors" :key="comp.competitor_name"
                      class="text-right px-4 py-2 border-b border-r border-grey-200"
                      :style="{ position: 'sticky', top: '0', zIndex: 30, minWidth: '132px', background: compIdx(comp.competitor_name) % 2 ? '#EFEFEF' : '#F3F4F6' }">
                    <div class="inline-flex items-center gap-1.5">
                      <CompetitorLogo :name="comp.competitor_name" />
                      <span class="text-caption font-bold text-grey-700">{{ comp.competitor_name }}</span>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in data.rows" :key="row.fp_name" class="hover:bg-brand-50/40 transition-colors">
                  <!-- FP name (sticky left) -->
                  <th class="text-left px-4 py-2.5 border-b border-r border-grey-100 align-middle bg-white"
                      style="position: sticky; left: 0; z-index: 20;">
                    <div class="text-body font-semibold text-grey-900 whitespace-nowrap">{{ row.fp_name }}</div>
                  </th>
                  <!-- Our price -->
                  <td class="text-right px-4 py-2.5 border-b border-grey-100" style="border-right: 2px solid #E5E7EB; background: #FCFAFC;">
                    <span class="font-mono text-body font-semibold text-grey-900">{{ fmt(row.bf_sale_price) }}</span>
                  </td>
                  <!-- Competitor cells -->
                  <td v-for="cell in row.cells" :key="cell.competitor_name"
                      class="text-right px-4 py-2 border-b border-r border-grey-100 align-middle"
                      :style="cell.state === 'not_mapped' ? { background: HATCH } : {}">
                    <!-- priced (fresh) -->
                    <div v-if="cell.state === 'priced'" class="flex flex-col items-end gap-1">
                      <span class="font-mono text-caption font-medium text-grey-700">{{ fmt(cell.price) }}</span>
                      <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-micro font-bold" :class="[piBgClass(cell.pi), piTextClass(cell.pi)]">
                        <span class="text-[9px]">{{ piArrow(cell.pi) }}</span>
                        <span class="font-mono">{{ cell.pi != null ? cell.pi.toFixed(2) : '—' }}</span>
                      </span>
                    </div>
                    <!-- stale -->
                    <div v-else-if="cell.state === 'stale'" class="flex flex-col items-end gap-1">
                      <span class="font-mono text-caption font-medium text-grey-400">{{ fmt(cell.price) }}</span>
                      <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-micro font-semibold text-grey-400 bg-grey-100 border border-dashed border-grey-300">
                        <Clock class="w-2.5 h-2.5" />{{ cell.days_since_update != null ? `${cell.days_since_update}d old` : 'stale' }}
                      </span>
                    </div>
                    <!-- mapped, no price -->
                    <div v-else-if="cell.state === 'no_price'" class="flex flex-col items-end gap-0.5">
                      <span class="text-caption italic text-grey-400">No price</span>
                      <span class="text-micro text-grey-300">awaiting crawl</span>
                    </div>
                    <!-- not mapped -->
                    <div v-else class="flex items-center justify-end">
                      <span class="text-caption font-medium text-grey-400">Not mapped</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <!-- Legend -->
          <div class="flex items-center gap-4 px-6 py-2.5 border-t border-grey-100 shrink-0 flex-wrap bg-grey-50">
            <span class="text-micro font-semibold text-grey-400 uppercase tracking-wide">Legend</span>
            <span class="inline-flex items-center gap-1.5 text-micro text-grey-500"><span class="w-5 h-3.5 rounded border border-grey-200" :class="SWATCH_CHEAPER" />{{ legendCheaper }}</span>
            <span class="inline-flex items-center gap-1.5 text-micro text-grey-500"><span class="w-5 h-3.5 rounded border border-grey-200" :class="SWATCH_PARITY" />Parity ({{ PI_CHEAP }}–{{ PI_EXPENSIVE }})</span>
            <span class="inline-flex items-center gap-1.5 text-micro text-grey-500"><span class="w-5 h-3.5 rounded border border-grey-200" :class="SWATCH_PRICIER" />{{ legendPricier }}</span>
            <span class="inline-flex items-center gap-1.5 text-micro text-grey-500"><span class="w-5 h-3.5 rounded" :style="{ background: HATCH }" />Not mapped</span>
          </div>
        </template>

        <!-- SKELETON -->
        <div v-else-if="loading" class="flex-1 min-h-0 overflow-hidden">
          <div class="flex px-4 py-3 border-b border-grey-200 bg-grey-50 gap-4">
            <div class="skel h-4 w-36" />
            <div class="skel h-4 w-20 ml-auto" />
            <div class="skel h-4 w-24" /><div class="skel h-4 w-24" /><div class="skel h-4 w-24" />
          </div>
          <div v-for="n in 6" :key="n" class="flex px-4 py-3.5 border-b border-grey-100 gap-4 items-center">
            <div class="skel h-3.5 w-32" />
            <div class="skel h-6 w-16 ml-auto" />
            <div class="skel h-6 w-[72px]" /><div class="skel h-6 w-[72px]" /><div class="skel h-6 w-[72px]" />
          </div>
        </div>

        <!-- EMPTY -->
        <div v-else-if="isEmpty" class="flex-1 flex flex-col items-center justify-center text-center px-8 py-12" style="min-height: 280px;">
          <div class="w-[52px] h-[52px] rounded-2xl bg-grey-100 flex items-center justify-center mb-3.5"><Unlink2 class="w-6 h-6 text-grey-400" /></div>
          <div class="text-body font-bold text-grey-700 mb-1">No competitor mappings yet</div>
          <p class="text-body text-grey-500 max-w-xs mb-1 leading-relaxed">This product isn't mapped to any competitor product, so there's no Price Index to show across fulfillment points.</p>
          <p class="text-caption text-grey-400">Map it in the Master Data workspace to start tracking PI.</p>
        </div>

        <!-- ERROR -->
        <div v-else-if="error" class="flex-1 flex flex-col items-center justify-center text-center px-8 py-12" style="min-height: 280px;">
          <div class="w-[52px] h-[52px] rounded-2xl bg-red-50 flex items-center justify-center mb-3.5"><AlertTriangle class="w-6 h-6 text-red-500" /></div>
          <div class="text-body font-bold text-grey-700 mb-1">Couldn't load pricing detail</div>
          <p class="text-body text-grey-500 max-w-xs mb-4 leading-relaxed">The request failed. Check your connection and try again.</p>
          <PillButton variant="brand" size="sm" @click="load">Retry</PillButton>
        </div>
      </div>
    </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { X, Clock, Unlink2, AlertTriangle } from 'lucide-vue-next'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import PillButton from '../shared/PillButton.vue'
import { commercialApi } from '../../api/client'
import { useFiltersStore } from '../../stores/filters'
import { piTextClass, piBgClass, piArrow, piZone, PI_CHEAP, PI_EXPENSIVE } from '../../utils/piColor'

const props = defineProps({
  productId: { type: [String, Number], default: null },
})
const emit = defineEmits(['close'])

const filters = useFiltersStore()

const loading = ref(false)
const error = ref(false)
const data = ref(null)

// 45° hatch — visually distinct "no data" so it never reads as parity.
const HATCH = 'repeating-linear-gradient(45deg, #FAFAFA, #FAFAFA 5px, #F1F1F3 5px, #F1F1F3 10px)'

// Same action badge palette as ProductPivotTable, so labels/colors match the grid.
const ACTION_STYLE = {
  'Needs Mapping':      'background:#FEE2E2;color:#DC2626',
  'Review Match':       'background:#FEF3C7;color:#D97706',
  'Needs Price Update': 'background:#FDF2F9;color:#a3007c',
  'Complete':           'background:#D1FAE5;color:#059669',
}

const summary = computed(() => data.value?.summary || {})
const isLoaded = computed(() => !loading.value && !error.value && data.value?.found && data.value.competitors?.length > 0)
const isEmpty = computed(() => !loading.value && !error.value && data.value && (!data.value.found || !data.value.competitors?.length))

// ── Min / Max PI by competitor (aggregated over the filtered FPs) ──
// Per-competitor agg_pi = bf modal ÷ modal(competitor price) is computed
// backend-side on the same basis as the pivot table, so these match the grid.
const COLOR_BY_ZONE = {
  green:   { bg: 'bg-green-50', border: 'border-green-200', divider: 'bg-green-200', text: 'text-green-700' },
  cyan:    { bg: 'bg-blue-50',  border: 'border-blue-200',  divider: 'bg-blue-200',  text: 'text-blue-700'  },
  red:     { bg: 'bg-red-50',   border: 'border-red-200',   divider: 'bg-red-200',   text: 'text-red-700'   },
  neutral: { bg: 'bg-grey-50',  border: 'border-grey-200',  divider: 'bg-grey-200',  text: 'text-grey-400'  },
}
function chipColors(pi) { return COLOR_BY_ZONE[piZone(pi)] || COLOR_BY_ZONE.neutral }

const rankedComps = computed(() =>
  (data.value?.competitors || [])
    .filter(c => c.agg_pi != null)
    .sort((a, b) => a.agg_pi - b.agg_pi)
)
const summaryChips = computed(() => {
  const r = rankedComps.value
  if (r.length === 0) return []
  if (r.length === 1) return [{ label: 'PI', c: r[0] }]
  return [{ label: 'Min PI', c: r[0] }, { label: 'Max PI', c: r[r.length - 1] }]
})

function compIdx(name) {
  return data.value?.competitors?.findIndex(c => c.competitor_name === name) ?? 0
}

function fmt(v) {
  return v != null ? Number(v).toFixed(2) : '—'
}

// PI convention (BF ÷ Competitor): PI < 1 = BF cheaper, PI > 1 = BF more
// expensive. The verdict/legend TEXT is driven by the PI value (so it's
// always correct), while the COLORS stay driven by piColor.js (unchanged) —
// swatches use piBgClass so the legend always matches the live cell colors.
const legendCheaper = `BF cheaper (PI < ${PI_CHEAP})`
const legendPricier = `BF more expensive (PI > ${PI_EXPENSIVE})`

// Cell-color zones for the legend swatches (follow piColor.js automatically).
const SWATCH_CHEAPER = piBgClass(PI_CHEAP - 0.05)
const SWATCH_PARITY = piBgClass(1)
const SWATCH_PRICIER = piBgClass(PI_EXPENSIVE + 0.05)

const verdict = computed(() => {
  const pi = summary.value?.blended_pi
  // Colors follow piColor.js's "both tails bad" zones: parity = green,
  // cheaper = cool/blue, pricier = warm/red (piZone re-oriented to PI = BF ÷ Comp).
  const colorByZone = {
    green:   { bg: 'bg-green-50', border: 'border-green-200', divider: 'bg-green-200', text: 'text-green-700' },
    cyan:    { bg: 'bg-blue-50',  border: 'border-blue-200',  divider: 'bg-blue-200',  text: 'text-blue-700'  },
    red:     { bg: 'bg-red-50',   border: 'border-red-200',   divider: 'bg-red-200',   text: 'text-red-700'   },
    neutral: { bg: 'bg-grey-50',  border: 'border-grey-200',  divider: 'bg-grey-200',  text: 'text-grey-400'  },
  }
  // Meaning: driven by the PI value, not the color.
  let meaning
  if (pi == null) meaning = { title: 'No index', sub: 'No fresh competitor prices to compare.' }
  else if (pi < PI_CHEAP) meaning = { title: 'BF is cheaper', sub: 'Breadfast is cheaper than the competitor basket across these FPs.' }
  else if (pi > PI_EXPENSIVE) meaning = { title: 'BF is more expensive', sub: 'Breadfast is pricier than the competitor basket across these FPs.' }
  else meaning = { title: 'At parity', sub: 'Breadfast tracks the competitor basket within ±5%.' }
  return { ...colorByZone[piZone(pi)], ...meaning, arrow: pi != null ? piArrow(pi) : '' }
})

function relTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d)) return ''
  // Compare CALENDAR days, not elapsed hours. bf_price_updated_at is day-grain,
  // so a price set earlier today must read "today" — rounding elapsed hours
  // would flip it to "yesterday" any time after ~midday.
  const startOfDay = (t) => { const x = new Date(t); x.setHours(0, 0, 0, 0); return x.getTime() }
  const days = Math.round((startOfDay(Date.now()) - startOfDay(d)) / 86400000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days} days ago`
  return d.toLocaleDateString()
}

async function load() {
  if (props.productId == null) return
  loading.value = true
  error.value = false
  data.value = null
  try {
    const res = await commercialApi.getProductFpMatrix(props.productId, filters.activeFilters)
    data.value = res.data
  } catch (e) {
    error.value = true
    console.error('FP matrix fetch error:', e)
  } finally {
    loading.value = false
  }
}

watch(() => props.productId, (id) => { if (id != null) load() })
// Re-fetch when the dashboard filters change while the modal is open.
watch(() => filters.activeFilters, () => { if (props.productId != null) load() }, { deep: true })

function onKey(e) {
  if (e.key === 'Escape' && props.productId != null) emit('close')
}
onMounted(() => {
  window.addEventListener('keydown', onKey)
  if (props.productId != null) load()
})
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
/* Overlay entrance: backdrop + card fade in together; the card also scales via
   the shared .animate-scale-in class. Both collapse to instant under the global
   prefers-reduced-motion block in breadfast.css. */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s var(--ease-premium);
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.skel {
  background: linear-gradient(90deg, #F3F4F6 25%, #E5E7EB 50%, #F3F4F6 75%);
  background-size: 200% 100%;
  animation: skelShimmer 1.5s ease-in-out infinite;
  border-radius: 6px;
}
@keyframes skelShimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
@media (prefers-reduced-motion: reduce) {
  .skel { animation: none; }
}
</style>
