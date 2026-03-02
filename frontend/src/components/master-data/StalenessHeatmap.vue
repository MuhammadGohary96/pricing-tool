<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between">
      <div class="flex items-center gap-1.5">
        <span class="text-subheading font-bold text-grey-900">Staleness Heatmap</span>
        <HelpTooltip text="Staleness = days since last competitor price update. Darker cells = more stale products needing re-scraping." />
      </div>
      <span class="text-micro px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary font-medium">Darker = more stale products</span>
    </div>
    <v-chart
      v-if="data && data.cells && data.cells.length"
      :option="chartOption"
      autoresize
      :style="{ height: chartHeight + 'px' }"
    />
    <EmptyState v-else :icon="CalendarDaysIcon" title="No staleness data" message="No data for current filters. Try broadening your selection." />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import EmptyState from '../shared/EmptyState.vue'
import { CalendarDays as CalendarDaysIcon } from 'lucide-vue-next'
import HelpTooltip from '../shared/HelpTooltip.vue'
import { use } from 'echarts/core'
import { HeatmapChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([HeatmapChart, TooltipComponent, GridComponent, VisualMapComponent, CanvasRenderer])

const props = defineProps({
  data: { type: Object, default: null },
})

const chartHeight = computed(() => {
  const rows = props.data?.subcategories?.length || 0
  return Math.max(300, rows * 28 + 60)
})

const chartOption = computed(() => {
  if (!props.data) return {}

  const subcats = props.data.subcategories || []
  const buckets = props.data.buckets || []
  const cells = props.data.cells || []

  const bucketIndex = {}
  buckets.forEach((b, i) => { bucketIndex[b] = i })
  const subcatIndex = {}
  subcats.forEach((s, i) => { subcatIndex[s] = i })

  const heatmapData = cells.map(c => [
    bucketIndex[c.bucket] ?? 0,
    subcatIndex[c.sub_category_name] ?? 0,
    c.count,
  ])

  const maxCount = Math.max(...cells.map(c => c.count), 1)

  return {
    animationDuration: 500,
    animationEasing: 'cubicInOut',
    animationDurationUpdate: 400,
    animationEasingUpdate: 'cubicInOut',
    tooltip: {
      formatter(params) {
        const d = params.data
        if (!d) return ''
        return `<b>${subcats[d[1]]}</b><br/>
          ${buckets[d[0]]}: ${d[2]} products`
      },
    },
    grid: {
      left: 160,
      right: 30,
      top: 10,
      bottom: 36,
      containLabel: false,
    },
    xAxis: {
      type: 'category',
      data: buckets,
      axisLabel: { fontSize: 11, color: '#666' },
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: subcats,
      axisLabel: { fontSize: 11, color: '#555', width: 150, overflow: 'truncate' },
      inverse: true,
    },
    visualMap: {
      min: 0,
      max: maxCount,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      show: false,
      inRange: {
        color: ['#f3e3ed', '#d4a0c3', '#a3007c', '#7a005d', '#4d003a'],
      },
    },
    series: [{
      type: 'heatmap',
      data: heatmapData,
      label: {
        show: true,
        fontSize: 11,
        color: '#333',
        formatter(params) {
          return params.data[2] > 0 ? params.data[2] : ''
        },
      },
      emphasis: {
        itemStyle: { shadowBlur: 4, shadowColor: 'rgba(0,0,0,0.2)' },
      },
    }],
  }
})
</script>
