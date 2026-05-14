<template>
  <div class="flex gap-3">
    <KpiCard
      label="Total Crawled"
      :value="kpis?.total_crawled ?? 0"
      format="number"
      :icon="Database"
      icon-bg="bg-grey-100"
      :stagger-index="0"
    />
    <KpiCard
      label="Mapped BF Products"
      :value="kpis?.mapped_bf ?? 0"
      format="number"
      :icon="GitCompareArrows"
      icon-bg="bg-green-50"
      :stagger-index="1"
    />
    <KpiCard
      label="Mapped Competitor"
      :value="kpis?.mapped_competitor ?? 0"
      format="number"
      :icon="Link"
      icon-bg="bg-amber-50"
      :stagger-index="2"
    />
    <KpiCard
      label="Mapping Rate"
      :value="kpis?.mapping_rate ?? 0"
      format="percent"
      :icon="Percent"
      icon-bg="bg-brand-50"
      :stagger-index="3"
    />
    <KpiCard
      label="Fresh ≤7d"
      :value="kpis?.fresh ?? 0"
      format="number"
      :icon="CalendarClock"
      icon-bg="bg-blue-50"
      :stagger-index="4"
    />
  </div>
</template>

<script setup>
import KpiCard from '../layout/KpiCard.vue'
import { Database, GitCompareArrows, Link, Percent, CalendarClock } from 'lucide-vue-next'

defineProps({
  kpis: { type: Object, default: null },
})
</script>
