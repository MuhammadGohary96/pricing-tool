<template>
  <div v-if="subcategory" class="flex items-center gap-1.5 text-body px-1 py-0.5 animate-fade-in-up">
    <button class="text-grey-500 hover:text-brand-primary transition-colors" @click="$emit('clear')">
      All Subcategories
    </button>
    <ChevronRight class="w-3.5 h-3.5 text-grey-300 shrink-0" />
    <span class="text-grey-900 font-medium">{{ subcategory }}</span>
    <button class="ml-0.5 text-grey-400 hover:text-grey-700 leading-none text-lg" @click="$emit('clear')">&times;</button>
  </div>
</template>

<script setup>
import { ChevronRight } from 'lucide-vue-next'
defineProps({ subcategory: { type: String, default: null } })
defineEmits(['clear'])
</script>
