<template>
  <Teleport to="body">
    <TransitionGroup
      name="toast"
      tag="div"
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      class="fixed bottom-6 right-6 z-[9999] flex flex-col-reverse gap-2 pointer-events-none"
    >
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-lg shadow-lg text-white max-w-[300px]"
        :style="{ background: typeColors[toast.type] }"
      >
        <span class="flex-shrink-0 mt-0.5 opacity-90" v-html="typeIcons[toast.type]"></span>
        <div class="flex-1 min-w-0">
          <div class="font-semibold text-[12px] leading-snug">{{ toast.title }}</div>
          <div v-if="toast.message" class="text-[11px] mt-0.5 opacity-80">{{ toast.message }}</div>
          <button
            v-if="toast.action"
            class="mt-1.5 text-[11px] font-bold underline opacity-90 hover:opacity-100 transition-opacity"
            @click="toast.action.fn(); remove(toast.id)"
          >{{ toast.action.label }}</button>
        </div>
        <button
          @click="remove(toast.id)"
          class="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity text-[16px] leading-none"
          aria-label="Dismiss"
        >&times;</button>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'

const toasts = ref([])
let nextId = 0

const typeColors = {
  success: '#059669',
  error:   '#DC2626',
  warning: '#D97706',
  info:    '#2563EB',
}

const typeIcons = {
  success: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
  error:   '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
  warning: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>',
  info:    '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
}

function add(type, title, message = '', duration = 3000, action = null) {
  const id = nextId++
  toasts.value.push({ id, type, title, message, action })
  if (duration > 0) {
    setTimeout(() => remove(id), duration)
  }
}

function remove(id) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

defineExpose({ add, remove })
</script>

<style scoped>
.toast-enter-active {
  animation: slideInUp 0.3s ease-out;
}
.toast-leave-active {
  transition: all 0.2s ease-in;
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.95);
}

@keyframes slideInUp {
  0%   { opacity: 0; transform: translateY(24px); }
  100% { opacity: 1; transform: translateY(0); }
}
</style>
