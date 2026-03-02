<template>
  <div class="min-h-screen bg-grey-100 overflow-x-hidden">
    <!-- 1. Login screen (not authenticated) -->
    <LoginScreen v-if="!auth.isAuthenticated" />

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
      <AppHeader @resync="resync" />
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
import LoginScreen from './components/shared/LoginScreen.vue'
import { setToastRef } from './composables/useToast'
import { startupApi, catalogApi } from './api/client'
import { useAuthStore } from './stores/auth'
import { useFiltersStore } from './stores/filters'

const auth = useAuthStore()
const filters = useFiltersStore()
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
  try {
    await startupApi.reload()
  } catch {
    // Backend may not support reload yet — fall back to just re-fetching
  }
  // Reset state to show startup progress screen
  backendReady.value = false
  startupStage.value = 'Reloading data...'
  startupProgress.value = 0
  startupTotal.value = 0
  enriching.value = false
  enrichProgress.value = 0
  enrichTotal.value = 0
  // Re-run the startup flow (polls until ready, then triggers enrichment)
  await startFlow()
}

onMounted(async () => {
  window.addEventListener('keydown', handleKeydown)
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
