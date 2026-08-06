import { defineStore } from 'pinia'
import { gapApi } from '../api/client'
import { useFiltersStore } from './filters'

/**
 * Brand & Subcategory Gap Analysis.
 *
 * Category, subcategory, brand and scope come from the GLOBAL filters store, so
 * this view, Executive and Commercial all answer the same question about the
 * same slice. Only genuinely view-local state lives here: the selected
 * competitor, the view switch, and table paging.
 *
 * Tier and FP are deliberately not offered on this screen — see the hideTier /
 * hideFp props on FilterBar for why.
 *
 * The competitor is deliberately SINGLE-select and view-local. Every question
 * this tab answers is "against whom" — mapping %, shared brands, what they carry
 * that we do not. Unioning two competitors would double-count products they both
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

    // ── view-local filter ──────────────────────────────────────
    // Everything else (category, subcategory, brand, vertical, private label)
    // comes from the global filters store.
    competitor: null,          // single-select; set from filterOptions on load

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
    /** Shared filters from the global store, plus this view's competitor.
     *  Tier, FP and action type are dropped: tier and FP are not offered here,
     *  and action type is a Commercial-only vocabulary. */
    filterParams(state) {
      const f = useFiltersStore()
      const p = {}
      if (f.mainCategory.length) p.main_category = f.mainCategory.join(',')
      if (f.subCategory.length) p.sub_category = f.subCategory.join(',')
      if (f.brand.length) p.brand = f.brand.join(',')
      if (f.vertical) p.vertical = f.vertical
      if (!f.includePrivateLabel) p.exclude_private_label = true
      if (f.brandScope) p.brand_scope = f.brandScope
      if (state.competitor) p.competitor = state.competitor
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
      const f = useFiltersStore()
      return f.vertical === 'Supermarket' && ['Seoudi', 'Rabbit'].includes(state.competitor)
    },
  },

  actions: {
    async init() {
      if (!this.filterOptions.competitors.length) {
        const res = await gapApi.getFilters()
        this.filterOptions = res.data
      }
      // A competitor in the URL wins, so a shared link reopens the same
      // comparison. Namespaced as `gap_competitor` because competitor is
      // view-local: a Gap link must not silently set Commercial's.
      const fromUrl = new URLSearchParams(window.location.search).get('gap_competitor')
      const known = this.filterOptions.competitors.map(c => c.name)
      if (fromUrl && known.includes(fromUrl)) {
        this.competitor = fromUrl
      } else if (!this.competitor) {
        // Default to the best-matched competitor, not the one with the most
        // competitor-only rows — that would land on whoever we've matched
        // *least*, and an opening screen at 5% matched reads as a broken tab.
        const usable = this.filterOptions.competitors.filter(c => c.has_catalogue)
        const best = [...usable].sort((a, b) => b.matched_products - a.matched_products)[0]
        this.competitor = best?.name || this.filterOptions.competitors[0]?.name || null
      }
      this._syncCompetitorToUrl()
      await this.fetchAll()
    },

    async setCompetitor(name) {
      if (!name || name === this.competitor) return
      this.competitor = name
      this.currentPage = 1
      this._syncCompetitorToUrl()
      await this.fetchAll()
    },

    _syncCompetitorToUrl() {
      try {
        const url = new URL(window.location.href)
        if (this.competitor) url.searchParams.set('gap_competitor', this.competitor)
        else url.searchParams.delete('gap_competitor')
        window.history.replaceState({}, '', url)
      } catch { /* history is unavailable in some embeds; not worth failing over */ }
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
      // Shared filters are cleared by the FilterBar's own Clear All; this only
      // resets what belongs to this view.
      this.brandTypeFilter = null
      this.searchQuery = ''
      this.currentPage = 1
    },
  },
})
