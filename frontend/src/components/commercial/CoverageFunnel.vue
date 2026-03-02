<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden flex flex-col">
    <div class="px-4 py-3 border-b border-grey-100 shrink-0">
      <span class="text-subheading font-bold text-grey-900">{{ title }}</span>
    </div>
    <v-chart
      v-if="stages.length"
      :option="chartOption"
      autoresize
      class="flex-1 min-h-[200px]"
    />
    <div v-else class="p-4 text-center text-body text-grey-500">No funnel data</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { FunnelChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([FunnelChart, TooltipComponent, CanvasRenderer])

const props = defineProps({
  title: { type: String, default: 'Coverage Funnel' },
  stages: { type: Array, default: () => [] },
})

const COLORS = ['#4d003a', '#7a005d', '#a3007c', '#d4a0c3']

const chartOption = computed(() => ({
  color: COLORS,
  tooltip: {
    trigger: 'item',
    formatter(params) {
      const d = params.data
      return `<b>${d.name}</b><br/>Count: ${d.count.toLocaleString()}<br/>Percentage: ${d.value}%`
    },
  },
  series: [{
    type: 'funnel',
    left: '10%',
    top: 10,
    bottom: 10,
    width: '80%',
    sort: 'descending',
    gap: 4,
    label: {
      show: true,
      position: 'inside',
      formatter(params) {
        return `${params.data.name}\n${params.data.count.toLocaleString()} (${params.data.value}%)`
      },
      fontSize: 12,
      color: '#fff',
      lineHeight: 16,
    },
    itemStyle: {
      borderColor: '#fff',
      borderWidth: 1,
    },
    emphasis: {
      itemStyle: {
        shadowBlur: 10,
        shadowColor: 'rgba(163, 0, 124, 0.3)',
      },
    },
    data: props.stages.map((stage) => ({
      name: stage.name,
      value: stage.pct,
      count: stage.count,
    })),
  }],
}))
</script>
