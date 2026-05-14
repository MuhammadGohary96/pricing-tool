<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2">
      <BarChart3 class="w-4 h-4 text-brand-primary" />
      <span class="text-subheading font-bold text-grey-900">Competitors Products Last Update</span>
      <span class="text-caption text-grey-400 ml-1">last 30 days</span>
    </div>
    <div class="p-4">
      <v-chart v-if="data.length" :option="chartOption" autoresize style="height: 320px" />
      <div v-else class="h-[320px] flex items-center justify-center text-grey-400 text-body">
        No crawl data available
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
} from 'echarts/components'
import { BarChart3 } from 'lucide-vue-next'

use([CanvasRenderer, BarChart, TooltipComponent, GridComponent, LegendComponent, MarkLineComponent])

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const COLORS = {
  Talabat: '#FF6B00',
  Carrefour: '#004E98',
  Instashop: '#00B4D8',
}

const chartOption = computed(() => {
  if (!props.data.length) return {}

  const dates = [...new Set(props.data.map((d) => d.date))].sort()
  const competitors = [...new Set(props.data.map((d) => d.competitor_name))]

  const dataMap = {}
  props.data.forEach((d) => {
    const key = `${d.date}|${d.competitor_name}`
    dataMap[key] = d.count
  })

  const series = competitors.map((comp, i) => ({
    name: comp,
    type: 'bar',
    stack: 'total',
    barMaxWidth: 24,
    itemStyle: {
      color: COLORS[comp] || ['#a3007c', '#00B4D8', '#FF6B00', '#22C55E'][i % 4],
      borderRadius: i === competitors.length - 1 ? [2, 2, 0, 0] : 0,
    },
    data: dates.map((d) => dataMap[`${d}|${comp}`] || 0),
    ...(i === 0
      ? {
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { type: 'dashed', color: '#EF4444', width: 1 },
            label: {
              formatter: '7d threshold',
              fontSize: 10,
              color: '#EF4444',
            },
            data: [
              {
                xAxis: (() => {
                  const d = new Date()
                  d.setDate(d.getDate() - 7)
                  return d.toISOString().slice(0, 10)
                })(),
              },
            ],
          },
        }
      : {}),
  }))

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      top: 0,
      textStyle: { fontSize: 11 },
    },
    grid: { left: 50, right: 16, top: 36, bottom: 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        fontSize: 10,
        formatter: (v) => {
          const d = new Date(v)
          return `${d.getDate()}/${d.getMonth() + 1}`
        },
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 10 },
    },
    series,
  }
})
</script>
