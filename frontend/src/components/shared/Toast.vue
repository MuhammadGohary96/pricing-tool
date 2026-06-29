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
        class="pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl shadow-toast text-white max-w-[300px]"
        :style="{ background: typeColors[toast.type] }"
      >
        <component :is="typeIcons[toast.type]" class="w-4 h-4 flex-shrink-0 mt-0.5 opacity-90" />
        <div class="flex-1 min-w-0">
          <div class="font-semibold text-caption leading-snug">{{ toast.title }}</div>
          <div v-if="toast.message" class="text-micro mt-0.5 opacity-80">{{ toast.message }}</div>
          <button
            v-if="toast.action"
            class="mt-1.5 text-micro font-bold underline opacity-90 hover:opacity-100 transition-opacity"
            @click="toast.action.fn(); remove(toast.id)"
          >{{ toast.action.label }}</button>
        </div>
        <button
          @click="remove(toast.id)"
          class="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
          aria-label="Dismiss"
        ><X class="w-4 h-4" /></button>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-vue-next'

const toasts = ref([])
let nextId = 0

// Semantic status hues (success/error/warning/info) — not the brand accent.
const typeColors = {
  success: '#059669',
  error:   '#DC2626',
  warning: '#D97706',
  info:    '#2563EB',
}

const typeIcons = {
  success: CheckCircle2,
  error:   XCircle,
  warning: AlertTriangle,
  info:    Info,
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
