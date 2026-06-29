<template>
  <div class="grid grid-cols-2 lg:grid-cols-4 rounded-2xl ring-1 ring-grey-200/70 bg-white shadow-panel overflow-hidden">
    <div
      v-for="(c, i) in caps" :key="c.title"
      class="p-5 lg:p-6 border-grey-100"
      :class="[
        (i % 2 === 0) ? 'border-r' : '',
        (i % 4 !== 3) ? 'lg:border-r' : '',
        (i < caps.length - 2) ? 'border-b' : '',
        (i < caps.length - (caps.length % 4 || 4)) ? 'lg:border-b' : 'lg:border-b-0',
      ]"
    >
      <component :is="c.icon" class="w-4 h-4 text-brand-primary" :stroke-width="1.75" />
      <h3 class="text-body font-semibold tracking-tightish mt-3">{{ c.title }}</h3>
      <p class="text-micro text-grey-600 leading-relaxed mt-1.5">{{ c.body }}</p>
    </div>
  </div>
</template>

<script setup>
import { Table2, ScatterChart, Layers, ArrowDownUp, Network, Clock, Bookmark, SlidersHorizontal } from 'lucide-vue-next'

const caps = [
  { icon: Table2, title: 'Product pivot', body: 'PI per competitor, cell by cell, colored by the gap.' },
  { icon: ScatterChart, title: 'PI distribution', body: 'The spread of products across the index, not just the average.' },
  { icon: Layers, title: 'Subcategory → FP drill', body: 'From a subcategory down to a single FP in one click.' },
  { icon: ArrowDownUp, title: 'Min / Max PI', body: 'The best and worst competitor for any product, at a glance.' },
  { icon: Network, title: 'Mapping coverage', body: 'How much of the catalog is matched, by competitor and category.' },
  { icon: Clock, title: 'Crawl & freshness', body: 'When each competitor price was last seen, on a timeline.' },
  { icon: Bookmark, title: 'Saved views & export', body: 'Pin a filter set to return to; take any table to CSV.' },
  { icon: SlidersHorizontal, title: 'Filters & estimates', body: 'Slice by category, brand, tier, or FP — and opt into estimated prices.' },
]
</script>
