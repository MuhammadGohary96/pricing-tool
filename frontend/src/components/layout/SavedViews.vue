<template>
  <div class="relative" ref="wrapper">
    <button
      class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-body font-medium transition-colors"
      :class="savedViews.length > 0
        ? 'border-brand-primary bg-brand-50 text-brand-primary'
        : 'border-grey-200 bg-white text-grey-700 hover:border-grey-300'"
      @click="open = !open"
    >
      <BookmarkIcon class="w-3.5 h-3.5" />
      Views
      <span v-if="savedViews.length > 0" class="text-micro px-1.5 py-px rounded-full bg-brand-primary text-white font-bold">{{ savedViews.length }}</span>
      <ChevronDown class="w-3 h-3 transition-transform" :class="open ? 'rotate-180' : ''" />
    </button>

    <Transition name="dropdown">
      <div
        v-if="open"
        class="absolute z-30 mt-1 left-0 bg-white rounded-xl shadow-dropdown ring-1 ring-grey-200/70 py-1 min-w-[220px]"
      >
        <div class="px-3 py-1 text-micro font-semibold text-grey-400 uppercase tracking-wide">Presets</div>
        <button
          v-for="preset in PRESETS"
          :key="preset.name"
          class="w-full text-left px-3 py-1.5 text-body text-grey-700 hover:bg-grey-50 transition-colors"
          @click="applyView(preset); open = false"
        >{{ preset.name }}</button>

        <template v-if="savedViews.length > 0">
          <div class="border-t border-grey-100 my-1"></div>
          <div class="px-3 py-1 text-micro font-semibold text-grey-400 uppercase tracking-wide">Saved</div>
          <div
            v-for="(view, i) in savedViews"
            :key="view.name"
            class="flex items-center group"
          >
            <button
              class="flex-1 text-left px-3 py-1.5 text-body text-grey-700 hover:bg-grey-50 transition-colors"
              @click="applyView(view); open = false"
            >{{ view.name }}</button>
            <button
              class="px-2 py-1.5 text-grey-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
              title="Delete view"
              @click.stop="deleteView(i)"
            ><XIcon class="w-3 h-3" /></button>
          </div>
        </template>

        <div class="border-t border-grey-100 my-1"></div>
        <button
          class="w-full text-left px-3 py-1.5 text-body text-brand-primary font-medium hover:bg-brand-50 transition-colors flex items-center gap-1.5"
          @click="saveCurrentView"
        >
          <PlusIcon class="w-3.5 h-3.5" />
          Save current view
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { Bookmark as BookmarkIcon, ChevronDown, X as XIcon, Plus as PlusIcon } from 'lucide-vue-next'
import { useFiltersStore } from '../../stores/filters'

const filters = useFiltersStore()

const PRESETS = [
  { name: 'All Categories', filters: {} },
]

const LS_KEY = 'bf_saved_views'
const savedViews = ref(loadViews())

function loadViews() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || '[]') } catch { return [] }
}

function persistViews() {
  try { localStorage.setItem(LS_KEY, JSON.stringify(savedViews.value)) } catch {}
}

// Filter state fields captured in a saved view (state shape: camelCase + arrays/flags).
const SNAP_KEYS = [
  'mainCategory', 'subCategory', 'globalTier', 'subcatTier', 'actionType',
  'brand', 'competitor', 'fpNames', 'includePrivateLabel', 'priceFallback',
]

// API-param key → state key, for normalizing views saved in the older (broken)
// activeFilters shape so they still apply correctly.
const API_TO_STATE = {
  main_category: 'mainCategory', sub_category: 'subCategory', global_tier: 'globalTier',
  subcat_tier: 'subcatTier', action_type: 'actionType', brand: 'brand',
  competitor: 'competitor', fp_names: 'fpNames',
}

function snapshot() {
  const s = {}
  for (const k of SNAP_KEYS) {
    const v = filters[k]
    s[k] = Array.isArray(v) ? [...v] : v
  }
  return s
}

// Accept either the current state shape or the legacy API-param shape.
function normalize(f = {}) {
  const out = {}
  for (const [k, v] of Object.entries(f)) {
    if (k === 'exclude_private_label') { out.includePrivateLabel = !v; continue }
    if (k === 'price_fallback') { out.priceFallback = !!v; continue }
    if (k in API_TO_STATE) {
      out[API_TO_STATE[k]] = Array.isArray(v)
        ? v
        : String(v).split(',').map(s => s.trim()).filter(Boolean)
      continue
    }
    out[k] = v  // already state-shape (presets + new saves)
  }
  return out
}

function applyView(view) {
  filters.applySnapshot(normalize(view.filters))
}

function saveCurrentView() {
  const name = window.prompt('Name this view:')
  if (!name?.trim()) return
  savedViews.value.push({ name: name.trim(), filters: snapshot() })
  persistViews()
}

function deleteView(i) {
  savedViews.value.splice(i, 1)
  persistViews()
}

const open = ref(false)
const wrapper = ref(null)
onClickOutside(wrapper, () => { open.value = false })
</script>

<style scoped>
.dropdown-enter-active, .dropdown-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}
.dropdown-enter-from, .dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
