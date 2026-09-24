import { defineStore } from 'pinia'
import { filtersApi } from '../api/client'

// The Vertical is derived from storefront main category: Beauty is this one
// main category, Supermarket is every other.
const BEAUTY_MAIN_CATEGORY = 'fragrances & beauty'

/** Main-category options that fit a vertical ('' | 'Beauty' | 'Supermarket'). */
export function mainCategoriesForVertical(all, vertical) {
  const v = String(vertical || '').toLowerCase()
  if (v === 'beauty') return all.filter(m => m.toLowerCase() === BEAUTY_MAIN_CATEGORY)
  if (v === 'supermarket') return all.filter(m => m.toLowerCase() !== BEAUTY_MAIN_CATEGORY)
  return all
}

export const useFiltersStore = defineStore('filters', {
  state: () => ({
    // NB: `mainCategory` is the COMMERCIAL category (legacy name, kept because
    // it is in saved views and shared URLs). The storefront main category —
    // "Main Category" in the UI, main_category_name — is `mainCategoryName`.
    mainCategory: [],
    mainCategoryName: [],
    subCategory: [],
    globalTier: [],
    subcatTier: [],
    actionType: [],
    brand: [],
    competitor: [],
    fpNames: [],
    // Vertical — single-select toggle: '' (All) | 'Beauty' | 'Supermarket'.
    // Beauty = main_category_name 'Fragrances & Beauty'; Supermarket = the rest.
    vertical: '',
    includePrivateLabel: true,
    // Added rather than folded into includePrivateLabel: that flag is in saved
    // views and shared URLs, and renaming it would silently reinterpret both.
    // The two combine into three states — all / exclude / only.
    privateLabelOnly: false,
    // Brand scope — '' (All brands) | 'shared'. 'shared' keeps only products
    // whose brand the competitor also carries, which is the realistic ceiling:
    // a brand they do not stock can never be matched.
    brandScope: '',
    // Competitor pills. Cosmetic most of the time, but under Shared-only they
    // decide which competitors count as sharing a brand, so they move numbers —
    // and therefore stage behind Apply like every other filter.
    //   pendingVisibleCompetitors — what the pills are showing right now
    //   visibleCompetitors        — what the views actually query with
    // When Shared-only is off the two are kept in lockstep, so focusing stays
    // instant and free.
    visibleCompetitors: [],
    pendingVisibleCompetitors: [],
    // Mode (not a scope filter): fill mapped-but-not-fresh prices with the
    // product×competitor modal, flagged estimated. Default OFF.
    priceFallback: false,
    categories: [],
    mainCategories: [],
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
      if (state.mainCategoryName.length) params.main_category_name = state.mainCategoryName.join(',')
      if (state.subCategory.length) params.sub_category = state.subCategory.join(',')
      if (state.globalTier.length) params.global_tier = state.globalTier.join(',')
      if (state.subcatTier.length) params.subcat_tier = state.subcatTier.join(',')
      if (state.actionType.length) params.action_type = state.actionType.join(',')
      if (state.brand.length) params.brand = state.brand.join(',')
      if (state.competitor.length) params.competitor = state.competitor.join(',')
      if (state.fpNames.length) params.fp_names = state.fpNames.join(',')
      if (state.vertical) params.vertical = state.vertical
      if (!state.includePrivateLabel) params.exclude_private_label = true
      if (state.privateLabelOnly) params.private_label_only = true
      if (state.brandScope) params.brand_scope = state.brandScope
      if (state.priceFallback) params.price_fallback = true
      return params
    },
    hasActiveFilters(state) {
      return !!(
        state.mainCategory.length ||
        state.mainCategoryName.length ||
        state.subCategory.length ||
        state.globalTier.length ||
        state.subcatTier.length ||
        state.actionType.length ||
        state.brand.length ||
        state.competitor.length ||
        state.fpNames.length ||
        !!state.vertical ||
        !!state.brandScope ||
        !state.includePrivateLabel ||
        state.privateLabelOnly
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
          // A cache written before a list existed is a miss, or that dropdown
          // stays empty until the TTL runs out.
          if (Date.now() - ts < CACHE_TTL && Array.isArray(data.mainCategories)) {
            this.categories = data.categories
            this.mainCategories = data.mainCategories
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
        const [catRes, mainRes, tierRes, compRes, fpsRes] = await Promise.all([
          filtersApi.getCategories(),
          filtersApi.getMainCategories(),
          filtersApi.getTiers(),
          filtersApi.getCompetitors(),
          filtersApi.getFPs(),
        ])
        this.categories = catRes.data.categories
        this.mainCategories = mainRes.data.main_categories || []
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
              mainCategories: this.mainCategories,
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

    async fetchSubcategories(commercialOverride, mainNameOverride) {
      try {
        // Overrides let the FilterBar load subcategory options for a *staged*
        // (not-yet-applied) selection. Each falls back to the committed one.
        // Both category axes narrow the list — to their intersection when set.
        const commercial = commercialOverride === undefined ? this.mainCategory : commercialOverride
        const mainName = mainNameOverride === undefined ? this.mainCategoryName : mainNameOverride
        const res = await filtersApi.getSubcategories(
          commercial?.length ? commercial.join(',') : null,
          mainName?.length ? mainName.join(',') : null,
        )
        this.subcategories = res.data.subcategories
      } catch (err) {
        console.error('Failed to fetch subcategories:', err)
      }
    },

    async setFilter(key, value) {
      this[key] = value
      if (key === 'vertical') {
        // Drop main categories the new vertical rules out.
        const fits = new Set(mainCategoriesForVertical(this.mainCategoryName, value))
        const kept = this.mainCategoryName.filter(m => fits.has(m))
        if (kept.length !== this.mainCategoryName.length) {
          this.mainCategoryName = kept
          this.subCategory = []
          await this.fetchSubcategories()
        }
      }
      if (key === 'mainCategory' || key === 'mainCategoryName') {
        this.subCategory = []
        await this.fetchSubcategories()
      }
    },

    clearAll() {
      this.mainCategory = []
      this.mainCategoryName = []
      this.subCategory = []
      this.globalTier = []
      this.subcatTier = []
      this.actionType = []
      this.brand = []
      this.competitor = []
      this.fpNames = []
      this.vertical = ''
      this.brandScope = ''
      this.visibleCompetitors = []
      this.pendingVisibleCompetitors = []
      this.includePrivateLabel = true
      this.privateLabelOnly = false
      this.fetchSubcategories()
    },

    // Restore a full filter snapshot (state shape: camelCase arrays + flags).
    // Scope filters absent from the snapshot reset to empty; the two flags reset
    // to their defaults only when the snapshot explicitly carries them, so a
    // partial preset (e.g. { globalTier: ['T1'] }) clears scopes without
    // silently flipping privateLabel / priceFallback.
    applySnapshot(snap = {}) {
      this.mainCategory = Array.isArray(snap.mainCategory) ? [...snap.mainCategory] : []
      this.mainCategoryName = Array.isArray(snap.mainCategoryName) ? [...snap.mainCategoryName] : []
      this.subCategory = Array.isArray(snap.subCategory) ? [...snap.subCategory] : []
      this.globalTier = Array.isArray(snap.globalTier) ? [...snap.globalTier] : []
      this.subcatTier = Array.isArray(snap.subcatTier) ? [...snap.subcatTier] : []
      this.actionType = Array.isArray(snap.actionType) ? [...snap.actionType] : []
      this.brand = Array.isArray(snap.brand) ? [...snap.brand] : []
      this.competitor = Array.isArray(snap.competitor) ? [...snap.competitor] : []
      this.fpNames = Array.isArray(snap.fpNames) ? [...snap.fpNames] : []
      this.vertical = typeof snap.vertical === 'string' ? snap.vertical : ''
      // Must be listed here: this method assigns field by field, so anything
      // missing is silently dropped on Apply rather than committed.
      this.brandScope = typeof snap.brandScope === 'string' ? snap.brandScope : ''
      if (Array.isArray(snap.visibleCompetitors)) {
        this.visibleCompetitors = [...snap.visibleCompetitors]
        this.pendingVisibleCompetitors = [...snap.visibleCompetitors]
      }
      this.includePrivateLabel = 'includePrivateLabel' in snap ? !!snap.includePrivateLabel : true
      this.privateLabelOnly = 'privateLabelOnly' in snap ? !!snap.privateLabelOnly : false
      if ('priceFallback' in snap) this.priceFallback = !!snap.priceFallback
      this.fetchSubcategories()
    },
  },
})
