<template>
  <span class="tabular-nums">{{ display }}</span>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
  duration: { type: Number, default: 650 },
  decimals: { type: Number, default: 0 },
})

const display = ref('0')
let raf = null
let startTs = null
let from = 0

const prefersReduced =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

function fmt(n) {
  return Number(n).toLocaleString(undefined, {
    minimumFractionDigits: props.decimals,
    maximumFractionDigits: props.decimals,
  })
}

// ease-out-quint: fast start, gentle settle — matches --ease-premium feel
function ease(t) {
  return 1 - Math.pow(1 - t, 5)
}

function animateTo(target) {
  if (raf) cancelAnimationFrame(raf)
  if (prefersReduced || props.duration <= 0) {
    display.value = fmt(target)
    return
  }
  from = Number(String(display.value).replace(/,/g, '')) || 0
  startTs = null
  const step = (ts) => {
    if (startTs === null) startTs = ts
    const p = Math.min(1, (ts - startTs) / props.duration)
    const current = from + (target - from) * ease(p)
    display.value = fmt(current)
    if (p < 1) raf = requestAnimationFrame(step)
  }
  raf = requestAnimationFrame(step)
}

onMounted(() => animateTo(props.value))
watch(() => props.value, (v) => animateTo(v))
onUnmounted(() => { if (raf) cancelAnimationFrame(raf) })
</script>
