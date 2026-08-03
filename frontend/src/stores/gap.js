import { defineStore } from 'pinia'
import { gapApi } from '../api/client'

/**
 * Brand & Subcategory Gap Analysis.
 *
 * Tab-local filter state, like the Competitors tab: the dimensions here are
 * gap-specific (scope toggles, a single competitor, a view switch) and do not
 * belong in the global FilterBar.
 *
 * The competitor is deliberately SINGLE-select. Every question this tab answers
 * is "against whom" — mapping %, shared brands, what they carry that we do not.
 * Unioning two competitors would silently double-count products they both
 * stock and make brand counts meaningless.
 */
export const useGapStore = defineStore('gap', {
  state: () => ({
    kpis: null,
    subcategories: [],
    brands: [],
    brandsTotal: 0,
    products: [],
    productsTotal: 0,
    filterOptions: { competitors: [], sub_categories: [], main_categories: [] },

    loading: false,
    error: null,
    lastFetchedAt: null,

    // ── filters ────────────────────────────────────────────────
    competitor: null,          // single-select; set from filterOptions on load
    subCategoryFilter: [],
    mainCategoryFilter: [],
    // Beauty and private label are excluded by default: in those ranges "we
    // don't carry it" is usually a deliberate assortment call, not a gap.
    excludeBeautyPL: true,
    includePrivateLabel: false,

    // ── view state ─────────────────────────────────────────────
    view: 'subcategories',     // subcategories | brands | products
    brandTypeFilter: null,     // shared | bf_only | comp_only
    productSide: 'competitor', // breadfast | competitor
    searchQuery: '',
    currentPage: 1,
    pageSize: 50,
    sortBy: null,
    sortDir: 'desc',
  }),

  getters: {
    filterParams(state) {
      const p = {}
      if (state.competitor) p.competitor = state.competitor
      if (state.subCategoryFilter.length) p.sub_category = state.subCategoryFilter.join(',')
      if (state.mainCategoryFilter.length) p.main_category = state.mainCategoryFilter.join(',')
      p.scope = state.excludeBeautyPL ? 'excl_beauty_pl' : 'all'
      if (state.excludeBeautyPL && state.includePrivateLabel) p.include_private_label = true
      return p
    },

    selectedCompetitor(state) {
      return state.filterOptions.competitors.find(c => c.name === state.competitor) || null
    },

    /** Carrefour has no live v2 catalogue, so there is no competitor-only side
     *  to show. Say so instead of rendering a wall of zeros. */
    competitorHasNoCatalogue() {
      return this.selectedCompetitor ? !this.selectedCompetitor.has_catalogue : false
    },

    /** Seoudi and Rabbit file everything under one flat "Beauty and Personal
     *  Care" node, so the bridge's beauty share never crosses the cutoff and
     *  their beauty products survive the exclude-beauty scope. Disclosed rather
     *  than silently patched. */
    hasBeautyBlindSpot(state) {
      return state.excludeBeautyPL && ['Seoudi', 'Rabbit'].includes(state.competitor)
    },
  },

  actions: {
    async init() {
      if (!this.filterOptions.competitors.length) {
        const res = await gapApi.getFilters()
        this.filterOptions = res.data
      }
      if (!this.competitor) {
        // Default to the best-matched competitor, not the one with the most
        // competitor-only rows — that would land on whoever we've matched
        // *least*, and an opening screen at 5% matched reads as a broken tab.
        const usable = this.filterOptions.competitors.filter(c => c.has_catalogue)
        const best = [...usable].sort((a, b) => b.matched_products - a.matched_products)[0]
        this.competitor = best?.name || this.filterOptions.competitors[0]?.name || null
      }
      await this.fetchAll()
    },

    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        await Promise.all([this.fetchKpis(), this.fetchView()])
      } catch (err) {
        this.error = err?.response?.data?.detail || err.message || 'Failed to load gap analysis'
        console.error('Gap fetch error:', err)
      } finally {
        this.loading = false
        this.lastFetchedAt = new Date()
      }
    },

    /** Only the active view is fetched — the brand list is ~1,700 rows and the
     *  product list is paginated, so loading all three on every filter change
     *  would be wasteful. */
    async fetchView() {
      if (this.view === 'brands') return this.fetchBrands()
      if (this.view === 'products') return this.fetchProducts()
      return this.fetchSubcategories()
    },

    async fetchKpis() {
      const res = await gapApi.getKPIs(this.filterParams)
      this.kpis = res.data
    },

    async fetchSubcategories() {
      const res = await gapApi.getSubcategories(this.filterParams)
      this.subcategories = res.data || []
    },

    async fetchBrands() {
      const params = { ...this.filterParams }
      if (this.brandTypeFilter) params.brand_type = this.brandTypeFilter
      const res = await gapApi.getBrands(params)
      this.brands = res.data.items || []
      this.brandsTotal = res.data.total_count || 0
    },

    async fetchProducts() {
      const params = {
        ...this.filterParams,
        side: this.productSide,
        page: this.currentPage,
        page_size: this.pageSize,
      }
      if (this.searchQuery) params.search = this.searchQuery
      if (this.sortBy) { params.sort_by = this.sortBy; params.sort_dir = this.sortDir }
      const res = await gapApi.getProducts(params)
      this.products = res.data.items || []
      this.productsTotal = res.data.total_count || 0
    },

    async setView(view) {
      this.view = view
      this.currentPage = 1
      this.searchQuery = ''
      this.sortBy = null
      await this.fetchView()
    },

    async setProductSide(side) {
      this.productSide = side
      this.currentPage = 1
      this.searchQuery = ''
      this.sortBy = null
      await this.fetchProducts()
    },

    async setBrandType(type) {
      this.brandTypeFilter = type
      await this.fetchBrands()
    },

    async setPage(page) {
      this.currentPage = page
      await this.fetchProducts()
    },

    async setSearch(query) {
      this.searchQuery = query
      this.currentPage = 1
      await this.fetchProducts()
    },

    async setSort(column) {
      if (this.sortBy === column) {
        this.sortDir = this.sortDir === 'desc' ? 'asc' : 'desc'
      } else {
        this.sortBy = column
        this.sortDir = 'desc'
      }
      this.currentPage = 1
      await this.fetchProducts()
    },

    resetFilters() {
      this.subCategoryFilter = []
      this.mainCategoryFilter = []
      this.excludeBeautyPL = true
      this.includePrivateLabel = false
      this.brandTypeFilter = null
      this.searchQuery = ''
      this.currentPage = 1
    },
  },
})
