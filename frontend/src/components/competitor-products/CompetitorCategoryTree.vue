<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden flex-1">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center gap-2">
      <TreePine class="w-4 h-4 text-brand-primary" />
      <span class="text-subheading font-bold text-grey-900">Category Breakdown</span>
      <span class="text-caption text-grey-400 ml-1">size = products, color = mapping %</span>
    </div>
    <div class="p-4">
      <v-chart v-if="data.length" :option="chartOption" autoresize style="height: 360px" />
      <div v-else class="h-[360px] flex items-center justify-center text-grey-400 text-body">
        No category data available
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { TreemapChart } from 'echarts/charts'
import { TooltipComponent, VisualMapComponent } from 'echarts/components'
import { TreePine } from 'lucide-vue-next'

use([CanvasRenderer, TreemapChart, TooltipComponent, VisualMapComponent])

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const chartOption = computed(() => {
  if (!props.data.length) return {}

  const treeData = props.data.map((l1) => ({
    name: l1.name,
    value: l1.total,
    mapping_rate: l1.mapping_rate,
    children: (l1.children || []).map((l2) => ({
      name: l2.name,
      value: l2.total,
      mapping_rate: l2.mapping_rate,
    })),
  }))

  return {
    tooltip: {
      formatter(info) {
        const r = info.data
        return `<b>${info.name}</b><br/>Products: ${r.value?.toLocaleString() ?? '—'}<br/>Mapping: ${r.mapping_rate ?? 0}%`
      },
    },
    visualMap: {
      type: 'continuous',
      min: 0,
      max: 100,
      dimension: 'mapping_rate',
      inRange: {
        color: ['#FCA5A5', '#FDE68A', '#86EFAC'],
      },
      text: ['100%', '0%'],
      textStyle: { fontSize: 10 },
      show: true,
      right: 4,
      bottom: 4,
      itemWidth: 12,
      itemHeight: 80,
    },
    series: [
      {
        type: 'treemap',
        data: treeData,
        leafDepth: 1,
        roam: false,
        breadcrumb: { show: true, top: 4, left: 4, itemStyle: { color: '#f5f5f5' } },
        levels: [
          {
            itemStyle: { borderWidth: 2, borderColor: '#fff', gapWidth: 2 },
            upperLabel: { show: true, height: 20, fontSize: 11, fontWeight: 'bold' },
          },
          {
            itemStyle: { borderWidth: 1, borderColor: '#eee', gapWidth: 1 },
            upperLabel: { show: false },
          },
        ],
        label: {
          show: true,
          fontSize: 10,
          formatter: '{b}',
        },
      },
    ],
  }
})
</script>
