import { defineStore } from 'pinia'
import { masterDataApi } from '../api/client'
import { useFiltersStore } from './filters'

export const useMasterDataStore = defineStore('masterData', {
  state: () => ({
    actionSummary: null,
    actionBreakdown: [],
    worklist: [],
    worklistTotal: 0,
    matchReviews: [],
    matchReviewsTotal: 0,
    staleness: null,
    loading: false,
    error: null,
    lastFetchedAt: null,
    currentPage: 1,
    pageSize: 50,
    reviewPage: 1,
    reviewPageSize: 20,
  }),

  actions: {
    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        await Promise.all([
          this.fetchActionSummary(),
          this.fetchActionBreakdown(),
          this.fetchWorklist(),
          this.fetchMatchReviews(),
          this.fetchStaleness(),
        ])
      } catch (err) {
        this.error = err.message || 'Failed to load master data'
        console.error('Master data fetch error:', err)
      } finally {
        this.loading = false
        this.lastFetchedAt = new Date()
      }
    },

    _params() {
      return useFiltersStore().activeFilters
    },

    async fetchActionSummary() {
      const res = await masterDataApi.getActionSummary(this._params())
      this.actionSummary = res.data
    },

    async fetchActionBreakdown() {
      const res = await masterDataApi.getActionBreakdown(this._params())
      this.actionBreakdown = res.data
    },

    async fetchWorklist() {
      const res = await masterDataApi.getWorklist({
        ...this._params(),
        page: this.currentPage,
        page_size: this.pageSize,
      })
      this.worklist = res.data.items || []
      this.worklistTotal = res.data.total_count || 0
    },

    async fetchMatchReviews() {
      const res = await masterDataApi.getMatchReviews({
        ...this._params(),
        page: this.reviewPage,
        page_size: this.reviewPageSize,
      })
      this.matchReviews = res.data.items || []
      this.matchReviewsTotal = res.data.total_count || 0
    },

    async fetchStaleness() {
      const res = await masterDataApi.getStalenessHeatmap(this._params())
      this.staleness = res.data
    },

    async setPage(page) {
      this.currentPage = page
      await this.fetchWorklist()
    },

    async setReviewPage(page) {
      this.reviewPage = page
      await this.fetchMatchReviews()
    },
  },
})
