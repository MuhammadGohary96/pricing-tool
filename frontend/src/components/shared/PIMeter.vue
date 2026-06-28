<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 p-6 select-none">
    <div class="flex items-baseline justify-between gap-4 mb-1">
      <span class="text-micro font-semibold uppercase tracking-wide text-grey-500">Price Index</span>
      <span class="text-micro font-semibold uppercase tracking-wide text-grey-400 bg-grey-100 px-2 py-0.5 rounded-full">Drag to explore</span>
    </div>

    <div class="flex items-baseline gap-3 mt-1 mb-4">
      <span class="font-mono text-5xl font-semibold tracking-tightish leading-none">{{ pi.toFixed(2) }}</span>
      <span class="text-2xl font-bold" :style="{ color: verdict.color }">{{ verdict.glyph }}</span>
    </div>
    <div class="text-heading font-bold tracking-tightish" :style="{ color: verdict.color }">{{ verdict.title }}</div>
    <div class="text-body text-grey-600 mt-0.5 min-h-[2.5em]">{{ verdict.sub }}</div>

    <!-- diverging track -->
    <div class="mt-5">
      <div
        ref="track"
        class="pi-track relative h-4 rounded-full cursor-pointer"
        role="slider"
        tabindex="0"
        aria-label="Price Index, Breadfast price divided by competitor price"
        :aria-valuemin="MIN" :aria-valuemax="MAX" :aria-valuenow="pi.toFixed(2)"
        :aria-valuetext="`${pi.toFixed(2)}, ${verdict.title}`"
        @mousedown="onDown" @touchstart.passive="onDown" @keydown="onKey"
      >
        <span class="band" :style="{ left: pctFor(PI_CHEAP) + '%' }" aria-hidden="true" />
        <span class="band" :style="{ left: pctFor(PI_EXPENSIVE) + '%' }" aria-hidden="true" />
        <span class="thumb" :style="{ left: pct + '%', '--thumb': verdict.color }" />
      </div>
      <div class="flex justify-between mt-3 text-micro font-medium text-grey-400" aria-hidden="true">
        <span>0.70 · cheaper</span>
        <span class="text-green-600 font-semibold">1.00 · parity</span>
        <span>1.30 · pricier</span>
      </div>
    </div>

    <div class="flex gap-5 mt-5 pt-4 border-t border-grey-100">
      <div class="text-micro text-grey-500"><b class="block text-grey-900 font-semibold" style="color:#2563EB">Below 0.95</b>Margin left on the table</div>
      <div class="text-micro text-grey-500"><b class="block font-semibold" style="color:#16A34A">0.95–1.05</b>Healthy, tracking the market</div>
      <div class="text-micro text-grey-500"><b class="block font-semibold" style="color:#DC2626">Above 1.05</b>Demand risk</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { PI_CHEAP, PI_EXPENSIVE } from '../../utils/piColor'
import { prefersReducedMotion } from '../../utils/motion'

const MIN = 0.70, MAX = 1.30, RANGE = MAX - MIN

const props = defineProps({
  modelValue: { type: Number, default: 1.06 },
})

const pi = ref(prefersReducedMotion() ? props.modelValue : MIN + 0.14)
const pct = computed(() => ((pi.value - MIN) / RANGE) * 100)
function pctFor(v) { return ((v - MIN) / RANGE) * 100 }

// Verdict copy is driven by the PI value (always correct); colors follow the
// PI "both tails bad" scale: cheaper = cool/blue, parity = green, pricier = warm/red.
const verdict = computed(() => {
  const v = pi.value
  if (v < 0.80) return { glyph: '▼▼', color: '#1D4ED8', title: 'Breadfast is much cheaper', sub: 'Well below the market. Real margin is being left on the table.' }
  if (v < 0.90) return { glyph: '▼', color: '#2563EB', title: 'Breadfast is cheaper', sub: 'Below the competitor basket. Room to recover margin.' }
  if (v < PI_CHEAP) return { glyph: '▼', color: '#3B82F6', title: 'Slightly cheaper', sub: 'A touch under the market. Close to the healthy band.' }
  if (v <= PI_EXPENSIVE) return { glyph: '◆', color: '#16A34A', title: 'At parity', sub: 'Breadfast tracks the market within ±5%. The healthy target.' }
  if (v <= 1.10) return { glyph: '▲', color: '#F59E0B', title: 'Slightly pricey', sub: 'A touch over the market. Worth a look before it widens.' }
  if (v <= 1.20) return { glyph: '▲', color: '#EA580C', title: 'Breadfast is more expensive', sub: 'Above the competitor basket. Demand is at risk.' }
  return { glyph: '▲▲', color: '#DC2626', title: 'Breadfast is much more expensive', sub: 'Well above the market. Clear demand risk; correct the price.' }
})

const track = ref(null)
let dragging = false

function setFromClientX(x) {
  const r = track.value.getBoundingClientRect()
  const p = Math.min(1, Math.max(0, (x - r.left) / r.width))
  pi.value = MIN + p * RANGE
}
function onDown(e) {
  dragging = true
  setFromClientX((e.touches ? e.touches[0] : e).clientX)
  e.preventDefault?.()
}
function onMove(e) { if (dragging) setFromClientX((e.touches ? e.touches[0] : e).clientX) }
function onUp() { dragging = false }
function onKey(e) {
  const step = e.shiftKey ? 0.05 : 0.01
  if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { pi.value = Math.min(MAX, pi.value + step); e.preventDefault() }
  else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { pi.value = Math.max(MIN, pi.value - step); e.preventDefault() }
  else if (e.key === 'Home') { pi.value = MIN; e.preventDefault() }
  else if (e.key === 'End') { pi.value = MAX; e.preventDefault() }
}

let raf = null
onMounted(() => {
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
  window.addEventListener('touchmove', onMove, { passive: true })
  window.addEventListener('touchend', onUp)
  // One-time settle animation to the sample value (skipped under reduced motion)
  if (!prefersReducedMotion()) {
    const from = pi.value, to = props.modelValue, dur = 1000
    let start = null
    const step = (ts) => {
      if (start == null) start = ts
      const k = Math.min(1, (ts - start) / dur)
      const e = 1 - Math.pow(1 - k, 3)
      pi.value = from + (to - from) * e
      if (k < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseup', onUp)
  window.removeEventListener('touchmove', onMove)
  window.removeEventListener('touchend', onUp)
  if (raf) cancelAnimationFrame(raf)
})
</script>

<style scoped>
.pi-track {
  background: linear-gradient(90deg,
    #1E40AF 0%, #2563EB 16.7%, #60A5FA 33.3%, #4ADE80 41.7%,
    #16A34A 50%, #4ADE80 58.3%, #FBBF24 66.7%, #F97316 83.3%, #DC2626 100%);
  box-shadow: inset 0 1px 2px rgba(40,16,48,0.25);
}
.band {
  position: absolute; top: -5px; bottom: -5px; width: 2px;
  background: rgba(255,255,255,0.85); border-radius: 2px;
  box-shadow: 0 0 0 1px rgba(40,16,48,0.12);
}
.thumb {
  position: absolute; top: 50%; width: 26px; height: 26px; border-radius: 9999px;
  background: #fff; transform: translate(-50%, -50%);
  box-shadow: 0 2px 8px rgba(40,16,48,0.3), inset 0 0 0 1px rgba(40,16,48,0.08);
  display: grid; place-items: center; cursor: grab;
}
.thumb:active { cursor: grabbing; }
.thumb::after { content: ""; width: 8px; height: 8px; border-radius: 9999px; background: var(--thumb, #16A34A); }
</style>
