<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2 min-w-0">
        <ArrowLeftRight class="w-4 h-4 text-brand-primary shrink-0" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Portfolio comparison</span>
        <HelpTooltip text="Our range and one competitor's combined, split into only-ours, both, only-theirs. One scale across rows, so a longer wing is a bigger range. The pale band is matched to something they have delisted." />
      </div>
      <div class="flex items-center gap-3 flex-wrap text-caption">
        <span class="inline-flex items-center gap-1.5 text-grey-600"><span class="w-2.5 h-2.5 rounded-sm bg-brand-primary"></span>Only ours</span>
        <span class="inline-flex items-center gap-1.5 text-grey-600"><span class="w-2.5 h-2.5 rounded-sm bg-green-500"></span>Both</span>
        <span class="inline-flex items-center gap-1.5 text-grey-600"><span class="w-2.5 h-2.5 rounded-sm bg-green-500/30 ring-1 ring-green-600/40"></span>Both, they've delisted it</span>
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
            <!-- The pale band is ours-matched-to-something-they-no-longer-list.
                 It sits on OUR side only, because their side counts live
                 listings and these are by definition not among them. -->
            <div v-if="r.delisted" class="h-full bg-green-500/25 border-y border-green-600/30"
                 :style="{ width: `${r.w.delistedHalf}%` }"
                 :title="`Both carried it, but ${r.name} has not listed it in 7 days: ${r.delisted.toLocaleString()}\nStill counted as mapped on our side; gone from their catalogue.`"></div>
            <div class="h-full bg-green-500" :style="{ width: `${r.w.liveHalf}%` }"></div>
          </div>

          <div class="flex-1 flex justify-start h-6">
            <div class="h-full bg-green-500 flex items-center justify-center overflow-hidden"
                 :style="{ width: `${r.w.liveHalf}%` }"
                 :title="`Both still carry it: ${r.live.toLocaleString()} of ours, matched onto ${r.sharedTheirs.toLocaleString()} of theirs.\nFewer of theirs because several of ours can share one of their listings.`">
              <span v-if="r.w.liveHalf > 10" class="font-mono text-micro font-bold text-white px-1">{{ r.live.toLocaleString() }}</span>
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
        <p v-if="divergence" class="text-caption text-grey-500">
          <strong class="text-grey-700">{{ divergence.name }}</strong>:
          {{ divergence.shared.toLocaleString() }} of our products map onto only
          {{ divergence.sharedTheirs.toLocaleString() }} of theirs.
          <template v-if="divergence.delistedLeads">
            Mostly delisting — <strong class="text-grey-700">{{ divergence.delisted.toLocaleString() }}</strong>
            are matched to something they no longer list, against
            {{ divergence.manyToOne.toLocaleString() }} where several of ours share one listing.
          </template>
          <template v-else>
            Mostly one listing answering several of ours
            ({{ divergence.manyToOne.toLocaleString() }}), with
            {{ divergence.delisted.toLocaleString() }} matched to something they no longer list.
          </template>
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
  // The shared middle is drawn from the LIVE matches, the ones both sides can
  // still be seen to carry. Our delisted matches ride outside it on our side
  // only -- they are ours, matched, and no longer on their shelf.
  const live = r => Math.max(0, (r.matched || 0) - (r.mapped_comp_delisted || 0))
  const half = r => live(r) / 2
  const maxSide = Math.max(...src.map(r =>
    Math.max((r.our_only_products || 0) + (r.mapped_comp_delisted || 0) + half(r),
             (r.comp_only_products || 0) + half(r))), 1)

  return src.map(r => {
    const oursOnly = r.our_only_products || 0
    const shared = r.matched || 0
    const theirsOnly = r.comp_only_products || 0
    // Their side of the SAME matches. It is not the same number as ours, and
    // that difference is the interesting part — see `compression` below.
    const sharedTheirs = Math.max(0, (r.comp_products_in_scope || 0) - theirsOnly)
    // Matched on our side, gone from their catalogue.
    const delisted = r.mapped_comp_delisted || 0
    const union = oursOnly + shared + theirsOnly

    return {
      name: r.competitor_name,
      oursOnly, shared, theirsOnly, sharedTheirs, delisted,
      live: Math.max(0, shared - delisted),
      // A competitor with nothing crawled has no right wing at all, so its
      // overlap would compute to the highest on the page purely by absence.
      // Ranking it first would be the exact opposite of the truth.
      blind: !r.has_catalogue,
      overlap: union ? Math.round(shared / union * 1000) / 10 : 0,
      breadth: r.bf_products ? Math.round((r.comp_products_in_scope || 0) / r.bf_products * 100) / 100 : 0,
      w: {
        oursOnly: (oursOnly / maxSide) * 100,
        delistedHalf: (delisted / maxSide) * 100,
        liveHalf: (half(r) / maxSide) * 100,
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

// Our matched count exceeds their paired count for two quite different reasons,
// and until this was measured the panel asserted the wrong one. At Talabat the
// difference is 1,008: 785 of it is products they have delisted, only 223 is
// several of ours sharing one of their listings. Report whichever dominates.
const divergence = computed(() => {
  const c = measurable.value
    .filter(r => r.sharedTheirs > 0 && r.shared > r.sharedTheirs)
    .sort((a, b) => (b.shared - b.sharedTheirs) - (a.shared - a.sharedTheirs))[0]
  if (!c) return null
  const gap = c.shared - c.sharedTheirs
  const manyToOne = Math.max(0, gap - c.delisted)
  return { ...c, gap, manyToOne, delistedLeads: c.delisted > manyToOne }
})
</script>
