import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const api = axios.create({
  baseURL: '/api',
})

// Attach Google OAuth token to every request (except startup-status)
api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken && !config.url.includes('startup-status')) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

// On 401, clear auth state so user is sent back to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      auth.logout()
    }
    return Promise.reject(error)
  },
)

export default api

export const healthApi = {
  check: () => api.get('/health'),
}

export const startupApi = {
  getStatus: () => api.get('/startup-status'),
  reload: () => api.post('/reload'),
}

export const filtersApi = {
  getCategories: () => api.get('/filters/categories'),
  getSubcategories: (main) => api.get('/filters/subcategories', { params: { main } }),
  getTiers: () => api.get('/filters/tiers'),
}

export const catalogApi = {
  triggerEnrich: () => api.post('/commercial/catalog/enrich'),
}

export const commercialApi = {
  getKPIs: (params) => api.get('/commercial/kpis', { params }),
  getTreemap: (params) => api.get('/commercial/treemap', { params }),
  getBlendedPI: (params) => api.get('/commercial/blended-pi', { params }),
  getProducts: (params) => api.get('/commercial/products', { params }),
  getFunnel: (params) => api.get('/commercial/funnel', { params }),
  exportCSV: (params) => api.get('/commercial/export', { params, responseType: 'blob' }),
  updateProductPrice: (productId, payload) => api.patch(`/commercial/products/${productId}`, payload),
}

export const masterDataApi = {
  getActionSummary: (params) => api.get('/master-data/action-summary', { params }),
  getActionBreakdown: (params) => api.get('/master-data/action-breakdown', { params }),
  getWorklist: (params) => api.get('/master-data/worklist', { params }),
  getMatchReviews: (params) => api.get('/master-data/match-reviews', { params }),
  getStalenessHeatmap: (params) => api.get('/master-data/staleness-heatmap', { params }),
}

export const executiveApi = {
  getSummary: () => api.get('/executive/summary'),
  getPITrend: () => api.get('/executive/pi-trend'),
  getCoverageTrend: () => api.get('/executive/coverage-trend'),
  getCategoryPerformance: (params) => api.get('/executive/category-performance', { params }),
  getWeekOverWeek: () => api.get('/executive/week-over-week'),
  getTopActions: (limit = 10) => api.get('/executive/top-actions', { params: { limit } }),
}
