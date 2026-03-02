import { defineStore } from 'pinia'
import { filtersApi } from '../api/client'

export const useFiltersStore = defineStore('filters', {
  state: () => ({
    mainCategory: [],
    subCategory: [],
    globalTier: [],
    subcatTier: [],
    actionType: [],
    brand: [],
    includePrivateLabel: true,
    categories: [],
    subcategories: [],
    globalTiers: [],
    subcatTiers: [],
    actionTypes: [],
    brands: [],
  }),

  getters: {
    activeFilters(state) {
      const params = {}
      if (state.mainCategory.length) params.main_category = state.mainCategory.join(',')
      if (state.subCategory.length) params.sub_category = state.subCategory.join(',')
      if (state.globalTier.length) params.global_tier = state.globalTier.join(',')
      if (state.subcatTier.length) params.subcat_tier = state.subcatTier.join(',')
      if (state.actionType.length) params.action_type = state.actionType.join(',')
      if (state.brand.length) params.brand = state.brand.join(',')
      if (!state.includePrivateLabel) params.exclude_private_label = true
      return params
    },
    hasActiveFilters(state) {
      return !!(
        state.mainCategory.length ||
        state.subCategory.length ||
        state.globalTier.length ||
        state.subcatTier.length ||
        state.actionType.length ||
        state.brand.length ||
        !state.includePrivateLabel
      )
    },
  },

  actions: {
    async fetchFilterOptions() {
      try {
        const [catRes, tierRes] = await Promise.all([
          filtersApi.getCategories(),
          filtersApi.getTiers(),
        ])
        this.categories = catRes.data.categories
        this.globalTiers = tierRes.data.global_tiers
        this.subcatTiers = tierRes.data.subcat_tiers
        this.actionTypes = tierRes.data.action_types
        this.brands = tierRes.data.brands || []

        await this.fetchSubcategories()
      } catch (err) {
        console.error('Failed to fetch filter options:', err)
      }
    },

    async fetchSubcategories() {
      try {
        const main = this.mainCategory.length === 1 ? this.mainCategory[0] : null
        const res = await filtersApi.getSubcategories(main)
        this.subcategories = res.data.subcategories
      } catch (err) {
        console.error('Failed to fetch subcategories:', err)
      }
    },

    async setFilter(key, value) {
      this[key] = value
      if (key === 'mainCategory') {
        this.subCategory = []
        await this.fetchSubcategories()
      }
    },

    clearAll() {
      this.mainCategory = []
      this.subCategory = []
      this.globalTier = []
      this.subcatTier = []
      this.actionType = []
      this.brand = []
      this.includePrivateLabel = true
      this.fetchSubcategories()
    },
  },
})
