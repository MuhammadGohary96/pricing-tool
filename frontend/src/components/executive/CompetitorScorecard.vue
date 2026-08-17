<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2 min-w-0">
        <LayoutList class="w-4 h-4 text-brand-primary shrink-0" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">By competitor</span>
        <span class="text-caption text-grey-400">three questions, three tables</span>
      </div>
      <ExportButton :fetcher="exportData" label="Export Excel" filename="Competitor_Scorecard.xlsx" />
    </div>

    <p v-if="!isSupermarket" class="px-4 py-2 text-caption text-grey-500 bg-grey-50/70 border-b border-grey-100">
      <Info class="w-3.5 h-3.5 inline -mt-0.5 text-grey-400" />
      Showing all verticals. Set <strong>Vertical → Supermarket</strong> above to match the
      <em>excl. beauty</em> brand-portfolio workbook.
    </p>

    <template v-if="rows.length">
      <!-- One panel, three tables. Sixteen columns under a grouped header asked a
           reader to hold three unrelated questions at once; each table now asks
           one, and because each is only 4-9 wide none of them hides anything. -->

      <!-- ── 1 ▸ ARE WE PRICED RIGHT ─────────────────────────────────────── -->
      <SectionHead icon="price" title="Price position"
                   sub="what we charge against what they charge" />
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="bg-grey-50 border-b border-grey-100">
              <th :class="TH_L" class="sticky left-0 bg-grey-50 z-10">Competitor</th>
              <th :class="TH_R">
                <span :class="HDR">Blended PI
                  <HelpTooltip text="Quantity-weighted Breadfast price divided by competitor price. Above 1.00 means BREADFAST IS MORE EXPENSIVE. Both tails matter." />
                </span>
              </th>
              <!-- Named "Priced", then "Util %", now Confidence %: how much of the
                   revenue-weighted range the PI beside it is actually built on. -->
              <th :class="TH_C" style="min-width: 128px">
                <span :class="HDR">Confidence %
                  <HelpTooltip text="Used ÷ Eligible. How much of our revenue-weighted range the Blended PI beside it is built on — a PI from 6% of the range is a different claim from one from 42%." />
                </span>
              </th>
              <!-- The funnel in order, so a low Confidence % can be diagnosed:
                   the drop from Eligible to Mapped is a matching problem, the
                   drop from Mapped to Used is a freshness one. -->
              <th :class="TH_R">
                <span :class="HDR">Our SKUs
                  <HelpTooltip text="Our whole tracked range in scope. Eligible beside it is the subset worth pricing against — the drop between them is by design, not missing data." />
                </span>
              </th>
              <th :class="TH_R">
                <span :class="HDR">Eligible
                  <HelpTooltip text="Our top-80%-of-revenue range, excluding anything with no sellable price. The denominator of Confidence %. Identical on every competitor row by construction — that is correct, not a bug." />
                </span>
              </th>
              <th :class="TH_R">
                <span :class="HDR">Mapped
                  <HelpTooltip text="Of those eligible products, how many are matched here. Everything lost between Eligible and this is a MATCHING gap; between this and Used, a FRESHNESS one." />
                </span>
              </th>
              <th :class="TH_R">
                <span :class="HDR">Used
                  <HelpTooltip text="Our eligible products that actually carry a PI — mapped AND priced recently on both sides. The NUMERATOR behind Confidence %." />
                </span>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-grey-50">
            <tr v-for="row in rows" :key="row.competitor_name" :class="ROW"
                :title="rowTitle(row)" @click="$emit('select-competitor', row.competitor_name)">
              <Competitor :row="row" />
              <td class="px-4 py-3 text-right">
                <span v-if="row.blended_pi != null"
                      class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-mono text-body font-bold"
                      :class="piBgClass(row.blended_pi)">
                  <span :class="piTextClass(row.blended_pi)">{{ piArrow(row.blended_pi) }}</span>
                  {{ row.blended_pi.toFixed(2) }}
                </span>
                <span v-else class="text-grey-300">—</span>
              </td>
              <td class="px-4 py-3"><Bar :pct="row.priced_pct" /></td>
              <td :class="[TD_N, 'text-grey-500']">{{ n(row.bf_products) }}</td>
              <td :class="[TD_N, 'text-grey-600']">{{ n(row.eligible_products) }}</td>
              <td :class="[TD_N, 'text-grey-700']" :title="mappedEligibleTitle(row)">{{ n(row.mapped_eligible) }}</td>
              <td :class="[TD_N, 'text-grey-700 font-semibold']" :title="usedTitle(row)">{{ n(row.used_products) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── 2 ▸ HOW MUCH CAN WE EVEN COMPARE ────────────────────────────── -->
      <SectionHead icon="mapping" title="Mapping coverage"
                   sub="how much of our range is matched, and how much can be">
        <!-- Summaries of THIS table, beside the table they summarise. -->
        <div v-if="addressablePct != null" class="flex items-baseline gap-1.5">
          <span class="text-caption text-grey-500">Addressable</span>
          <span class="font-mono text-body font-bold text-grey-900 tabular-nums">{{ addressablePct }}%</span>
          <HelpTooltip text="Mapped over what CAN be mapped, pooled across every competitor. Products the matcher positively rejected leave the denominator." />
        </div>
        <div v-if="freshPct != null" class="flex items-baseline gap-1.5">
          <span class="text-caption text-grey-500">Benchmark freshness</span>
          <span class="font-mono text-body font-bold tabular-nums"
                :class="freshPct < 80 ? 'text-amber-600' : 'text-grey-900'">{{ freshPct }}%</span>
          <HelpTooltip text="Share of our matches whose competitor product was seen in the last 7 days. A match that has gone quiet is a benchmark quietly going stale." />
        </div>
        <!-- Sixteen columns is right for the manager who lives in this table and
             hostile to anyone scanning it. Says WHAT it hides and HOW MANY, because
             a control that only says "detail" gives no reason to press it, and
             columns hidden without a count read as columns that do not exist. -->
        <button type="button"
                class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-caption font-semibold ring-1 active:scale-[0.97] transition-[transform,background-color,box-shadow] duration-200 ease-premium"
                :class="detailed
                  ? 'bg-brand-primary text-white ring-brand-primary hover:bg-brand-dark'
                  : 'bg-brand-50 text-brand-primary ring-brand-light/60 hover:bg-brand-lightest hover:ring-brand-light'"
                :aria-pressed="detailed"
                :title="detailed
                  ? `Show the main columns only, hiding ${DETAIL_COLUMNS.length}: ${DETAIL_COLUMNS.join(', ')}`
                  : `Show all columns — ${DETAIL_COLUMNS.length} more: ${DETAIL_COLUMNS.join(', ')}`"
                @click="toggleDetail">
          <component :is="detailed ? Minus : Plus" class="w-3.5 h-3.5" />
          {{ detailed ? 'Main columns only' : 'Show all columns' }}
        </button>
      </SectionHead>
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <!-- The one table that keeps a grouped header, because it now runs the
                 SAME chain twice: base -> mapped -> rate -> rejected -> addressable.
                 Once over everything we sell, once over just the brands they
                 stock. Without the group row the two "No-match" columns are
                 indistinguishable. -->
            <tr class="bg-grey-50 border-b border-grey-100">
              <th :class="TH_L" rowspan="2" class="sticky left-0 bg-grey-50 z-10 align-bottom">Competitor</th>
              <th :class="GROUP" :colspan="detailed ? 8 : 3">All brands</th>
              <th :class="[GROUP, 'border-l border-grey-200']" :colspan="detailed ? 8 : 4">
                In brands they carry
                <HelpTooltip text="The same eight columns restricted to products whose brand this competitor stocks — the only part of our range matching can ever reach." />
              </th>
            </tr>
            <tr class="bg-grey-50 border-b border-grey-100">
              <th :class="TH_R">Our SKUs</th>
              <th v-if="detailed" :class="TH_R">Mapped</th>
              <th v-if="detailed" :class="TH_R">
                <span :class="HDR">Fresh
                  <HelpTooltip text="Mapped AND the competitor product was seen in the last 7 days. A match that has gone quiet is a benchmark quietly going stale." />
                </span>
              </th>
              <th :class="TH_C" style="min-width: 112px">Mapped %</th>
              <th v-if="detailed" :class="TH_R">
                <span :class="HDR">No-match
                  <HelpTooltip text="Our products the matcher positively REJECTED here — it looked at every candidate and turned them all down. Subtracted from Our SKUs to give Addressable, so these leave the denominator rather than counting against it." />
                </span>
              </th>
              <th v-if="detailed" :class="TH_R">
                <span :class="HDR">Addressable
                  <HelpTooltip text="Our SKUs minus confirmed no-match: the products it is still possible to map. The DENOMINATOR of Addressable %, with Mapped as its numerator." />
                </span>
              </th>
              <th :class="TH_C" style="min-width: 112px">
                <span :class="HDR">Addr %
                  <HelpTooltip text="Mapped ÷ Addressable. A competitor at 30% mapped but 100% addressable is finished, not behind." />
                </span>
              </th>
              <th v-if="detailed" :class="TH_R">
                <span :class="HDR">Potential
                  <HelpTooltip text="Unmatched products with a candidate at similarity ≥ 0.85 — the matcher never ruled them out, so this is the part of the backlog most likely to be a genuine miss." />
                </span>
              </th>

              <th v-if="detailed" :class="[TH_R, 'border-l border-grey-200']">
                <span :class="HDR">Our SKUs
                  <HelpTooltip text="Our products whose brand this competitor also carries — the base of everything to its right, and the only part of our range matching can ever reach." />
                </span>
              </th>
              <th :class="[TH_R, detailed ? '' : 'border-l border-grey-200']">
                <span :class="HDR">of our range
                  <HelpTooltip text="The column to its left ÷ Our SKUs. How much of what we sell is even in brands they stock; the rest cannot be matched at any effort." />
                </span>
              </th>
              <th v-if="detailed" :class="TH_R">Mapped</th>
              <th :class="TH_C" style="min-width: 112px">
                <span :class="HDR">Mapped %
                  <HelpTooltip text="Mapped ÷ Our SKUs, both within shared brands. The realistic target for matching effort: the gap between this and the Mapped % on the left is assortment, not backlog." />
                </span>
              </th>
              <th v-if="detailed" :class="TH_R">
                <span :class="HDR">No-match
                  <HelpTooltip text="Confirmed no-match within shared brands: they stock the brand, and the matcher still rejected every candidate for this item." />
                </span>
              </th>
              <th v-if="detailed" :class="TH_R">
                <span :class="HDR">Addressable
                  <HelpTooltip text="Products in brands they carry, minus the ones positively rejected. The tightest honest denominator on the page." />
                </span>
              </th>
              <th :class="TH_C" style="min-width: 112px">
                <span :class="HDR">Addr %
                  <HelpTooltip text="THE CEILING: mapped over what is left once you drop both the brands they do not stock and the items they positively rejected. Anything short of 100% here is work that can actually be done." />
                </span>
              </th>
              <th :class="TH_R">
                <span :class="HDR">Potential
                  <HelpTooltip text="Potential matches inside brands they carry — reachable, unrejected, strong candidate. The tightest definition of workable backlog on the page." />
                </span>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-grey-50">
            <tr v-for="row in rows" :key="row.competitor_name" :class="ROW"
                :title="rowTitle(row)" @click="$emit('select-competitor', row.competitor_name)">
              <Competitor :row="row" />
              <td :class="[TD_N, 'text-grey-700']">{{ n(row.bf_products) }}</td>
              <td v-if="detailed" :class="[TD_N, 'text-green-600 font-semibold']">{{ n(row.matched) }}</td>
              <td v-if="detailed" :class="[TD_N, row.matched_fresh === 0 && row.matched > 0 ? 'text-red-500 font-semibold' : 'text-grey-600']"
                  :title="staleTitle(row)">{{ n(row.matched_fresh) }}</td>
              <td class="px-4 py-3"><Bar :pct="row.mapping_pct" /></td>
              <td v-if="detailed" :class="[TD_N, 'text-grey-500']">{{ n(row.confirmed_no_match) }}</td>
              <td v-if="detailed" :class="[TD_N, 'text-grey-700']">{{ n(row.addressable) }}</td>
              <td class="px-4 py-3"><Bar :pct="row.addressable_pct" /></td>
              <td v-if="detailed" :class="[TD_N, 'text-amber-600']">{{ n(row.potential_match) }}</td>

              <td v-if="detailed" :class="[TD_N, 'border-l border-grey-100 text-grey-700']">{{ n(row.shared_brand_products) }}</td>
              <td :class="[TD_N, 'text-grey-500', detailed ? '' : 'border-l border-grey-100']">{{ pct(row.shared_brand_pct) }}</td>
              <td v-if="detailed" :class="[TD_N, 'text-green-600 font-semibold']">{{ n(row.matched_shared_brand) }}</td>
              <td class="px-4 py-3"><Bar :pct="row.mapping_pct_shared" /></td>
              <td v-if="detailed" :class="[TD_N, 'text-grey-500']">{{ n(row.confirmed_no_match_shared) }}</td>
              <td v-if="detailed" :class="[TD_N, 'text-grey-700']">{{ n(row.addressable_shared) }}</td>
              <td class="px-4 py-3"><Bar :pct="row.addressable_pct_shared" /></td>
              <td :class="[TD_N, 'text-amber-600 font-semibold']" :title="potentialTitle(row)">{{ n(row.potential_match_shared) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── 3 ▸ WHOSE SHELF IS IT ───────────────────────────────────────── -->
      <SectionHead icon="assortment" title="Assortment gap"
                   sub="what they stock that we don't, and the reverse">
        <button type="button"
                class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-caption font-semibold ring-1 active:scale-[0.97] transition-[transform,background-color,box-shadow] duration-200 ease-premium"
                :class="assortDetail
                  ? 'bg-brand-primary text-white ring-brand-primary hover:bg-brand-dark'
                  : 'bg-brand-50 text-brand-primary ring-brand-light/60 hover:bg-brand-lightest hover:ring-brand-light'"
                :aria-pressed="assortDetail"
                :title="assortDetail
                  ? `Show the main columns only, hiding ${ASSORT_COLUMNS.length}: ${ASSORT_COLUMNS.join(', ')}`
                  : `Show all columns — ${ASSORT_COLUMNS.length} more: ${ASSORT_COLUMNS.join(', ')}`"
                @click="toggleAssort">
          <component :is="assortDetail ? Minus : Plus" class="w-3.5 h-3.5" />
          {{ assortDetail ? 'Main columns only' : 'Show all columns' }}
        </button>
      </SectionHead>
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <!-- Same shape as Mapping coverage: one chain run twice, once over
                 everything and once over brands they actually carry. Both blocks
                 close the same two partitions --
                   Both + Both delisted + Ours only = Our SKUs
                   Both(theirs) + They only        = Their catalogue
                 -- which is why the shared block uses the paired/unpaired counts
                 rather than the BigQuery brand-label scalar. -->
            <tr class="bg-grey-50 border-b border-grey-100">
              <th :class="TH_L" rowspan="2" class="sticky left-0 bg-grey-50 z-10 align-bottom">Competitor</th>
              <th :class="GROUP" :colspan="assortDetail ? 6 : 4">All brands</th>
              <th :class="[GROUP, 'border-l border-grey-200']" :colspan="assortDetail ? 6 : 4">
                In brands they carry
                <HelpTooltip text="The same six columns restricted to brands both of us stock. Everything outside them is a brand one of us carries and the other does not — assortment, not a matching gap." />
              </th>
              <th :class="[GROUP, 'border-l border-grey-200']" colspan="3">Shape</th>
            </tr>
            <tr class="bg-grey-50 border-b border-grey-100">
              <th :class="TH_R">
                <span :class="HDR">Our SKUs
                  <HelpTooltip text="Our whole tracked range in scope. Both + Both delisted + Ours only add back to it exactly." />
                </span>
              </th>
              <th v-if="assortDetail" :class="TH_R">
                <span :class="HDR">Both
                  <HelpTooltip text="Our products matched to something they still list. Counted on OUR side, so it is not the paired half of their catalogue — several of ours can share one of their listings." />
                </span>
              </th>
              <th v-if="assortDetail" :class="TH_R">
                <span :class="HDR">Both, delisted
                  <HelpTooltip text="Matched, but they have not listed it in 7 days. Still mapped on our side and gone from their shelf, so the benchmark is historical rather than current." />
                </span>
              </th>
              <th :class="TH_R">
                <span :class="HDR">Ours only
                  <HelpTooltip text="Our SKUs minus Mapped. A CEILING, not a work queue: what they genuinely do not stock together with what we failed to match. Hover a row for the split." />
                </span>
              </th>
              <th :class="TH_R">
                <span :class="HDR">Their catalogue
                  <HelpTooltip :text="catalogueHelp" />
                </span>
                <span class="block text-micro font-normal normal-case tracking-normal"
                      :class="isNarrowed ? 'text-brand-primary' : 'text-grey-400'">{{ catalogueBasis }}</span>
              </th>
              <th :class="TH_R">
                <span :class="HDR">They only
                  <HelpTooltip text="Their products with no link to anything in our tracked range. NEVER sum this across views: one of their products bridges to several of our subcategories, so the total double-counts." />
                </span>
              </th>

              <th :class="[TH_R, 'border-l border-grey-200']">
                <span :class="HDR">Our SKUs
                  <HelpTooltip text="Our products whose brand this competitor also carries — the only part of our range matching can ever reach." />
                </span>
              </th>
              <th v-if="assortDetail" :class="TH_R">Both</th>
              <th v-if="assortDetail" :class="TH_R">Both, delisted</th>
              <th :class="TH_R">
                <span :class="HDR">Ours only
                  <HelpTooltip text="Unmatched inside brands they carry. Unlike the all-brands column this cannot be blamed on assortment — they stock the brand and we still have no match." />
                </span>
              </th>
              <th :class="TH_R">
                <span :class="HDR">Their catalogue
                  <HelpTooltip text="Their live catalogue inside brands we also carry, counted the same way as the all-brands column: the products of theirs we matched plus the products of theirs we did not." />
                </span>
              </th>
              <th :class="TH_R">They only</th>

              <th :class="[TH_R, 'border-l border-grey-200']">
                <span :class="HDR">Overlap %
                  <HelpTooltip text="The shared middle over the whole combined assortment: Mapped ÷ (Ours only + Mapped + They only). Low overlap with a big range means a different game, not worse coverage." />
                </span>
              </th>
              <th :class="TH_R">
                <span :class="HDR">Their range
                  <HelpTooltip text="Their in-scope catalogue ÷ our SKUs. Above 1.00 they carry more than we do." />
                </span>
              </th>
              <th :class="TH_C" style="min-width: 168px">
                <span :class="HDR">Brands: shared · by match / only ours / only theirs
                  <HelpTooltip text="Brands we share, of which proved BY MATCH — a subset, not a fourth bucket. Then only-ours and only-theirs, the last an upper bound since variants are not collapsed." />
                </span>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-grey-50">
            <tr v-for="row in rows" :key="row.competitor_name" :class="ROW"
                :title="rowTitle(row)" @click="$emit('select-competitor', row.competitor_name)">
              <Competitor :row="row" />
              <td :class="[TD_N, 'text-grey-500']">{{ n(row.bf_products) }}</td>
              <td v-if="assortDetail" :class="[TD_N, 'text-green-600 font-semibold']" :title="bothTitle(row)">{{ n(bothLive(row)) }}</td>
              <td v-if="assortDetail" :class="[TD_N, row.mapped_comp_delisted ? 'text-grey-500' : 'text-grey-300']">{{ n(row.mapped_comp_delisted) }}</td>
              <td :class="[TD_N, 'text-brand-primary font-semibold']" :title="ourOnlyTitle(row)">{{ n(row.our_only_products) }}</td>
              <td :class="[TD_N, 'text-grey-600']" :title="catalogueTitle(row)">{{ n(catalogueVal(row)) }}</td>
              <td :class="[TD_N, 'text-amber-700 font-semibold']">{{ n(row.comp_only_products) }}</td>

              <td :class="[TD_N, 'border-l border-grey-100 text-grey-500']" :title="sharedBothTitle(row)">{{ n(row.shared_brand_products) }}</td>
              <td v-if="assortDetail" :class="[TD_N, 'text-green-600 font-semibold']">{{ n(bothLiveShared(row)) }}</td>
              <td v-if="assortDetail" :class="[TD_N, row.mapped_comp_delisted_shared ? 'text-grey-500' : 'text-grey-300']">{{ n(row.mapped_comp_delisted_shared) }}</td>
              <td :class="[TD_N, 'text-brand-primary font-semibold']">{{ n(oursOnlyShared(row)) }}</td>
              <td :class="[TD_N, 'text-grey-600']">{{ n(row.comp_catalogue_shared) }}</td>
              <td :class="[TD_N, 'text-amber-700 font-semibold']">{{ n(row.comp_only_shared) }}</td>

              <td :class="[TD_N, 'border-l border-grey-100 text-grey-700']">
                <template v-if="row.has_catalogue">{{ overlapPct(row) }}%</template>
                <span v-else class="text-red-400 text-caption font-sans">not measurable</span>
              </td>
              <td :class="[TD_N, row.has_catalogue ? 'text-grey-700' : 'text-grey-300']">
                {{ row.has_catalogue ? `${breadth(row)}×` : '—' }}
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-1 text-caption font-mono">
                  <span class="px-1.5 py-0.5 rounded bg-green-50 text-green-700" title="Brands both of us carry">{{ row.shared_brands }}</span>
                  <!-- Middle dot, not a slash: this one is inside the number to
                       its left, and a slash would read as a fourth bucket. -->
                  <span class="text-grey-300">·</span>
                  <span class="px-1.5 py-0.5 rounded ring-1 ring-green-200 text-green-700"
                        :title="`${row.shared_by_match_brands} of those ${row.shared_brands} shared brands are named differently on each side — proved by matching products, not by the label.`">
                    {{ row.shared_by_match_brands }}
                  </span>
                  <span class="text-grey-300">/</span>
                  <span class="px-1.5 py-0.5 rounded bg-brand-50 text-brand-primary" title="Brands only we carry">{{ row.bf_only_brands }}</span>
                  <span class="text-grey-300">/</span>
                  <span class="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700" title="Brands only they carry. Name variants are not collapsed, so this is an upper bound.">{{ row.comp_only_brands }}</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <EmptyState v-else message="No competitor data for the current filters" />
  </div>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import { LayoutList, Info, Plus, Minus, Scale, Link2, PackageSearch } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'
import EmptyState from '../shared/EmptyState.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import { piTextClass, piBgClass, piArrow } from '../../utils/piColor'

const props = defineProps({
  data: { type: Array, default: () => [] },
  /** mapping_progress rows, keyed by competitor, for the hover breakdown. */
  mappingProgress: { type: Array, default: () => [] },
  vertical: { type: String, default: '' },
  /** '' | 'shared' — switches the catalogue column onto the shared-brand basis. */
  brandScope: { type: String, default: '' },
  /** Supplied by the view, which owns the filter params. Takes the competitor
      names on screen and resolves to { blob, filename }. */
  exportFetcher: { type: Function, default: null },
})
defineEmits(['select-competitor'])

const GROUP = 'px-4 py-1.5 text-center text-micro font-bold uppercase tracking-wide text-grey-400'
const TH_L = 'px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_R = 'px-4 py-2 text-right text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_C = 'px-4 py-2 text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TD_N = 'px-4 py-3 text-right text-body font-mono'
const HDR = 'inline-flex items-center gap-1'
const ROW = 'hover:bg-brand-50 transition-colors cursor-pointer'

// Named here rather than only in the template, so the button can say how many
// columns it hides -- and so this list cannot drift from the v-ifs without
// someone noticing the count is wrong.
const DETAIL_COLUMNS = [
  'Mapped', 'Fresh', 'No-match', 'Addressable', 'Potential',
  'Our SKUs (shared)', 'Mapped (shared)', 'No-match (shared)', 'Addressable (shared)',
]

// Remembered, because a daily reader should not re-set it every morning.
// Defaults to SHOWN: these columns were asked for, and hiding them on first load
// would read as them never having arrived.
const detailed = ref(localStorage.getItem('exec-mapping-detail') !== '0')
function toggleDetail() {
  detailed.value = !detailed.value
  try { localStorage.setItem('exec-mapping-detail', detailed.value ? '1' : '0') } catch {}
}

// One entry per folded column, so the button's count cannot lie.
// One entry per column the main view leaves out, so the count cannot lie.
const ASSORT_COLUMNS = [
  'Both', 'Both delisted', 'Both (shared brands)', 'Both delisted (shared brands)',
]
const assortDetail = ref(localStorage.getItem('exec-assortment-detail') !== '0')
function toggleAssort() {
  assortDetail.value = !assortDetail.value
  try { localStorage.setItem('exec-assortment-detail', assortDetail.value ? '1' : '0') } catch {}
}

const ICONS = { price: Scale, mapping: Link2, assortment: PackageSearch }

// Each table's own title bar. Tinted rather than white so the three read as
// sections of one panel instead of three panels that lost their borders.
const SectionHead = (p, { slots }) => h('div', {
  class: 'px-4 py-2 bg-grey-50/60 border-y border-grey-100 flex items-center justify-between gap-3 flex-wrap',
}, [
  h('div', { class: 'flex items-center gap-2 min-w-0' }, [
    h(ICONS[p.icon], { class: 'w-3.5 h-3.5 text-brand-primary shrink-0' }),
    h('span', { class: 'text-caption font-bold text-grey-800 uppercase tracking-wide' }, p.title),
    h('span', { class: 'text-caption text-grey-400 truncate' }, p.sub),
  ]),
  slots.default ? h('div', { class: 'flex items-center gap-4 flex-wrap' }, slots.default()) : null,
])

// The one cell all three tables share, so the sticky column can never drift
// out of step between them.
const Competitor = (p) => h('td', { class: 'px-4 py-3 sticky left-0 bg-white z-10' }, [
  h('div', { class: 'flex items-center gap-2' }, [
    h(CompetitorLogo, { name: p.row.competitor_name }),
    h('span', { class: 'text-body font-semibold text-grey-900' }, p.row.competitor_name),
    p.row.has_catalogue ? null : h('span', {
      class: 'px-1.5 py-0.5 rounded text-caption font-semibold bg-red-50 text-red-600 whitespace-nowrap',
      title: 'Nothing crawled into the catalogue in the last 7 days. The competitor-side columns are a collection gap, not an assortment gap; our matching figures are still valid.',
    }, 'no catalogue'),
  ]),
])

const rows = computed(() => props.data || [])
const isSupermarket = computed(() => String(props.vertical).toLowerCase() === 'supermarket')

const mappingByComp = computed(() =>
  Object.fromEntries((props.mappingProgress || []).map(m => [m.competitor_name, m])))

function pooled(numKey, denFn) {
  const r = rows.value
  if (!r.length) return null
  const num = r.reduce((s, x) => s + (x[numKey] || 0), 0)
  const den = r.reduce((s, x) => s + (denFn(x) || 0), 0)
  return den > 0 ? Math.round((num / den) * 1000) / 10 : null
}
const addressablePct = computed(() => pooled('matched', r => r.addressable))
const freshPct = computed(() => pooled('matched_fresh', r => r.matched))

function n(v) { return v == null ? '—' : Number(v).toLocaleString() }
function pct(v) { return v == null ? '—' : `${v}%` }
// Either shared mode: both narrow by brand, so both change what this column means.
const sharedOnly = computed(() => !!props.brandScope)

// Same arithmetic as the butterfly panel below, which is the point: the table
// gives the figure, the picture gives its shape, and they must not disagree.
function overlapPct(row) {
  const union = (row.our_only_products || 0) + (row.matched || 0) + (row.comp_only_products || 0)
  return union ? Math.round((row.matched / union) * 1000) / 10 : 0
}
function breadth(row) {
  return row.bf_products
    ? Math.round(((row.comp_products_in_scope || 0) / row.bf_products) * 100) / 100
    : 0
}

// Their catalogue is counted from the filtered rows — the paired half off our
// side, the unpaired half off theirs — so it narrows like every other column. No
// prop is needed to know whether it has: if the scoped count is below the
// competitor-level total, a filter is biting.
function catalogueVal(row) {
  return row.comp_products_in_scope ?? row.comp_products
}
const isNarrowed = computed(() => rows.value.some(r =>
  r.comp_products_in_scope != null && r.comp_products > 0
  && r.comp_products_in_scope < r.comp_products))

const catalogueBasis = computed(() => {
  if (!isNarrowed.value) return 'all brands'
  return sharedOnly.value ? 'shared brands, in scope' : 'in current scope'
})

const catalogueHelp = computed(() => isNarrowed.value
  ? 'Their live catalogue as narrowed by the filters above: the products of theirs we matched, plus the products of theirs we did not, both counted inside the current scope. Products of theirs that the category bridge cannot attribute to one of our subcategories are excluded as soon as you filter by category or subcategory — they cannot be placed, so counting them would inflate whichever categories you happened to pick. Hover a row for how many were excluded.'
  : 'Their ENTIRE live catalogue, across every category and brand. Filter by category, subcategory or brand scope and this narrows with everything else.')

function catalogueTitle(row) {
  const all = row.comp_products || 0
  const scope = row.comp_products_in_scope ?? all
  if (!all) return `Nothing crawled for ${row.competitor_name}`
  const pct = v => `${Math.round((v / all) * 1000) / 10}%`
  const lines = [
    `${row.competitor_name} live catalogue`,
    `All brands, all categories: ${all.toLocaleString()}`,
  ]
  if (scope !== all) {
    lines.push(`In the current scope: ${scope.toLocaleString()} (${pct(scope)})`)
    lines.push('', `${(all - scope).toLocaleString()} excluded — outside the filters, or with no`,
               'category mapping to attribute them to one of our subcategories.')
  } else {
    lines.push('', 'The matched and unmatched halves account for all of it.')
  }
  return lines.join('\n')
}

// "Ours only" is one number covering three very different situations, and the
// mix is what decides whether it is an assortment story or a matching backlog.
// The three are disjoint and exhaustive by construction.
function ourOnlyTitle(row) {
  const only = row.our_only_products || 0
  if (!only) return `Every one of our SKUs is matched at ${row.competitor_name}`
  const confirmed = row.confirmed_no_match || 0
  const potential = row.potential_match || 0
  const unresolved = Math.max(0, only - confirmed - potential)
  return [
    `${only.toLocaleString()} of our SKUs have no match at ${row.competitor_name}`,
    '',
    `They confirmably do not stock it: ${confirmed.toLocaleString()}`,
    `Likely a matching miss (similarity ≥ 0.85): ${potential.toLocaleString()}`,
    `Never ruled either way: ${unresolved.toLocaleString()}`,
  ].join('\n')
}
// Matched minus the ones they have stopped listing, whole range and shared.
function bothLiveShared(row) {
  return Math.max(0, (row.matched_shared_brand || 0) - (row.mapped_comp_delisted_shared || 0))
}
function oursOnlyShared(row) {
  return Math.max(0, (row.shared_brand_products || 0) - (row.matched_shared_brand || 0))
}

function bothLive(row) {
  return Math.max(0, (row.matched || 0) - (row.mapped_comp_delisted || 0))
}
function bothTitle(row) {
  const live = bothLive(row), del = row.mapped_comp_delisted || 0
  const theirs = row.comp_paired_in_scope || 0
  if (!row.matched) return `Nothing matched at ${row.competitor_name}`
  return [
    `${(row.matched || 0).toLocaleString()} of our products are matched here`,
    `  ${live.toLocaleString()} to something they still list`,
    `  ${del.toLocaleString()} to something they have delisted`,
    '',
    `Those ${live.toLocaleString()} land on ${theirs.toLocaleString()} of their listings —`,
    'several of ours can share one of theirs.',
    '',
    `Both + Both delisted + Ours only = ${(row.bf_products || 0).toLocaleString()} Our SKUs.`,
  ].join('\n')
}

// The two shared-brand columns are the comparable slice of each range, and the
// share they represent is wildly different per competitor -- which is the whole
// argument for reading "They only" against them rather than against the totals.
function sharedBothTitle(row) {
  const ours = row.shared_brand_products || 0
  const theirs = row.comp_products_shared || 0
  const pct = (a, b) => (b ? `${Math.round((a / b) * 1000) / 10}%` : '—')
  return [
    `Comparable slice of each range at ${row.competitor_name}`,
    '',
    `Ours in brands they carry:  ${ours.toLocaleString()} of ${(row.bf_products || 0).toLocaleString()} (${pct(ours, row.bf_products)})`,
    `Theirs in brands we carry:  ${theirs.toLocaleString()} of ${(row.comp_products || 0).toLocaleString()} (${pct(theirs, row.comp_products)})`,
    '',
    'Everything outside these two is a brand one of us stocks and the',
    'other does not — assortment, not a matching backlog.',
  ].join('\n')
}

// The two Potential columns differ by exactly the products whose brand they do
// not stock -- work that can never be done -- so the gap between them is the
// single most useful thing this table says about a backlog.
function potentialTitle(row) {
  const all = row.potential_match || 0
  const shared = row.potential_match_shared || 0
  if (!all) return `Nothing with a strong unmatched candidate at ${row.competitor_name}`
  return [
    `${all.toLocaleString()} potential matches in total`,
    `${shared.toLocaleString()} of them in brands ${row.competitor_name} actually carries`,
    '',
    `${(all - shared).toLocaleString()} are in brands they do not stock — a strong candidate`,
    'there is a false lead, not a backlog item.',
  ].join('\n')
}

// Which of the two drops is bigger says what to do about it.
function mappedEligibleTitle(row) {
  const elig = row.eligible_products || 0
  const mapped = row.mapped_eligible || 0
  const used = row.used_products || 0
  if (!elig) return 'Nothing eligible in this scope'
  const unmatched = elig - mapped
  const stale = mapped - used
  return [
    `${elig.toLocaleString()} eligible → ${mapped.toLocaleString()} mapped → ${used.toLocaleString()} used`,
    '',
    `${unmatched.toLocaleString()} never matched at ${row.competitor_name} — a matching gap`,
    `${stale.toLocaleString()} matched but not priced fresh on both sides — a freshness gap`,
    '',
    unmatched > stale ? 'Matching is the binding constraint here.'
                      : 'Freshness is the binding constraint here.',
  ].join('\n')
}

// Used is bounded twice over — by Eligible and by Matched — and which bound is
// binding says what to do about it: a matching problem or a freshness problem.
function usedTitle(row) {
  const used = row.used_products || 0
  const elig = row.eligible_products || 0
  const matched = row.matched || 0
  if (!used) return `Nothing priced against ${row.competitor_name}`
  return [
    `${used.toLocaleString()} of our products carry a PI against ${row.competitor_name}`,
    `${elig.toLocaleString()} eligible → Confidence ${elig ? Math.round((used / elig) * 1000) / 10 : 0}%`,
    `${matched.toLocaleString()} matched → ${matched ? Math.round((used / matched) * 1000) / 10 : 0}% of matches are priced and fresh`,
  ].join('\n')
}
function staleTitle(row) {
  if (!row.matched) return 'Nothing matched'
  const stale = row.matched - row.matched_fresh
  return stale <= 0
    ? 'Every match was seen in the last 7 days'
    : `${stale.toLocaleString()} of ${row.matched.toLocaleString()} matches have not been seen in 7 days`
}

// The classification split is still the quickest way to see why the unmatched
// remainder is what it is, so it stays on every row of all three tables.
function rowTitle(row) {
  const m = mappingByComp.value[row.competitor_name]
  const head = `${row.competitor_name} — click to open Commercial filtered to this competitor`
  if (!m) return head
  const mapped = (m.mapped_not_pl || 0) + (m.mapped_pl || 0)
  const potential = (m.potential_not_pl || 0) + (m.potential_pl || 0)
  const noPotential = (m.no_potential_not_pl || 0) + (m.no_potential_pl || 0)
  const noMatch = (m.no_match_not_pl || 0) + (m.no_match_pl || 0)
  return [
    head,
    '',
    `Mapped: ${mapped.toLocaleString()}`,
    `Potential match: ${potential.toLocaleString()}`,
    `No likely match: ${noPotential.toLocaleString()}`,
    `Confirmed no match: ${noMatch.toLocaleString()}`,
    m.potential_reach_pct != null ? `Potential reach: ${m.potential_reach_pct}%` : '',
  ].filter(Boolean).join('\n')
}

const Bar = (p) => {
  const v = p.pct
  const color = v == null ? 'bg-grey-200' : v >= 80 ? 'bg-green-500' : v >= 50 ? 'bg-amber-500' : 'bg-red-400'
  const text = v == null ? 'text-grey-300' : v >= 80 ? 'text-green-600' : v >= 50 ? 'text-amber-600' : 'text-red-500'
  return h('div', { class: 'flex items-center gap-2' }, [
    h('div', { class: 'flex-1 h-1.5 bg-grey-100 rounded-full overflow-hidden' }, [
      h('div', { class: `h-full rounded-full transition-all duration-500 ${color}`, style: { width: `${v || 0}%` } }),
    ]),
    h('span', { class: `text-caption font-semibold w-10 text-right ${text}` }, v == null ? '—' : `${v}%`),
  ])
}

// The file is built by the backend — see utils/workbook.js for why. All this
// has to say is which competitors are on screen, since the pills are client-side
// visibility and never reach the query.
function exportData() {
  if (!props.exportFetcher) return []
  return props.exportFetcher(rows.value.map(r => r.competitor_name))
}
</script>
