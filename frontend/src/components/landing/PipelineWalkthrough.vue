<template>
  <section id="how" class="py-16 border-t border-grey-200/70">
    <!-- Intro -->
    <span class="text-micro font-semibold uppercase tracking-[0.16em] text-brand-primary">The number, and why you can trust it</span>
    <h2 class="text-3xl md:text-4xl font-semibold tracking-tightish leading-tight mt-3 max-w-[22ch]">How the number is built.</h2>
    <p class="text-body md:text-lg text-grey-600 leading-relaxed max-w-[60ch] mt-4">
      The Price Index isn't a list-price comparison. Here's the exact path from a raw crawled price to the headline figure — every step the tool takes, in order, on a real-shaped example.
    </p>
    <div class="inline-flex flex-wrap items-center gap-x-3 gap-y-1 mt-7 px-5 py-3.5 rounded-2xl bg-brand-wash ring-1 ring-brand-tint">
      <span class="font-mono text-body font-semibold text-brand-dark">PI = BF price ÷ Competitor price</span>
      <span class="text-caption text-grey-600">weighted by quantity sold</span>
    </div>

    <!-- Pipeline: a genuine ordered sequence, so the numbered markers carry meaning -->
    <ol class="mt-12 flex flex-col">
      <RevealOnScroll
        v-for="(s, i) in steps" :key="s.n" tag="li"
        :delay="`${i * 0.04}s`"
        class="relative grid grid-cols-[2.25rem_1fr] md:grid-cols-[2.5rem_minmax(0,22rem)_1fr] gap-x-4 md:gap-x-7 gap-y-3 pb-10"
      >
        <!-- Rail: index marker + connector -->
        <div class="relative flex flex-col items-center">
          <span class="z-10 grid place-items-center w-9 h-9 md:w-10 md:h-10 rounded-full bg-white ring-1 ring-grey-200 shadow-panel font-mono text-caption font-semibold text-brand-primary shrink-0">{{ s.n }}</span>
          <span v-if="i < steps.length - 1" class="absolute top-9 md:top-10 bottom-[-2.5rem] w-px bg-grey-200" aria-hidden="true" />
        </div>

        <!-- Copy -->
        <div class="min-w-0 pt-1">
          <h3 class="text-heading font-bold tracking-tightish">{{ s.title }}</h3>
          <p class="text-caption text-grey-600 leading-relaxed mt-1.5 max-w-[42ch]">{{ s.body }}</p>
        </div>

        <!-- Visual — distinct per step, never a repeated card -->
        <div class="col-start-2 md:col-start-3 min-w-0">
          <!-- 1 · Crawled prices -->
          <div v-if="s.kind === 'crawl'" class="rounded-2xl ring-1 ring-grey-200/70 bg-white shadow-panel overflow-hidden">
            <div class="px-4 py-2 border-b border-grey-100 text-micro font-semibold text-grey-500 flex items-center justify-between">
              <span class="inline-flex items-center gap-1.5"><CompetitorLogo name="Talabat" /> Talabat · Juhayna Full Cream 1L</span>
              <span class="text-grey-400 normal-case font-medium">4 FPs</span>
            </div>
            <div v-for="o in crawl" :key="o.fp" class="flex items-center justify-between px-4 py-2 border-b border-grey-50 last:border-0"
                 :class="o.stale ? 'opacity-55' : ''">
              <span class="text-caption text-grey-700">{{ o.fp }}</span>
              <span class="flex items-center gap-3">
                <span class="font-mono text-caption font-medium text-grey-800">EGP {{ o.price }}</span>
                <span class="inline-flex items-center gap-1 text-micro font-semibold px-1.5 py-0.5 rounded-full"
                      :class="o.stale ? 'text-amber-700 bg-amber-50 border border-dashed border-amber-300' : 'text-green-700 bg-green-50'">
                  <Clock v-if="o.stale" class="w-2.5 h-2.5" />{{ o.age }}
                </span>
              </span>
            </div>
          </div>

          <!-- 2 · Modal price -->
          <div v-else-if="s.kind === 'modal'" class="rounded-2xl ring-1 ring-grey-200/70 bg-white shadow-panel p-5">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-mono text-caption text-grey-400 line-through">60</span>
              <span class="font-mono text-caption text-grey-700">62</span>
              <span class="font-mono text-caption text-grey-700">62</span>
              <span class="font-mono text-caption text-grey-700">64</span>
              <ArrowRight class="w-4 h-4 text-grey-300 mx-1" />
              <span class="font-mono text-lg font-semibold text-brand-dark px-3 py-1 rounded-xl bg-brand-wash ring-1 ring-brand-tint">EGP 62</span>
            </div>
            <p class="text-micro text-grey-500 mt-3 leading-relaxed">Most-frequent <b class="text-grey-700">fresh</b> price (ties break to the lowest). The 34-day reading is held out — it never silently sets the price.</p>
          </div>

          <!-- 3 · Price Index -->
          <div v-else-if="s.kind === 'pi'" class="rounded-2xl ring-1 ring-grey-200/70 bg-white shadow-panel p-5">
            <div class="flex items-center gap-2.5 font-mono text-caption text-grey-600 flex-wrap">
              <span class="px-2 py-1 rounded-lg bg-grey-50 ring-1 ring-grey-200">BF 58</span>
              <span class="text-grey-400">÷</span>
              <span class="px-2 py-1 rounded-lg bg-grey-50 ring-1 ring-grey-200">Comp 62</span>
              <span class="text-grey-400">=</span>
              <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-caption font-bold" :class="[piBgClass(0.94), piTextClass(0.94)]">
                <span class="text-[10px]">{{ piArrow(0.94) }}</span><span class="font-mono">0.94</span>
              </span>
            </div>
            <p class="text-micro text-grey-500 mt-3">Below 1.00 → Breadfast is ~6% cheaper here. Cool = cheaper, green = parity, warm = pricier.</p>
          </div>

          <!-- 4 · Quantity weighting -->
          <div v-else-if="s.kind === 'weight'" class="rounded-2xl ring-1 ring-grey-200/70 bg-white shadow-panel overflow-hidden">
            <table class="w-full text-caption border-separate border-spacing-0">
              <thead>
                <tr class="text-micro uppercase tracking-wide text-grey-400">
                  <th class="text-left font-semibold px-4 pt-3 pb-2">Product</th>
                  <th class="text-right font-semibold px-2 pt-3 pb-2">PI</th>
                  <th class="text-right font-semibold px-2 pt-3 pb-2">Qty/day</th>
                  <th class="text-right font-semibold px-4 pt-3 pb-2">PI × Qty</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in blend" :key="r.name">
                  <td class="px-4 py-2 border-t border-grey-100 text-grey-800">{{ r.name }}</td>
                  <td class="px-2 py-2 border-t border-grey-100 text-right">
                    <span class="inline-flex items-center gap-0.5 font-mono font-semibold" :class="piTextClass(r.pi)"><span class="text-[9px]">{{ piArrow(r.pi) }}</span>{{ r.pi.toFixed(2) }}</span>
                  </td>
                  <td class="px-2 py-2 border-t border-grey-100 text-right font-mono text-grey-600">{{ r.qty }}</td>
                  <td class="px-4 py-2 border-t border-grey-100 text-right font-mono text-grey-800">{{ (r.pi * r.qty).toFixed(1) }}</td>
                </tr>
              </tbody>
            </table>
            <p class="text-micro text-grey-500 px-4 py-2.5 border-t border-grey-100 bg-grey-50">High-volume products move the index more than the long tail.</p>
          </div>

          <!-- 5 · Eligible & used -->
          <div v-else-if="s.kind === 'gate'" class="rounded-2xl ring-1 ring-grey-200/70 bg-white shadow-panel p-5 flex flex-col gap-3">
            <div v-for="g in gate" :key="g.label" class="grid grid-cols-[8.5rem_1fr_3rem] items-center gap-3">
              <span class="text-caption text-grey-600">{{ g.label }}</span>
              <div class="h-2.5 rounded-full bg-paper-2 overflow-hidden"><div class="h-full rounded-full" :style="{ width: g.pct + '%', background: g.color }" /></div>
              <span class="font-mono text-caption font-semibold text-grey-700 text-right">{{ g.value }}</span>
            </div>
            <p class="text-micro text-grey-500 leading-relaxed">Eligible = the top 80% of subcategory revenue. Used = eligible <i>and</i> mapped <i>and</i> fresh. Unmapped or stale products stay counted as “needs action” — never dropped from the denominator to flatter the number.</p>
          </div>

          <!-- 6 · Three price tiers -->
          <div v-else-if="s.kind === 'tiers'" class="grid sm:grid-cols-3 gap-3">
            <div v-for="t in tiers" :key="t.label" class="rounded-2xl ring-1 bg-white shadow-panel p-4" :class="t.ring">
              <span class="inline-flex items-center gap-1.5 text-caption font-bold" :class="t.tone">
                <component :is="t.icon" v-if="t.icon" class="w-3.5 h-3.5" /><span v-else class="font-mono">≈</span>{{ t.label }}
              </span>
              <p class="text-micro text-grey-500 leading-relaxed mt-2">{{ t.body }}</p>
            </div>
          </div>

          <!-- 7 · Blended index -->
          <div v-else-if="s.kind === 'result'" class="rounded-2xl ring-1 ring-grey-200/70 bg-white shadow-panel p-5">
            <div class="font-mono text-caption text-grey-600 flex items-center gap-2 flex-wrap">
              <span class="text-grey-400">Σ(PI × Qty)</span>
              <span class="text-grey-300">/</span>
              <span class="text-grey-400">Σ Qty</span>
              <span class="text-grey-300">=</span>
              <span class="text-grey-700">{{ sumPiQty.toFixed(1) }}</span>
              <span class="text-grey-300">/</span>
              <span class="text-grey-700">{{ sumQty }}</span>
              <span class="text-grey-300">=</span>
            </div>
            <div class="flex items-baseline gap-3 mt-3">
              <span class="font-mono text-5xl font-semibold tracking-tightish leading-none" :style="{ color: resultHex }">{{ blended.toFixed(2) }}</span>
              <span class="text-2xl font-bold" :style="{ color: resultHex }">{{ piArrow(blended) }}</span>
              <span class="text-caption font-semibold uppercase tracking-wide" :style="{ color: resultHex }">Slightly pricey</span>
            </div>
            <p class="text-micro text-grey-500 mt-3">This is the headline index — the same figure the gauge on the Executive view settles on. Cheap winners can't hide a pricey, high-volume tail, because volume is in the math.</p>
          </div>
        </div>
      </RevealOnScroll>
    </ol>

    <p class="text-micro text-grey-400 mt-1 flex items-center gap-1.5"><Zap class="w-3.5 h-3.5 text-brand-primary" /> Illustrative example; the arithmetic is exactly what the tool runs.</p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { ArrowRight, Clock, Zap, Check } from 'lucide-vue-next'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import RevealOnScroll from './RevealOnScroll.vue'
import { piBgClass, piTextClass, piArrow, piTreatment } from '../../utils/piColor'

const crawl = [
  { fp: 'Maadi FP #2', price: 62, age: '2d', stale: false },
  { fp: 'Nasr City FP #1', price: 62, age: '1d', stale: false },
  { fp: 'Heliopolis FP #3', price: 64, age: '5d', stale: false },
  { fp: 'New Cairo FP #5', price: 60, age: '34d', stale: true },
]

// Worked blend — the arithmetic resolves to the 1.06 headline carried elsewhere.
const blend = [
  { name: 'Juhayna Full Cream', pi: 0.94, qty: 100 },
  { name: 'Almarai Low Fat', pi: 1.10, qty: 90 },
  { name: 'Domty Feta', pi: 1.22, qty: 60 },
]
const sumPiQty = computed(() => blend.reduce((a, r) => a + r.pi * r.qty, 0))
const sumQty = computed(() => blend.reduce((a, r) => a + r.qty, 0))
const blended = computed(() => sumPiQty.value / sumQty.value)
const resultHex = computed(() => piTreatment(blended.value).bold)

const gate = [
  { label: 'Tracked in Dairy', value: '1,240', pct: 100, color: '#E2DAEC' },
  { label: 'Eligible (top 80%)', value: '312', pct: 56, color: '#a3007c' },
  { label: 'Used (mapped + fresh)', value: '248', pct: 44, color: '#16A34A' },
]

const tiers = [
  { label: 'Fresh', icon: Check, tone: 'text-green-700', ring: 'ring-green-200', body: 'A recent price at this FP. Trusted, and always in the blend.' },
  { label: 'Estimated', icon: null, tone: 'text-brand-primary', ring: 'ring-brand-light', body: 'No fresh price here, but the pair is fresh elsewhere — filled from its fresh modal when you opt in. Counted, and marked ≈.' },
  { label: 'Outdated', icon: Clock, tone: 'text-amber-700', ring: 'ring-amber-300', body: 'Only a stale price exists anywhere. Shown for reference, flagged — never blended into the verdict.' },
]

const steps = [
  { n: '01', kind: 'crawl', title: 'Start with crawled prices', body: 'Every competitor price we observe, per FP, with the date it was last seen.' },
  { n: '02', kind: 'modal', title: 'Reduce to the modal price', body: 'Collapse the readings to the most-frequent fresh price — robust to one-off promos and bad scrapes.' },
  { n: '03', kind: 'pi', title: 'Divide to get the index', body: 'PI is the Breadfast price over the competitor’s, so 1.00 is parity and the direction is unambiguous.' },
  { n: '04', kind: 'weight', title: 'Weight by quantity sold', body: 'Each product’s PI is weighted by how much it actually sells, not counted one-SKU-one-vote.' },
  { n: '05', kind: 'gate', title: 'Gate on eligibility & freshness', body: 'Only revenue-relevant, mapped, freshly-priced products feed the live verdict — but nothing is hidden.' },
  { n: '06', kind: 'tiers', title: 'Label every price by trust', body: 'Fresh, estimated, or outdated — each value carries how much you should trust it.' },
  { n: '07', kind: 'result', title: 'Blend to the headline index', body: 'The quantity-weighted average of the used products — one defensible number.' },
]
</script>
