<template>
  <div class="bg-white rounded-2xl shadow-panel ring-1 ring-grey-200/70 overflow-hidden">
    <div class="px-4 py-3 border-b border-grey-100 flex items-center justify-between gap-3 flex-wrap">
      <div class="flex items-center gap-2">
        <PackageSearch class="w-4 h-4 text-brand-primary" />
        <span class="text-subheading font-bold text-grey-900 tracking-tightish">Products</span>
        <span class="text-caption text-grey-400 ml-1">{{ total.toLocaleString() }} rows</span>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <div class="flex items-center gap-1 bg-grey-50 rounded-lg p-0.5">
          <button
            v-for="opt in SIDES"
            :key="opt.value"
            @click="$emit('side', opt.value)"
            class="px-2.5 py-1 rounded-md text-caption font-semibold transition-colors"
            :class="side === opt.value ? 'bg-white text-grey-900 shadow-sm' : 'text-grey-500 hover:text-grey-700'"
          >{{ opt.label }}</button>
        </div>
        <input
          :value="searchQuery"
          @input="onSearch($event.target.value)"
          type="search"
          :placeholder="side === 'competitor' ? 'Search their products…' : 'Search our products…'"
          class="text-body border border-grey-200 rounded-lg px-3 py-1.5 w-56 focus:outline-none focus:ring-1 focus:ring-brand-primary"
        />
        <ExportButton :fetcher="exportFetcher" label="Export Excel" :filename="`gap_products_${side}.xlsx`" />
      </div>
    </div>

    <div v-if="items.length" class="overflow-x-auto">
      <!-- ── Their products we don't carry ───────────────────────── -->
      <table v-if="side === 'competitor'" class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100">
          <tr>
            <th :class="TH_L">Their product</th>
            <th :class="TH_L">Brand</th>
            <th :class="TH_L">Their category path</th>
            <th :class="TH_L">
              <span class="inline-flex items-center gap-1">
                Placed in our subcategory
                <HelpTooltip text="Inferred from where already-matched products in the same competitor category landed on our side. Confidence is the share of that evidence pointing here." />
              </span>
            </th>
            <th :class="TH_R">Confidence</th>
            <th :class="TH_L">Brand overlap</th>
            <th :class="TH_R">Last seen</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in items" :key="row.competitor_product_key" class="hover:bg-brand-50 transition-colors">
            <td class="px-4 py-3">
              <div class="text-body font-semibold text-grey-900 max-w-[300px] truncate" :title="row.product_name">{{ row.product_name }}</div>
              <div class="text-caption text-grey-400">{{ row.classification }}</div>
            </td>
            <td class="px-4 py-3 text-body text-grey-700">{{ row.brand_name || '—' }}</td>
            <td class="px-4 py-3 text-caption text-grey-500 max-w-[240px] truncate"
                :title="path(row)">{{ path(row) }}</td>
            <td class="px-4 py-3">
              <div v-if="row.sub_category_name" class="text-body text-grey-900">{{ row.sub_category_name }}</div>
              <div v-else class="text-caption text-grey-400 italic">not placed</div>
              <div v-if="row.mapped_bf_sub_categories_all && row.mapped_bf_sub_categories_all !== row.sub_category_name"
                   class="text-caption text-grey-400 truncate max-w-[220px]"
                   :title="row.mapped_bf_sub_categories_all">also: {{ row.mapped_bf_sub_categories_all }}</div>
            </td>
            <td class="px-4 py-3 text-center">
              <span v-if="row.mapped_pct_of_comp_category != null"
                    class="text-caption font-mono px-1.5 py-0.5 rounded"
                    :class="confClass(row.mapped_pct_of_comp_category, row.bridge_level)">
                {{ Math.round(row.mapped_pct_of_comp_category * 100) }}%
              </span>
              <span v-else class="text-grey-300">—</span>
              <div v-if="row.bridge_level === 'parent_l3_fallback'" class="text-caption text-grey-400">via parent</div>
            </td>
            <td class="px-4 py-3">
              <span class="px-2 py-0.5 rounded-md text-caption font-semibold"
                    :class="row.is_shared_brand ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'">
                {{ row.is_shared_brand ? 'We carry this brand' : 'New brand' }}
              </span>
            </td>
            <td class="px-4 py-3 text-center text-caption font-mono text-grey-500">{{ row.comp_last_seen || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- ── Our products and their match state ──────────────────── -->
      <table v-else class="w-full">
        <thead class="bg-grey-50 border-b border-grey-100">
          <tr>
            <th :class="TH_L">Our product</th>
            <th :class="TH_L">
              <span class="inline-flex items-center gap-1">Their product
                <HelpTooltip text="The competitor product this one is matched to, by their name for it. Empty for anything not mapped here — there is no counterpart to name. Searchable: when chasing a match you often only know what they call it." />
              </span>
            </th>
            <th :class="TH_L">Brand</th>
            <th :class="TH_L">
              <span class="inline-flex items-center gap-1">Their brand
                <HelpTooltip text="What this competitor calls the brand, from products we actually matched. Blank where nothing of this brand is mapped here." />
              </span>
            </th>
            <th :class="TH_L">Subcategory</th>
            <th :class="TH_L">Tier</th>
            <th :class="TH_L">Match state</th>
            <th :class="TH_R">Best similarity</th>
            <th :class="TH_R">Our price</th>
            <th :class="TH_R">Their price</th>
            <th :class="TH_C" class="cursor-pointer select-none" @click="$emit('sort', 'sale_PI')">
              <span class="inline-flex items-center gap-1">PI
                <HelpTooltip text="Our price divided by theirs, so ABOVE 1.00 means we are more expensive. Only the mapped products have one — an unmatched product has no competitor price to compare against." />
              </span>
            </th>
            <th :class="TH_C" style="min-width: 150px">
              <span class="inline-flex items-center gap-1">Eligible · Updated · Used
                <HelpTooltip text="A funnel: ELIGIBLE (top 80% of revenue), UPDATED (both prices refreshed recently), USED (carries a PI). Whichever first reads no is why a mapped product moves nothing." />
              </span>
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-grey-50">
          <tr v-for="row in items" :key="row.product_id" class="hover:bg-brand-50 transition-colors">
            <td class="px-4 py-3">
              <div class="text-body font-semibold text-grey-900 max-w-[320px] truncate" :title="row.product_name">{{ row.product_name }}</div>
              <div class="text-caption text-grey-400">{{ row.commercial_category_name }}</div>
            </td>
            <td class="px-4 py-3 max-w-[280px]">
              <div v-if="row.competitor_product_name"
                   class="text-body text-grey-700 truncate" :title="row.competitor_product_name">
                {{ row.competitor_product_name }}
              </div>
              <span v-else class="text-grey-300">—</span>
            </td>
            <td class="px-4 py-3 text-body text-grey-700">
              {{ row.brand_name || '—' }}
              <span v-if="!row.is_shared_brand" class="ml-1 text-caption text-amber-600" title="The competitor does not carry this brand at all">·&nbsp;brand not stocked</span>
              <!-- Only shown when the overlap was PROVED rather than read off the
                   name, because that is the case a reader would otherwise
                   dispute: the two brand strings do not match. -->
              <span v-else-if="row.shared_by_match"
                    class="ml-1 text-caption text-green-700"
                    title="The brand names do not match, but at least half of this brand's products are mapped here — so they stock it under another name.">·&nbsp;by match</span>
            </td>
            <!-- This column is BRAND-level, not product-level: it is what the
                 competitor calls the brand, inferred from whichever products of
                 that brand we did match. On an unmatched row it is therefore
                 context, not a counterpart -- our Breadfast items show "talabat"
                 because the two private labels map to each other, not because
                 that product was matched. Dimmed there so it cannot be misread
                 as this product's twin. -->
            <td class="px-4 py-3 text-caption max-w-[170px]"
                :class="row.is_mapped ? 'text-grey-500' : 'text-grey-300 italic'">
              <span v-if="theirBrands(row).length" :title="theirBrandTitle(row)" class="cursor-help">
                {{ theirBrands(row).slice(0, 2).join(', ')
                }}<span v-if="theirBrands(row).length > 2"
                        class="ml-1 px-1 py-px rounded-full bg-grey-100 text-grey-500 font-semibold"
                  >+{{ theirBrands(row).length - 2 }}</span>
              </span>
              <span v-else class="text-grey-300">—</span>
            </td>
            <td class="px-4 py-3 text-body text-grey-700">{{ row.sub_category_name }}</td>
            <td class="px-4 py-3"><TierBadge v-if="row.global_tier" :tier="row.global_tier" /></td>
            <td class="px-4 py-3">
              <span class="px-2 py-0.5 rounded-md text-caption font-semibold" :class="stateStyle(row)">{{ stateLabel(row) }}</span>
            </td>
            <td class="px-4 py-3 text-center text-body font-mono text-grey-600">
              {{ row.best_similarity != null ? `${Math.round(row.best_similarity * 100)}%` : '—' }}
            </td>
            <td class="px-4 py-3 text-center text-body font-mono text-grey-700">{{ money(row.bf_sale_price) }}</td>
            <td class="px-4 py-3 text-center text-body font-mono text-grey-700">{{ money(row.comp_sale_price) }}</td>
            <td class="px-4 py-3 text-center">
              <span v-if="row.sale_PI != null"
                    class="font-mono text-body font-bold px-1.5 py-0.5 rounded-md"
                    :class="piBgClass(row.sale_PI)">
                <span :class="piTextClass(row.sale_PI)">{{ piArrow(row.sale_PI) }}</span>
                {{ row.sale_PI.toFixed(2) }}
              </span>
              <span v-else class="text-grey-300">—</span>
            </td>
            <!-- Read left to right as a funnel; the first "no" is the reason.
                 Deliberately three marks rather than three columns of ticks: the
                 useful reading is where the chain breaks, not each flag alone. -->
            <td class="px-4 py-3">
              <div class="flex items-center justify-center gap-1" :title="flagTitle(row)">
                <span v-for="f in flags(row)" :key="f.key"
                      class="px-1.5 py-0.5 rounded text-micro font-bold tracking-wide"
                      :class="f.on ? 'bg-green-50 text-green-700' : 'bg-grey-100 text-grey-400'">
                  {{ f.label }}
                </span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <EmptyState v-else message="No products match the current scope" />

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="px-4 py-3 border-t border-grey-100 flex items-center justify-between">
      <span class="text-caption text-grey-500">
        {{ ((page - 1) * pageSize + 1).toLocaleString() }}–{{ Math.min(page * pageSize, total).toLocaleString() }}
        of {{ total.toLocaleString() }}
      </span>
      <div class="flex items-center gap-1">
        <button :disabled="page <= 1" @click="$emit('page', page - 1)" :class="PAGE_BTN">Previous</button>
        <span class="text-caption text-grey-600 px-2">Page {{ page }} / {{ totalPages }}</span>
        <button :disabled="page >= totalPages" @click="$emit('page', page + 1)" :class="PAGE_BTN">Next</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { PackageSearch } from 'lucide-vue-next'
import ExportButton from '../shared/ExportButton.vue'
import EmptyState from '../shared/EmptyState.vue'
import HelpTooltip from '../shared/HelpTooltip.vue'
import TierBadge from '../shared/TierBadge.vue'
import { piTextClass, piBgClass, piArrow } from '../../utils/piColor'

const props = defineProps({
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 },
  side: { type: String, default: 'competitor' },
  searchQuery: { type: String, default: '' },
  exportFetcher: { type: Function, required: true },
})
const emit = defineEmits(['page', 'search', 'side', 'sort'])

const SIDES = [
  { label: "They carry, we don't", value: 'competitor' },
  { label: 'Our products', value: 'breadfast' },
]
const TH_L = 'px-4 py-2 text-left text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_R = 'px-4 py-2 text-center text-caption font-semibold text-grey-500 uppercase tracking-wide'
const TH_C = 'px-4 py-2 text-center text-caption font-semibold text-grey-500 uppercase tracking-wide'
const PAGE_BTN = 'px-3 py-1 text-caption font-semibold rounded-lg border border-grey-200 text-grey-700 hover:bg-grey-50 disabled:opacity-40 disabled:cursor-not-allowed'

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

let searchTimer = null
function onSearch(v) {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => emit('search', v), 350)
}

function n(v) { return v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 }) }
function path(row) {
  return [row.category_level_1, row.category_level_2, row.category_level_3].filter(Boolean).join(' › ') || '—'
}
function confClass(v, level) {
  if (level === 'parent_l3_fallback') return 'bg-grey-100 text-grey-600'
  if (v >= 0.7) return 'bg-green-50 text-green-700'
  if (v >= 0.4) return 'bg-amber-50 text-amber-700'
  return 'bg-grey-100 text-grey-600'
}
// comp_brand_variants is "Nestle:45|Paradise:39", ranked and capped upstream.
// Same encoding the brand table parses; the counts are dropped here because on a
// single product row the question is WHICH brand it landed on, not how many.
function theirBrands(row) {
  const raw = row.comp_brand_variants
  if (!raw) return []
  return String(raw).split('|').map(part => {
    const i = part.lastIndexOf(':')
    return i <= 0 ? '' : part.slice(0, i).trim()
  }).filter(Boolean)
}
function theirBrandTitle(row) {
  const v = theirBrands(row)
  if (!v.length) return ''
  const head = `${row.brand_name} is shelved here as:`
  const foot = row.is_mapped
    ? ''
    : '\n\nBrand-level: this product itself is not matched, so this is what\nthey call the BRAND, not a counterpart for this product.'
  return `${head}\n\n  ${v.join('\n  ')}${foot}`
}

// Eligible -> Updated -> Used, in funnel order.
function flags(row) {
  return [
    { key: 'e', label: 'ELIG', on: !!row.eligible_product },
    { key: 'u', label: 'UPD',  on: !!row.updated },
    { key: 's', label: 'USED', on: !!row.used_product },
  ]
}

// Names the first broken link rather than restating the three marks, because
// that is the whole question: why does a matched product move no number?
function flagTitle(row) {
  if (row.used_product) return 'Carries a PI and feeds the blended figure.'
  if (!row.eligible_product)
    return 'Not eligible — outside the top 80% of revenue, so it never carries a PI.'
  if (!row.updated)
    return 'Eligible, but one side of the price is stale, so it carries no PI.'
  if (!row.is_mapped)
    return 'Eligible and priced, but not matched here — nothing to compare against.'
  return 'Eligible and priced, but not used in the PI.'
}

function money(v) {
  return v == null ? '—' : Number(v).toLocaleString(undefined, {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })
}

function stateLabel(row) {
  if (row.is_mapped) return row.matched_comp_active_7d ? 'Matched' : 'Matched · stale'
  if (row.is_confirmed_no_match) return 'Confirmed no match'
  if (row.is_potential_match) return 'Potential match'
  return 'Unmatched'
}
function stateStyle(row) {
  if (row.is_mapped) return row.matched_comp_active_7d ? 'bg-green-50 text-green-700' : 'bg-grey-100 text-grey-600'
  if (row.is_confirmed_no_match) return 'bg-grey-100 text-grey-500'
  if (row.is_potential_match) return 'bg-amber-50 text-amber-700'
  return 'bg-red-50 text-red-600'
}
</script>
