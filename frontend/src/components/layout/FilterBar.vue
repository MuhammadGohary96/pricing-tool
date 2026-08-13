<template>
  <div class="bg-white rounded-xl shadow-panel ring-1 ring-grey-200/70 px-5 py-3">
    <!-- Mobile toggle button -->
    <button class="lg:hidden flex items-center gap-1.5 text-body text-grey-600 font-medium mb-2" @click="expanded = !expanded">
      <FilterIcon class="w-4 h-4" />
      Filters
      <span v-if="activeCount > 0" class="text-micro px-1.5 py-px rounded-full bg-brand-primary text-white font-bold">{{ activeCount }}</span>
      <ChevronDown class="w-3.5 h-3.5 transition-transform" :class="expanded ? 'rotate-180' : ''" />
    </button>

    <div :class="['flex items-center gap-3 flex-wrap', expanded ? '' : 'hidden lg:flex']">
      <div class="flex items-center gap-1.5 text-subheading text-grey-500 font-semibold">
        <FilterIcon class="w-4 h-4" />
        Filters
      </div>

      <div class="h-5 w-px bg-grey-200"></div>

      <!-- Vertical (single-select toggle) -->
      <div class="inline-flex items-center gap-1.5">
        <span class="text-body text-grey-500 font-medium">Vertical</span>
        <div class="inline-flex items-center rounded-lg border border-grey-200 overflow-hidden">
          <button
            v-for="opt in verticalOptions"
            :key="opt.value"
            type="button"
            class="px-2.5 py-1.5 text-body font-medium transition-colors border-r border-grey-200 last:border-r-0"
            :class="pending.vertical === opt.value ? 'bg-brand-primary text-white' : 'bg-white text-grey-600 hover:bg-grey-50'"
            @click="pending.vertical = opt.value"
          >{{ opt.label }}</button>
        </div>
      </div>

      <!-- Brand scope: the realistic-ceiling switch. Shared-only answers "of the
           brands they actually stock, how are we doing", which is a different
           question from the raw mapping rate. -->
      <div class="inline-flex items-center gap-1.5">
        <span class="text-body text-grey-500 font-medium">Brands</span>
        <div class="inline-flex items-center rounded-lg border border-grey-200 overflow-hidden">
          <button
            v-for="opt in brandScopeOptions"
            :key="opt.value"
            type="button"
            :title="opt.title"
            class="px-2.5 py-1.5 text-body font-medium transition-colors border-r border-grey-200 last:border-r-0"
            :class="pending.brandScope === opt.value ? 'bg-brand-primary text-white' : 'bg-white text-grey-600 hover:bg-grey-50'"
            @click="pending.brandScope = opt.value"
          >{{ opt.label }}</button>
        </div>
      </div>

      <div class="h-5 w-px bg-grey-200"></div>

      <MultiSelect
        :model-value="pending.mainCategory"
        :options="filters.categories"
        label="Categories"
        @update:model-value="onMainCategory($event)"
      />

      <MultiSelect
        :model-value="pending.subCategory"
        :options="filters.subcategories"
        label="Subcategories"
        @update:model-value="pending.subCategory = $event"
      />

      <MultiSelect
        v-if="!hideTier"
        :model-value="pending.globalTier"
        :options="filters.globalTiers"
        label="Tiers"
        @update:model-value="pending.globalTier = $event"
      />

      <MultiSelect
        :model-value="pending.brand"
        :options="filters.brands"
        label="Brands"
        @update:model-value="pending.brand = $event"
      />

      <MultiSelect
        v-if="!hideCompetitor"
        :model-value="pending.competitor"
        :options="filters.competitors"
        label="Competitor"
        @update:model-value="pending.competitor = $event"
      />

      <MultiSelect
        v-if="!hideFp"
        :model-value="pending.fpNames"
        :options="filters.fps"
        label="FPs"
        @update:model-value="pending.fpNames = $event"
      />

      <div class="h-5 w-px bg-grey-200"></div>

      <!-- Include Private Label checkbox -->
      <label class="flex items-center gap-1.5 cursor-pointer select-none group">
        <input
          type="checkbox"
          :checked="pending.includePrivateLabel"
          class="w-3.5 h-3.5 rounded border-grey-300 text-brand-primary focus:ring-brand-lightest accent-[var(--brand-primary)]"
          @change="pending.includePrivateLabel = $event.target.checked"
        />
        <span class="text-body text-grey-600 group-hover:text-grey-900 transition-colors whitespace-nowrap">Include Private Label</span>
      </label>

      <!-- Price-fallback mode (staged like every other control until Apply). -->
      <button
        type="button"
        :aria-pressed="pending.priceFallback"
        class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-body font-medium transition-colors whitespace-nowrap active:scale-[0.98]"
        :class="pending.priceFallback
          ? 'border-brand-primary bg-brand-50 text-brand-primary'
          : 'border-grey-200 bg-white text-grey-600 hover:border-grey-300'"
        :title="pending.priceFallback
          ? 'Estimating missing prices from the typical price across fulfillment points'
          : 'Fill mapped-but-unpriced cells with the typical (modal) price, flagged estimated'"
        @click="pending.priceFallback = !pending.priceFallback"
      >
        <span class="font-mono">≈</span>
        {{ pending.priceFallback ? 'Estimating prices' : 'Estimate missing prices' }}
      </button>

      <div class="h-5 w-px bg-grey-200"></div>

      <!-- Apply: commits the staged selection (single refetch + URL update). -->
      <button
        type="button"
        :disabled="!isDirty"
        class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-body font-bold transition-colors active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
        :class="isDirty ? 'bg-brand-primary text-white hover:bg-brand-dark' : 'bg-grey-100 text-grey-400'"
        @click="applyFilters"
      >
        <Check class="w-3.5 h-3.5" />
        Apply
        <span v-if="isDirty && pendingChanges > 0" class="text-micro px-1.5 py-px rounded-full bg-white/25 font-bold">{{ pendingChanges }}</span>
      </button>

      <Transition name="filter">
        <div v-if="loading" class="flex items-center gap-1.5 text-caption text-brand-primary font-medium">
          <Loader2 class="w-3.5 h-3.5 animate-spin" />
          Updating...
        </div>
      </Transition>

      <SavedViews />

      <Transition name="filter">
        <button
          v-if="filters.hasActiveFilters"
          @click="copyLink"
          class="text-body text-grey-500 font-medium px-3 py-1.5 rounded-lg border border-grey-200 bg-white hover:bg-grey-50 transition-colors inline-flex items-center gap-1.5"
        >
          <LinkIcon class="w-3.5 h-3.5" />
          {{ linkCopied ? 'Copied!' : 'Copy link' }}
        </button>
      </Transition>

      <Transition name="filter">
        <button
          v-if="pendingHasFilters"
          @click="clearFilters"
          class="text-body text-brand-primary font-bold px-3 py-1.5 rounded-lg border border-brand-light bg-brand-50 hover:bg-brand-lightest transition-colors"
        >
          Clear All
        </button>
      </Transition>
    </div>

    <!-- Selected (staged) filter chips -->
    <Transition name="filter">
      <div v-if="pendingHasFilters" class="flex items-center gap-1.5 flex-wrap mt-2 pt-2 border-t border-grey-100">
        <span class="text-micro text-grey-400 font-medium">Selected:</span>
        <span v-if="pending.vertical" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ pending.vertical }}
          <button class="hover:text-brand-dark" @click="pending.vertical = ''"><X class="w-3 h-3" /></button>
        </span>
        <span v-if="pending.brandScope" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          Shared brands only
          <button class="hover:text-brand-dark" @click="pending.brandScope = ''"><X class="w-3 h-3" /></button>
        </span>
        <span v-for="cat in pending.mainCategory" :key="'cat-' + cat" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ cat }}
          <button class="hover:text-brand-dark" @click="removeChip('mainCategory', cat)"><X class="w-3 h-3" /></button>
        </span>
        <span v-for="sub in pending.subCategory" :key="'sub-' + sub" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ sub }}
          <button class="hover:text-brand-dark" @click="removeChip('subCategory', sub)"><X class="w-3 h-3" /></button>
        </span>
        <span v-for="tier in pending.globalTier" :key="'tier-' + tier" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ tier }}
          <button class="hover:text-brand-dark" @click="removeChip('globalTier', tier)"><X class="w-3 h-3" /></button>
        </span>
        <span v-for="b in pending.brand" :key="'brand-' + b" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ b }}
          <button class="hover:text-brand-dark" @click="removeChip('brand', b)"><X class="w-3 h-3" /></button>
        </span>
        <span v-for="c in pending.competitor" :key="'comp-' + c" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          <CompetitorLogo :name="c" size="sm" />
          {{ c }}
          <button class="hover:text-brand-dark" @click="removeChip('competitor', c)"><X class="w-3 h-3" /></button>
        </span>
        <span v-for="fp in pending.fpNames" :key="'fp-' + fp" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ fp }}
          <button class="hover:text-brand-dark" @click="removeChip('fpNames', fp)"><X class="w-3 h-3" /></button>
        </span>
        <span v-if="!pending.includePrivateLabel" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-micro font-medium border border-amber-200">
          Excl. Private Label
          <button class="hover:text-amber-900" @click="pending.includePrivateLabel = true"><X class="w-3 h-3" /></button>
        </span>
        <span v-if="isDirty" class="text-micro text-grey-400 italic ml-1">unapplied — press Apply</span>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { Filter as FilterIcon, Loader2, Link as LinkIcon, ChevronDown, X, Check } from 'lucide-vue-next'
import MultiSelect from '../shared/MultiSelect.vue'
import SavedViews from './SavedViews.vue'
import CompetitorLogo from '../shared/CompetitorLogo.vue'
import { useFiltersStore } from '../../stores/filters'

defineProps({
  loading: { type: Boolean, default: false },
  hideCompetitor: { type: Boolean, default: false },
  // Gap Analysis hides these two. Its competitor-only rows are national and
  // carry no tier of ours, so tier and FP could only ever narrow half that
  // screen — a filter that silently applies to one column and not the next is
  // worse than not offering it.
  hideTier: { type: Boolean, default: false },
  hideFp: { type: Boolean, default: false },
})

const filters = useFiltersStore()
const linkCopied = ref(false)
const expanded = ref(false)

const brandScopeOptions = [
  { value: '', label: 'All', title: 'Every brand we carry' },
  { value: 'shared', label: 'Shared only', title: 'Only products whose brand the competitor also carries — the realistic matching ceiling, since a brand they do not stock can never be matched' },
]

const verticalOptions = [
  { value: '', label: 'All' },
  { value: 'Beauty', label: 'Beauty' },
  { value: 'Supermarket', label: 'Supermarket' },
]

// The FilterBar edits a local staged copy; nothing hits the store (and so no
// refetch / URL change) until Apply. subcatTier & actionType are carried through
// even though they have no control here, so committing never wipes filters set
// elsewhere (e.g. Master Data action cards).
const FIELDS = ['mainCategory', 'subCategory', 'globalTier', 'subcatTier', 'actionType', 'brand', 'competitor', 'fpNames', 'vertical', 'brandScope', 'includePrivateLabel', 'priceFallback']

function committedSnapshot() {
  const s = {}
  for (const k of FIELDS) s[k] = Array.isArray(filters[k]) ? [...filters[k]] : filters[k]
  return s
}

const pending = reactive(committedSnapshot())

function syncFromStore() {
  Object.assign(pending, committedSnapshot())
}

// Re-sync whenever the committed store changes from ANY source outside this bar
// (table drill-downs, SavedViews, URL restore, Clear All). Keyed on a stable
// serialization so option-list refetches don't retrigger it.
watch(() => JSON.stringify(committedSnapshot()), syncFromStore)

// Selecting a (staged) category resets the staged subcategory and loads that
// category's subcategory options so they can be picked before Apply.
function onMainCategory(value) {
  pending.mainCategory = value
  pending.subCategory = []
  filters.fetchSubcategories(value.length === 1 ? value[0] : null)
}

const pendingSnapStr = computed(() => {
  const s = {}
  for (const k of FIELDS) s[k] = Array.isArray(pending[k]) ? [...pending[k]] : pending[k]
  return JSON.stringify(s)
})
// The competitor pills live in the store rather than in `pending`, because they
// are rendered by the views, not by this bar — but they must still gate Apply.
const pillsDirty = computed(() =>
  JSON.stringify(filters.pendingVisibleCompetitors) !== JSON.stringify(filters.visibleCompetitors))
const isDirty = computed(() =>
  pendingSnapStr.value !== JSON.stringify(committedSnapshot()) || pillsDirty.value)

const pendingChanges = computed(() =>
  [pending.mainCategory, pending.subCategory, pending.globalTier, pending.brand, pending.competitor, pending.fpNames]
    .reduce((n, a) => n + a.length, 0)
  + (pending.vertical ? 1 : 0)
  + (pending.brandScope ? 1 : 0)
  + (pillsDirty.value ? 1 : 0)
  + (!pending.includePrivateLabel ? 1 : 0)
  + (pending.priceFallback ? 1 : 0)
)

// Gates the "Selected:" chip row and Clear All, so brandScope has to be counted
// or its chip never appears when it is the only thing set.
const pendingHasFilters = computed(() =>
  !!(pending.mainCategory.length || pending.subCategory.length || pending.globalTier.length ||
     pending.brand.length || pending.competitor.length || pending.fpNames.length ||
     pending.vertical || pending.brandScope || !pending.includePrivateLabel)
)

const activeCount = computed(() => pendingChanges.value)

function applyFilters() {
  if (!isDirty.value) return
  // Atomic commit → the views' watchers refetch once and the URL syncs once.
  // Commit the pills in the same tick, so one Apply is one refetch.
  filters.visibleCompetitors = [...filters.pendingVisibleCompetitors]
  filters.applySnapshot({ ...pending, visibleCompetitors: [...filters.pendingVisibleCompetitors], mainCategory: [...pending.mainCategory], subCategory: [...pending.subCategory], globalTier: [...pending.globalTier], subcatTier: [...pending.subcatTier], actionType: [...pending.actionType], brand: [...pending.brand], competitor: [...pending.competitor], fpNames: [...pending.fpNames] })
}

function clearFilters() {
  filters.clearAll()   // commits cleared state; the store watcher re-syncs pending
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(window.location.href)
    linkCopied.value = true
    setTimeout(() => { linkCopied.value = false }, 2000)
  } catch {}
}

function removeChip(key, value) {
  const current = [...pending[key]]
  const idx = current.indexOf(value)
  if (idx >= 0) {
    current.splice(idx, 1)
    pending[key] = current
  }
}
</script>
