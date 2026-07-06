<template>
  <!-- Shared command header — premium, dashboard-scaled. Eyebrow + display
       title with a brand accent, richer subtitle, entrance motion. The #stats
       slot fuses a KPI strip into the same card; #actions sits beside the title. -->
  <section class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden animate-fade-in-up">
    <div
      class="px-6 lg:px-7 pt-6 pb-5 flex flex-wrap items-start justify-between gap-x-6 gap-y-3"
      :class="$slots.stats ? 'border-b border-grey-100' : ''"
    >
      <div class="min-w-0">
        <span v-if="eyebrow" class="text-micro font-semibold uppercase tracking-[0.16em] text-brand-primary">{{ eyebrow }}</span>
        <h1
          class="text-2xl md:text-3xl lg:text-[2.15rem] font-semibold text-grey-900 tracking-tightish leading-[1.08] text-balance"
          :class="eyebrow ? 'mt-2' : ''"
        >
          {{ title }}<template v-if="accent">{{ ' ' }}<span class="text-brand-primary">{{ accent }}</span></template>
        </h1>
        <p v-if="subtitle" class="text-body md:text-lg text-grey-600 leading-relaxed mt-2.5 max-w-[62ch]">{{ subtitle }}</p>
      </div>

      <div v-if="$slots.actions" class="shrink-0">
        <slot name="actions" />
      </div>
    </div>

    <slot name="stats" />
  </section>
</template>

<script setup>
defineProps({
  eyebrow: { type: String, default: '' },
  title: { type: String, required: true },
  accent: { type: String, default: '' },
  subtitle: { type: String, default: '' },
})
</script>
