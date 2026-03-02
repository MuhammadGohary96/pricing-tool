<template>
  <span class="relative inline-flex items-center" @mouseenter="show = true" @mouseleave="show = false">
    <button
      type="button"
      class="w-4 h-4 rounded-full bg-grey-100 text-grey-500 text-micro font-bold flex items-center justify-center hover:bg-brand-50 hover:text-brand-primary transition-colors focus:outline-none focus:ring-1 focus:ring-brand-primary"
      :aria-label="`Help: ${text}`"
    >?</button>
    <Transition name="tooltip">
      <div
        v-if="show"
        class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-56 bg-grey-900 text-white text-micro rounded-lg px-3 py-2 shadow-lg leading-relaxed pointer-events-none"
        role="tooltip"
      >
        {{ text }}
        <div class="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-grey-900"></div>
      </div>
    </Transition>
  </span>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  text: { type: String, required: true },
})

const show = ref(false)
</script>

<style scoped>
.tooltip-enter-active, .tooltip-leave-active { transition: all 0.15s ease; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: translateX(-50%) translateY(4px); }
</style>
