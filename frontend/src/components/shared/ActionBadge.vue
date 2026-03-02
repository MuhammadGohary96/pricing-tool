<template>
  <span
    class="inline-flex items-center gap-1 px-2 py-0.5 text-micro font-bold rounded-full whitespace-nowrap"
    :style="config.style"
  >
    <component :is="config.icon" class="w-3 h-3" />
    {{ config.label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { Link, BrainCircuit, RefreshCw, CircleCheck } from 'lucide-vue-next'

const props = defineProps({
  action: { type: String, required: true },
})

const ACTION_MAP = {
  'Needs Mapping':      { icon: Link,         label: 'Needs Mapping',      style: 'background:#FEE2E2;color:#DC2626' },
  'Review Match':       { icon: BrainCircuit,  label: 'Review Match',       style: 'background:#FEF3C7;color:#D97706' },
  'Needs Price Update': { icon: RefreshCw,     label: 'Needs Price Update', style: 'background:#DBEAFE;color:#2563EB' },
  'Complete':           { icon: CircleCheck,   label: 'Complete',           style: 'background:#D1FAE5;color:#059669' },
}

const config = computed(() => ACTION_MAP[props.action] ?? ACTION_MAP['Needs Mapping'])
</script>
