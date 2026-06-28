<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2">
      <PieChartIcon class="w-4 h-4 text-brand-primary" />
      <h2 class="text-subheading font-bold text-grey-900 tracking-tightish">Product classification</h2>

      <!-- Competitor toggle -->
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

    <div class="flex gap-0">
      <!-- Donut chart -->
      <div class="flex-1 min-w-0">
        <v-chart
          v-if="hasData"
          :option="chartOption"
          autoresize
          style="height: 280px;"
          @click="onSegmentClick"
        />
        <EmptyState v-else :icon="PieChartIcon" title="No classification data" message="No data available." />
      </div>

      <!-- Summary legend -->
      <div class="w-44 shrink-0 flex flex-col justify-center gap-2 pr-4">
        <div v-for="item in legendItems" :key="item.label" class="flex items-center gap-2">
          <div class="w-2.5 h-2.5 rounded-sm shrink-0" :style="{ background: item.color }"></div>
          <div class="min-w-0">
            <div class="text-micro text-grey-500 leading-tight">{{ item.label }}</div>
            <div class="text-body font-bold text-grey-900">
              {{ item.count.toLocaleString() }}
              <span class="text-micro font-normal text-grey-400">({{ item.pct }}%)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { prefersReducedMotion } from '../../utils/motion'
import { PieChart as PieChartIcon } from 'lucide-vue-next'
import VChart from 'vue-echarts'
import EmptyState from '../shared/EmptyState.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, GraphicComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([PieChart, TooltipComponent, GraphicComponent, CanvasRenderer])

const props = defineProps({
  data: {
    type: Object,
    default: () => ({}),
  },
  mappingProgress: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['navigate'])

const LS_KEY = 'bf_selected_competitor_classification'
const selectedCompetitor = ref(null)

const competitorNames = computed(() =>
  props.mappingProgress.map(r => r.competitor_name).sort()
)

// Auto-select Talabat by default; fall back to first competitor. Persisted in localStorage.
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

// Resolve classification counts
const d = computed(() => {
  if (selectedCompetitor.value && props.mappingProgress.length) {
    const entry = props.mappingProgress.find(r => r.competitor_name === selectedCompetitor.value)
    if (entry) {
      return {
        mapped_not_pl: entry.mapped_not_pl || 0,
        mapped_pl: entry.mapped_pl || 0,
        not_mapped_not_pl_potential: entry.potential_not_pl || 0,
        not_mapped_not_pl_no_potential: entry.no_potential_not_pl || 0,
        not_mapped_pl_potential: entry.potential_pl || 0,
        not_mapped_pl_no_potential: entry.no_potential_pl || 0,
        not_mapped_not_pl_no_match: entry.no_match_not_pl || 0,
        not_mapped_pl_no_match: entry.no_match_pl || 0,
      }
    }
  }
  return props.data || {}
})

const total = computed(() => {
  const v = d.value
  return (
    (v.mapped_not_pl || 0) + (v.mapped_pl || 0) +
    (v.not_mapped_not_pl_potential || 0) + (v.not_mapped_not_pl_no_potential || 0) +
    (v.not_mapped_pl_potential || 0) + (v.not_mapped_pl_no_potential || 0) +
    (v.not_mapped_not_pl_no_match || 0) + (v.not_mapped_pl_no_match || 0)
  )
})

// The mapped buckets are now driven by is_mapped on the backend (same definition
// as "Blended PI by competitor" → Mapping Coverage), so mapped_not_pl + mapped_pl
// equals mapped_products and the donut center matches both its own green arcs and
// that table.
const mappedTotal = computed(() => (d.value.mapped_not_pl || 0) + (d.value.mapped_pl || 0))
const mappedPct = computed(() => total.value > 0 ? Math.round(mappedTotal.value / total.value * 100) : 0)

const hasData = computed(() => total.value > 0)

function pct(val) {
  if (!val || !total.value) return 0
  return Math.round(val / total.value * 1000) / 10
}

const legendItems = computed(() => {
  const v = d.value
  const potential = (v.not_mapped_not_pl_potential || 0) + (v.not_mapped_pl_potential || 0)
  const noPotential = (v.not_mapped_not_pl_no_potential || 0) + (v.not_mapped_pl_no_potential || 0)
  const noMatch = (v.not_mapped_not_pl_no_match || 0) + (v.not_mapped_pl_no_match || 0)
  const mapped = (v.mapped_not_pl || 0) + (v.mapped_pl || 0)
  return [
    { label: 'Mapped', count: mapped, color: '#059669', pct: pct(mapped) },
    { label: 'Potential match', count: potential, color: '#F59E0B', pct: pct(potential) },
    { label: 'No likely match', count: noPotential, color: '#EF4444', pct: pct(noPotential) },
    { label: 'Confirmed no match', count: noMatch, color: '#9CA3AF', pct: pct(noMatch) },
  ]
})

const SEGMENT_DATA = computed(() => {
  const v = d.value
  const potential = (v.not_mapped_not_pl_potential || 0) + (v.not_mapped_pl_potential || 0)
  const noPotential = (v.not_mapped_not_pl_no_potential || 0) + (v.not_mapped_pl_no_potential || 0)
  const noMatch = (v.not_mapped_not_pl_no_match || 0) + (v.not_mapped_pl_no_match || 0)
  const mapped = (v.mapped_not_pl || 0) + (v.mapped_pl || 0)
  return [
    { name: 'Mapped', value: mapped, itemStyle: { color: '#059669' } },
    { name: 'Potential match', value: potential, itemStyle: { color: '#F59E0B' } },
    { name: 'No likely match', value: noPotential, itemStyle: { color: '#EF4444' } },
    { name: 'Confirmed no match', value: noMatch, itemStyle: { color: '#9CA3AF' } },
  ].filter(s => s.value > 0)
})

const chartOption = computed(() => {
  const t = total.value || 1
  return {
    animation: !prefersReducedMotion(),
    animationDuration: 400,
    animationEasing: 'cubicOut',
    animationDurationUpdate: 300,
    textStyle: { fontFamily: 'Geist, system-ui, sans-serif' },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(17,24,39,0.96)',
      borderColor: 'transparent',
      borderWidth: 0,
      textStyle: { color: '#fff', fontSize: 11, fontFamily: 'Geist, system-ui, sans-serif' },
      extraCssText: 'border-radius:10px;box-shadow:0 8px 24px rgba(40,16,48,0.18);padding:8px 10px;',
      formatter: p => `${p.name}<br/><b>${p.value?.toLocaleString()}</b> (${((p.value / t) * 100).toFixed(1)}%)`,
    },
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: '42%',
        style: {
          text: `${mappedPct.value}%`,
          fontSize: 22,
          fontWeight: 900,
          fontFamily: 'Geist, system-ui, sans-serif',
          fill: '#111827',
          textAlign: 'center',
        },
      },
      {
        type: 'text',
        left: 'center',
        top: '55%',
        style: {
          text: 'Mapped',
          fontSize: 11,
          fontFamily: 'Geist, system-ui, sans-serif',
          fill: '#6B7280',
          textAlign: 'center',
        },
      },
    ],
    series: [{
      type: 'pie',
      radius: ['50%', '78%'],
      center: ['50%', '50%'],
      data: SEGMENT_DATA.value,
      label: { show: false },
      emphasis: {
        scaleSize: 6,
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' },
      },
      itemStyle: {
        borderRadius: 3,
        borderColor: '#fff',
        borderWidth: 2,
      },
    }],
  }
})

function onSegmentClick(params) {
  const actionMap = {
    'Mapped': 'Complete',
    'Potential match': 'Review Match',
    'No likely match': 'Needs Mapping',
    // 'Confirmed no match' intentionally omitted — it's resolved, no action.
  }
  const action = actionMap[params.name]
  if (action) {
    emit('navigate', { action_type: action })
  }
}
</script>
