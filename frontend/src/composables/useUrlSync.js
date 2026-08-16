import { watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useFiltersStore } from '../stores/filters'

const FILTER_KEYS = ['mainCategory', 'subCategory', 'globalTier', 'subcatTier', 'actionType', 'brand', 'fpNames']
const URL_PARAM_MAP = {
  mainCategory: 'category',
  subCategory: 'subcat',
  globalTier: 'tier',
  subcatTier: 'subcat_tier',
  actionType: 'action',
  brand: 'brand',
  fpNames: 'fp',
}
const REVERSE_MAP = Object.fromEntries(
  Object.entries(URL_PARAM_MAP).map(([k, v]) => [v, k])
)

export function useUrlSync() {
  const router = useRouter()
  const route = useRoute()
  const filters = useFiltersStore()

  // Restore filters from URL on init
  function restoreFromUrl() {
    const query = route.query
    let changed = false
    for (const [param, filterKey] of Object.entries(REVERSE_MAP)) {
      if (query[param]) {
        // URL stores comma-separated arrays
        const val = query[param]
        filters[filterKey] = val.includes(',') ? val.split(',') : [val]
        changed = true
      }
    }
    // Restore boolean private_label param
    if (query.private_label === '0') {
      filters.includePrivateLabel = false
      changed = true
    }
    // Restore price-fallback mode
    if (query.estimate === '1') {
      filters.priceFallback = true
      changed = true
    }
    // Restore vertical (single-select: 'Beauty' | 'Supermarket')
    if (query.vertical) {
      filters.vertical = query.vertical
      changed = true
    }
    if (query.brands === 'shared' || query.brands === 'shared_name') {
      filters.brandScope = query.brands
      changed = true
    }
    if (changed && query.category) {
      filters.fetchSubcategories()
    }
  }

  // Push filter state to URL
  function syncToUrl() {
    const query = {}
    for (const key of FILTER_KEYS) {
      const param = URL_PARAM_MAP[key]
      if (filters[key] && filters[key].length) {
        query[param] = Array.isArray(filters[key]) ? filters[key].join(',') : filters[key]
      }
    }
    // Sync boolean
    if (!filters.includePrivateLabel) {
      query.private_label = '0'
    }
    if (filters.priceFallback) {
      query.estimate = '1'
    }
    if (filters.vertical) {
      query.vertical = filters.vertical
    }
    if (filters.brandScope) {
      query.brands = filters.brandScope
    }

    const currentQuery = { ...route.query }
    // Remove filter params from current query
    for (const param of Object.values(URL_PARAM_MAP)) {
      delete currentQuery[param]
    }
    delete currentQuery.private_label
    delete currentQuery.estimate
    delete currentQuery.vertical
    delete currentQuery.brands

    router.replace({ query: { ...currentQuery, ...query } })
  }

  // Restore on first call
  restoreFromUrl()

  // Watch filter changes and sync to URL
  watch(
    () => [...FILTER_KEYS.map(k => filters[k]), filters.includePrivateLabel, filters.privateLabelOnly, filters.priceFallback, filters.vertical, filters.brandScope],
    () => syncToUrl(),
    { deep: true }
  )
}
