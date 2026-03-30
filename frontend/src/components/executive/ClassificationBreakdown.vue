<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2">
      <PieChartIcon class="w-4 h-4 text-brand-primary" />
      <span class="text-subheading font-bold text-grey-900">Product Classification</span>

      <!-- Competitor toggle -->
      <div class="ml-auto flex items-center gap-1 flex-wrap justify-end">
        <button
          v-for="comp in competitorNames"
          :key="comp"
          class="px-2 py-0.5 rounded text-micro font-medium transition-colors"
          :class="selectedCompetitor === comp
            ? 'bg-brand-primary text-white'
            : 'bg-grey-100 text-grey-600 hover:bg-grey-200'"
          @click="selectedCompetitor = comp"
        >{{ comp }}</button>
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
import { PieChart as PieChartIcon } from 'lucide-vue-next'
import VChart from 'vue-echarts'
import EmptyState from '../shared/EmptyState.vue'
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

const selectedCompetitor = ref(null)

const competitorNames = computed(() =>
  props.mappingProgress.map(r => r.competitor_name).sort()
)

// Auto-select Talabat by default; fall back to first competitor
watch(competitorNames, (names) => {
  if (!names.length) return
  if (selectedCompetitor.value && names.includes(selectedCompetitor.value)) return
  selectedCompetitor.value = names.includes('Talabat') ? 'Talabat' : names[0]
}, { immediate: true })

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
    (v.not_mapped_pl_potential || 0) + (v.not_mapped_pl_no_potential || 0)
  )
})

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
  const noMatch = (v.not_mapped_not_pl_no_potential || 0) + (v.not_mapped_pl_no_potential || 0)
  return [
    { label: 'Mapped (Not PL)', count: v.mapped_not_pl || 0, color: '#059669', pct: pct(v.mapped_not_pl) },
    { label: 'Mapped (PL)', count: v.mapped_pl || 0, color: '#34D399', pct: pct(v.mapped_pl) },
    { label: 'Potential Match', count: potential, color: '#F59E0B', pct: pct(potential) },
    { label: 'No Potential', count: noMatch, color: '#EF4444', pct: pct(noMatch) },
  ]
})

const SEGMENT_DATA = computed(() => {
  const v = d.value
  const potential = (v.not_mapped_not_pl_potential || 0) + (v.not_mapped_pl_potential || 0)
  const noMatch = (v.not_mapped_not_pl_no_potential || 0) + (v.not_mapped_pl_no_potential || 0)
  return [
    { name: 'Mapped (Not PL)', value: v.mapped_not_pl || 0, itemStyle: { color: '#059669' } },
    { name: 'Mapped (PL)', value: v.mapped_pl || 0, itemStyle: { color: '#34D399' } },
    { name: 'Potential Match', value: potential, itemStyle: { color: '#F59E0B' } },
    { name: 'No Potential', value: noMatch, itemStyle: { color: '#EF4444' } },
  ].filter(s => s.value > 0)
})

const chartOption = computed(() => {
  const t = total.value || 1
  return {
    animationDuration: 400,
    animationEasing: 'cubicOut',
    animationDurationUpdate: 300,
    tooltip: {
      trigger: 'item',
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
    'Mapped (Not PL)': 'Complete',
    'Mapped (PL)': 'Complete',
    'Potential Match': 'Review Match',
    'No Potential': 'Needs Mapping',
  }
  const action = actionMap[params.name]
  if (action) {
    emit('navigate', { action_type: action })
  }
}
</script>
