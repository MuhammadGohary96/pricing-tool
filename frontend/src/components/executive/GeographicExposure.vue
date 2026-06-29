<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <!-- Panel header -->
    <div class="px-5 py-3.5 border-b border-grey-100 flex items-center gap-2.5 flex-wrap">
      <MapPin class="w-4 h-4 text-brand-primary shrink-0" />
      <h2 class="text-subheading font-bold text-grey-900 tracking-tightish">Geographic exposure</h2>
      <span class="text-caption text-grey-400">Blended PI by fulfillment point{{ hasData ? ` · ${fpCount} FPs` : '' }}</span>
      <button
        v-if="hasData"
        class="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg ring-1 ring-grey-200 bg-white text-caption font-medium text-grey-700 hover:ring-brand-primary active:scale-[0.98] transition-[transform,box-shadow] duration-200 ease-premium"
        @click="toggleAll"
      >
        {{ allExpanded ? 'Collapse all' : 'Expand all' }}
      </button>
    </div>

    <!-- Empty -->
    <EmptyState
      v-if="!hasData"
      :icon="MapPin"
      title="No fulfillment-point PI yet"
      message="No fresh competitor prices for this selection. Adjust the filters or check back after the next crawl."
    />

    <template v-else>
      <!-- Search + legend -->
      <div class="px-5 py-3 flex items-center gap-3 border-b border-grey-100">
        <div class="relative flex-1 max-w-[260px]">
          <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-grey-400 pointer-events-none" />
          <input
            v-model="search"
            type="text"
            placeholder="Search fulfillment points…"
            class="w-full pl-8 pr-3 py-1.5 text-body border border-grey-200 rounded-lg bg-grey-50 focus:bg-white focus:border-brand-primary focus:ring-2 focus:ring-brand-lightest outline-none transition-all"
          />
        </div>
        <div class="text-micro text-grey-400 ml-auto inline-flex items-center gap-3">
          <span v-if="estimatedPct > 0" class="inline-flex items-center gap-1" title="Cells filled from the typical fresh price across fulfillment points"><span class="font-mono text-brand-primary">≈</span> {{ estimatedPct }}% estimated</span>
          <span class="inline-flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-sm border border-dashed border-grey-300"></span> low coverage (&lt;20%)</span>
        </div>
      </div>

      <!-- Region-grouped grid (Areas collapsed by default) -->
      <div class="overflow-auto" style="max-height: 520px">
        <table class="w-full border-separate border-spacing-0 text-caption">
          <thead>
            <tr>
              <th class="text-left px-4 py-2.5 text-micro font-semibold text-grey-500 uppercase tracking-wide bg-grey-50 border-b border-r border-grey-200"
                  style="position: sticky; top: 0; left: 0; z-index: 30; min-width: 180px;">Fulfillment point</th>
              <th v-for="comp in competitors" :key="comp"
                  class="px-3 py-2.5 bg-grey-50 border-b border-grey-200 whitespace-nowrap"
                  style="position: sticky; top: 0; z-index: 20; min-width: 96px;">
                <span class="inline-flex items-center gap-1.5 justify-center">
                  <CompetitorLogo :name="comp" />
                  <span class="text-caption font-bold text-grey-700">{{ comp }}</span>
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in filteredGroups" :key="group.area">
              <!-- Area group header (collapsible) -->
              <tr class="bg-grey-50/60">
                <th :colspan="competitors.length + 1" class="text-left px-4 py-1.5 border-b border-grey-100"
                    style="position: sticky; left: 0;">
                  <button class="inline-flex items-center gap-1.5 text-micro font-bold uppercase tracking-wide text-grey-600 hover:text-brand-primary transition-colors" @click="toggleArea(group.area)">
                    <ChevronRight class="w-3 h-3 transition-transform duration-200" :class="{ 'rotate-90': isAreaOpen(group.area) }" />
                    {{ group.area }}
                    <span class="text-grey-400 font-medium normal-case tracking-normal">{{ group.fps.length }} {{ group.fps.length === 1 ? 'FP' : 'FPs' }}</span>
                  </button>
                </th>
              </tr>
              <!-- FP rows (shown when the Area is open, or while searching) -->
              <tr v-for="fp in (isAreaOpen(group.area) ? group.fps : [])" :key="fp.fp_name" class="hover:bg-brand-50/40 transition-colors">
                <th class="text-left px-4 py-2 border-b border-r border-grey-100 bg-white font-normal"
                    style="position: sticky; left: 0; z-index: 10;">
                  <button class="text-body font-medium text-grey-800 hover:text-brand-primary transition-colors whitespace-nowrap" :title="`Filter Executive to ${fp.fp_name}`" @click="$emit('select-fp', fp.fp_name)">{{ fp.fp_name }}</button>
                </th>
                <td v-for="comp in competitors" :key="comp" class="px-2 py-2 border-b border-grey-100 text-center align-middle">
                  <template v-if="fp.cells[comp] && fp.cells[comp].blended_pi != null">
                    <span
                      class="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-md font-mono text-caption font-semibold"
                      :class="[
                        piBgClass(fp.cells[comp].blended_pi),
                        piTextClass(fp.cells[comp].blended_pi),
                        isFullyEstimated(fp.cells[comp]) ? 'opacity-60 ring-1 ring-dashed ring-brand-light'
                          : (isThin(fp.cells[comp]) ? 'opacity-55 ring-1 ring-dashed ring-grey-300' : ''),
                      ]"
                      :title="cellTitle(fp.cells[comp])"
                    >
                      <span v-if="isEstimated(fp.cells[comp])" class="text-[9px] opacity-80" aria-label="estimated">≈</span>
                      <span class="text-[9px]">{{ piArrow(fp.cells[comp].blended_pi) }}</span>{{ fp.cells[comp].blended_pi.toFixed(2) }}
                    </span>
                  </template>
                  <span v-else class="text-grey-300" title="No fresh price">·</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { MapPin, ChevronRight, Search } from 'lucide-vue-next'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import EmptyState from '../shared/EmptyState.vue'
import { piBgClass, piTextClass, piArrow } from '../../utils/piColor'

const props = defineProps({
  data: { type: Object, default: null },  // { competitors: [], cells: [] }
})
defineEmits(['select-fp'])

const search = ref('')
const expandedAreas = ref(new Set())  // empty = all collapsed by default

// A cell is flagged low-coverage when its priced products are under 20% of the
// eligible basket — the PI then rests on too thin a slice to read as the FP's
// true position. Muted + dashed; never hidden.
const MIN_COVERAGE = 20
function isThin(c) { return c.coverage_pct < MIN_COVERAGE }

// Estimate flags (backend fills mapped-but-not-fresh cells with the modal price).
function isEstimated(c) { return (c.estimated_count ?? 0) > 0 }
function isFullyEstimated(c) { return c.used_count > 0 && (c.observed_count ?? c.used_count) === 0 }

const cells = computed(() => props.data?.cells ?? [])
const competitors = computed(() => props.data?.competitors ?? [])
const hasData = computed(() => cells.value.length > 0)
const fpCount = computed(() => new Set(cells.value.map(c => c.fp_name)).size)
const estimatedPct = computed(() => props.data?.estimated_pct ?? 0)

function cellTitle(c) {
  const est = c.estimated_count ?? 0
  if (est > 0) {
    const obs = c.observed_count ?? 0
    const split = `${obs} observed + ${est} estimated of ${c.eligible_count} eligible`
    return obs === 0 ? `Fully estimated — ${split}` : `Partly estimated — ${split}`
  }
  const base = `${c.used_count} products priced, ${c.coverage_pct}% of the eligible basket`
  return isThin(c) ? `Low coverage, ${base}` : base
}

// Region-grouped matrix: areas and the FPs within them ordered alphabetically
// (numeric-aware so "FP #2" precedes "FP #10").
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })
const groups = computed(() => {
  const byFp = new Map()
  for (const c of cells.value) {
    if (!byFp.has(c.fp_name)) byFp.set(c.fp_name, { fp_name: c.fp_name, area: c.area, cells: {} })
    byFp.get(c.fp_name).cells[c.competitor_name] = c
  }
  const byArea = new Map()
  for (const fp of byFp.values()) {
    if (!byArea.has(fp.area)) byArea.set(fp.area, [])
    byArea.get(fp.area).push(fp)
  }
  const result = []
  for (const [area, fps] of byArea) {
    fps.sort((a, b) => collator.compare(a.fp_name, b.fp_name))
    result.push({ area, fps })
  }
  result.sort((a, b) => collator.compare(a.area, b.area))
  return result
})

const filteredGroups = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return groups.value
  return groups.value
    .map(g => ({ ...g, fps: g.fps.filter(f => f.fp_name.toLowerCase().includes(q)) }))
    .filter(g => g.fps.length)
})

// While searching, reveal every matching row regardless of collapse state.
function isAreaOpen(area) {
  return search.value.trim() ? true : expandedAreas.value.has(area)
}

function toggleArea(area) {
  if (search.value.trim()) return  // search forces open; collapse toggling is moot
  const next = new Set(expandedAreas.value)
  next.has(area) ? next.delete(area) : next.add(area)
  expandedAreas.value = next
}

const allExpanded = computed(() =>
  filteredGroups.value.length > 0 && filteredGroups.value.every(g => expandedAreas.value.has(g.area))
)

function toggleAll() {
  expandedAreas.value = allExpanded.value ? new Set() : new Set(groups.value.map(g => g.area))
}
</script>
