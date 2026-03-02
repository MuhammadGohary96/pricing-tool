<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100">
      <span class="text-subheading font-bold text-grey-900">Blended PI Trend (30 Days)</span>
    </div>
    <v-chart
      v-if="data.length"
      :option="chartOption"
      autoresize
      style="height: 220px"
    />
    <div v-else class="flex items-center justify-center h-40 text-body text-grey-500">
      No trend data
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, TooltipComponent, GridComponent, MarkLineComponent, CanvasRenderer])

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    formatter(params) {
      const p = params[0]
      return `${p.name}<br/>Blended PI: <b>${p.value.toFixed(4)}</b>`
    },
  },
  grid: {
    left: 60,
    right: 20,
    top: 20,
    bottom: 30,
  },
  xAxis: {
    type: 'category',
    data: props.data.map(d => d.date),
    axisLabel: {
      fontSize: 8,
      color: '#999',
      formatter(val) {
        return val.slice(5)
      },
    },
    boundaryGap: false,
  },
  yAxis: {
    type: 'value',
    min: 'dataMin',
    max: 'dataMax',
    axisLabel: { fontSize: 9, color: '#999' },
    splitLine: { lineStyle: { color: '#F5F5F5' } },
  },
  series: [{
    type: 'line',
    data: props.data.map(d => d.value),
    smooth: true,
    lineStyle: { color: '#a3007c', width: 2 },
    itemStyle: { color: '#a3007c' },
    areaStyle: {
      color: {
        type: 'linear',
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(171,1,132,0.15)' },
          { offset: 1, color: 'rgba(171,1,132,0.02)' },
        ],
      },
    },
    markLine: {
      silent: true,
      lineStyle: { color: '#999', type: 'dashed' },
      data: [{ yAxis: 1.0, label: { formatter: 'Parity', fontSize: 9, color: '#999' } }],
    },
  }],
}))
</script>
