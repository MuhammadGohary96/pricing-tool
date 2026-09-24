<template>
  <span
    v-if="parts"
    class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full ring-1 ring-inset text-micro leading-none font-mono whitespace-nowrap shrink-0"
    :class="flagged ? 'bg-amber-50 ring-amber-300 text-amber-800' : 'bg-white ring-grey-300 text-grey-900'"
    :title="title || undefined"
  >
    <component
      :is="unit === 'pcs' ? Package : Weight"
      class="w-3 h-3 shrink-0"
      :class="flagged ? 'text-amber-600' : 'text-grey-500'"
      aria-hidden="true"
    />
    <span><span class="font-semibold">{{ parts.num }}</span>&nbsp;<span :class="flagged ? 'text-amber-700' : 'text-grey-500'">{{ parts.unit }}</span></span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { Package, Weight } from 'lucide-vue-next'
import { sizeParts } from '../../utils/size'

// Pack-size tag for one side of a Fruits & Vegetables comparison (the model only
// sends sizes in that scope, so elsewhere this renders nothing). Reads like a
// shelf label: ringed white pill, number in ink, unit in grey. It stands out by
// structure rather than by a solid fill, so repeated down a dense table it does
// not outshout the PI colours. `flagged` turns it amber on a pair whose sizes
// failed the plausibility check, putting the warning on the cause itself.
const props = defineProps({
  value: { type: Number, default: null },
  unit: { type: String, default: null },
  title: { type: String, default: '' },
  flagged: { type: Boolean, default: false },
})

const parts = computed(() => sizeParts(props.value, props.unit))
</script>
