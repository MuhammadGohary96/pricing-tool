<template>
  <img
    v-if="!errored"
    :src="`/logos/${slug}.png`"
    :alt="name"
    :class="sizeClass"
    class="rounded-full object-cover inline-block"
    @error="errored = true"
  />
  <span
    v-else
    :class="sizeClass"
    class="rounded-full inline-flex items-center justify-center text-white font-bold shrink-0"
    :style="{ backgroundColor: bgColor, fontSize: size === 'md' ? '0.7rem' : '0.6rem' }"
  >
    {{ name.charAt(0).toUpperCase() }}
  </span>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: String, default: 'sm' },
})

const errored = ref(false)

const slug = computed(() =>
  props.name.toLowerCase().replace(/\s+/g, '-')
)

const sizeClass = computed(() =>
  props.size === 'md' ? 'w-6 h-6' : 'w-5 h-5'
)

const colorMap = {
  amazon: '#FF9900',
  'amazon now': '#FF9900',
  carrefour: '#004E98',
  'noon minutes': '#F5D312',
  rabbit: '#7C3AED',
  seoudi: '#E11D48',
  'seoudi app': '#E11D48',
  talabat: '#FF6B00',
  metro: '#003D7A',
  'elfar app': '#2563EB',
  oscar: '#10B981',
}

const bgColor = computed(() =>
  colorMap[props.name.toLowerCase()] || '#6B7280'
)
</script>
