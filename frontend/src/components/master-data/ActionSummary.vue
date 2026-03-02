<template>
  <div class="grid grid-cols-4 gap-3" v-if="counts">
    <div
      v-for="card in cards"
      :key="card.key"
      class="bg-white rounded-lg shadow-card px-4 py-4 flex items-center gap-4 cursor-pointer transition-all duration-150 border-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
      :class="selected === card.key ? 'border-brand-primary bg-brand-50' : 'border-transparent hover:border-brand-light'"
      tabindex="0"
      :aria-pressed="selected === card.key"
      :aria-label="`Filter by ${card.label}: ${card.value} items`"
      @click="toggleSelect(card.key)"
      @keyup.enter="toggleSelect(card.key)"
    >
      <!-- Icon Circle -->
      <div
        class="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
        :class="card.iconBg"
      >
        <component :is="card.icon" class="w-5 h-5" />
      </div>
      <!-- Data -->
      <div class="min-w-0">
        <div class="text-2xl font-bold text-grey-900 leading-tight tracking-tight">{{ card.value }}</div>
        <div class="text-caption text-grey-500 mt-0.5">{{ card.label }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { AlertTriangle, Link, BrainCircuit, RefreshCw } from 'lucide-vue-next'

const props = defineProps({
  counts: { type: Object, default: null },
})

const emit = defineEmits(['select'])

const selected = ref(null)

function toggleSelect(key) {
  if (selected.value === key) {
    selected.value = null
    emit('select', null)
  } else {
    selected.value = key
    emit('select', key)
  }
}

const cards = computed(() => {
  if (!props.counts) return []
  return [
    {
      key: 'total',
      icon: AlertTriangle,
      iconBg: 'bg-red-50 text-red-500',
      value: props.counts.total_needs_action?.toLocaleString() ?? '--',
      label: 'Total Need Action',
    },
    {
      key: 'Needs Mapping',
      icon: Link,
      iconBg: 'bg-red-100 text-red-600',
      value: props.counts.needs_mapping?.toLocaleString() ?? '--',
      label: 'Needs Mapping',
    },
    {
      key: 'Review Match',
      icon: BrainCircuit,
      iconBg: 'bg-amber-50 text-amber-500',
      value: props.counts.review_match?.toLocaleString() ?? '--',
      label: 'Review Match',
    },
    {
      key: 'Needs Price Update',
      icon: RefreshCw,
      iconBg: 'bg-blue-50 text-blue-500',
      value: props.counts.needs_price_update?.toLocaleString() ?? '--',
      label: 'Needs Price Update',
    },
  ]
})
</script>
