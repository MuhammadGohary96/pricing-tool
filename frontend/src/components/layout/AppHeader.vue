<template>
  <header class="bg-brand-darkest h-14 flex items-center px-6 gap-8 sticky top-0 z-50">
    <!-- Logo -->
    <div class="flex items-center gap-2.5 text-white font-bold text-base tracking-tight shrink-0">
      <img src="/breadfast-logo.png" alt="Breadfast" class="h-7 shrink-0" />
      Pricing Tool
    </div>

    <!-- Tabs -->
    <nav class="flex items-center gap-1 ml-6">
      <router-link
        v-for="tab in tabs"
        :key="tab.to"
        :to="tab.to"
        class="px-4 py-2 rounded-lg text-body font-medium cursor-pointer transition-all duration-150 no-underline"
        :class="[
          $route.path === tab.to
            ? 'text-white bg-brand-primary'
            : 'text-white/65 hover:text-white hover:bg-white/10'
        ]"
      >
        {{ tab.label }}
      </router-link>
    </nav>

    <!-- Right Side -->
    <div class="ml-auto flex items-center gap-4">
      <!-- Sync Badge + Resync -->
      <div class="flex items-center gap-2 shrink-0">
        <div class="text-micro text-white/50 flex items-center gap-1.5">
          <span class="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0"></span>
          {{ syncLabel }}
        </div>
        <button
          @click="$emit('resync')"
          class="text-white/40 hover:text-white transition-colors p-1 rounded hover:bg-white/10"
          title="Reload data from source"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
        </button>
      </div>

      <!-- Avatar -->
      <div v-if="auth.user" class="flex items-center gap-2">
        <img
          v-if="auth.user.picture"
          :src="auth.user.picture"
          :alt="auth.user.name"
          class="w-8 h-8 rounded-full border border-white/20"
          referrerpolicy="no-referrer"
        />
        <div v-else class="w-8 h-8 rounded-full bg-brand-primary flex items-center justify-center text-white text-caption font-semibold">
          {{ initials }}
        </div>
      </div>

      <!-- Logout -->
      <button
        @click="auth.logout()"
        class="text-white/40 hover:text-white transition-colors p-1 rounded hover:bg-white/10"
        title="Sign out"
      >
        <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1V4a1 1 0 00-1-1H3zm7.707 3.293a1 1 0 010 1.414L9.414 9H17a1 1 0 110 2H9.414l1.293 1.293a1 1 0 01-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0z" clip-rule="evenodd"/>
        </svg>
      </button>
    </div>
  </header>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useCommercialStore } from '../../stores/commercial'
import { useMasterDataStore } from '../../stores/masterData'
import { useExecutiveStore } from '../../stores/executive'

defineEmits(['resync'])

const auth = useAuthStore()
const commercial = useCommercialStore()
const masterData = useMasterDataStore()
const executive = useExecutiveStore()

const now = ref(new Date())
let timer = null

onMounted(() => {
  timer = setInterval(() => { now.value = new Date() }, 15000)
})
onUnmounted(() => {
  clearInterval(timer)
})

const lastFetchedAt = computed(() => {
  const timestamps = [
    commercial.lastFetchedAt,
    masterData.lastFetchedAt,
    executive.lastFetchedAt,
  ].filter(Boolean)
  if (!timestamps.length) return null
  return new Date(Math.max(...timestamps.map(t => t.getTime())))
})

const syncLabel = computed(() => {
  if (!lastFetchedAt.value) return 'Data synced'
  const diffMs = now.value - lastFetchedAt.value
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Synced just now'
  if (diffMin === 1) return 'Synced 1 min ago'
  return `Synced ${diffMin} mins ago`
})

const initials = computed(() => {
  if (!auth.user?.name) return '?'
  return auth.user.name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
})

const tabs = [
  { label: 'Commercial', to: '/commercial' },
  { label: 'Master Data', to: '/master-data' },
  { label: 'Executive', to: '/executive' },
]
</script>
