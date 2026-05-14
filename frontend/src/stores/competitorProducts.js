import { defineStore } from 'pinia'
import { competitorProductsApi } from '../api/client'

export const useCompetitorProductsStore = defineStore('competitorProducts', {
  state: () => ({
    kpis: null,
    crawlTimeline: [],
    categoryBreakdown: [],
    mappingSummary: [],
    products: [],
    productsTotal: 0,
    filterOptions: { competitors: [], categories_l1: [], categories_l2: [], categories_l3: [] },
    loading: false,
    error: null,
    lastFetchedAt: null,
    currentPage: 1,
    pageSize: 50,
    // Tab-specific filters (not shared with global FilterBar)
    competitorFilter: [],
    categoryL1Filter: [],
    categoryL2Filter: [],
    categoryL3Filter: [],
    mappingStatusFilter: null,
    freshnessFilter: null,
    bfDateFrom: null,
    bfDateTo: null,
    competitorDateFrom: null,
    competitorDateTo: null,
    searchQuery: '',
  }),

  getters: {
    filterParams(state) {
      const p = {}
      if (state.competitorFilter.length) p.competitor = state.competitorFilter.join(',')
      if (state.categoryL1Filter.length) p.category_level_1 = state.categoryL1Filter.join(',')
      if (state.categoryL2Filter.length) p.category_level_2 = state.categoryL2Filter.join(',')
      if (state.categoryL3Filter.length) p.category_level_3 = state.categoryL3Filter.join(',')
      if (state.mappingStatusFilter) p.mapping_status = state.mappingStatusFilter
      if (state.freshnessFilter) p.freshness = state.freshnessFilter
      if (state.bfDateFrom) p.bf_date_from = state.bfDateFrom
      if (state.bfDateTo) p.bf_date_to = state.bfDateTo
      if (state.competitorDateFrom) p.competitor_date_from = state.competitorDateFrom
      if (state.competitorDateTo) p.competitor_date_to = state.competitorDateTo
      return p
    },
  },

  actions: {
    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        await Promise.all([
          this.fetchKpis(),
          this.fetchTimeline(),
          this.fetchCategories(),
          this.fetchSummary(),
          this.fetchProducts(),
        ])
      } catch (err) {
        this.error = err.message || 'Failed to load competitor products data'
        console.error('Competitor products fetch error:', err)
      } finally {
        this.loading = false
        this.lastFetchedAt = new Date()
      }
    },

    async fetchKpis() {
      const res = await competitorProductsApi.getKPIs(this.filterParams)
      this.kpis = res.data
    },

    async fetchTimeline() {
      const res = await competitorProductsApi.getCrawlTimeline(this.filterParams)
      this.crawlTimeline = res.data
    },

    async fetchCategories() {
      const res = await competitorProductsApi.getCategoryBreakdown(this.filterParams)
      this.categoryBreakdown = res.data
    },

    async fetchSummary() {
      const res = await competitorProductsApi.getMappingSummary(this.filterParams)
      this.mappingSummary = res.data
    },

    async fetchProducts() {
      const params = {
        ...this.filterParams,
        page: this.currentPage,
        page_size: this.pageSize,
      }
      if (this.searchQuery) params.search = this.searchQuery
      const res = await competitorProductsApi.getProducts(params)
      this.products = res.data.items || []
      this.productsTotal = res.data.total_count || 0
      if (res.data.filter_options) {
        this.filterOptions = res.data.filter_options
        // Prune category selections that no longer exist for the current scope
        // Only reassign if values actually changed to avoid retriggering the watcher
        if (this.categoryL1Filter.length) {
          const valid = new Set(res.data.filter_options.categories_l1 || [])
          const pruned = this.categoryL1Filter.filter(c => valid.has(c))
          if (pruned.length !== this.categoryL1Filter.length) this.categoryL1Filter = pruned
        }
        if (this.categoryL2Filter.length) {
          const valid = new Set(res.data.filter_options.categories_l2 || [])
          const pruned = this.categoryL2Filter.filter(c => valid.has(c))
          if (pruned.length !== this.categoryL2Filter.length) this.categoryL2Filter = pruned
        }
        if (this.categoryL3Filter.length) {
          const valid = new Set(res.data.filter_options.categories_l3 || [])
          const pruned = this.categoryL3Filter.filter(c => valid.has(c))
          if (pruned.length !== this.categoryL3Filter.length) this.categoryL3Filter = pruned
        }
      }
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

    resetFilters() {
      this.competitorFilter = []
      this.categoryL1Filter = []
      this.categoryL2Filter = []
      this.categoryL3Filter = []
      this.mappingStatusFilter = null
      this.freshnessFilter = null
      this.bfDateFrom = null
      this.bfDateTo = null
      this.competitorDateFrom = null
      this.competitorDateTo = null
      this.searchQuery = ''
      this.currentPage = 1
    },
  },
})
