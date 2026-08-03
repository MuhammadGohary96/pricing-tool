<template>
  <header class="bg-brand-darkest h-14 flex items-center px-6 gap-8 sticky top-0 z-50">
    <!-- Logo -->
    <div class="flex items-center gap-2.5 text-white font-bold text-base tracking-tight shrink-0">
      <img src="/breadfast-logo.png" alt="Breadfast" class="h-7 shrink-0" />
      Pricing Intelligence Tool
    </div>

    <!-- Tabs -->
    <nav class="flex items-center gap-1 ml-6">
      <!-- Workspaces: the surfaces you act in -->
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

      <!-- Divider: the guide is a different kind of destination than the workspaces -->
      <span class="mx-2 h-5 w-px bg-white/15" aria-hidden="true"></span>

      <!-- How it works — the reference behind every number, set apart with an icon + brand ring -->
      <router-link
        to="/how-it-works"
        class="inline-flex items-center gap-1.5 pl-3 pr-3.5 py-2 rounded-lg text-body font-medium cursor-pointer transition-all duration-150 no-underline ring-1"
        :class="[
          $route.path === '/how-it-works'
            ? 'text-white bg-brand-primary ring-brand-primary'
            : 'text-white/75 ring-brand-light/30 hover:text-white hover:bg-white/10 hover:ring-brand-light/60'
        ]"
      >
        <BookOpen class="w-4 h-4 shrink-0" :class="$route.path === '/how-it-works' ? 'text-white' : 'text-brand-light'" />
        How it works
      </router-link>
    </nav>

    <!-- Right Side -->
    <div class="ml-auto flex items-center gap-4">
      <!-- Sync Badge + Resync -->
      <div class="flex items-center gap-2 shrink-0">
        <div class="text-micro text-white/50 flex items-center gap-1.5" :title="syncTitle">
          <template v-if="refreshing">
            <Loader2 class="w-3 h-3 animate-spin shrink-0 text-brand-light" />
            <span>Syncing{{ refreshPercent != null ? ` ${refreshPercent}%` : '…' }}</span>
          </template>
          <template v-else>
            <span class="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0"></span>
            {{ syncLabel }}
          </template>
        </div>
        <button
          @click="$emit('resync')"
          class="text-white/40 hover:text-white transition-colors p-1 rounded hover:bg-white/10 disabled:opacity-30"
          :disabled="refreshing"
          title="Check for new data (pulls only if the source changed)"
        >
          <RefreshCw class="w-3.5 h-3.5" />
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
        <LogOut class="w-4 h-4" />
      </button>
    </div>
  </header>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { Loader2, RefreshCw, LogOut, BookOpen } from 'lucide-vue-next'
import { useAuthStore } from '../../stores/auth'
import { dataApi } from '../../api/client'

const emit = defineEmits(['resync', 'data-updated'])

const auth = useAuthStore()

// Data freshness reflects the backend's last BigQuery sync (auto-refreshes
// hourly when the source table changes), NOT the browser's fetch time.
const now = ref(Date.now())
const lastCheckedAt = ref(null)    // badge counts from this (pull OR no-change check)
const dataSyncedAt = ref(null)     // when data actually changed (tooltip + refetch trigger)
const refreshing = ref(false)
const refreshPercent = ref(null)
let clockTimer = null
let pollTimer = null
let prevDataSyncedMs = null

async function pollDataStatus() {
  try {
    const { data } = await dataApi.getStatus()
    lastCheckedAt.value = data.last_checked_at ? new Date(data.last_checked_at) : null
    dataSyncedAt.value = data.data_synced_at ? new Date(data.data_synced_at) : null
    refreshing.value = !!data.refreshing
    refreshPercent.value = data.refresh_percent ?? null
    // Refetch the visible view ONLY when the data itself changed (a pull
    // landed) — never on a no-change check (which only advances last_checked).
    const dMs = dataSyncedAt.value ? dataSyncedAt.value.getTime() : null
    if (dMs && prevDataSyncedMs && dMs > prevDataSyncedMs) {
      emit('data-updated')
    }
    if (dMs) prevDataSyncedMs = dMs
  } catch {
    /* transient — keep last known values */
  }
}

onMounted(() => {
  pollDataStatus()
  clockTimer = setInterval(() => { now.value = Date.now() }, 15000)
  pollTimer = setInterval(pollDataStatus, 20000)
})
onUnmounted(() => {
  clearInterval(clockTimer)
  clearInterval(pollTimer)
})

const syncLabel = computed(() => {
  if (!lastCheckedAt.value) return 'Data synced'
  const diffMin = Math.floor((now.value - lastCheckedAt.value.getTime()) / 60000)
  if (diffMin < 1) return 'Synced just now'
  if (diffMin === 1) return 'Synced 1 min ago'
  if (diffMin < 60) return `Synced ${diffMin} mins ago`
  const h = Math.floor(diffMin / 60)
  return h === 1 ? 'Synced 1 hr ago' : `Synced ${h} hrs ago`
})

const syncTitle = computed(() => {
  if (refreshing.value) return 'Refreshing data from BigQuery…'
  const parts = []
  if (lastCheckedAt.value) parts.push(`Last checked: ${lastCheckedAt.value.toLocaleString()}`)
  if (dataSyncedAt.value) parts.push(`Data last changed: ${dataSyncedAt.value.toLocaleString()}`)
  return parts.length ? parts.join(' · ') : 'Data sync status'
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

// Workspaces only — "How it works" is rendered separately in the nav as the
// set-apart reference entry (icon + divider + brand ring), not a workspace tab.
const tabs = [
  { label: 'Executive', to: '/executive' },
  { label: 'Commercial', to: '/commercial' },
  { label: 'Competitors', to: '/competitor-products' },
  { label: 'Gap Analysis', to: '/gap-analysis' },
]
</script>
