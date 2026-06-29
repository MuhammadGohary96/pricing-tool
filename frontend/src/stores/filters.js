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
    competitor: [],
    fpNames: [],
    includePrivateLabel: true,
    // Mode (not a scope filter): fill mapped-but-not-fresh prices with the
    // product×competitor modal, flagged estimated. Default OFF.
    priceFallback: false,
    categories: [],
    subcategories: [],
    globalTiers: [],
    subcatTiers: [],
    actionTypes: [],
    brands: [],
    competitors: [],
    fps: [],
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
      if (state.competitor.length) params.competitor = state.competitor.join(',')
      if (state.fpNames.length) params.fp_names = state.fpNames.join(',')
      if (!state.includePrivateLabel) params.exclude_private_label = true
      if (state.priceFallback) params.price_fallback = true
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
        state.competitor.length ||
        state.fpNames.length ||
        !state.includePrivateLabel
      )
    },
  },

  actions: {
    async fetchFilterOptions(force = false) {
      const CACHE_KEY = 'bf_filter_options'
      const CACHE_TTL = 15 * 60 * 1000 // 15 minutes

      // force=true bypasses the cache so newly-synced values (e.g. new FPs)
      // show up immediately after a background BigQuery refresh.
      if (!force) try {
        const cached = sessionStorage.getItem(CACHE_KEY)
        if (cached) {
          const { data, ts } = JSON.parse(cached)
          if (Date.now() - ts < CACHE_TTL) {
            this.categories = data.categories
            this.globalTiers = data.globalTiers
            this.subcatTiers = data.subcatTiers
            this.actionTypes = data.actionTypes
            this.brands = data.brands
            this.competitors = data.competitors
            this.fps = data.fps || []
            await this.fetchSubcategories()
            return
          }
        }
      } catch {}

      try {
        const [catRes, tierRes, compRes, fpsRes] = await Promise.all([
          filtersApi.getCategories(),
          filtersApi.getTiers(),
          filtersApi.getCompetitors(),
          filtersApi.getFPs(),
        ])
        this.categories = catRes.data.categories
        this.globalTiers = tierRes.data.global_tiers
        this.subcatTiers = tierRes.data.subcat_tiers
        this.actionTypes = tierRes.data.action_types
        this.brands = tierRes.data.brands || []
        this.competitors = compRes.data.competitors || []
        this.fps = fpsRes.data.fps || []

        try {
          sessionStorage.setItem(CACHE_KEY, JSON.stringify({
            ts: Date.now(),
            data: {
              categories: this.categories,
              globalTiers: this.globalTiers,
              subcatTiers: this.subcatTiers,
              actionTypes: this.actionTypes,
              brands: this.brands,
              competitors: this.competitors,
              fps: this.fps,
            },
          }))
        } catch {}

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
      this.competitor = []
      this.fpNames = []
      this.includePrivateLabel = true
      this.fetchSubcategories()
    },

    // Restore a full filter snapshot (state shape: camelCase arrays + flags).
    // Scope filters absent from the snapshot reset to empty; the two flags reset
    // to their defaults only when the snapshot explicitly carries them, so a
    // partial preset (e.g. { globalTier: ['T1'] }) clears scopes without
    // silently flipping privateLabel / priceFallback.
    applySnapshot(snap = {}) {
      this.mainCategory = Array.isArray(snap.mainCategory) ? [...snap.mainCategory] : []
      this.subCategory = Array.isArray(snap.subCategory) ? [...snap.subCategory] : []
      this.globalTier = Array.isArray(snap.globalTier) ? [...snap.globalTier] : []
      this.subcatTier = Array.isArray(snap.subcatTier) ? [...snap.subcatTier] : []
      this.actionType = Array.isArray(snap.actionType) ? [...snap.actionType] : []
      this.brand = Array.isArray(snap.brand) ? [...snap.brand] : []
      this.competitor = Array.isArray(snap.competitor) ? [...snap.competitor] : []
      this.fpNames = Array.isArray(snap.fpNames) ? [...snap.fpNames] : []
      this.includePrivateLabel = 'includePrivateLabel' in snap ? !!snap.includePrivateLabel : true
      if ('priceFallback' in snap) this.priceFallback = !!snap.priceFallback
      this.fetchSubcategories()
    },
  },
})
