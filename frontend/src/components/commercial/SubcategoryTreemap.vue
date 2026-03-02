<template>
  <div class="bg-white rounded-lg shadow-card overflow-hidden flex flex-col">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-2 shrink-0">
      <span class="text-subheading font-bold text-grey-900">Subcategory Treemap</span>
      <div class="flex items-center gap-2 shrink-0">
        <!-- Selected state indicator -->
        <span v-if="selected" class="text-micro px-2 py-0.5 rounded-full bg-green-50 text-green-700 font-medium flex items-center gap-1">
          Viewing: {{ selected }}
          <button class="hover:text-green-900 font-bold" @click="$emit('select', null)">&times;</button>
        </span>
        <span v-else class="text-micro px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary font-medium">Click a region to filter</span>
      </div>
    </div>
    <v-chart
      v-if="data.length"
      :option="chartOption"
      autoresize
      class="flex-1 min-h-[380px]"
      aria-label="Treemap showing subcategory revenue distribution colored by price index. Click a region to filter."
      @click="handleClick"
    />
    <EmptyState v-else :icon="MapIcon" title="No subcategory data" message="No data for current filters. Try broadening your selection." action-label="Clear Filters" @action="$emit('clearFilters')" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import EmptyState from '../shared/EmptyState.vue'
import { Map as MapIcon } from 'lucide-vue-next'
import { piToHex } from '../../utils/piColor'
import { use } from 'echarts/core'
import { TreemapChart } from 'echarts/charts'
import { TooltipComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([TreemapChart, TooltipComponent, VisualMapComponent, CanvasRenderer])

const props = defineProps({
  data: { type: Array, default: () => [] },
  selected: { type: String, default: null },
})

const emit = defineEmits(['select', 'clearFilters'])

const chartOption = computed(() => ({
  tooltip: {
    formatter(params) {
      const d = params.data
      if (!d || !d.name) return ''
      const pi = d.blended_pi != null ? d.blended_pi.toFixed(4) : 'N/A'
      const rev = d.value != null ? Math.round(d.value).toLocaleString() : 'N/A'
      return `<b>${d.name}</b><br/>
        Blended PI: ${pi}<br/>
        Revenue: ${rev} EGP<br/>
        Products: ${d.product_count || 0}`
    },
  },
  animationDuration: 500,
  animationEasing: 'cubicInOut',
  animationDurationUpdate: 400,
  animationEasingUpdate: 'cubicInOut',
  series: [{
    type: 'treemap',
    roam: false,
    nodeClick: false,
    breadcrumb: { show: false },
    label: {
      show: true,
      formatter: '{b}',
      fontSize: 9,
      color: '#fff',
    },
    itemStyle: {
      borderColor: '#fff',
      borderWidth: 1,
      gapWidth: 1,
    },
    emphasis: {
      itemStyle: {
        shadowBlur: 10,
        shadowColor: 'rgba(163, 0, 124, 0.3)',
        borderColor: '#a3007c',
        borderWidth: 2,
      },
    },
    levels: [{
      itemStyle: {
        borderColor: '#fff',
        borderWidth: 2,
        gapWidth: 2,
      },
    }],
    data: props.data.map(item => ({
      name: item.name,
      value: item.value,
      blended_pi: item.blended_pi,
      product_count: item.product_count,
      itemStyle: {
        color: piToHex(item.blended_pi),
      },
      label: {
        color: item.blended_pi != null && (item.blended_pi >= 1.15 || item.blended_pi < 0.85) ? '#fff' : '#1F2937',
      },
    })),
  }],
}))

function handleClick(params) {
  if (params.data && params.data.name) {
    emit('select', params.data.name)
  }
}
</script>
