<template>
  <!--
    Teaching legend for the "both tails bad" PI system. Three swatches only:
    both ends carry a cost; only the center is the target. No swatch implies a
    "good tail." Pulls its colors/glyphs straight from piColor.js so it can
    never drift from the live cells.
  -->
  <div
    class="flex items-center gap-1 rounded-lg ring-1 ring-grey-200/70 bg-white overflow-hidden text-micro"
    role="img"
    aria-label="Price Index legend: both too cheap and too pricey are bad; parity is the target."
  >
    <span
      v-for="seg in segments"
      :key="seg.key"
      class="flex items-center gap-1.5 px-2.5 py-1.5 leading-tight"
      :style="{ background: seg.fill, color: seg.text }"
    >
      <span class="font-mono font-bold" style="font-size:11px">{{ seg.glyph }}</span>
      <span class="font-semibold">{{ seg.title }}</span>
      <span class="opacity-70 hidden sm:inline">{{ seg.note }}</span>
    </span>
  </div>
</template>

<script setup>
import { piTreatment } from '../../utils/piColor'

// Representative values: deep-cheap, parity, deep-pricey. The swatch colors and
// glyphs come from piTreatment so they match the tables/charts exactly.
const cheap = piTreatment(0.82)
const parity = piTreatment(1.0)
const pricey = piTreatment(1.18)

const segments = [
  { key: 'cheap',  fill: cheap.fill,  text: cheap.text,  glyph: '▼', title: 'Too cheap', note: '· margin lost' },
  { key: 'parity', fill: parity.fill, text: parity.text, glyph: '◆', title: 'Parity', note: '· target ✓' },
  { key: 'pricey', fill: pricey.fill, text: pricey.text, glyph: '▲', title: 'Too pricey', note: '· demand risk' },
]
</script>
