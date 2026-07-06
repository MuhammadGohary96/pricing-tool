<template>
  <div class="max-w-[1180px] mx-auto text-grey-900">
    <!-- ===================== HERO ===================== -->
    <section class="grid lg:grid-cols-[1.04fr_0.96fr] gap-12 lg:gap-14 items-center pt-10 pb-14 lg:pt-14">
      <div class="animate-fade-in-up">
        <span class="text-micro font-semibold uppercase tracking-[0.16em] text-brand-primary">Methodology &amp; views</span>
        <h1 class="text-4xl md:text-5xl lg:text-[3.4rem] font-semibold tracking-tightish leading-[1.05] text-balance mt-4">
          How the Index works, <span class="text-brand-primary">end to end.</span>
        </h1>
        <p class="text-body md:text-lg text-grey-600 leading-relaxed max-w-[58ch] mt-5">
          The exact path from a raw crawled price to the headline figure — every step the tool takes, in order — and how each view reads it. Every number below is an illustrative, real-shaped example; the arithmetic is what the tool actually runs.
        </p>
      </div>

      <div class="animate-fade-in-up stagger-1">
        <PIMeter :model-value="SAMPLE_PI" />
        <p class="flex items-center gap-2 text-micro text-grey-400 mt-3">
          <Zap class="w-3.5 h-3.5 text-brand-primary" />
          PI is the Breadfast price ÷ the competitor's, weighted by quantity. 1.00 is parity; both tails cost money. Drag the handle.
        </p>
      </div>
    </section>

    <!-- ===================== HOW THE NUMBER IS BUILT ===================== -->
    <PipelineWalkthrough />

    <!-- ===================== THE VIEWS ===================== -->
    <section id="views" class="py-16 border-t border-grey-200/70">
      <h2 class="text-3xl md:text-4xl font-semibold tracking-tightish leading-tight max-w-[24ch]">Scan it on one screen. Act on it on the next.</h2>
      <p class="text-body md:text-lg text-grey-600 leading-relaxed max-w-[60ch] mt-4">
        The same table, badge, and filter language runs across every view. Leadership scans for exposure; category managers read the gap down to the FP — without leaving the data.
      </p>

      <!-- Executive -->
      <div class="grid lg:grid-cols-[0.92fr_1.08fr] gap-10 lg:gap-14 items-center py-12">
        <div>
          <span class="inline-flex items-center gap-2 text-caption font-semibold text-grey-500"><span class="w-1.5 h-1.5 rounded-full bg-brand-primary" />Executive</span>
          <h3 class="text-2xl md:text-3xl font-semibold tracking-tightish mt-3">Are we winning, or exposed?</h3>
          <p class="text-body text-grey-600 leading-relaxed max-w-[46ch] mt-3.5">A quick scan for leadership: the blended index, the per-competitor split, and where exposure concentrates geographically — FP by FP.</p>
          <ul class="flex flex-col gap-2.5 mt-5">
            <li v-for="t in execList" :key="t" class="flex gap-2.5 text-caption text-grey-600"><Check class="w-4 h-4 text-brand-primary shrink-0 mt-0.5" />{{ t }}</li>
          </ul>
        </div>
        <!-- viz: blended position + geographic exposure -->
        <div class="flex flex-col gap-4">
          <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 p-6">
            <div class="flex items-center justify-between mb-5">
              <span class="text-caption font-semibold text-grey-600 flex items-center gap-2"><BarChart3 class="w-4 h-4 text-brand-primary" />Blended position</span>
              <span class="text-micro text-grey-400">illustrative</span>
            </div>
            <div class="flex items-center gap-6">
              <div class="relative shrink-0" style="width:150px;height:90px">
                <canvas ref="gauge" width="300" height="180" style="width:150px;height:90px"></canvas>
                <div class="absolute inset-x-0 bottom-0 text-center">
                  <div class="font-mono text-3xl font-semibold" :style="{ color: sample.bold }">{{ SAMPLE_PI.toFixed(2) }}</div>
                  <div class="text-micro uppercase tracking-wide text-grey-400 font-semibold">Slightly pricey</div>
                </div>
              </div>
              <div class="flex-1 flex flex-col gap-3.5">
                <div class="flex items-baseline justify-between gap-2"><span class="text-caption text-grey-600">vs. Talabat</span><span class="font-mono text-caption font-semibold" :class="piTextClass(1.09)">1.09</span></div>
                <div class="flex items-baseline justify-between gap-2"><span class="text-caption text-grey-600">vs. Carrefour</span><span class="font-mono text-caption font-semibold" :class="piTextClass(0.99)">0.99</span></div>
                <div class="flex items-baseline justify-between gap-2"><span class="text-caption text-grey-600">vs. Rabbit</span><span class="font-mono text-caption font-semibold" :class="piTextClass(1.03)">1.03</span></div>
                <div>
                  <div class="flex items-baseline justify-between gap-2 mb-1.5"><span class="text-caption text-grey-600">Catalog mapped</span><span class="font-mono text-caption font-semibold text-grey-900">71%</span></div>
                  <div class="h-1.5 rounded-full bg-paper-2 overflow-hidden"><div class="h-full rounded-full bg-brand-primary" style="width:71%"></div></div>
                </div>
              </div>
            </div>
          </div>
          <!-- Geographic exposure mini -->
          <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 p-6">
            <div class="flex items-center justify-between mb-4">
              <span class="text-caption font-semibold text-grey-600 flex items-center gap-2"><MapPin class="w-4 h-4 text-brand-primary" />Geographic exposure</span>
              <span class="text-micro text-grey-400 inline-flex items-center gap-1"><span class="font-mono text-brand-primary">≈</span> estimated</span>
            </div>
            <table class="w-full text-caption border-separate border-spacing-0">
              <thead>
                <tr class="text-micro uppercase tracking-wide text-grey-400">
                  <th class="text-left font-semibold pb-2.5">FP</th>
                  <th v-for="c in geoComps" :key="c" class="text-center font-semibold pb-2.5">{{ c }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in geo" :key="r.fp">
                  <td class="py-1.5 border-t border-grey-100 text-grey-800 font-medium">{{ r.fp }}</td>
                  <td v-for="(cell, ci) in r.cells" :key="ci" class="py-1.5 border-t border-grey-100 text-center">
                    <span class="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-md font-mono text-micro font-semibold"
                          :class="[piBgClass(cell.pi), piTextClass(cell.pi), cell.est ? 'ring-1 ring-dashed ring-brand-light' : '']">
                      <span v-if="cell.est" class="text-[8px] opacity-80">≈</span><span class="text-[8px]">{{ piArrow(cell.pi) }}</span>{{ cell.pi.toFixed(2) }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Commercial (flipped) -->
      <div class="grid lg:grid-cols-[1.08fr_0.92fr] gap-10 lg:gap-14 items-center py-12 border-t border-grey-100">
        <div class="lg:order-2">
          <span class="inline-flex items-center gap-2 text-caption font-semibold text-grey-500"><span class="w-1.5 h-1.5 rounded-full bg-brand-primary" />Commercial</span>
          <h3 class="text-2xl md:text-3xl font-semibold tracking-tightish mt-3">Read the gap, right down to the FP.</h3>
          <p class="text-body text-grey-600 leading-relaxed max-w-[46ch] mt-3.5">The working surface for category managers. Pivot a subcategory against every competitor, see the PI colored cell by cell, and drill into any product’s FPs to read exactly where the gap is.</p>
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
                    <span class="inline-flex flex-col items-end gap-0.5 px-2 py-1 rounded-lg" :class="[piBgClass(cell.pi), piTextClass(cell.pi)]">
                      <span class="font-mono text-micro opacity-80">EGP {{ cell.price }}</span>
                      <span class="font-mono text-caption font-semibold">{{ piArrow(cell.pi) }} {{ cell.pi.toFixed(2) }}</span>
                    </span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Everything else -->
      <div class="pt-4">
        <h3 class="text-heading font-bold tracking-tightish">Everything else in the working set</h3>
        <p class="text-caption text-grey-500 mt-1.5 max-w-[60ch]">The rest of what the tool does, in the same vocabulary.</p>
        <CapabilityGrid class="mt-5" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { BarChart3, Table2, MapPin, Zap, Check } from 'lucide-vue-next'
import PIMeter from '../components/shared/PIMeter.vue'
import PipelineWalkthrough from '../components/landing/PipelineWalkthrough.vue'
import CapabilityGrid from '../components/landing/CapabilityGrid.vue'
import { piBgClass, piTextClass, piArrow, piToHex, piTreatment } from '../utils/piColor'

// One illustrative headline, carried across the meter, the walkthrough result,
// and the Executive gauge so the page never contradicts itself.
const SAMPLE_PI = 1.06
const sample = piTreatment(SAMPLE_PI)

const execList = ['Blended PI with the diverging gauge', 'Per-competitor blended PI, best to worst', 'Geographic exposure by FP']
const commList = ['Product pivot, PI per competitor per cell', 'Per-product FP detail, with Min/Max PI', 'Drill from subcategory to FP']

// Mini pivot — PI numeric; colors/arrows resolved through the real piColor scale.
const pivot = [
  { name: 'Juhayna Full Cream', cells: [
    { price: 62, pi: 1.11 }, { price: 58, pi: 1.02 }, { price: 55, pi: 0.93 },
  ] },
  { name: 'Almarai Low Fat', cells: [
    { price: 64, pi: 1.01 }, { price: 60, pi: 1.07 }, { price: 63, pi: 1.00 },
  ] },
]

// Geographic-exposure mini — one estimated (≈) cell.
const geoComps = ['Talabat', 'Carrefour', 'Rabbit']
const geo = [
  { fp: 'Maadi FP #2', cells: [{ pi: 1.09 }, { pi: 0.99 }, { pi: 1.04 }] },
  { fp: 'New Cairo FP #5', cells: [{ pi: 1.12 }, { pi: 1.01, est: true }, { pi: 0.97 }] },
  { fp: 'Heliopolis FP #3', cells: [{ pi: 1.06 }, { pi: 0.98 }, { pi: 1.03 }] },
]

// Executive gauge: the same diverging scale the app uses, drawn from piToHex so
// the colors are byte-faithful to the live gauge. Needle at the sample PI.
const gauge = ref(null)
onMounted(() => {
  const c = gauge.value
  if (!c) return
  const ctx = c.getContext('2d')
  const cx = 150, cy = 160, r = 120
  const seg = 120
  for (let i = 0; i < seg; i++) {
    const t0 = i / seg
    ctx.beginPath()
    ctx.strokeStyle = piToHex(0.70 + t0 * 0.60)  // map arc position to PI ∈ [0.70, 1.30]
    ctx.lineWidth = 15
    ctx.arc(cx, cy, r, Math.PI + t0 * Math.PI, Math.PI + (i + 1) / seg * Math.PI)
    ctx.stroke()
  }
  const p = (SAMPLE_PI - 0.70) / 0.60, ang = Math.PI + p * Math.PI
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(ang)
  ctx.beginPath(); ctx.moveTo(-8, 0); ctx.lineTo(r - 22, 0); ctx.lineWidth = 4; ctx.lineCap = 'round'; ctx.strokeStyle = '#1C1622'; ctx.stroke()
  ctx.restore()
  ctx.beginPath(); ctx.arc(cx, cy, 7, 0, 2 * Math.PI); ctx.fillStyle = '#1C1622'; ctx.fill()
  ctx.beginPath(); ctx.arc(cx, cy, 3.2, 0, 2 * Math.PI); ctx.fillStyle = '#fff'; ctx.fill()
})
</script>
