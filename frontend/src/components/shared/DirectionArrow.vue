<template>
  <span class="text-body font-bold" :class="colorClass">
    {{ symbol }} {{ formatted }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  deviation: { type: Number, default: null },
})

const symbol = computed(() => {
  if (props.deviation === null || props.deviation === undefined) return '—'
  if (props.deviation > 0.005) return '▲'
  if (props.deviation < -0.005) return '▼'
  return '—'
})

const formatted = computed(() => {
  if (props.deviation === null || props.deviation === undefined) return ''
  const sign = props.deviation > 0 ? '+' : ''
  return `${sign}${(props.deviation * 100).toFixed(1)}%`
})

const colorClass = computed(() => {
  if (props.deviation === null || props.deviation === undefined) return 'text-grey-400'
  if (props.deviation > 0.005) return 'text-green-600'
  if (props.deviation < -0.005) return 'text-red-600'
  return 'text-grey-400'
})
</script>
