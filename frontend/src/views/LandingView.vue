<template>
  <div class="min-h-[100dvh] bg-paper text-grey-900 overflow-x-hidden flex flex-col">
    <!-- ===================== HEADER ===================== -->
    <header class="sticky top-0 z-50 bg-paper/85 backdrop-blur border-b border-grey-200/70">
      <div class="max-w-[1180px] mx-auto px-6 h-16 flex items-center gap-3">
        <img src="/breadfast-icon.png" alt="" aria-hidden="true" class="w-7 h-7 rounded-lg shrink-0" />
        <span class="font-bold tracking-tightish">Pricing Tool <span class="text-grey-400 font-medium">· Breadfast</span></span>
        <button
          class="ml-auto inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-primary text-white text-caption font-semibold hover:bg-brand-dark active:scale-[0.98] transition-[transform,background-color] duration-200 ease-premium disabled:opacity-50"
          :disabled="loading"
          @click="signIn"
        >
          <GoogleMark class="w-4 h-4 bg-white rounded-full p-px" />
          {{ loading ? 'Signing in…' : 'Sign in' }}
        </button>
      </div>
    </header>

    <!-- ===================== HERO ===================== -->
    <main class="flex-1 flex items-center">
      <div class="max-w-[1180px] w-full mx-auto px-6 py-20">
        <div class="max-w-[46ch] animate-fade-in-up">
          <span class="text-micro font-semibold uppercase tracking-[0.16em] text-brand-primary">Competitive price intelligence</span>
          <h1 class="text-4xl md:text-5xl lg:text-6xl font-semibold tracking-tightish leading-[1.04] text-balance mt-4">
            Know exactly where you stand. <span class="text-brand-primary">Then move the price.</span>
          </h1>

          <div class="flex flex-wrap items-center gap-3 mt-9">
            <button
              class="group inline-flex items-center gap-3 pl-5 pr-2 py-2.5 rounded-full bg-brand-primary text-white text-body font-semibold hover:bg-brand-dark active:scale-[0.98] transition-[transform,background-color] duration-200 ease-premium disabled:opacity-50"
              :disabled="loading"
              @click="signIn"
            >
              <GoogleMark class="w-5 h-5 bg-white rounded-full p-0.5" />
              {{ loading ? 'Signing in…' : 'Sign in with Google' }}
              <span class="grid place-items-center w-7 h-7 rounded-full bg-white/18 transition-transform duration-200 ease-premium group-hover:translate-x-0.5">
                <ArrowRight class="w-3.5 h-3.5" />
              </span>
            </button>
          </div>

          <div v-if="auth.isDevMode" class="mt-5 flex items-center gap-2 max-w-sm">
            <input
              v-model="devEmail" type="email" placeholder="you@breadfast.com"
              class="flex-1 px-3 py-2 rounded-lg border border-grey-200 text-body bg-white focus:outline-none focus:ring-2 focus:ring-brand-lightest focus:border-brand-primary"
              @keyup.enter="devSignIn"
            />
            <button class="px-4 py-2 rounded-lg bg-grey-900 text-white text-body font-semibold hover:bg-black active:scale-[0.98] transition-transform" @click="devSignIn">Go</button>
          </div>
          <div v-if="error" class="mt-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-caption text-red-700 max-w-md">{{ error }}</div>
          <p class="text-micro text-grey-400 mt-4">Only @breadfast.com accounts can sign in.</p>
        </div>

        <div class="flex gap-8 mt-14 flex-wrap animate-fade-in-up stagger-1">
          <div class="max-w-[240px]">
            <h3 class="text-caption font-semibold flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-brand-primary" />Category managers</h3>
            <p class="text-caption text-grey-600 mt-2 leading-relaxed">Filter to a category, read the competitive position, find the gap that moves revenue.</p>
          </div>
          <div class="max-w-[240px]">
            <h3 class="text-caption font-semibold flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-brand-primary" />Leadership</h3>
            <p class="text-caption text-grey-600 mt-2 leading-relaxed">A quick scan for whether you're winning or exposed, and where.</p>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, watch, h } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '../stores/auth'
import { ArrowRight } from 'lucide-vue-next'

const auth = useAuthStore()
const { error } = storeToRefs(auth)
const loading = ref(false)
const devEmail = ref('')

watch(error, (v) => { if (v) loading.value = false })
watch(() => auth.isAuthenticated, (v) => { if (v) loading.value = false })

function signIn() {
  loading.value = true
  auth.login()
  setTimeout(() => { loading.value = false }, 10000)
}
function devSignIn() {
  auth.devLogin(devEmail.value || 'dev@breadfast.com')
}

// Official Google "G" mark — brand logo, kept as-is (logos are exempt from the
// no-hand-rolled-SVG rule and Google requires this exact artwork).
const GoogleMark = (props) => h('svg', { viewBox: '0 0 24 24', ...props }, [
  h('path', { d: 'M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z', fill: '#4285F4' }),
  h('path', { d: 'M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z', fill: '#34A853' }),
  h('path', { d: 'M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z', fill: '#FBBC05' }),
  h('path', { d: 'M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z', fill: '#EA4335' }),
])
</script>
