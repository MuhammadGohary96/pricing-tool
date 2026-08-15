<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2 min-w-0">
        <ArrowLeftRight class="w-4 h-4 text-brand-primary shrink-0" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Whose shelf is it on</span>
        <HelpTooltip text="Each row is the combined assortment of us and one competitor, split three ways: only we carry it, both of us do, only they do. Wings share one scale across rows, so a longer wing really is a bigger range — this is the panel that shows Amazon is a different KIND of competitor rather than a worse-covered one. Overlap is the shared middle over the whole combined range." />
      </div>
      <div class="flex items-center gap-3 flex-wrap text-caption">
        <span class="inline-flex items-center gap-1.5 text-grey-600"><span class="w-2.5 h-2.5 rounded-sm bg-brand-primary"></span>Only ours</span>
        <span class="inline-flex items-center gap-1.5 text-grey-600"><span class="w-2.5 h-2.5 rounded-sm bg-green-500"></span>Both</span>
        <span class="inline-flex items-center gap-1.5 text-grey-600"><span class="w-2.5 h-2.5 rounded-sm bg-amber-500"></span>Only theirs</span>
      </div>
    </div>

    <div v-if="rows.length" class="px-4 py-3 flex flex-col gap-2">
      <div v-for="r in rows" :key="r.name"
           class="flex items-center gap-3"
           :class="r.blind ? 'opacity-60' : ''">
        <div class="w-28 shrink-0 flex items-center gap-1.5 min-w-0">
          <CompetitorLogo :name="r.name" />
          <span class="text-caption font-semibold text-grey-800 truncate">{{ r.name }}</span>
        </div>

        <!-- Butterfly: both halves share one scale, so wings compare across rows. -->
        <div class="flex-1 min-w-0 flex items-center">
          <div class="flex-1 flex justify-end h-6">
            <div v-if="r.oursOnly" class="h-full bg-brand-primary flex items-center justify-center rounded-l-md overflow-hidden"
                 :style="{ width: `${r.w.oursOnly}%` }"
                 :title="`Only we carry it: ${r.oursOnly.toLocaleString()}`">
              <span v-if="r.w.oursOnly > 14" class="font-mono text-micro font-bold text-white px-1">{{ r.oursOnly.toLocaleString() }}</span>
            </div>
            <div class="h-full bg-green-500" :style="{ width: `${r.w.sharedHalf}%` }"></div>
          </div>

          <div class="flex-1 flex justify-start h-6">
            <div class="h-full bg-green-500 flex items-center justify-center overflow-hidden"
                 :style="{ width: `${r.w.sharedHalf}%` }"
                 :title="`Both carry it: ${r.shared.toLocaleString()} of ours matched to ${r.sharedTheirs.toLocaleString()} of theirs`">
              <span v-if="r.w.sharedHalf > 10" class="font-mono text-micro font-bold text-white px-1">{{ r.shared.toLocaleString() }}</span>
            </div>
            <div v-if="r.theirsOnly" class="h-full bg-amber-500 flex items-center justify-center rounded-r-md overflow-hidden"
                 :style="{ width: `${r.w.theirsOnly}%` }"
                 :title="`Only they carry it: ${r.theirsOnly.toLocaleString()}`">
              <span v-if="r.w.theirsOnly > 14" class="font-mono text-micro font-bold text-white px-1">{{ r.theirsOnly.toLocaleString() }}</span>
            </div>
          </div>
        </div>

        <div class="w-40 shrink-0 text-right">
          <template v-if="r.blind">
            <div class="text-caption font-semibold text-red-500 leading-tight">not measurable</div>
            <div class="text-micro text-grey-400 leading-tight">no catalogue crawled</div>
          </template>
          <template v-else>
            <div class="font-mono text-body font-bold text-grey-900 tabular-nums leading-none">{{ r.overlap }}%</div>
            <div class="text-micro text-grey-400 leading-tight">
              common ground · their range {{ r.breadth }}×
            </div>
          </template>
        </div>
      </div>

      <div class="mt-1 space-y-1">
        <p v-if="widest" class="text-caption text-grey-500">
          <strong class="text-grey-700">{{ widest.name }}</strong> carries
          {{ widest.breadth }}× our range and shares only
          <strong class="text-grey-700">{{ widest.overlap }}%</strong> of the combined assortment —
          a different kind of competitor, not a worse-covered one.
        </p>
        <p v-if="compression" class="text-caption text-grey-500">
          Matching compresses: {{ compression.shared.toLocaleString() }} of our products map onto
          {{ compression.sharedTheirs.toLocaleString() }} of {{ compression.name }}'s, so their shelf
          holds fewer, larger listings where we hold variants.
        </p>
      </div>
    </div>
    <EmptyState v-else message="No competitor data for the current filters" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ArrowLeftRight } from 'lucide-vue-next'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'
import EmptyState from '../shared/EmptyState.vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const rows = computed(() => {
  const src = (props.data || []).filter(r => r.bf_products)
  if (!src.length) return []

  // One scale for every wing, or a long bar would mean nothing across rows.
  // Each half is measured from the centre of the shared block outwards.
  const half = r => (r.matched || 0) / 2
  const maxSide = Math.max(...src.map(r =>
    Math.max((r.our_only_products || 0) + half(r), (r.comp_only_products || 0) + half(r))), 1)

  return src.map(r => {
    const oursOnly = r.our_only_products || 0
    const shared = r.matched || 0
    const theirsOnly = r.comp_only_products || 0
    // Their side of the SAME matches. It is not the same number as ours, and
    // that difference is the interesting part — see `compression` below.
    const sharedTheirs = Math.max(0, (r.comp_products_in_scope || 0) - theirsOnly)
    const union = oursOnly + shared + theirsOnly

    return {
      name: r.competitor_name,
      oursOnly, shared, theirsOnly, sharedTheirs,
      // A competitor with nothing crawled has no right wing at all, so its
      // overlap would compute to the highest on the page purely by absence.
      // Ranking it first would be the exact opposite of the truth.
      blind: !r.has_catalogue,
      overlap: union ? Math.round(shared / union * 1000) / 10 : 0,
      breadth: r.bf_products ? Math.round((r.comp_products_in_scope || 0) / r.bf_products * 100) / 100 : 0,
      w: {
        oursOnly: (oursOnly / maxSide) * 100,
        sharedHalf: (half(r) / maxSide) * 100,
        theirsOnly: (theirsOnly / maxSide) * 100,
      },
    }
  }).sort((a, b) => (a.blind - b.blind) || (b.overlap - a.overlap))
})

const measurable = computed(() => rows.value.filter(r => !r.blind))

// The competitor whose range most outsizes ours.
const widest = computed(() => {
  if (!measurable.value.length) return null
  const w = measurable.value.reduce((a, b) => (b.breadth > a.breadth ? b : a))
  return w.breadth > 1.5 ? w : null
})

// Many of our products can map onto one of theirs. Where the two counts diverge
// most, their catalogue is coarser than ours — one listing where we hold several
// variants — which is worth knowing before reading any per-product gap.
const compression = computed(() => {
  const c = measurable.value
    .filter(r => r.sharedTheirs > 0 && r.shared > r.sharedTheirs)
    .sort((a, b) => (b.shared - b.sharedTheirs) - (a.shared - a.sharedTheirs))[0]
  return c || null
})
</script>
