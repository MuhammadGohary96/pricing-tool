<template>
  <div class="fixed inset-0 z-50 bg-grey-100 flex items-center justify-center">
    <div class="bg-white rounded-xl shadow-card-hover px-10 py-8 flex flex-col items-center gap-5 w-full max-w-md">
      <!-- Logo -->
      <div class="flex items-center gap-3">
        <img src="/breadfast-icon.png" alt="Breadfast" class="w-10 h-10 rounded-lg shrink-0" />
        <div>
          <div class="text-subheading font-bold text-grey-900">Breadfast Pricing Tool</div>
          <div class="text-caption text-grey-500">Loading data...</div>
        </div>
      </div>

      <!-- Stage text -->
      <div class="text-body text-grey-700 text-center">{{ stage }}</div>

      <!-- Progress bar -->
      <div class="w-full">
        <!-- Determinate: catalog fetch phase -->
        <div v-if="total > 0" class="w-full">
          <div class="w-full h-2.5 bg-grey-100 rounded-full overflow-hidden">
            <div
              class="h-full bg-gradient-to-r from-brand-primary to-brand-darkest rounded-full transition-all duration-300 ease-out"
              :style="{ width: percentage + '%' }"
            />
          </div>
          <div class="flex items-center justify-between mt-2">
            <span class="text-caption text-grey-500">{{ progress.toLocaleString() }} / {{ total.toLocaleString() }} products</span>
            <span class="text-caption font-bold text-brand-primary">{{ percentage }}%</span>
          </div>
        </div>

        <!-- Indeterminate: BQ load phase -->
        <div v-else class="w-full">
          <div class="w-full h-2.5 bg-grey-100 rounded-full overflow-hidden">
            <div class="h-full w-1/3 bg-gradient-to-r from-brand-primary to-brand-darkest rounded-full animate-indeterminate" />
          </div>
        </div>
      </div>

      <!-- Error state -->
      <div v-if="isError" class="text-caption text-red-600 bg-red-50 rounded-lg px-4 py-2 w-full text-center">
        {{ stage }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stage: { type: String, default: 'Initializing...' },
  progress: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
})

const percentage = computed(() => {
  if (props.total <= 0) return 0
  return Math.min(100, Math.round((props.progress / props.total) * 100))
})

const isError = computed(() => props.stage?.startsWith('Error:'))
</script>

<style scoped>
@keyframes indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}
.animate-indeterminate {
  animation: indeterminate 1.5s ease-in-out infinite;
}
</style>
