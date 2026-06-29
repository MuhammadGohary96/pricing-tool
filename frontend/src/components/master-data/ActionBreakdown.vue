<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between">
      <span class="text-subheading font-bold text-grey-900 tracking-tightish">Action Breakdown by Category</span>
      <span class="text-micro px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary font-medium">Click a category to filter</span>
    </div>
    <v-chart
      v-if="data.length"
      :option="chartOption"
      autoresize
      style="height: 280px"
      @click="handleClick"
    />
    <EmptyState v-else :icon="ChartColumnBig" title="No actions to break down" message="Action counts by category will appear here once products need attention." />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { prefersReducedMotion } from '../../utils/motion'
import { ChartColumnBig } from 'lucide-vue-next'
import EmptyState from '../shared/EmptyState.vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const emit = defineEmits(['select'])

const chartOption = computed(() => {
  const categories = props.data.map(d => d.category)

  return {
    animation: !prefersReducedMotion(),
    animationDuration: 500,
    animationEasing: 'cubicInOut',
    animationDurationUpdate: 400,
    animationEasingUpdate: 'cubicInOut',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      data: ['Needs Mapping', 'Review Match', 'Needs Price Update'],
      bottom: 0,
      textStyle: { fontSize: 9, color: '#999' },
    },
    grid: {
      left: 120,
      right: 20,
      top: 10,
      bottom: 40,
    },
    xAxis: {
      type: 'value',
      axisLabel: { fontSize: 9, color: '#999' },
    },
    yAxis: {
      type: 'category',
      data: categories,
      axisLabel: { fontSize: 9, color: '#555', width: 110, overflow: 'truncate' },
      inverse: true,
    },
    series: [
      {
        name: 'Needs Mapping',
        type: 'bar',
        stack: 'total',
        data: props.data.map(d => d.needs_mapping),
        itemStyle: { color: '#4d003a' },
        barMaxWidth: 20,
      },
      {
        name: 'Review Match',
        type: 'bar',
        stack: 'total',
        data: props.data.map(d => d.review_match),
        itemStyle: { color: '#a3007c' },
      },
      {
        name: 'Needs Price Update',
        type: 'bar',
        stack: 'total',
        data: props.data.map(d => d.needs_price_update),
        itemStyle: { color: '#d4a0c3' },
      },
    ],
  }
})

function handleClick(params) {
  if (params.name) {
    emit('select', params.name)
  }
}
</script>
