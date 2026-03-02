<template>
  <div class="bg-white rounded-lg shadow-card px-5 py-3">
    <div class="flex items-center gap-3 flex-wrap">
      <div class="flex items-center gap-1.5 text-subheading text-grey-500 font-semibold">
        <FilterIcon class="w-4 h-4" />
        Filters
      </div>

      <div class="h-5 w-px bg-grey-200"></div>

      <MultiSelect
        :model-value="filters.mainCategory"
        :options="filters.categories"
        label="Categories"
        @update:model-value="filters.setFilter('mainCategory', $event)"
      />

      <MultiSelect
        :model-value="filters.subCategory"
        :options="filters.subcategories"
        label="Subcategories"
        @update:model-value="filters.setFilter('subCategory', $event)"
      />

      <MultiSelect
        :model-value="filters.globalTier"
        :options="filters.globalTiers"
        label="Tiers"
        @update:model-value="filters.setFilter('globalTier', $event)"
      />

      <MultiSelect
        :model-value="filters.actionType"
        :options="filters.actionTypes"
        label="Actions"
        @update:model-value="filters.setFilter('actionType', $event)"
      />

      <MultiSelect
        :model-value="filters.brand"
        :options="filters.brands"
        label="Brands"
        @update:model-value="filters.setFilter('brand', $event)"
      />

      <div class="h-5 w-px bg-grey-200"></div>

      <!-- Include Private Label checkbox -->
      <label class="flex items-center gap-1.5 cursor-pointer select-none group">
        <input
          type="checkbox"
          :checked="filters.includePrivateLabel"
          class="w-3.5 h-3.5 rounded border-grey-300 text-brand-primary focus:ring-brand-lightest accent-[var(--brand-primary)]"
          @change="filters.setFilter('includePrivateLabel', $event.target.checked)"
        />
        <span class="text-body text-grey-600 group-hover:text-grey-900 transition-colors whitespace-nowrap">Include Private Label</span>
      </label>

      <Transition name="filter">
        <div v-if="loading" class="flex items-center gap-1.5 text-caption text-brand-primary font-medium">
          <Loader2 class="w-3.5 h-3.5 animate-spin" />
          Updating...
        </div>
      </Transition>

      <Transition name="filter">
        <button
          v-if="filters.hasActiveFilters"
          @click="filters.clearAll()"
          class="text-body text-brand-primary font-bold px-3 py-1.5 rounded-lg border border-brand-light bg-brand-50 hover:bg-brand-lightest transition-colors"
        >
          Clear All
        </button>
      </Transition>
    </div>

    <!-- Active filter chips -->
    <Transition name="filter">
      <div v-if="filters.hasActiveFilters" class="flex items-center gap-1.5 flex-wrap mt-2 pt-2 border-t border-grey-100">
        <span class="text-micro text-grey-400 font-medium">Filtered:</span>
        <span v-for="cat in filters.mainCategory" :key="'cat-' + cat" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ cat }}
          <button class="hover:text-brand-dark" @click="removeChip('mainCategory', cat)">&times;</button>
        </span>
        <span v-for="sub in filters.subCategory" :key="'sub-' + sub" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ sub }}
          <button class="hover:text-brand-dark" @click="removeChip('subCategory', sub)">&times;</button>
        </span>
        <span v-for="tier in filters.globalTier" :key="'tier-' + tier" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ tier }}
          <button class="hover:text-brand-dark" @click="removeChip('globalTier', tier)">&times;</button>
        </span>
        <span v-for="action in filters.actionType" :key="'act-' + action" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ action }}
          <button class="hover:text-brand-dark" @click="removeChip('actionType', action)">&times;</button>
        </span>
        <span v-for="b in filters.brand" :key="'brand-' + b" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-brand-50 text-brand-primary text-micro font-medium border border-brand-light">
          {{ b }}
          <button class="hover:text-brand-dark" @click="removeChip('brand', b)">&times;</button>
        </span>
        <span v-if="!filters.includePrivateLabel" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-micro font-medium border border-amber-200">
          Excl. Private Label
          <button class="hover:text-amber-900" @click="filters.setFilter('includePrivateLabel', true)">&times;</button>
        </span>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { Filter as FilterIcon, Loader2 } from 'lucide-vue-next'
import MultiSelect from '../shared/MultiSelect.vue'
import { useFiltersStore } from '../../stores/filters'

defineProps({
  loading: { type: Boolean, default: false },
})

const filters = useFiltersStore()

function removeChip(key, value) {
  const current = [...filters[key]]
  const idx = current.indexOf(value)
  if (idx >= 0) {
    current.splice(idx, 1)
    filters.setFilter(key, current)
  }
}
</script>
