<template>
  <div>
    <!-- Loading skeleton -->
    <div v-if="loading" class="flex flex-col gap-4 animate-fade-in-up">
      <!-- Skeleton filter bar -->
      <div class="bg-white rounded-lg shadow-card px-5 py-3">
        <div class="flex gap-3">
          <div class="skeleton-shimmer h-8 w-32 rounded-lg"></div>
          <div class="skeleton-shimmer h-8 w-32 rounded-lg"></div>
          <div class="skeleton-shimmer h-8 w-32 rounded-lg"></div>
          <div class="skeleton-shimmer h-8 w-24 rounded-lg"></div>
        </div>
      </div>
      <!-- Skeleton KPI strip -->
      <div class="flex gap-3">
        <div v-for="i in 5" :key="i" class="flex-1 bg-white rounded-lg shadow-card px-4 py-3">
          <div class="skeleton-shimmer h-3 w-16 rounded mb-2"></div>
          <div class="skeleton-shimmer h-7 w-20 rounded"></div>
        </div>
      </div>
      <!-- Skeleton main content -->
      <div class="flex gap-4">
        <div class="w-5/12 min-w-0 shrink-0 bg-white rounded-lg shadow-card p-4">
          <div class="skeleton-shimmer h-[360px] rounded"></div>
        </div>
        <div class="flex-1 bg-white rounded-lg shadow-card p-4">
          <div class="skeleton-shimmer h-[260px] rounded mb-4"></div>
          <div class="skeleton-shimmer h-[260px] rounded"></div>
        </div>
      </div>
    </div>

    <!-- Error banner -->
    <div v-if="error" class="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 flex items-center justify-between animate-fade-in-down">
      <div class="flex items-center gap-2">
        <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
        <span class="text-body text-red-800">{{ error }}</span>
      </div>
      <button class="text-caption font-bold text-red-600 hover:text-red-800 px-3 py-1 rounded-lg hover:bg-red-100 transition-colors" @click="$emit('retry')">Retry</button>
    </div>

    <div v-if="!loading">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: null },
})

defineEmits(['retry'])
</script>
