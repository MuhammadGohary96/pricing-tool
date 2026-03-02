<template>
  <div class="fixed inset-0 z-50 bg-grey-100 flex items-center justify-center">
    <div class="bg-white rounded-xl shadow-card-hover px-10 py-10 flex flex-col items-center gap-6 w-full max-w-sm">
      <!-- Logo -->
      <div class="flex items-center gap-3">
        <img src="/breadfast-icon.png" alt="Breadfast" class="w-12 h-12 rounded-lg shrink-0" />
        <div>
          <div class="text-subheading font-bold text-grey-900">Breadfast Pricing Tool</div>
          <div class="text-caption text-grey-500">Breadfast Commercial Team</div>
        </div>
      </div>

      <div class="w-full border-t border-grey-100"></div>

      <!-- Dev mode login -->
      <template v-if="auth.isDevMode">
        <div class="w-full rounded-lg bg-amber-50 border border-amber-200 px-4 py-2 text-caption text-amber-700 text-center">
          Dev mode — no Google Client ID configured
        </div>
        <div class="w-full flex gap-2">
          <input
            v-model="devEmail"
            type="email"
            placeholder="you@breadfast.com"
            class="flex-1 px-3 py-2 border border-grey-200 rounded-lg text-body text-grey-700 focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
            @keyup.enter="handleDevLogin"
          />
          <button
            @click="handleDevLogin"
            class="px-4 py-2 bg-brand-primary text-white rounded-lg text-body font-semibold hover:bg-brand-darkest transition-colors"
          >
            Go
          </button>
        </div>
      </template>

      <!-- Google Sign-In -->
      <template v-else>
        <p class="text-body text-grey-600 text-center">
          Sign in with your Breadfast Google account to access the pricing dashboard.
        </p>

        <button
          @click="handleLogin"
          :disabled="loading"
          class="w-full flex items-center justify-center gap-3 px-4 py-3 border border-grey-200 rounded-lg bg-white hover:bg-grey-50 hover:shadow-card transition-all text-body font-semibold text-grey-700 disabled:opacity-50"
        >
          <svg class="w-5 h-5" viewBox="0 0 24 24">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
          </svg>
          {{ loading ? 'Signing in...' : 'Sign in with Google' }}
        </button>
      </template>

      <!-- Error message -->
      <div v-if="error" class="w-full rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-caption text-red-700">
        {{ error }}
      </div>

      <p class="text-micro text-grey-400 text-center">
        Only @breadfast.com accounts are allowed
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { storeToRefs } from 'pinia'

const auth = useAuthStore()
const { error } = storeToRefs(auth)
const loading = ref(false)
const devEmail = ref('')

// Clear loading immediately when an error appears or auth succeeds
watch(error, (val) => { if (val) loading.value = false })
watch(() => auth.isAuthenticated, (val) => { if (val) loading.value = false })

function handleLogin() {
  loading.value = true
  auth.login()
  setTimeout(() => { loading.value = false }, 10000)
}

function handleDevLogin() {
  auth.devLogin(devEmail.value || 'dev@breadfast.com')
}
</script>
