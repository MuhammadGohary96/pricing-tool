<template>
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
    <KpiCard
      :value="kpis?.mapping_pct ?? 0"
      format="percent"
      label="Mapped"
      :subtitle="`${fmt(kpis?.matched)} of ${fmt(kpis?.bf_products)} products`"
      :icon="GitCompareArrows"
      icon-bg="bg-green-50"
      :stagger-index="0"
      highlight
    />
    <KpiCard
      :value="kpis?.addressable_pct ?? 0"
      format="percent"
      label="Addressable"
      :subtitle="`excludes ${fmt(kpis?.confirmed_no_match)} confirmed no-match`"
      :icon="Target"
      icon-bg="bg-brand-50"
      :stagger-index="1"
    />
    <KpiCard
      :value="kpis?.comp_only_products ?? 0"
      label="They carry, we don't"
      :subtitle="`${fmt(kpis?.comp_only_bridged)} placed in one of our subcategories`"
      :icon="PackageSearch"
      icon-bg="bg-amber-50"
      :stagger-index="2"
    />
    <KpiCard
      :value="kpis?.our_only ?? 0"
      label="Ours only"
      subtitle="our products with no match here — a ceiling, not all of it is workable"
      :icon="PackageX"
      icon-bg="bg-brand-50"
      :stagger-index="3"
    />
  </div>

  <!-- Brand overlap: a compact second row rather than four more big cards -->
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
    <div
      v-for="(s, i) in strip"
      :key="s.label"
      class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 px-4 py-3 flex items-center gap-3 animate-fade-in-up"
      :style="{ animationDelay: `${0.05 * i}s` }"
    >
      <div class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" :class="s.bg">
        <component :is="s.icon" class="w-4 h-4" :class="s.fg" />
      </div>
      <div class="min-w-0">
        <div class="text-subheading font-bold text-grey-900 tabular-nums leading-tight">{{ fmt(s.value) }}</div>
        <div class="text-caption text-grey-500 truncate">{{ s.label }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import KpiCard from '../layout/KpiCard.vue'
import {
  GitCompareArrows, Target, PackageSearch, PackageX,
  Handshake, Home, Store, Sparkles,
} from 'lucide-vue-next'

const props = defineProps({
  kpis: { type: Object, default: null },
})

const strip = computed(() => [
  { label: 'Shared brands', value: props.kpis?.shared_brands, icon: Handshake, bg: 'bg-green-50', fg: 'text-green-600' },
  { label: 'Brands only we carry', value: props.kpis?.bf_only_brands, icon: Home, bg: 'bg-brand-50', fg: 'text-brand-primary' },
  { label: 'Brands only they carry', value: props.kpis?.comp_only_brands, icon: Store, bg: 'bg-amber-50', fg: 'text-amber-600' },
  { label: 'Brands shared by match', value: props.kpis?.shared_by_match_brands, icon: Sparkles, bg: 'bg-green-50', fg: 'text-green-700', title: 'Of the shared brands, those whose names DISAGREE on the two sides — the overlap was proved by matching at least half their products, not read off the label. Our Froneri is their Nestle and Paradise. Included in Shared brands, not additional to it.' },
])

function fmt(v) {
  if (v == null) return '—'
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })
}
</script>
