<template>
  <div class="bg-white rounded-xl shadow-card-hover px-6 py-6 text-center flex flex-col items-center card-interactive">
    <!-- PI value display -->
    <div class="mb-3 flex flex-col items-center justify-center">
      <div class="text-4xl font-black leading-none" :class="valueTextColor">
        {{ value != null ? value.toFixed(4) : '--' }}
      </div>
      <div class="text-caption text-grey-400 mt-1 flex items-center justify-center gap-1">
        Blended PI
        <HelpTooltip text="Weighted price index: Competitor price ÷ BF price for eligible products. &gt;1 = BF cheaper, &lt;1 = BF more expensive." />
      </div>
    </div>
    <!-- Interpretation -->
    <div v-if="value != null" class="text-heading mt-1" :class="valueTextColor">
      {{ interpretation }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import HelpTooltip from '../shared/HelpTooltip.vue'
import { piTextClass } from '../../utils/piColor'

const props = defineProps({
  value: { type: Number, default: null },
})

const valueTextColor = computed(() => piTextClass(props.value))

const interpretation = computed(() => {
  if (props.value == null) return ''
  const pct = Math.abs((props.value - 1) * 100).toFixed(1)
  if (props.value >= 1.001) return `Breadfast is ${pct}% cheaper overall`
  if (props.value <= 0.999) return `Breadfast is ${pct}% more expensive`
  return 'At parity with competitor'
})
</script>

