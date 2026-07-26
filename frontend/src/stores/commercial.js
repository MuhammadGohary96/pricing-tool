import { defineStore } from 'pinia'
import { commercialApi } from '../api/client'
import { useFiltersStore } from './filters'

export const useCommercialStore = defineStore('commercial', {
  state: () => ({
    kpis: null,
    treemap: [],
    blendedPI: [],
    products: [],
    productsTotal: 0,
    pivotedProducts: [],
    pivotedTotal: 0,
    pivotedSubcatCount: 0,
    pivotedCompetitors: [],
    blendedCompetitors: [],
    // Blended-PI table grain: 'sub_category' (default) | 'commercial_category'.
    // A view control, not a filter — changing it refetches immediately.
    blendedGroupBy: 'sub_category',
    needsActionOnly: false,
    funnelMapping: [],
    funnelCoverage: [],
    loading: false,
    // in-place refetch flags (filter/sort/search) — distinct from full-page `loading`
    refreshingBlended: false,
    refreshingPivot: false,
    error: null,
    currentPage: 1,
    pageSize: 50,
    sortBy: 'weighted_score',
    sortDir: 'desc',
    search: '',
    lastFetchedAt: null,
  }),

  actions: {
    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        await Promise.all([
          this.fetchBlendedPI(),
          this.fetchPivotedProducts(),
        ])
      } catch (err) {
        this.error = err.message || 'Failed to load commercial data'
        console.error('Commercial fetch error:', err)
      } finally {
        this.loading = false
        this.lastFetchedAt = new Date()
      }
    },

    _params() {
      return useFiltersStore().activeFilters
    },

    async fetchKPIs() {
      const res = await commercialApi.getKPIs(this._params())
      this.kpis = res.data
    },

    async fetchTreemap() {
      const res = await commercialApi.getTreemap(this._params())
      this.treemap = res.data.children || []
    },

    async fetchBlendedPI() {
      this.refreshingBlended = true
      try {
        const res = await commercialApi.getBlendedPI({ ...this._params(), group_by: this.blendedGroupBy })
        this.blendedPI = res.data.items || []
        this.blendedCompetitors = res.data.competitors || []
      } finally {
        this.refreshingBlended = false
      }
    },

    // Switch the blended-PI table grain and refetch just that table.
    setBlendedGroupBy(mode) {
      const next = mode === 'commercial_category' ? 'commercial_category' : 'sub_category'
      if (next === this.blendedGroupBy) return
      this.blendedGroupBy = next
      this.fetchBlendedPI()
    },

    async fetchProducts() {
      const params = {
        ...this._params(),
        page: this.currentPage,
        page_size: this.pageSize,
      }
      if (this.sortBy) params.sort_by = this.sortBy
      if (this.sortDir) params.sort_dir = this.sortDir
      if (this.search) params.search = this.search
      const res = await commercialApi.getProducts(params)
      this.products = res.data.items || []
      this.productsTotal = res.data.total_count || 0
    },

    async fetchPivotedProducts() {
      this.refreshingPivot = true
      try {
        const params = {
          ...this._params(),
          page: this.currentPage,
          page_size: this.pageSize,
          sort_by: this.sortBy,
          sort_dir: this.sortDir,
        }
        if (this.search) params.search = this.search
        if (this.needsActionOnly) params.action_type = 'Needs Mapping,Review Match,Needs Price Update'
        const res = await commercialApi.getPivotedProducts(params)
        this.pivotedProducts = res.data.items || []
        this.pivotedTotal = res.data.total_count || 0
        this.pivotedSubcatCount = res.data.subcategory_count || 0
        this.pivotedCompetitors = res.data.competitors || []
      } finally {
        this.refreshingPivot = false
      }
    },

    async setSort(key, dir) {
      this.sortBy = key
      this.sortDir = dir
      this.currentPage = 1
      await this.fetchPivotedProducts()
    },

    async setSearch(query) {
      this.search = query
      this.currentPage = 1
      await this.fetchPivotedProducts()
    },

    async fetchFunnel() {
      const res = await commercialApi.getFunnel(this._params())
      this.funnelMapping = res.data.mapping_funnel || []
      this.funnelCoverage = res.data.coverage_funnel || []
    },

    async setPage(page) {
      this.currentPage = page
      await this.fetchPivotedProducts()
    },

    async setNeedsActionOnly(val) {
      this.needsActionOnly = val
      this.currentPage = 1
      await this.fetchPivotedProducts()
    },
  },
})
