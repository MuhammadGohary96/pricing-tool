<template>
  <div class="flex flex-col items-center justify-center py-10 text-center px-4">
    <component :is="icon" v-if="icon" class="w-8 h-8 mb-2.5 text-grey-300" />
    <p v-if="title" class="text-subheading font-semibold text-grey-700 mb-1">{{ title }}</p>
    <p class="text-body text-grey-500">{{ message }}</p>
    <button
      v-if="actionLabel"
      class="mt-4 px-4 py-1.5 rounded-lg text-caption font-semibold bg-brand-50 text-brand-primary border border-brand-light hover:bg-brand-lightest transition-colors"
      @click="$emit('action')"
    >{{ actionLabel }}</button>
  </div>
</template>

<script setup>
import { CircleOff } from 'lucide-vue-next'

defineProps({
  icon: { type: [String, Object], default: () => CircleOff },
  title: { type: String, default: '' },
  message: { type: String, default: 'No data matches your filters' },
  actionLabel: { type: String, default: '' },
})

defineEmits(['action'])
</script>
