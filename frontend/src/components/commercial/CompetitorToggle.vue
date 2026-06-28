<template>
  <div class="flex items-center gap-2 flex-wrap">
    <span class="text-micro font-semibold uppercase tracking-wide text-grey-400 mr-0.5">Competitors</span>

    <button
      v-for="comp in visibleComps"
      :key="comp"
      type="button"
      :aria-pressed="isSelected(comp)"
      :title="isSelected(comp) ? `Hide ${comp}` : `Show ${comp}`"
      class="group inline-flex items-center gap-1.5 pl-1 pr-3 py-1 rounded-full ring-1 text-caption font-semibold transition-[transform,background-color,box-shadow,color] duration-200 ease-premium active:scale-[0.97]"
      :class="isSelected(comp)
        ? 'bg-brand-50 ring-brand-light/60 text-brand-dark'
        : 'bg-white ring-grey-200 text-grey-400 hover:ring-grey-300'"
      @click="toggle(comp)"
    >
      <span :class="isSelected(comp) ? '' : 'grayscale opacity-50 group-hover:opacity-70 transition-opacity'">
        <CompetitorLogo :name="comp" size="md" />
      </span>
      {{ comp }}
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

    <!-- Reset to all when a partial selection is active -->
    <button
      v-if="hasSelection"
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
  modelValue: { type: Array, default: () => [] },
  defaultLimit: { type: Number, default: 5 },
})

const emit = defineEmits(['update:modelValue'])

const showAll = ref(false)

const visibleComps = computed(() =>
  showAll.value ? props.competitors : props.competitors.slice(0, props.defaultLimit)
)

// Empty model = every competitor shown. A partial selection means the user has
// hidden some, so the "All" reset becomes available.
const hasSelection = computed(() => props.modelValue.length > 0 && props.modelValue.length < props.competitors.length)

function isSelected(comp) {
  return props.modelValue.length === 0 || props.modelValue.includes(comp)
}

function toggle(comp) {
  let current = props.modelValue.length === 0
    ? [...props.competitors]
    : [...props.modelValue]

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
