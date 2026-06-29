<template>
  <div
    class="bg-white rounded-xl shadow-panel ring-1 ring-grey-200/70 px-4 py-3 flex-1 min-w-0 card-interactive animate-fade-in-up relative overflow-hidden kpi-card-wrap"
    :style="{ animationDelay: `${staggerIndex * 0.06}s` }"
  >
    <!-- Top accent bar (appears on hover via CSS) -->
    <div class="kpi-accent-bar"></div>

    <div class="flex items-start justify-between gap-2 mb-1">
      <span class="text-caption text-grey-600 font-semibold uppercase tracking-wide leading-tight">{{ label }}</span>
      <div v-if="icon" class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" :class="iconBg">
        <component :is="icon" class="w-4 h-4" />
      </div>
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-kpi text-grey-900 tabular-nums">{{ formattedValue }}</span>
      <!-- Trend badge -->
      <span
        v-if="trend"
        class="inline-flex items-center gap-0.5 text-micro font-bold px-1.5 py-0.5 rounded"
        :class="trend.direction === 'up' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'"
      >
        <component :is="trend.direction === 'up' ? ArrowUp : ArrowDown" class="w-3 h-3" />
        {{ trend.value }}
      </span>
    </div>
    <div v-if="subtitle" class="text-caption text-grey-500 mt-1">{{ subtitle }}</div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useTransition } from '@vueuse/core'
import { ArrowUp, ArrowDown } from 'lucide-vue-next'

const props = defineProps({
  value: { type: [Number, String], default: 0 },
  label: { type: String, required: true },
  subtitle: { type: String, default: '' },
  format: { type: String, default: 'number' },
  staggerIndex: { type: Number, default: 0 },
  highlight: { type: Boolean, default: false },
  trend: { type: Object, default: null }, // { direction: 'up'|'down', value: '2.1%' }
  icon: { type: [String, Object], default: null },
  iconBg: { type: String, default: 'bg-grey-100' },
})

const numericValue = ref(0)
watch(() => props.value, (newVal) => {
  numericValue.value = typeof newVal === 'number' ? newVal : 0
}, { immediate: true })

const animatedValue = useTransition(numericValue, {
  duration: 600,
  transition: [0.25, 0.1, 0.25, 1],
})

const formattedValue = computed(() => {
  if (props.value === null || props.value === undefined) return '--'
  if (props.format === 'string') return props.value
  const val = animatedValue.value
  if (props.format === 'pi') return val.toFixed(2)
  if (props.format === 'percent') return `${val.toFixed(1)}%`
  return Math.round(val).toLocaleString()
})
</script>

<style scoped>
.kpi-accent-bar {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--brand-primary);
  border-radius: 16px 16px 0 0;
  opacity: 0;
  transition: opacity 0.2s;
}
.kpi-card-wrap:hover .kpi-accent-bar {
  opacity: 1;
}
</style>
