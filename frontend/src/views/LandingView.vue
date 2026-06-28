<template>
  <div class="min-h-[100dvh] bg-paper text-grey-900 overflow-x-hidden">
    <!-- ===================== HEADER ===================== -->
    <header class="sticky top-0 z-50 bg-paper/85 backdrop-blur border-b border-grey-200/70">
      <div class="max-w-[1180px] mx-auto px-6 h-16 flex items-center gap-3">
        <img src="/breadfast-icon.png" alt="" aria-hidden="true" class="w-7 h-7 rounded-lg shrink-0" />
        <span class="font-bold tracking-tightish">Pricing Tool <span class="text-grey-400 font-medium">· Breadfast</span></span>
        <nav class="hidden md:flex items-center gap-1 ml-6">
          <a href="#index" class="px-3 py-1.5 rounded-full text-caption font-medium text-grey-600 hover:bg-brand-wash hover:text-brand-dark transition-colors">The Index</a>
          <a href="#views" class="px-3 py-1.5 rounded-full text-caption font-medium text-grey-600 hover:bg-brand-wash hover:text-brand-dark transition-colors">The Views</a>
          <a href="#trust" class="px-3 py-1.5 rounded-full text-caption font-medium text-grey-600 hover:bg-brand-wash hover:text-brand-dark transition-colors">Trust</a>
        </nav>
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

    <main class="max-w-[1180px] mx-auto px-6">
      <!-- ===================== HERO ===================== -->
      <section class="grid lg:grid-cols-[1.04fr_0.96fr] gap-12 lg:gap-14 items-center pt-16 pb-14 lg:pt-20">
        <div class="animate-fade-in-up">
          <span class="text-micro font-semibold uppercase tracking-[0.16em] text-brand-primary">Competitive price intelligence</span>
          <h1 class="text-4xl md:text-5xl lg:text-6xl font-semibold tracking-tightish leading-[1.04] text-balance mt-4">
            Know exactly where you stand. <span class="text-brand-primary">Then move the price.</span>
          </h1>
          <p class="text-body md:text-lg text-grey-600 leading-relaxed max-w-[58ch] mt-5">
            Breadfast's quantity-weighted Price Index tracks every product against every competitor, down to the fulfillment point, so commercial teams can read the gap and correct it without leaving the screen.
          </p>

          <div class="flex flex-wrap items-center gap-3 mt-8">
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
            <a href="#index" class="px-5 py-2.5 rounded-full bg-white ring-1 ring-grey-200 text-body font-medium hover:ring-brand-primary active:scale-[0.98] transition-[transform,box-shadow] duration-200 ease-premium">How the Index works</a>
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

        <div class="animate-fade-in-up stagger-1">
          <PIMeter :model-value="1.06" />
          <p class="flex items-center gap-2 text-micro text-grey-400 mt-3">
            <Zap class="w-3.5 h-3.5 text-brand-primary" />
            Both tails cost money. Only the middle is winning. Sample value, drag the handle.
          </p>
        </div>
      </section>

      <!-- ===================== THE INDEX ===================== -->
      <section id="index" class="py-16 border-t border-grey-200/70">
        <span class="text-micro font-semibold uppercase tracking-[0.16em] text-brand-primary">The number, and why you can trust it</span>
        <h2 class="text-3xl md:text-4xl font-semibold tracking-tightish leading-tight mt-3 max-w-[20ch]">One index, built to be defensible.</h2>
        <p class="text-body md:text-lg text-grey-600 leading-relaxed max-w-[60ch] mt-4">
          The Price Index isn't a list-price comparison. It's quantity-weighted, fulfillment-point aware, and gated on data freshness, so the figure you act on reflects what customers actually buy, where they buy it.
        </p>
        <div class="inline-flex items-center gap-3 mt-7 px-5 py-3.5 rounded-2xl bg-brand-wash ring-1 ring-brand-tint">
          <span class="font-mono text-body font-semibold text-brand-dark">PI = BF price ÷ Competitor price</span>
          <span class="text-caption text-grey-600">weighted by quantity sold</span>
        </div>

        <div class="grid md:grid-cols-2 lg:grid-cols-4 mt-9 rounded-2xl ring-1 ring-grey-200/70 bg-white shadow-panel overflow-hidden">
          <div
            v-for="(m, i) in method" :key="m.title"
            class="p-6 border-grey-100"
            :class="[i < method.length - 1 ? 'lg:border-r' : '', i % 2 === 0 ? 'md:border-r lg:border-r' : '', i < 2 ? 'md:border-b lg:border-b-0' : '']"
          >
            <div class="font-mono text-caption font-medium text-brand-primary">{{ m.n }}</div>
            <h3 class="text-heading font-bold tracking-tightish mt-3.5">{{ m.title }}</h3>
            <p class="text-caption text-grey-600 leading-relaxed mt-2">{{ m.body }}</p>
          </div>
        </div>
      </section>

      <!-- ===================== THE VIEWS ===================== -->
      <section id="views" class="py-12 border-t border-grey-200/70">
        <span class="text-micro font-semibold uppercase tracking-[0.16em] text-brand-primary">Three views, one vocabulary</span>
        <h2 class="text-3xl md:text-4xl font-semibold tracking-tightish leading-tight mt-3 max-w-[24ch]">Scan it. Act on it. Keep it honest.</h2>
        <p class="text-body text-grey-600 leading-relaxed max-w-[60ch] mt-4">
          The same table, badge, and filter language runs across every view. Leadership scans for exposure; category managers act on it; the mapping that feeds it all stays visible and current.
        </p>

        <!-- Executive -->
        <div class="grid lg:grid-cols-[0.92fr_1.08fr] gap-10 lg:gap-14 items-center py-12">
          <div>
            <span class="inline-flex items-center gap-2 text-caption font-semibold text-grey-500"><span class="w-1.5 h-1.5 rounded-full bg-brand-primary" />Executive</span>
            <h3 class="text-2xl md:text-3xl font-semibold tracking-tightish mt-3">Are we winning, or exposed?</h3>
            <p class="text-body text-grey-600 leading-relaxed max-w-[46ch] mt-3.5">A quick scan built for leadership: the blended index, week-over-week movement, and how much of the catalog is actually mapped and trustworthy.</p>
            <ul class="flex flex-col gap-2.5 mt-5">
              <li v-for="t in execList" :key="t" class="flex gap-2.5 text-caption text-grey-600"><Check class="w-4 h-4 text-brand-primary shrink-0 mt-0.5" />{{ t }}</li>
            </ul>
          </div>
          <!-- viz: blended position -->
          <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 p-6">
            <div class="flex items-center justify-between mb-5">
              <span class="text-caption font-semibold text-grey-600 flex items-center gap-2"><BarChart3 class="w-4 h-4 text-brand-primary" />Blended position</span>
              <span class="text-micro text-grey-400">illustrative</span>
            </div>
            <div class="flex items-center gap-6">
              <div class="relative shrink-0" style="width:150px;height:90px">
                <canvas ref="gauge" width="300" height="180" style="width:150px;height:90px"></canvas>
                <div class="absolute inset-x-0 bottom-0 text-center">
                  <div class="font-mono text-3xl font-semibold" style="color:#EA580C">1.06</div>
                  <div class="text-micro uppercase tracking-wide text-grey-400 font-semibold">Slightly pricey</div>
                </div>
              </div>
              <div class="flex-1 flex flex-col gap-3.5">
                <div class="flex items-baseline justify-between gap-2"><span class="text-caption text-grey-600">Week-over-week</span><span class="font-mono text-caption font-semibold px-2 py-0.5 rounded-full" style="color:#DC2626;background:#FEE2E2">▲ +0.03</span></div>
                <div class="flex items-baseline justify-between gap-2"><span class="text-caption text-grey-600">vs. Talabat</span><span class="font-mono text-caption font-semibold" style="color:#DC2626">1.09</span></div>
                <div class="flex items-baseline justify-between gap-2"><span class="text-caption text-grey-600">vs. Carrefour</span><span class="font-mono text-caption font-semibold" style="color:#16A34A">0.99</span></div>
                <div>
                  <div class="flex items-baseline justify-between gap-2 mb-1.5"><span class="text-caption text-grey-600">Catalog mapped</span><span class="font-mono text-caption font-semibold text-grey-900">71%</span></div>
                  <div class="h-1.5 rounded-full bg-paper-2 overflow-hidden"><div class="h-full rounded-full bg-brand-primary" style="width:71%"></div></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Commercial (flipped) -->
        <div class="grid lg:grid-cols-[1.08fr_0.92fr] gap-10 lg:gap-14 items-center py-12 border-t border-grey-100">
          <div class="lg:order-2">
            <span class="inline-flex items-center gap-2 text-caption font-semibold text-grey-500"><span class="w-1.5 h-1.5 rounded-full bg-brand-primary" />Commercial</span>
            <h3 class="text-2xl md:text-3xl font-semibold tracking-tightish mt-3">Read the gap. Fix the price. Same screen.</h3>
            <p class="text-body text-grey-600 leading-relaxed max-w-[46ch] mt-3.5">The working surface for category managers. Pivot a subcategory against every competitor, see the PI colored cell by cell, and edit prices inline or in bulk, synced straight to the catalog.</p>
            <ul class="flex flex-col gap-2.5 mt-5">
              <li v-for="t in commList" :key="t" class="flex gap-2.5 text-caption text-grey-600"><Check class="w-4 h-4 text-brand-primary shrink-0 mt-0.5" />{{ t }}</li>
            </ul>
          </div>
          <!-- viz: mini pivot -->
          <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 p-6 lg:order-1">
            <div class="flex items-center justify-between mb-4">
              <span class="text-caption font-semibold text-grey-600 flex items-center gap-2"><Table2 class="w-4 h-4 text-brand-primary" />Dairy · Fresh Milk 1L</span>
              <span class="text-micro text-grey-400">illustrative</span>
            </div>
            <table class="w-full text-caption border-separate border-spacing-0">
              <thead>
                <tr class="text-micro uppercase tracking-wide text-grey-400">
                  <th class="text-left font-semibold pb-3">Product</th>
                  <th v-for="c in ['Talabat','Carrefour','Instashop']" :key="c" class="text-right font-semibold pb-3">{{ c }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in pivot" :key="row.name">
                  <td class="py-2.5 border-t border-grey-100 font-medium text-grey-900">{{ row.name }}</td>
                  <td v-for="(cell, ci) in row.cells" :key="ci" class="py-2.5 border-t border-grey-100">
                    <div class="flex justify-end">
                      <span class="inline-flex flex-col items-end gap-0.5 px-2 py-1 rounded-lg" :class="cell.cls">
                        <span class="font-mono text-micro opacity-80">EGP {{ cell.price }}</span>
                        <span class="font-mono text-caption font-semibold">{{ cell.arrow }} {{ cell.pi }}</span>
                      </span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
            <div class="flex items-center justify-between mt-4 pt-4 border-t border-grey-100">
              <span class="text-micro text-grey-400 max-w-[60%]">Two cells above parity on Talabat. Adjust the price here and it syncs to the catalog.</span>
              <span class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-brand-primary text-white text-micro font-semibold"><PencilLine class="w-3 h-3" />Edit price</span>
            </div>
          </div>
        </div>

        <!-- Competitors -->
        <div class="grid lg:grid-cols-[0.92fr_1.08fr] gap-10 lg:gap-14 items-center py-12 border-t border-grey-100">
          <div>
            <span class="inline-flex items-center gap-2 text-caption font-semibold text-grey-500"><span class="w-1.5 h-1.5 rounded-full bg-brand-primary" />Competitors</span>
            <h3 class="text-2xl md:text-3xl font-semibold tracking-tightish mt-3">Every number is only as good as the mapping.</h3>
            <p class="text-body text-grey-600 leading-relaxed max-w-[46ch] mt-3.5">Where the catalog meets theirs. Track crawl coverage and freshness by competitor and category, review AI-proposed matches, and keep the foundation the index stands on honest.</p>
            <ul class="flex flex-col gap-2.5 mt-5">
              <li v-for="t in compList" :key="t" class="flex gap-2.5 text-caption text-grey-600"><Check class="w-4 h-4 text-brand-primary shrink-0 mt-0.5" />{{ t }}</li>
            </ul>
          </div>
          <!-- viz: mapping coverage -->
          <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 p-6">
            <div class="flex items-center justify-between mb-5">
              <span class="text-caption font-semibold text-grey-600 flex items-center gap-2"><Network class="w-4 h-4 text-brand-primary" />Mapping coverage</span>
              <span class="text-micro text-grey-400">illustrative</span>
            </div>
            <div class="flex flex-col gap-4">
              <div v-for="m in mapping" :key="m.name" class="grid grid-cols-[88px_1fr_46px] items-center gap-3">
                <span class="text-caption font-semibold text-grey-700">{{ m.name }}</span>
                <div class="h-2 rounded-full bg-paper-2 overflow-hidden"><div class="h-full rounded-full bg-brand-primary" :style="{ width: m.pct + '%' }"></div></div>
                <span class="font-mono text-caption font-semibold text-grey-600 text-right">{{ m.pct }}%</span>
              </div>
            </div>
            <div class="flex items-center gap-1.5 mt-5 pt-4 border-t border-grey-100">
              <span class="text-micro text-grey-400 mr-1.5">Price freshness, last 14 days</span>
              <span v-for="(c, i) in freshness" :key="i" class="w-3.5 h-3.5 rounded" :style="{ background: c }"></span>
            </div>
          </div>
        </div>
      </section>

      <!-- ===================== TRUST ===================== -->
      <section id="trust" class="py-12">
        <div class="relative overflow-hidden rounded-[28px] bg-brand-darkest text-white px-8 py-14 md:px-12">
          <div class="absolute -right-28 -top-28 w-[380px] h-[380px] rounded-full pointer-events-none" style="background:radial-gradient(circle, rgba(163,0,124,0.55), transparent 68%)"></div>
          <div class="relative">
            <span class="text-micro font-semibold uppercase tracking-[0.16em]" style="color:#E9A9D4">Data integrity, made visible</span>
            <h2 class="text-3xl md:text-4xl font-semibold tracking-tightish leading-tight mt-3.5 max-w-[20ch]">A figure you can't trust is worse than no figure.</h2>
            <p class="text-body md:text-lg leading-relaxed max-w-[60ch] mt-4 text-white/70">
              Every number carries its provenance. The tool shows what's synced versus locally edited, how complete the mapping is, and how stale each price is, so confidence is earned on screen, not assumed.
            </p>
            <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-8 mt-11">
              <div v-for="t in trust" :key="t.title">
                <h3 class="text-body font-semibold flex items-center gap-2.5"><component :is="t.icon" class="w-4 h-4" style="color:#E9A9D4" />{{ t.title }}</h3>
                <p class="text-caption text-white/60 leading-relaxed mt-2">{{ t.body }}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ===================== CLOSE ===================== -->
      <section class="text-center pt-16 pb-10">
        <span class="text-micro font-semibold uppercase tracking-[0.16em] text-brand-primary">Built for the people who set the price</span>
        <h2 class="text-3xl md:text-4xl font-semibold tracking-tightish leading-tight mt-3 max-w-[18ch] mx-auto">Turn competitor data into pricing decisions, fast.</h2>
        <p class="text-body text-grey-600 mt-4">Sign in with your Breadfast account to open your category.</p>
        <button
          class="group inline-flex items-center gap-3 pl-5 pr-2 py-2.5 rounded-full bg-brand-primary text-white text-body font-semibold hover:bg-brand-dark active:scale-[0.98] transition-[transform,background-color] duration-200 ease-premium disabled:opacity-50 mt-7"
          :disabled="loading"
          @click="signIn"
        >
          <GoogleMark class="w-5 h-5 bg-white rounded-full p-0.5" />
          {{ loading ? 'Signing in…' : 'Sign in with Google' }}
          <span class="grid place-items-center w-7 h-7 rounded-full bg-white/18 transition-transform duration-200 ease-premium group-hover:translate-x-0.5"><ArrowRight class="w-3.5 h-3.5" /></span>
        </button>
        <div class="flex gap-8 justify-center mt-12 flex-wrap text-left">
          <div class="max-w-[240px]">
            <h3 class="text-caption font-semibold flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-brand-primary" />Category managers</h3>
            <p class="text-caption text-grey-600 mt-2 leading-relaxed">Filter to a category, read the competitive position, edit prices inline, move on.</p>
          </div>
          <div class="max-w-[240px]">
            <h3 class="text-caption font-semibold flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-brand-primary" />Leadership</h3>
            <p class="text-caption text-grey-600 mt-2 leading-relaxed">A quick scan for whether you're winning or exposed this week, and where.</p>
          </div>
        </div>
      </section>
    </main>

    <footer class="border-t border-grey-200/70">
      <div class="max-w-[1180px] mx-auto px-6 py-7 flex items-center justify-between gap-4 flex-wrap text-caption text-grey-400">
        <span class="font-medium text-grey-600">Pricing Tool · Breadfast</span>
        <span>Quantity-weighted Price Index, refreshed from the source on every sync.</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, watch, h, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '../stores/auth'
import { BarChart3, Table2, Network, ArrowRight, Zap, Check, PencilLine, RefreshCw, Clock, ShieldCheck } from 'lucide-vue-next'
import PIMeter from '../components/shared/PIMeter.vue'
import { prefersReducedMotion } from '../utils/motion'

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

const method = [
  { n: '01', title: 'Quantity-weighted', body: 'High-volume products move the index more than the long tail, so the headline number reflects real revenue exposure, not an unweighted average of SKUs nobody buys.' },
  { n: '02', title: 'Per fulfillment point', body: 'Prices and competitor coverage vary by location. PI is computed at the fulfillment-point level, then rolled up, so a national average never hides a local gap.' },
  { n: '03', title: 'Freshness-gated', body: "Stale competitor prices are flagged and excluded from the live verdict. A number you can't date is worse than no number, so the tool always shows when each price was last seen." },
  { n: '04', title: 'Both tails bad', body: 'Under-pricing bleeds margin; over-pricing loses demand. Color encodes both directions and the severity, so the screen tells you which way to move at a glance.' },
]

const execList = ['Blended PI with the diverging gauge', 'Week-over-week movement, per competitor', 'Mapping coverage and classification mix']
const commList = ['Product pivot, PI per competitor per cell', 'Inline and bulk price edits', 'Drill from subcategory to fulfillment point']
const compList = ['Mapping coverage by competitor and category', 'Crawl timeline and price freshness', 'Accept or reject AI-proposed matches']

const Z = {
  cheap:  'bg-blue-50 text-blue-800',
  parity: 'bg-green-50 text-green-800',
  pricey: 'bg-red-50 text-red-800',
  amber:  'bg-amber-50 text-amber-800',
}
const pivot = [
  { name: 'Juhayna Full Cream', cells: [
    { price: 62, pi: '1.11', arrow: '▲', cls: Z.pricey },
    { price: 58, pi: '1.02', arrow: '◆', cls: Z.parity },
    { price: 55, pi: '0.93', arrow: '▼', cls: Z.cheap },
  ] },
  { name: 'Almarai Low Fat', cells: [
    { price: 64, pi: '1.01', arrow: '◆', cls: Z.parity },
    { price: 60, pi: '1.07', arrow: '▲', cls: Z.amber },
    { price: 63, pi: '1.00', arrow: '◆', cls: Z.parity },
  ] },
]

const mapping = [
  { name: 'Talabat', pct: 84 },
  { name: 'Carrefour', pct: 71 },
  { name: 'Instashop', pct: 58 },
]
const freshness = ['#16A34A', '#16A34A', '#16A34A', '#FBBF24', '#16A34A', '#16A34A', '#E2DAEC']

const trust = [
  { icon: RefreshCw, title: 'Synced vs. local', body: 'Edits are marked until they sync to the catalog, so you always know which prices are live.' },
  { icon: Network, title: 'Mapping coverage', body: 'Unmapped products are counted, never silently dropped from the denominator.' },
  { icon: Clock, title: 'Price staleness', body: 'Each competitor price is dated; stale ones are flagged and held out of the verdict.' },
  { icon: ShieldCheck, title: 'Eligible vs. used', body: 'Bulk actions show exactly how many products qualify and how many were changed.' },
]

// Executive gauge: diverging blue→green→red semicircle, needle at PI 1.06.
const gauge = ref(null)
function mix(a, b, t) {
  t = Math.min(1, Math.max(0, t))
  const h2 = (x) => [parseInt(x.slice(1, 3), 16), parseInt(x.slice(3, 5), 16), parseInt(x.slice(5, 7), 16)]
  const A = h2(a), B = h2(b)
  return `rgb(${Math.round(A[0] + (B[0] - A[0]) * t)},${Math.round(A[1] + (B[1] - A[1]) * t)},${Math.round(A[2] + (B[2] - A[2]) * t)})`
}
onMounted(() => {
  const c = gauge.value
  if (!c) return
  const ctx = c.getContext('2d')
  const cx = 150, cy = 160, r = 120
  const stops = [['#1E40AF', 0], ['#2563EB', 0.18], ['#60A5FA', 0.36], ['#16A34A', 0.5], ['#FBBF24', 0.66], ['#F97316', 0.82], ['#DC2626', 1]]
  const seg = 120
  for (let i = 0; i < seg; i++) {
    const t0 = i / seg
    let col = stops[stops.length - 1][0]
    for (let s = 1; s < stops.length; s++) {
      if (t0 <= stops[s][1]) { col = mix(stops[s - 1][0], stops[s][0], (t0 - stops[s - 1][1]) / (stops[s][1] - stops[s - 1][1])); break }
    }
    ctx.beginPath()
    ctx.strokeStyle = col
    ctx.lineWidth = 15
    ctx.arc(cx, cy, r, Math.PI + t0 * Math.PI, Math.PI + (i + 1) / seg * Math.PI)
    ctx.stroke()
  }
  const pi = 1.06, p = (pi - 0.70) / 0.60, ang = Math.PI + p * Math.PI
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(ang)
  ctx.beginPath(); ctx.moveTo(-8, 0); ctx.lineTo(r - 22, 0); ctx.lineWidth = 4; ctx.lineCap = 'round'; ctx.strokeStyle = '#1C1622'; ctx.stroke()
  ctx.restore()
  ctx.beginPath(); ctx.arc(cx, cy, 7, 0, 2 * Math.PI); ctx.fillStyle = '#1C1622'; ctx.fill()
  ctx.beginPath(); ctx.arc(cx, cy, 3.2, 0, 2 * Math.PI); ctx.fillStyle = '#fff'; ctx.fill()
})
</script>
