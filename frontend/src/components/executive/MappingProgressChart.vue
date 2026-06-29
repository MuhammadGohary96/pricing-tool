<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <!-- Header: title + the two figures that matter (coverage now, work queued) -->
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2">
        <BarChart2 class="w-4 h-4 text-brand-primary" />
        <h2 class="text-subheading font-bold text-grey-900 tracking-tightish">Mapping progress by competitor</h2>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <span v-if="avgMappedPct > 0" class="text-micro font-bold px-2 py-0.5 rounded bg-green-50 text-green-700">{{ avgMappedPct }}% avg mapped</span>
      </div>
    </div>

    <template v-if="rows.length">
      <!-- Legend -->
      <div class="px-4 pt-3 flex items-center gap-3.5 flex-wrap text-micro text-grey-500">
        <span class="inline-flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm shrink-0" style="background:#059669"></span>Mapped</span>
        <span class="inline-flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm shrink-0" style="background:#F59E0B"></span>Potential — reachable next</span>
        <span class="inline-flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm shrink-0" style="background:#EF4444"></span>No likely match</span>
        <span class="inline-flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm shrink-0" style="background:#9CA3AF"></span>Confirmed no match</span>
      </div>

      <!-- One row per competitor, best-covered first -->
      <div class="px-4 py-3 flex flex-col divide-y divide-grey-100">
        <div
          v-for="r in rows"
          :key="r.name"
          class="grid grid-cols-[minmax(8.5rem,1fr)_minmax(0,2.2fr)_5.5rem] items-center gap-3 py-2.5 first:pt-1 last:pb-1"
        >
          <!-- Identity + absolute scale -->
          <div class="min-w-0">
            <div class="flex items-center gap-1.5">
              <CompetitorLogo :name="r.name" size="sm" />
              <span class="text-body font-semibold text-grey-800 truncate">{{ r.name }}</span>
            </div>
            <div class="font-mono text-micro text-grey-500 mt-0.5 tabular-nums">{{ r.mapped.toLocaleString() }} / {{ r.total.toLocaleString() }}</div>
          </div>

          <!-- Coverage bar: mapped (done) ▸ potential (reachable) ▸ track (out of reach) -->
          <div
            class="relative h-2.5 rounded-full bg-grey-100 overflow-hidden flex"
            role="img"
            :aria-label="barLabel(r)"
            :title="barLabel(r)"
          >
            <div class="h-full transition-[width] duration-700 ease-out" :style="{ width: pctW(r.mappedPct), background: '#059669' }"></div>
            <div class="h-full transition-[width] duration-700 ease-out" :style="{ width: pctW(r.potentialPct), background: '#F59E0B' }"></div>
            <div class="h-full transition-[width] duration-700 ease-out" :style="{ width: pctW(r.noLikelyPct), background: '#EF4444' }"></div>
            <div class="h-full transition-[width] duration-700 ease-out" :style="{ width: pctW(r.noMatchPct), background: '#9CA3AF' }"></div>
          </div>

          <!-- Verdict: coverage now + reachable headroom -->
          <div class="text-right tabular-nums">
            <div class="font-mono text-body font-bold text-grey-900 leading-none">{{ Math.round(r.mappedPct) }}%</div>
            <div class="text-micro mt-1 leading-none" :class="r.potentialPct >= 0.5 ? 'text-amber-700 font-semibold' : 'text-grey-400'">
              {{ r.potentialPct >= 0.5 ? `+${Math.round(r.potentialPct)}% reachable` : 'fully reached' }}
            </div>
          </div>
        </div>
      </div>
    </template>

    <EmptyState v-else :icon="BarChart2" title="No mapping data" message="No competitor mapping data available." />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { BarChart2 } from 'lucide-vue-next'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import EmptyState from '../shared/EmptyState.vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

// Bars grow in from zero on mount; the global prefers-reduced-motion block
// collapses the transition to instant, so this never gates visibility.
const mounted = ref(false)
onMounted(() => { mounted.value = true })
function pctW(p) { return (mounted.value ? p : 0) + '%' }

// Collapse the raw PL / not-PL · no-potential · no-match fields into the three
// tiers an executive reads: done (mapped), reachable next (potential), and the
// out-of-reach remainder. The fine-grained split lives in the hover title.
const rows = computed(() =>
  props.data
    .map((d) => {
      const total = d.total || 0
      const mapped = (d.mapped_not_pl || 0) + (d.mapped_pl || 0)
      const potential = (d.potential_not_pl || 0) + (d.potential_pl || 0)
      const noLikely = (d.no_potential_not_pl || 0) + (d.no_potential_pl || 0)
      const noMatch = (d.no_match_not_pl || 0) + (d.no_match_pl || 0)
      return {
        name: d.competitor_name,
        total,
        mapped,
        potential,
        noLikely,
        noMatch,
        mappedPl: d.mapped_pl || 0,
        mappedNotPl: d.mapped_not_pl || 0,
        mappedPct: total ? (mapped / total) * 100 : 0,
        potentialPct: total ? (potential / total) * 100 : 0,
        noLikelyPct: total ? (noLikely / total) * 100 : 0,
        noMatchPct: total ? (noMatch / total) * 100 : 0,
      }
    })
    .sort((a, b) => b.mappedPct - a.mappedPct)
)

// Quantity-weighted average coverage (matches the previous headline figure).
const avgMappedPct = computed(() => {
  const total = props.data.reduce((s, d) => s + (d.total || 0), 0)
  const mapped = props.data.reduce((s, d) => s + (d.mapped_not_pl || 0) + (d.mapped_pl || 0), 0)
  return total > 0 ? Math.round((mapped / total) * 100) : 0
})

function barLabel(r) {
  const pct = (n) => (r.total ? Math.round((n / r.total) * 100) : 0)
  return [
    r.name,
    `Mapped: ${r.mapped.toLocaleString()} (${pct(r.mapped)}%) — non-PL ${r.mappedNotPl.toLocaleString()}, PL ${r.mappedPl.toLocaleString()}`,
    `Potential to review: ${r.potential.toLocaleString()} (+${pct(r.potential)}%)`,
    `No likely match: ${r.noLikely.toLocaleString()}`,
    `Confirmed no match: ${r.noMatch.toLocaleString()}`,
    `Total tracked: ${r.total.toLocaleString()}`,
  ].join('\n')
}
</script>
