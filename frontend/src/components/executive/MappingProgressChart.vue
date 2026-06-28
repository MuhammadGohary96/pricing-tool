<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2">
        <BarChart2 class="w-4 h-4 text-brand-primary" />
        <h2 class="text-subheading font-bold text-grey-900 tracking-tightish">Mapping progress by competitor</h2>
      </div>
      <!-- Summary badge + Legend -->
      <div class="flex items-center gap-3 flex-wrap">
        <span v-if="avgMappedPct > 0" class="text-micro font-bold px-2 py-0.5 rounded bg-green-50 text-green-700">
          {{ avgMappedPct }}% avg. mapped
        </span>
        <div class="w-px h-3 bg-grey-200"></div>
        <div v-for="seg in SEGMENTS" :key="seg.key" class="flex items-center gap-1">
          <div class="w-2.5 h-2.5 rounded-sm shrink-0" :style="{ background: seg.color }"></div>
          <span class="text-micro text-grey-500">{{ seg.label }}</span>
        </div>
        <div class="flex items-center gap-1">
          <div class="w-5 h-0 border-t-2 border-dashed border-brand-primary shrink-0"></div>
          <span class="text-micro text-grey-500">Potential Reach</span>
        </div>
      </div>
    </div>

    <v-chart
      v-if="data.length"
      :option="chartOption"
      autoresize
      style="height: 260px;"
    />
    <EmptyState v-else :icon="BarChart2" title="No mapping data" message="No competitor mapping data available." />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { prefersReducedMotion } from '../../utils/motion'
import { BarChart2 } from 'lucide-vue-next'
import VChart from 'vue-echarts'
import EmptyState from '../shared/EmptyState.vue'
import { use } from 'echarts/core'
import { BarChart, ScatterChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, ScatterChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const avgMappedPct = computed(() => {
  if (!props.data.length) return 0
  const total = props.data.reduce((s, d) => s + (d.total || 0), 0)
  const mapped = props.data.reduce((s, d) => s + (d.mapped_not_pl || 0) + (d.mapped_pl || 0), 0)
  return total > 0 ? Math.round(mapped / total * 100) : 0
})

const SEGMENTS = [
  { key: 'mapped_not_pl', label: 'Mapped', color: '#059669' },
  { key: 'mapped_pl',     label: 'Mapped (PL)', color: '#34D399' },
  { key: 'potential',     label: 'Potential Match', color: '#F59E0B' },
  { key: 'no_potential',  label: 'No Potential Match', color: '#EF4444' },
  { key: 'no_match',      label: 'No Match (decided)', color: '#9CA3AF' },
]

const chartOption = computed(() => {
  const competitors = props.data.map(d => d.competitor_name)
  const totals = props.data.map(d => d.total || 1)

  // Convert each segment to percentage of total
  function pct(val, i) { return val != null ? Math.round(val / totals[i] * 100 * 10) / 10 : 0 }

  const mappedNotPl  = props.data.map((d, i) => pct(d.mapped_not_pl, i))
  const mappedPl     = props.data.map((d, i) => pct(d.mapped_pl, i))
  const potential    = props.data.map((d, i) => pct((d.potential_not_pl || 0) + (d.potential_pl || 0), i))
  const noPotential  = props.data.map((d, i) => pct((d.no_potential_not_pl || 0) + (d.no_potential_pl || 0), i))
  const noMatch      = props.data.map((d, i) => pct((d.no_match_not_pl || 0) + (d.no_match_pl || 0), i))

  const barH = Math.max(32, Math.min(48, 200 / Math.max(competitors.length, 1)))

  return {
    animation: !prefersReducedMotion(),
    animationDuration: 500,
    textStyle: { fontFamily: 'Geist, system-ui, sans-serif' },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(17,24,39,0.96)',
      borderColor: 'transparent',
      borderWidth: 0,
      textStyle: { color: '#fff', fontSize: 11, fontFamily: 'Geist, system-ui, sans-serif' },
      extraCssText: 'border-radius:10px;box-shadow:0 8px 24px rgba(40,16,48,0.18);padding:8px 10px;',
      formatter(params) {
        const idx = params[0].dataIndex
        const d = props.data[idx]
        const mapped = (d.mapped_not_pl || 0) + (d.mapped_pl || 0)
        const pot = (d.potential_not_pl || 0) + (d.potential_pl || 0)
        const total = d.total || 1
        const reach = mapped + pot
        return [
          `<b>${d.competitor_name}</b>`,
          `Mapped: <b>${mapped.toLocaleString()}</b> (${d.mapped_pct}%)`,
          `&nbsp;&nbsp;Not PL: ${(d.mapped_not_pl || 0).toLocaleString()} · PL: ${(d.mapped_pl || 0).toLocaleString()}`,
          `Potential: <b>${pot.toLocaleString()}</b>`,
          `No Potential Match: <b>${((d.no_potential_not_pl || 0) + (d.no_potential_pl || 0)).toLocaleString()}</b>`,
          `No Match (decided): <b>${((d.no_match_not_pl || 0) + (d.no_match_pl || 0)).toLocaleString()}</b>`,
          `<hr style="margin:4px 0;border-color:#e5e7eb"/>`,
          `Total: <b>${total.toLocaleString()}</b>`,
          `Potential Reach: <b style="color:#a3007c">${d.potential_reach_pct}%</b> (excl. No Match)`,
        ].join('<br/>')
      },
    },
    grid: { left: 90, right: 60, top: 8, bottom: 20 },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%', fontSize: 9, color: '#999' },
      splitLine: { lineStyle: { color: '#F5F5F5' } },
    },
    yAxis: {
      type: 'category',
      data: competitors,
      axisLabel: { fontSize: 11, color: '#555' },
      inverse: true,
    },
    series: [
      {
        name: 'Mapped',
        type: 'bar',
        stack: 'total',
        barMaxWidth: barH,
        data: mappedNotPl,
        itemStyle: { color: '#059669' },
        label: {
          show: true,
          position: 'inside',
          fontSize: 9,
          color: '#fff',
          formatter: p => p.value > 6 ? `${p.value}%` : '',
        },
      },
      {
        name: 'Mapped (PL)',
        type: 'bar',
        stack: 'total',
        barMaxWidth: barH,
        data: mappedPl,
        itemStyle: { color: '#34D399' },
        label: {
          show: true,
          position: 'inside',
          fontSize: 9,
          color: '#065F46',
          formatter: p => p.value > 6 ? `${p.value}%` : '',
        },
      },
      {
        name: 'Potential Match',
        type: 'bar',
        stack: 'total',
        barMaxWidth: barH,
        data: potential,
        itemStyle: { color: '#F59E0B' },
        label: {
          show: true,
          position: 'inside',
          fontSize: 9,
          color: '#78350F',
          formatter: p => p.value > 6 ? `${p.value}%` : '',
        },
      },
      {
        name: 'No Potential Match',
        type: 'bar',
        stack: 'total',
        barMaxWidth: barH,
        data: noPotential,
        itemStyle: { color: '#EF4444' },
        label: {
          show: true,
          position: 'inside',
          fontSize: 9,
          color: '#fff',
          formatter: p => p.value > 6 ? `${p.value}%` : '',
        },
      },
      {
        name: 'No Match (decided)',
        type: 'bar',
        stack: 'total',
        barMaxWidth: barH,
        data: noMatch,
        itemStyle: { color: '#9CA3AF' },
        label: {
          show: true,
          position: 'inside',
          fontSize: 9,
          color: '#fff',
          formatter: p => p.value > 6 ? `${p.value}%` : '',
        },
      },
      // Potential reach diamond — sits at the right edge of the mapped+potential
      // segments (% of total), so it stays aligned with the stacked bar. (The
      // headline reach % in the tooltip is computed excl. No Match.)
      {
        type: 'scatter',
        data: props.data.map((d, i) => [
          Math.round((mappedNotPl[i] + mappedPl[i] + potential[i]) * 10) / 10,
          competitors[i],
        ]),
        symbolSize: 10,
        symbol: 'diamond',
        itemStyle: { color: '#a3007c' },
        tooltip: { show: false },
        z: 10,
      },
    ],
  }
})
</script>
