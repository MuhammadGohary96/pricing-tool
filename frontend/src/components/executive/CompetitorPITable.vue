<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2">
      <TrendingUp class="w-4 h-4 text-brand-primary" />
      <span class="text-subheading font-bold text-grey-900">Blended PI by Competitor</span>
      <span class="text-caption text-grey-400 ml-1">sorted by PI ↓</span>
      <ExportButton :fetcher="exportData" filename="competitor_pi.csv" class="ml-auto" />
    </div>

    <table v-if="data.length" class="w-full">
      <thead class="bg-grey-50 border-b border-grey-100">
        <tr>
          <th class="px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide w-36">Competitor</th>
          <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">Blended PI</th>
          <th class="px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide">vs Parity</th>
          <th class="px-4 py-2 text-caption font-semibold text-grey-500 uppercase tracking-wide" style="min-width:180px">
            Mapping Coverage
            <span class="text-micro font-normal normal-case tracking-normal text-grey-400 ml-1">mapped / total active</span>
          </th>
          <th class="px-4 py-2 text-caption font-semibold text-grey-500 uppercase tracking-wide" style="min-width:180px">
            Utilization
            <span class="text-micro font-normal normal-case tracking-normal text-grey-400 ml-1">used / eligible</span>
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-grey-50">
        <tr
          v-for="row in data"
          :key="row.competitor_name"
          class="hover:bg-brand-50 transition-colors cursor-pointer group relative"
          @click="$emit('select-competitor', row.competitor_name)"
          @mouseenter="hoveredRow = row"
          @mouseleave="hoveredRow = null"
        >
          <!-- Competitor name -->
          <td class="px-4 py-3">
            <div class="flex items-center gap-2">
              <CompetitorLogo :name="row.competitor_name" />
              <span class="text-body font-semibold text-grey-900 group-hover:text-brand-primary transition-colors">
                {{ row.competitor_name }}
              </span>
            </div>
          </td>

          <!-- Blended PI — colored cell -->
          <td class="px-4 py-3 text-right">
            <span
              class="inline-block px-2.5 py-1 rounded-lg font-mono font-bold text-body"
              :class="[piBgClass(row.blended_pi), piTextClass(row.blended_pi)]"
            >
              {{ row.blended_pi != null ? row.blended_pi.toFixed(4) : '—' }}
            </span>
          </td>

          <!-- Deviation — heatmap pill -->
          <td class="px-4 py-3 text-right">
            <span
              class="inline-block px-2 py-0.5 rounded font-mono text-body font-semibold"
              :class="[deviationClass(row.pi_deviation), deviationBgClass(row.pi_deviation)]"
            >
              {{ formatDeviation(row.pi_deviation) }}
            </span>
          </td>

          <!-- Mapping Coverage: mapped / total active -->
          <td class="px-4 py-3">
            <div class="flex flex-col gap-1">
              <div class="flex items-baseline gap-1">
                <span class="text-body font-mono font-semibold text-grey-900">
                  {{ (row.mapped_products ?? 0).toLocaleString() }}
                </span>
                <span class="text-micro text-grey-400">
                  / {{ (row._mapping?.total ?? row.eligible_products ?? 0).toLocaleString() }}
                </span>
                <span class="text-micro font-semibold ml-1" :class="barPctClass(mappingCoveragePct(row))">
                  ({{ mappingCoveragePct(row) }}%)
                </span>
              </div>
              <div class="h-1 bg-grey-100 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="barColorClass(mappingCoveragePct(row))"
                  :style="{ width: `${mappingCoveragePct(row)}%` }"
                ></div>
              </div>
            </div>
          </td>

          <!-- Utilization: used / eligible -->
          <td class="px-4 py-3">
            <div class="flex flex-col gap-1">
              <div class="flex items-baseline gap-1">
                <span class="text-body font-mono font-semibold text-grey-900">
                  {{ (row.used_products ?? 0).toLocaleString() }}
                </span>
                <span class="text-micro text-grey-400">
                  / {{ (row.eligible_products ?? 0).toLocaleString() }}
                </span>
                <span class="text-micro font-semibold ml-1" :class="barPctClass(utilizationPct(row))">
                  ({{ utilizationPct(row) }}%)
                </span>
              </div>
              <div class="h-1 bg-grey-100 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="barColorClass(utilizationPct(row))"
                  :style="{ width: `${utilizationPct(row)}%` }"
                ></div>
              </div>
            </div>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Hover tooltip -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="hoveredRow && hoveredRow._mapping"
          class="fixed z-50 bg-grey-900 text-white rounded-lg shadow-dropdown px-3 py-2 text-micro pointer-events-none max-w-xs"
          :style="tooltipStyle"
        >
          <div class="font-bold text-caption mb-1">{{ hoveredRow.competitor_name }}</div>
          <div class="flex flex-col gap-0.5">
            <div>Mapped: <b>{{ ((hoveredRow._mapping.mapped_not_pl || 0) + (hoveredRow._mapping.mapped_pl || 0)).toLocaleString() }}</b> ({{ hoveredRow._mapping.mapped_pct }}%)</div>
            <div>Potential: <b>{{ ((hoveredRow._mapping.potential_not_pl || 0) + (hoveredRow._mapping.potential_pl || 0)).toLocaleString() }}</b></div>
            <div>No Match: <b>{{ ((hoveredRow._mapping.no_potential_not_pl || 0) + (hoveredRow._mapping.no_potential_pl || 0)).toLocaleString() }}</b></div>
            <div class="border-t border-grey-700 pt-0.5 mt-0.5">
              Potential Reach: <b class="text-brand-light">{{ hoveredRow._mapping.potential_reach_pct }}%</b>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <EmptyState v-if="!data.length" :icon="TrendingUp" title="No competitor data" message="No competitor PI data available." />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { TrendingUp } from 'lucide-vue-next'
import EmptyState from '../shared/EmptyState.vue'
import ExportButton from '../shared/ExportButton.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import { piTextClass, piBgClass, piToHex } from '../../utils/piColor'

defineProps({
  data: { type: Array, default: () => [] },
})
defineEmits(['select-competitor'])

const hoveredRow = ref(null)
const tooltipStyle = ref({})

function onMouseMove(e) {
  tooltipStyle.value = {
    left: `${e.clientX + 12}px`,
    top: `${e.clientY - 10}px`,
  }
}

onMounted(() => window.addEventListener('mousemove', onMouseMove))
onUnmounted(() => window.removeEventListener('mousemove', onMouseMove))

function mappingCoveragePct(row) {
  const denom = row._mapping?.total ?? row.eligible_products ?? 0
  if (!denom) return 0
  return Math.round((row.mapped_products || 0) / denom * 100)
}

function utilizationPct(row) {
  if (!row.eligible_products) return 0
  return Math.round((row.used_products || 0) / row.eligible_products * 100)
}

function barPctClass(pct) {
  if (pct >= 60) return 'text-green-600'
  if (pct >= 35) return 'text-amber-600'
  return 'text-red-600'
}

function barColorClass(pct) {
  if (pct >= 60) return 'bg-green-500'
  if (pct >= 35) return 'bg-amber-400'
  return 'bg-red-500'
}

function formatDeviation(dev) {
  if (dev == null) return '—'
  const sign = dev > 0 ? '+' : ''
  return `${sign}${(dev * 100).toFixed(1)}%`
}

function deviationClass(dev) {
  if (dev == null) return 'text-grey-400'
  if (dev > 0.005) return 'text-green-600'
  if (dev < -0.005) return 'text-red-600'
  return 'text-grey-400'
}

function deviationBgClass(dev) {
  if (dev == null) return 'bg-grey-50'
  if (dev > 0.005) return 'bg-green-50'
  if (dev < -0.005) return 'bg-red-50'
  return 'bg-grey-50'
}

function exportData() {
  return props.data.map(r => ({
    competitor: r.competitor_name,
    blended_pi: r.blended_pi,
    pi_deviation: r.pi_deviation,
    mapped_products: r.mapped_products,
    eligible_products: r.eligible_products,
    used_products: r.used_products,
  }))
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
