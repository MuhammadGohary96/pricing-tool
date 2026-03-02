<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100">
      <span class="text-subheading font-bold text-grey-900">PI by Category</span>
    </div>
    <v-chart
      v-if="data.length"
      ref="chartRef"
      :option="chartOption"
      autoresize
      style="height: 280px; cursor: pointer"
      aria-label="Horizontal bar chart showing blended price index by main category"
      @click="onBarClick"
    />
    <EmptyState v-else :icon="BarChart3Icon" title="No category data" message="No data for current filters. Try broadening your selection." />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import EmptyState from '../shared/EmptyState.vue'
import { BarChart3 as BarChart3Icon } from 'lucide-vue-next'

const router = useRouter()
const chartRef = ref(null)
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, TooltipComponent, GridComponent, MarkLineComponent, CanvasRenderer])

const props = defineProps({
  data: { type: Array, default: () => [] },
})

function onBarClick(params) {
  if (params.name) {
    router.push({ path: '/commercial', query: { main_category: params.name } })
  }
}

const chartOption = computed(() => {
  const categories = props.data.map(d => d.category_name)
  const values = props.data.map(d => d.blended_pi)

  return {
    animationDuration: 500,
    animationEasing: 'cubicInOut',
    animationDurationUpdate: 400,
    animationEasingUpdate: 'cubicInOut',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter(params) {
        const p = params[0]
        const dev = props.data[p.dataIndex]?.pi_deviation
        const devStr = dev != null ? ` (${dev > 0 ? '+' : ''}${(dev * 100).toFixed(1)}%)` : ''
        return `${p.name}<br/>PI: <b>${p.value?.toFixed(4)}</b>${devStr}`
      },
    },
    grid: {
      left: 120,
      right: 30,
      top: 20,
      bottom: 20,
    },
    xAxis: {
      type: 'value',
      min: 0.85,
      max: 1.20,
      axisLabel: { fontSize: 9, color: '#999' },
      splitLine: { lineStyle: { color: '#F5F5F5' } },
    },
    yAxis: {
      type: 'category',
      data: categories,
      axisLabel: { fontSize: 9, color: '#555', width: 110, overflow: 'truncate' },
      inverse: true,
    },
    series: [{
      type: 'bar',
      data: values.map(v => ({
        value: v,
        itemStyle: {
          color: v >= 1 ? '#4d003a' : '#d4a0c3',
        },
      })),
      barMaxWidth: 20,
      markLine: {
        silent: true,
        lineStyle: { color: '#999', type: 'dashed' },
        data: [{ xAxis: 1.0, label: { formatter: '1.0', fontSize: 9, position: 'start' } }],
      },
    }],
  }
})
</script>
