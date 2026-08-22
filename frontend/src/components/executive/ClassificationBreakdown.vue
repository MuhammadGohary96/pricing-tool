<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2 flex-wrap">
      <BarChart3 class="w-4 h-4 text-brand-primary shrink-0" />
      <h2 class="text-subheading font-bold text-grey-900 tracking-tightish">Product classification</h2>
      <HelpTooltip text="Every product we track against this competitor, in one bar, ordered from done to impossible. The tick marks the reachable ceiling: everything past it is in a brand they do not stock, so no matching effort reaches it." />

      <div class="ml-auto flex items-center gap-1 flex-wrap justify-end">
        <button
          v-for="comp in competitorNames"
          :key="comp"
          class="px-2 py-0.5 rounded text-micro font-medium transition-colors"
          :class="selectedCompetitor === comp
            ? 'bg-brand-primary text-white'
            : 'bg-grey-100 text-grey-600 hover:bg-grey-200'"
          @click="selectCompetitor(comp)"
        ><CompetitorLogo :name="comp" /> {{ comp }}</button>
      </div>
    </div>

    <template v-if="hasData">
      <div class="px-4 pt-4 pb-3">
        <!-- The denominator, stated. A percentage bar without its total is what
             made the old donut answer "25% of what?" with 85,274 pairs. -->
        <div class="flex items-baseline justify-between mb-2">
          <span class="text-caption text-grey-500">
            <span class="font-mono font-bold text-grey-900 tabular-nums">{{ total.toLocaleString() }}</span>
            products tracked at {{ selectedCompetitor || 'all competitors' }}
          </span>
          <span class="text-caption text-grey-500">
            <span class="font-mono font-bold text-green-700 tabular-nums">{{ mappedPct }}%</span> mapped
          </span>
        </div>

        <!-- A bar, not a donut, for one reason: a donut has nowhere to put a
             threshold line, and the reachable ceiling is the number that decides
             whether the rest is work or assortment. -->
        <div class="relative">
          <div class="flex h-9 rounded-lg overflow-hidden ring-1 ring-grey-200">
            <div
              v-for="seg in segments"
              :key="seg.label"
              class="h-full flex items-center justify-center transition-[width] duration-500 ease-premium overflow-hidden"
              :class="[seg.cls, seg.action ? 'cursor-pointer hover:brightness-95' : '']"
              :style="{ width: `${seg.pct}%`, ...(seg.hatch ? { backgroundImage: HATCH } : {}) }"
              :title="`${seg.label}: ${seg.count.toLocaleString()} (${seg.pct.toFixed(1)}%)\n${seg.why}`"
              @click="seg.action && emit('navigate', { action_type: seg.action })"
            >
              <span v-if="seg.pct >= 6"
                    class="font-mono text-caption font-bold tabular-nums whitespace-nowrap px-1"
                    :class="seg.ink">{{ seg.count.toLocaleString() }}</span>
            </div>
          </div>

          <!-- The reachable ceiling. Sits exactly on the boundary before
               "not shared brand", because the segments are ordered so that
               everything unreachable is last. -->
          <div v-if="reachablePct < 99.95"
               class="absolute -top-1 -bottom-1 w-0.5 bg-grey-900 rounded-full pointer-events-none"
               :style="{ left: `${reachablePct}%` }"></div>
          <div v-if="reachablePct < 99.95"
               class="absolute top-full mt-1.5 -translate-x-1/2 whitespace-nowrap pointer-events-none"
               :style="{ left: `${reachablePct}%` }">
            <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-grey-900 text-white text-micro font-bold tabular-nums">
              reachable {{ reachablePct.toFixed(1) }}%
            </span>
          </div>
        </div>

        <div :class="reachablePct < 99.95 ? 'mt-8' : 'mt-3'">
          <!-- Legend as a row, which a bar affords and a donut did not: each
               entry sits under the segment it names. -->
          <div class="flex flex-wrap gap-x-5 gap-y-2">
            <div v-for="seg in segments" :key="'k-' + seg.label" class="flex items-start gap-1.5 min-w-0">
              <span class="w-2.5 h-2.5 rounded-sm shrink-0 mt-1 ring-1 ring-black/5"
                    :class="seg.cls"
                    :style="seg.hatch ? { backgroundImage: HATCH } : {}"></span>
              <div class="min-w-0">
                <div class="text-caption text-grey-600 leading-tight">{{ seg.label }}</div>
                <div class="text-body font-bold text-grey-900 leading-tight tabular-nums">
                  {{ seg.count.toLocaleString() }}
                  <span class="text-micro font-normal text-grey-400">{{ seg.pct.toFixed(1) }}%</span>
                </div>
                <div v-if="seg.pl != null" class="text-micro text-grey-400 leading-tight tabular-nums">
                  {{ seg.notPl.toLocaleString() }} non-PL · {{ seg.pl.toLocaleString() }} PL
                </div>
              </div>
            </div>
          </div>

          <p class="text-caption text-grey-500 mt-3">
            <strong class="text-grey-700">{{ reachable.toLocaleString() }}</strong> of
            {{ total.toLocaleString() }} products are reachable —
            {{ brandUnreachable.toLocaleString() }} sit in brands
            {{ selectedCompetitor || 'these competitors' }} does not stock, so matching cannot touch them.
            Of the reachable set, <strong class="text-green-700">{{ reachableMappedPct }}%</strong> is mapped.
          </p>
        </div>
      </div>
    </template>
    <EmptyState v-else :icon="BarChart3" title="No classification data" message="No data available." />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { BarChart3 } from 'lucide-vue-next'
import EmptyState from '../shared/EmptyState.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'

const props = defineProps({
  data: { type: Object, default: () => ({}) },
  mappingProgress: { type: Array, default: () => [] },
})
const emit = defineEmits(['navigate'])

// Same hatch as the delisted band in Portfolio comparison, and deliberately so:
// hatched means "outside what any effort reaches". One texture, one meaning.
const HATCH = "repeating-linear-gradient(45deg, rgb(203 213 225) 0 3px, rgb(241 245 249) 3px 6px)"

const LS_KEY = 'bf_selected_competitor_classification'
const selectedCompetitor = ref(null)

const competitorNames = computed(() =>
  props.mappingProgress.map(r => r.competitor_name).sort())

watch(competitorNames, (names) => {
  if (!names.length) return
  if (selectedCompetitor.value && names.includes(selectedCompetitor.value)) return
  const stored = localStorage.getItem(LS_KEY)
  selectedCompetitor.value = (stored && names.includes(stored))
    ? stored
    : (names.includes('Talabat') ? 'Talabat' : names[0])
}, { immediate: true })

function selectCompetitor(comp) {
  selectedCompetitor.value = comp
  localStorage.setItem(LS_KEY, comp)
}

// Every key listed explicitly. An earlier version rebuilt this object from a
// hand-written list and silently dropped the brand split, which then read 0%
// on screen while the API returned it correctly.
const d = computed(() => {
  if (selectedCompetitor.value && props.mappingProgress.length) {
    const e = props.mappingProgress.find(r => r.competitor_name === selectedCompetitor.value)
    if (e) {
      return {
        mapped_not_pl: e.mapped_not_pl || 0,
        mapped_pl: e.mapped_pl || 0,
        not_mapped_not_pl_potential: e.potential_not_pl || 0,
        not_mapped_pl_potential: e.potential_pl || 0,
        not_mapped_not_pl_no_potential: e.no_potential_not_pl || 0,
        not_mapped_pl_no_potential: e.no_potential_pl || 0,
        not_mapped_not_pl_no_match: e.no_match_not_pl || 0,
        not_mapped_pl_no_match: e.no_match_pl || 0,
        no_match_not_shared_brand: e.no_match_not_shared_brand || 0,
        no_potential_not_shared_brand: e.no_potential_not_shared_brand || 0,
      }
    }
  }
  return props.data || {}
})

const total = computed(() => {
  const v = d.value
  return (v.mapped_not_pl || 0) + (v.mapped_pl || 0)
       + (v.not_mapped_not_pl_potential || 0) + (v.not_mapped_pl_potential || 0)
       + (v.not_mapped_not_pl_no_potential || 0) + (v.not_mapped_pl_no_potential || 0)
       + (v.not_mapped_not_pl_no_match || 0) + (v.not_mapped_pl_no_match || 0)
})
const hasData = computed(() => total.value > 0)

const mappedTotal = computed(() => (d.value.mapped_not_pl || 0) + (d.value.mapped_pl || 0))
const mappedPct = computed(() => total.value ? Math.round(mappedTotal.value / total.value * 1000) / 10 : 0)

// Brand-unreachable spans BOTH dead ends, not just confirmed no-match. Counting
// only the first put the no-likely-match half into the reachable side and made
// the ceiling read several hundred products too generous.
const brandUnreachable = computed(() =>
  (d.value.no_match_not_shared_brand || 0) + (d.value.no_potential_not_shared_brand || 0))
const reachable = computed(() => Math.max(0, total.value - brandUnreachable.value))
const reachablePct = computed(() => total.value ? (reachable.value / total.value) * 100 : 100)
const reachableMappedPct = computed(() =>
  reachable.value ? Math.round(mappedTotal.value / reachable.value * 1000) / 10 : 0)

// Ordered done -> possible -> impossible, so the reachable tick lands exactly on
// the last boundary rather than floating inside a segment.
const segments = computed(() => {
  const v = d.value
  const t = total.value || 1
  const noPotAll = (v.not_mapped_not_pl_no_potential || 0) + (v.not_mapped_pl_no_potential || 0)
  const noMatchAll = (v.not_mapped_not_pl_no_match || 0) + (v.not_mapped_pl_no_match || 0)
  const rows = [
    { label: 'Mapped', count: mappedTotal.value, cls: 'bg-green-600', ink: 'text-white',
      notPl: v.mapped_not_pl || 0, pl: v.mapped_pl || 0, action: 'Complete',
      why: 'Matched to one of their products, so it carries a price comparison.' },
    { label: 'Potential match', count: (v.not_mapped_not_pl_potential || 0) + (v.not_mapped_pl_potential || 0),
      cls: 'bg-amber-500', ink: 'text-amber-950',
      notPl: v.not_mapped_not_pl_potential || 0, pl: v.not_mapped_pl_potential || 0, action: 'Review Match',
      why: 'Unmatched, but a candidate scores >= 0.85 — the likeliest genuine misses.' },
    { label: 'No likely match', count: Math.max(0, noPotAll - (v.no_potential_not_shared_brand || 0)),
      cls: 'bg-red-400', ink: 'text-white', action: 'Needs Mapping',
      why: 'They stock the brand, but nothing scores high enough to propose.' },
    { label: 'Confirmed no match', count: Math.max(0, noMatchAll - (v.no_match_not_shared_brand || 0)),
      cls: 'bg-grey-400', ink: 'text-white',
      why: 'They stock the brand and the matcher rejected every candidate for this item.' },
    { label: 'Not shared brand', count: brandUnreachable.value,
      cls: 'bg-slate-200', ink: 'text-slate-700', hatch: true,
      why: 'They do not stock the brand at all. No matching effort reaches these — the hatch means unreachable.' },
  ]
  return rows.filter(r => r.count > 0).map(r => ({ ...r, pct: (r.count / t) * 100 }))
})
</script>
