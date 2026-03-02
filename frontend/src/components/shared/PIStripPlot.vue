<template>
  <div class="relative" style="height: 28px; min-width: 160px">
    <svg
      width="100%"
      height="28"
      class="block"
      @mouseleave="hoveredIdx = null"
    >
      <!-- Background zones: left=red (low PI, BF expensive), middle=yellow, right=green (high PI, BF cheaper) -->
      <rect :x="0" y="0" :width="zoneLowPct + '%'" height="28" fill="#fee2e2" rx="2" />
      <rect :x="zoneLowPct + '%'" y="0" :width="(zoneHighPct - zoneLowPct) + '%'" height="28" fill="#fef9c3" />
      <rect :x="zoneHighPct + '%'" y="0" :width="(100 - zoneHighPct) + '%'" height="28" fill="#dcfce7" rx="2" />

      <!-- Parity line at 1.0 -->
      <line :x1="parityPct + '%'" y1="2" :x2="parityPct + '%'" y2="26" stroke="#9ca3af" stroke-width="1" stroke-dasharray="2,2" />

      <!-- Product dots -->
      <circle
        v-for="(dot, i) in dots"
        :key="i"
        :cx="dot.x + '%'"
        cy="14"
        :r="dot.r"
        :fill="dot.color"
        :opacity="hoveredIdx === i ? 1 : 0.7"
        :stroke="hoveredIdx === i ? '#1f2937' : 'white'"
        :stroke-width="hoveredIdx === i ? 1.5 : 0.5"
        class="cursor-pointer transition-opacity"
        @mouseenter="hoveredIdx = i"
        @click.stop="$emit('select-product', { productName: dot.name, subcategory })"
      />

      <!-- Blended PI diamond marker -->
      <polygon
        v-if="blendedPi != null"
        :points="diamondPoints"
        fill="#4d003a"
        stroke="white"
        stroke-width="1"
      />
    </svg>

    <!-- Tooltip -->
    <div
      v-if="hoveredIdx !== null && dots[hoveredIdx]"
      class="absolute z-50 px-2 py-1 text-[10px] bg-grey-900 text-white rounded shadow-lg whitespace-nowrap pointer-events-none"
      :style="tooltipStyle"
    >
      <div class="font-medium truncate" style="max-width: 180px">{{ dots[hoveredIdx].name }}</div>
      <div>PI: {{ dots[hoveredIdx].pi.toFixed(3) }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { piDotColor, PI_CHEAP, PI_EXPENSIVE } from '../../utils/piColor'

const props = defineProps({
  points: { type: Array, default: () => [] },
  blendedPi: { type: Number, default: null },
  subcategory: { type: String, default: '' },
  min: { type: Number, default: 0.5 },
  max: { type: Number, default: 1.5 },
})

defineEmits(['select-product'])

const hoveredIdx = ref(null)

function toPct(val) {
  return Math.min(100, Math.max(0, ((val - props.min) / (props.max - props.min)) * 100))
}

const parityPct = computed(() => toPct(1.0))
const zoneLowPct = computed(() => toPct(PI_CHEAP))
const zoneHighPct = computed(() => toPct(PI_EXPENSIVE))

const dots = computed(() => {
  if (!props.points?.length) return []
  const weights = props.points.map(p => p.weight)
  const maxW = Math.max(...weights, 1)
  return props.points.map(p => ({
    x: toPct(p.sale_PI),
    r: 2 + (p.weight / maxW) * 3,
    color: piDotColor(p.sale_PI),
    name: p.product_name,
    pi: p.sale_PI,
  }))
})

const diamondPoints = computed(() => {
  if (props.blendedPi == null) return ''
  const cx = toPct(props.blendedPi)
  // Diamond shape centered at (cx%, 14) with size 5
  // Convert percentage to approximate pixels (use 1.6 as px-per-pct for a ~160px-wide container)
  // But since SVG uses % for x, we use a relative approach
  const s = 0.8 // half-size in % units
  return `${cx},${14 - 5} ${cx + s},14 ${cx},${14 + 5} ${cx - s},14`
})

const tooltipStyle = computed(() => {
  if (hoveredIdx.value === null || !dots.value[hoveredIdx.value]) return {}
  const dot = dots.value[hoveredIdx.value]
  const left = dot.x > 70 ? 'auto' : `${dot.x}%`
  const right = dot.x > 70 ? `${100 - dot.x}%` : 'auto'
  return { left, right, bottom: '100%', marginBottom: '4px' }
})
</script>
