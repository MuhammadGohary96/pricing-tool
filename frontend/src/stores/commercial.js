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
    pivotedCompetitors: [],
    blendedCompetitors: [],
    needsActionOnly: false,
    funnelMapping: [],
    funnelCoverage: [],
    loading: false,
    error: null,
    currentPage: 1,
    pageSize: 50,
    sortBy: 'weighted_score',
    sortDir: 'desc',
    search: '',
    editedProducts: {},  // { productId: { catalog_synced, catalog_error } }
    editHistory: [],     // last 10 price edits for undo
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
      const res = await commercialApi.getBlendedPI(this._params())
      this.blendedPI = res.data.items || []
      this.blendedCompetitors = res.data.competitors || []
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
      this.pivotedCompetitors = res.data.competitors || []
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

    async updateProductPrice(productId, nowPrice, nowSalePrice) {
      const payload = {}
      if (nowPrice !== undefined) payload.now_price = nowPrice
      if (nowSalePrice !== undefined) payload.now_sale_price = nowSalePrice
      const res = await commercialApi.updateProductPrice(productId, payload)
      // Record previous values for undo before updating
      const idx = this.products.findIndex(p => p.product_id === productId)
      if (idx !== -1) {
        const prev = {
          productId,
          prevNowPrice: this.products[idx].now_price,
          prevNowSalePrice: this.products[idx].now_sale_price,
          productName: this.products[idx].product_name,
        }
        this.editHistory = [prev, ...this.editHistory].slice(0, 10)
        if (nowPrice !== undefined) this.products[idx].now_price = nowPrice
        if (nowSalePrice !== undefined) this.products[idx].now_sale_price = nowSalePrice
      }
      // Track edit status
      this.editedProducts[productId] = {
        catalog_synced: res.data.catalog_synced,
        catalog_error: res.data.catalog_error,
      }
      return res.data
    },

    async undoLastEdit() {
      const last = this.editHistory[0]
      if (!last) return
      this.editHistory = this.editHistory.slice(1)
      await this.updateProductPrice(last.productId, last.prevNowPrice, last.prevNowSalePrice)
    },
  },
})
