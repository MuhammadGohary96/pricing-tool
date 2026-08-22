<template>
  <div class="flex items-center gap-2 flex-wrap">
    <span class="text-micro font-semibold uppercase tracking-wide text-grey-400 mr-0.5">
      {{ single ? 'Compared with' : 'Competitors' }}
    </span>
    <!-- Under Shared-only these pills stop being cosmetic and decide which
         competitors "shared brand" is measured against, so the numbers move. -->
    <span
      v-if="scopesBrands"
      class="px-1.5 py-0.5 rounded-full text-micro font-semibold bg-brand-lightest text-brand-primary whitespace-nowrap"
      title="Shared-only is on, so these also decide which competitors count as sharing a brand. Deselecting one changes the numbers, not just what is shown."
    >scoping shared brands</span>

    <button
      v-for="comp in visibleComps"
      :key="comp"
      type="button"
      :aria-pressed="isSelected(comp)"
      :role="single ? 'radio' : undefined"
      :aria-checked="single ? isSelected(comp) : undefined"
      :title="titleFor(comp)"
      class="group inline-flex items-center gap-1.5 pl-1 pr-3 py-1 ring-1 text-caption font-semibold transition-[transform,background-color,box-shadow,color] duration-200 ease-premium active:scale-[0.97]"
      :class="[
        // Shape carries the semantics: pills toggle what you're looking at,
        // the squarer control on Gap SELECTS the subject of the whole screen.
        single ? 'rounded-lg' : 'rounded-full',
        isSelected(comp)
          ? 'bg-brand-50 ring-brand-light/60 text-brand-dark'
          : 'bg-white ring-grey-200 text-grey-400 hover:ring-grey-300',
        disabledFor(comp) ? 'opacity-60' : '',
      ]"
      @click="toggle(comp)"
    >
      <span :class="isSelected(comp) ? '' : 'grayscale opacity-50 group-hover:opacity-70 transition-opacity'">
        <CompetitorLogo :name="comp" size="md" />
      </span>
      {{ comp }}
      <!-- A competitor with nothing crawled cannot show an assortment gap; say
           so on the control rather than letting the screen render zeros. -->
      <span v-if="disabledFor(comp)" class="text-micro font-normal text-red-500">no catalogue</span>
    </button>

    <!-- Expand when there are more than the default limit -->
    <button
      v-if="competitors.length > defaultLimit"
      type="button"
      class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full ring-1 ring-grey-200 bg-white text-caption font-medium text-grey-500 hover:ring-grey-300 active:scale-[0.97] transition-[transform,box-shadow] duration-200 ease-premium"
      @click="showAll = !showAll"
    >
      <component :is="showAll ? ChevronLeft : Plus" class="w-3 h-3" />
      {{ showAll ? 'Show fewer' : `${competitors.length - defaultLimit} more` }}
    </button>

    <!-- Reset to all when a partial selection is active. Meaningless in
         single-select mode, where exactly one competitor is always chosen. -->
    <button
      v-if="hasSelection && !single"
      type="button"
      class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-full text-caption font-medium text-grey-400 hover:text-brand-primary hover:bg-brand-50 active:scale-[0.97] transition-[transform,background-color,color] duration-200 ease-premium"
      title="Show all competitors"
      @click="selectAll"
    >
      <RotateCcw class="w-3 h-3" /> All
    </button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Plus, ChevronLeft, RotateCcw } from 'lucide-vue-next'
import CompetitorLogo from '../shared/CompetitorLogo.vue'

const props = defineProps({
  competitors: { type: Array, default: () => [] },
  // Multi mode: an array of names, empty meaning "show all".
  // Single mode: a single name string.
  modelValue: { type: [Array, String], default: () => [] },
  defaultLimit: { type: Number, default: 5 },
  /**
   * Two genuinely different jobs, one widget so the vocabulary stays familiar:
   *
   *  multi  (Executive, Commercial) — visibility only BY DEFAULT: dims what you
   *         are not looking at, changes no number, issues no request. Executive's
   *         blended PI is defined across all tracked competitors, so letting
   *         these pills filter it would move the headline on every focus.
   *         ONE EXCEPTION: under the Shared-only brand toggle they also decide
   *         which competitors count as sharing a brand — "shared" is meaningless
   *         without saying shared with whom — so there they do filter and do
   *         refetch. `scopesBrands` makes that switch visible on the control.
   *  single (Gap Analysis)          — SELECTS the subject of the screen and
   *         refetches. Every number there is "against whom", so unioning
   *         competitors would double-count what both of them stock.
   */
  single: { type: Boolean, default: false },
  /** Names to mark as having no crawled catalogue. */
  withoutCatalogue: { type: Array, default: () => [] },
  /** True when Shared-only is active, i.e. these pills currently affect numbers. */
  scopesBrands: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const showAll = ref(false)

// In single mode every option must stay reachable — the picked competitor could
// otherwise be hidden behind "N more".
const visibleComps = computed(() =>
  showAll.value || props.single ? props.competitors : props.competitors.slice(0, props.defaultLimit)
)

const selectedList = computed(() =>
  Array.isArray(props.modelValue) ? props.modelValue : [props.modelValue].filter(Boolean)
)

// Empty model = every competitor shown. A partial selection means the user has
// hidden some, so the "All" reset becomes available.
const hasSelection = computed(() =>
  selectedList.value.length > 0 && selectedList.value.length < props.competitors.length)

function isSelected(comp) {
  if (props.single) return props.modelValue === comp
  return selectedList.value.length === 0 || selectedList.value.includes(comp)
}

function disabledFor(comp) {
  return props.withoutCatalogue.includes(comp)
}

function titleFor(comp) {
  if (props.single) return `Compare against ${comp}`
  return isSelected(comp) ? `Hide ${comp}` : `Show ${comp}`
}

function toggle(comp) {
  if (props.single) {
    // Radio semantics: clicking the active one is a no-op rather than
    // deselecting, since the screen needs a subject.
    if (props.modelValue !== comp) emit('update:modelValue', comp)
    return
  }

  let current = selectedList.value.length === 0
    ? [...props.competitors]
    : [...selectedList.value]

  if (current.includes(comp)) {
    current = current.filter(c => c !== comp)
  } else {
    current.push(comp)
  }
  // All or none selected → reset to empty (= show all)
  if (current.length === 0 || current.length === props.competitors.length) {
    emit('update:modelValue', [])
  } else {
    emit('update:modelValue', current)
  }
}

function selectAll() {
  emit('update:modelValue', [])
}
</script>
