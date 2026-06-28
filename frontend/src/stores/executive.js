import { defineStore } from 'pinia'
import { executiveApi } from '../api/client'
import { useFiltersStore } from './filters'

export const useExecutiveStore = defineStore('executive', {
  state: () => ({
    dashboard: null,  // { kpis, competitor_pi, mapping_progress, classification_breakdown }
    weekOverWeek: null,
    piTrend: null,
    topActions: null,
    categoryPerformance: null,
    fpCompetitorPi: null,  // { competitors: [], cells: [] } — geographic exposure
    loading: false,
    error: null,
    lastFetchedAt: null,
  }),

  actions: {
    _params() {
      const f = useFiltersStore()
      const p = {}
      if (f.mainCategory.length) p.main_category = f.mainCategory.join(',')
      if (f.subCategory.length) p.sub_category = f.subCategory.join(',')
      if (f.globalTier.length) p.global_tier = f.globalTier.join(',')
      if (f.brand.length) p.brand = f.brand.join(',')
      if (f.competitor.length) p.competitor = f.competitor.join(',')
      if (f.fpNames.length) p.fp_names = f.fpNames.join(',')
      if (!f.includePrivateLabel) p.exclude_private_label = true
      return p
    },

    async fetchAll() {
      this.loading = true
      this.error = null
      try {
        await Promise.all([
          this.fetchDashboard(),
          this.fetchWeekOverWeek(),
          this.fetchPITrend(),
          this.fetchTopActions(),
          this.fetchCategoryPerformance(),
          this.fetchFpCompetitorPi(),
        ])
      } catch (err) {
        this.error = err.message || 'Failed to load executive data'
        console.error('Executive fetch error:', err)
      } finally {
        this.loading = false
        this.lastFetchedAt = new Date()
      }
    },

    async fetchDashboard() {
      const res = await executiveApi.getDashboard(this._params())
      this.dashboard = res.data
    },

    async fetchWeekOverWeek() {
      try {
        const res = await executiveApi.getWeekOverWeek()
        this.weekOverWeek = res.data
      } catch { /* non-critical */ }
    },

    async fetchPITrend() {
      try {
        const res = await executiveApi.getPITrend()
        this.piTrend = res.data
      } catch { /* non-critical */ }
    },

    async fetchTopActions() {
      try {
        const res = await executiveApi.getTopActions(5, this._params())
        this.topActions = res.data?.items || []
      } catch { /* non-critical */ }
    },

    async fetchCategoryPerformance() {
      try {
        const res = await executiveApi.getCategoryPerformance(this._params())
        this.categoryPerformance = res.data
      } catch { /* non-critical */ }
    },

    async fetchFpCompetitorPi() {
      try {
        const res = await executiveApi.getFpCompetitorPi(this._params())
        this.fpCompetitorPi = res.data
      } catch { /* non-critical — panel hides if unavailable */ }
    },
  },
})
