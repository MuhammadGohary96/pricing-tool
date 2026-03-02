<template>
  <span
    class="inline-flex items-center gap-1 px-2 py-0.5 text-micro font-bold rounded-full whitespace-nowrap"
    :style="config.style"
  >
    <span v-if="config.stars" style="color:#F59E0B;letter-spacing:1px">{{ config.stars }}</span>
    {{ config.label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  tier: { type: String, required: true },
})

const TIER_MAP = {
  'Top+':     { stars: '★★★★★', label: 'Top+',     style: 'background:linear-gradient(135deg,#FDE68A,#F59E0B);color:#92400E' },
  'Top':      { stars: '★★★★',  label: 'Top',      style: 'background:#FEF3C7;color:#B45309' },
  'High':     { stars: '★★★',   label: 'High',     style: 'background:#E0E7FF;color:#4338CA' },
  'Mid':      { stars: '★★',    label: 'Mid',      style: 'background:#F3F4F6;color:#374151' },
  'Medium':   { stars: '★★',    label: 'Mid',      style: 'background:#F3F4F6;color:#374151' },
  'Low':      { stars: '★',     label: 'Low',      style: 'background:#F9FAFB;color:#6B7280;border:1px solid #E5E7EB' },
  'Very Low': { stars: '',      label: 'Very Low', style: 'background:#FEE2E2;color:#991B1B' },
}

const config = computed(() => TIER_MAP[props.tier] ?? TIER_MAP['Very Low'])
</script>
