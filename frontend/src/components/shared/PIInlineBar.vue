<template>
  <div class="flex items-center gap-2">
    <span class="text-body font-bold w-10 text-right" :class="textClass">{{ formatted }}</span>
    <div class="flex-1 relative overflow-hidden rounded-full bg-grey-100" style="height:6px;min-width:60px">
      <!-- Filled bar with gradient -->
      <div
        v-if="props.value != null"
        class="absolute top-0 left-0 h-full rounded-full"
        :style="{ width: fillPct + '%', background: barGradient }"
      />
      <!-- Parity line at 1.0 -->
      <div class="absolute top-0 h-full w-px bg-grey-400" :style="{ left: parityPos }" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { piTextClass, piBarGradient } from '../../utils/piColor'

const props = defineProps({
  value: { type: Number, default: null },
  min: { type: Number, default: 0.7 },
  max: { type: Number, default: 1.3 },
})

const formatted = computed(() => {
  if (props.value == null) return '--'
  return props.value.toFixed(2)
})

const fillPct = computed(() => {
  if (props.value == null) return 0
  return Math.min(100, Math.max(0, ((props.value - props.min) / (props.max - props.min)) * 100))
})

const parityPos = computed(() => {
  const pct = ((1 - props.min) / (props.max - props.min)) * 100
  return `${pct}%`
})

const barGradient = computed(() => piBarGradient(props.value))
const textClass = computed(() => piTextClass(props.value))
</script>
