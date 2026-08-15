<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2 min-w-0">
        <Layers3 class="w-4 h-4 text-brand-primary shrink-0" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">What the gap is actually made of</span>
        <HelpTooltip text="Every bar is our full range against one competitor, split by what stands between a product and a price comparison. Read it right to left: the two grey blocks are assortment reality — they do not stock the brand, or they stock the brand but not the item — and no matching work reaches them. Only the amber block is a backlog." />
      </div>
      <div class="flex items-center gap-3 flex-wrap text-caption">
        <span v-for="k in KEYS" :key="k.label" class="inline-flex items-center gap-1.5 text-grey-600">
          <span class="w-2.5 h-2.5 rounded-sm" :class="k.swatch"></span>{{ k.label }}
        </span>
      </div>
    </div>

    <div v-if="rows.length" class="px-4 py-3 flex flex-col gap-2.5">
      <div v-for="r in rows" :key="r.name" class="flex items-center gap-3">
        <div class="w-28 shrink-0 flex items-center gap-1.5 min-w-0">
          <CompetitorLogo :name="r.name" />
          <span class="text-caption font-semibold text-grey-800 truncate">{{ r.name }}</span>
        </div>

        <div class="flex-1 min-w-0 flex h-6 rounded-md overflow-hidden ring-1 ring-grey-200/70">
          <!-- Labelled in place. A hover-only number is unreadable in a
               screenshot, unprintable, and invisible on touch — and this panel
               exists to be quoted. Dropped only where the segment is too narrow
               to hold the digits without overlapping its neighbour. -->
          <div v-for="seg in r.segments" :key="seg.key"
               class="h-full flex items-center justify-center transition-[width] duration-500 ease-premium overflow-hidden"
               :class="seg.swatch"
               :style="{ width: `${seg.pct}%` }"
               :title="`${seg.label}: ${seg.value.toLocaleString()} (${seg.pct.toFixed(1)}%)\n${seg.why}`">
            <span v-if="seg.pct >= 7"
                  class="font-mono text-micro font-bold tabular-nums whitespace-nowrap px-1"
                  :class="seg.ink">{{ seg.value.toLocaleString() }}</span>
          </div>
        </div>

        <!-- The number the eye should land on: what is actually workable. -->
        <div class="w-28 shrink-0 text-right">
          <div class="font-mono text-body font-bold text-amber-600 tabular-nums leading-none">
            {{ r.backlog.toLocaleString() }}
          </div>
          <div class="text-micro text-grey-400 leading-tight">workable</div>
        </div>
      </div>

      <p class="text-caption text-grey-500 mt-1">
        "Ours only" counts everything left of Mapped. Most of it is assortment, not backlog —
        <strong class="text-grey-700">{{ headline.name }}</strong> reads
        {{ headline.oursOnly.toLocaleString() }} unmatched but only
        <strong class="text-amber-600">{{ headline.backlog.toLocaleString() }}</strong>
        can be closed by matching.
      </p>
    </div>
    <EmptyState v-else message="No competitor data for the current filters" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Layers3 } from 'lucide-vue-next'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'
import EmptyState from '../shared/EmptyState.vue'

const props = defineProps({
  /** competitor-overview rows */
  data: { type: Array, default: () => [] },
  /** dashboard.mapping_progress — carries the no-match brand split */
  mappingProgress: { type: Array, default: () => [] },
})

const KEYS = [
  { label: 'Mapped', swatch: 'bg-green-500' },
  { label: 'Workable backlog', swatch: 'bg-amber-400' },
  { label: 'They lack the item', swatch: 'bg-grey-300' },
  { label: 'They lack the brand', swatch: 'bg-grey-200' },
]

const byComp = computed(() =>
  Object.fromEntries((props.mappingProgress || []).map(m => [m.competitor_name, m])))

// Our full range against one competitor, decomposed so the four parts sum back
// to it exactly. Verified against the API for all seven competitors.
//
//   mapped                     we can compare it today
//   workable backlog           unmatched, and nothing says it is impossible
//   no-match, brand carried    they stock the brand but not this item
//   no-match, brand missing    they do not stock the brand at all
//
// The last two are assortment decisions, not matching debt, and lumping them
// into "Ours only" is what makes that column read 13x larger than the work.
const rows = computed(() => {
  const out = []
  for (const r of props.data || []) {
    const m = byComp.value[r.competitor_name]
    if (!m || !r.bf_products) continue
    const noMatch = (m.no_match_not_pl || 0) + (m.no_match_pl || 0)
    const noBrand = m.no_match_not_shared_brand || 0
    const oursOnly = r.our_only_products || 0
    const backlog = Math.max(0, oursOnly - noMatch)
    const total = r.bf_products
    const pct = v => (v / total) * 100

    out.push({
      name: r.competitor_name,
      backlog,
      oursOnly,
      segments: [
        { key: 'm', label: 'Mapped', value: r.matched, pct: pct(r.matched), swatch: 'bg-green-500', ink: 'text-white',
          why: 'Matched to one of their products, so it carries a price comparison.' },
        { key: 'b', label: 'Workable backlog', value: backlog, pct: pct(backlog), swatch: 'bg-amber-400', ink: 'text-amber-950',
          why: 'Unmatched, and nothing rules it out — this is the queue matching work can close.' },
        { key: 'i', label: 'They lack the item', value: noMatch - noBrand, pct: pct(noMatch - noBrand), swatch: 'bg-grey-300', ink: 'text-grey-700',
          why: 'They carry the brand but the matcher rejected every candidate for this item.' },
        { key: 'k', label: 'They lack the brand', value: noBrand, pct: pct(noBrand), swatch: 'bg-grey-200', ink: 'text-grey-600',
          why: 'They do not stock the brand at all. No amount of matching reaches these.' },
      ].filter(s => s.value > 0),
    })
  }
  return out.sort((a, b) => b.backlog - a.backlog)
})

// Lead with the widest gap between the scary number and the real one, because
// that is the misreading this panel exists to correct.
const headline = computed(() => {
  if (!rows.value.length) return { name: '', oursOnly: 0, backlog: 0 }
  return rows.value.reduce((a, b) =>
    (b.oursOnly - b.backlog) > (a.oursOnly - a.backlog) ? b : a)
})
</script>
