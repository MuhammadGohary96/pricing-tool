import { defineStore } from 'pinia'
import { executiveApi } from '../api/client'

export const useExecutiveStore = defineStore('executive', {
  state: () => ({
    summary: null,
    categoryPerformance: [],
    topActions: [],
    loading: false,
    error: null,
    lastFetchedAt: null,
  }),

  actions: {
    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        await Promise.all([
          this.fetchSummary(),
          this.fetchCategoryPerformance(),
          this.fetchTopActions(),
        ])
      } catch (err) {
        this.error = err.message || 'Failed to load executive data'
        console.error('Executive fetch error:', err)
      } finally {
        this.loading = false
        this.lastFetchedAt = new Date()
      }
    },

    async fetchSummary() {
      const res = await executiveApi.getSummary()
      this.summary = res.data
    },

    async fetchCategoryPerformance() {
      const res = await executiveApi.getCategoryPerformance()
      this.categoryPerformance = res.data
    },

    async fetchTopActions() {
      const res = await executiveApi.getTopActions(10)
      this.topActions = res.data.items || []
    },
  },
})
