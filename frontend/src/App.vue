<template>
  <div class="min-h-screen bg-paper overflow-x-hidden">
    <!-- 1. Landing / sign-in (not authenticated) -->
    <LandingView v-if="!auth.isAuthenticated" />

    <!-- 2. Startup progress (authenticated but backend not ready) -->
    <StartupProgress
      v-else-if="!backendReady"
      :stage="startupStage"
      :progress="startupProgress"
      :total="startupTotal"
    />

    <!-- 3. Catalog enrichment progress -->
    <StartupProgress
      v-else-if="enriching"
      :stage="enrichStage"
      :progress="enrichProgress"
      :total="enrichTotal"
    />

    <!-- 4. Normal app -->
    <template v-else>
      <!-- Skip to main content link (accessibility) -->
      <a href="#main-content" class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[9999] focus:px-4 focus:py-2 focus:bg-brand-primary focus:text-white focus:rounded-lg focus:text-body focus:font-semibold">Skip to content</a>
      <AppHeader @resync="resync" @data-updated="onDataUpdated" />
      <main id="main-content" class="px-6 lg:px-10 py-5">
        <router-view v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </router-view>
      </main>
      <Toast ref="toastComponent" />
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import AppHeader from './components/layout/AppHeader.vue'
import Toast from './components/shared/Toast.vue'
import StartupProgress from './components/shared/StartupProgress.vue'
import LandingView from './views/LandingView.vue'
import { setToastRef, useToast } from './composables/useToast'
import { startupApi, catalogApi, dataApi } from './api/client'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useFiltersStore } from './stores/filters'
import { useCommercialStore } from './stores/commercial'
import { useExecutiveStore } from './stores/executive'
import { useMasterDataStore } from './stores/masterData'
import { useCompetitorProductsStore } from './stores/competitorProducts'

const auth = useAuthStore()
const filters = useFiltersStore()
const route = useRoute()
const toast = useToast()

// Auto-refetch the visible view when an hourly background sync lands
// (AppHeader emits 'data-updated' when the BQ sync time advances).
function onDataUpdated() {
  // A new BQ sync may add categories / FPs / competitors — refresh the filter
  // option lists too (force past the cache), not just the visible view data.
  filters.fetchFilterOptions(true)
  const stores = {
    '/commercial': useCommercialStore,
    '/executive': useExecutiveStore,
    '/master-data': useMasterDataStore,
    '/competitor-products': useCompetitorProductsStore,
  }
  const match = Object.keys(stores).find((p) => route.path.startsWith(p))
  if (!match) return
  stores[match]().fetchAll()
  toast?.info?.('Data updated', 'Refreshed with the latest sync from BigQuery')
}
const toastComponent = ref(null)

// Global keyboard shortcuts
function handleKeydown(e) {
  // Escape = clear all filters
  if (e.key === 'Escape' && filters.hasActiveFilters) {
    filters.clearAll()
  }
}

// Startup state
const backendReady = ref(false)
const startupStage = ref('Connecting to server...')
const startupProgress = ref(0)
const startupTotal = ref(0)

// Enrichment state
const enriching = ref(false)
const enrichStage = ref('Fetching live prices from Catalog...')
const enrichProgress = ref(0)
const enrichTotal = ref(0)

let pollTimer = null

async function checkStartup() {
  try {
    const { data } = await startupApi.getStatus()
    startupStage.value = data.stage
    startupProgress.value = data.progress || 0
    startupTotal.value = data.total || 0
    if (data.ready) {
      backendReady.value = true
      clearInterval(pollTimer)
      pollTimer = null
    }
  } catch {
    startupStage.value = 'Connecting to server...'
  }
}

async function triggerEnrichment() {
  try {
    const { data } = await catalogApi.triggerEnrich()
    if (data.already_enriched) {
      // Already done from a previous session
      return
    }
    if (data.started || data.in_progress) {
      enriching.value = true
      pollEnrichment()
    }
  } catch (err) {
    // User may not have catalog access — that's OK, show dashboard anyway
    console.warn('[Catalog] Enrichment request failed:', err.response?.data?.error || err.message)
  }
}

let enrichTimer = null

function pollEnrichment() {
  enrichTimer = setInterval(async () => {
    try {
      const { data } = await startupApi.getStatus()
      const e = data.enrichment || {}
      enrichProgress.value = e.progress || 0
      enrichTotal.value = e.total || 0
      if (e.total > 0) {
        enrichStage.value = `Fetching live prices... ${e.progress}/${e.total}`
      }
      if (e.done) {
        enriching.value = false
        clearInterval(enrichTimer)
        enrichTimer = null
      }
      if (e.error) {
        enriching.value = false
        clearInterval(enrichTimer)
        enrichTimer = null
        console.warn('[Catalog] Enrichment error:', e.error)
      }
    } catch {
      // keep polling
    }
  }, 2000)
}

// When user logs in, start the startup check → enrichment flow
watch(() => auth.isAuthenticated, async (loggedIn) => {
  if (loggedIn) {
    await startFlow()
  }
})

async function startFlow() {
  // Poll backend startup
  await checkStartup()
  if (!backendReady.value) {
    pollTimer = setInterval(checkStartup, 2000)
    // Wait for backend to be ready
    await new Promise((resolve) => {
      const unwatch = watch(backendReady, (ready) => {
        if (ready) {
          unwatch()
          resolve()
        }
      })
    })
  }
  // Backend ready — trigger catalog enrichment
  await triggerEnrichment()
}

async function resync() {
  // Smart "check for new data": pulls in the background ONLY if the BQ table
  // changed; otherwise just confirms we're current. Never a blocking reload.
  try {
    const { data } = await dataApi.refreshNow()
    if (data.status === 'up_to_date') {
      toast?.success?.('Up to date', 'No new data since the last sync.')
    } else if (data.status === 'refreshing') {
      if (data.changed === null) {
        toast?.info?.('Already refreshing', 'A refresh is already running.')
      } else {
        toast?.info?.('New data found', 'Pulling the latest from BigQuery in the background — the app stays usable.')
      }
    } else {
      toast?.warning?.('Could not check', data.message || 'Backend not ready — try again shortly.')
    }
  } catch (err) {
    toast?.error?.('Check failed', err.response?.data?.message || err.message)
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handleKeydown)
  // Load the runtime OAuth client id from the server before anything else.
  await auth.fetchConfig()
  if (auth.isAuthenticated) {
    await startFlow()
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (enrichTimer) { clearInterval(enrichTimer); enrichTimer = null }
})

// Set toast ref once dashboard is visible
watch([backendReady, enriching], async ([ready, enr]) => {
  if (ready && !enr) {
    await nextTick()
    setToastRef(toastComponent.value)
  }
})
</script>
