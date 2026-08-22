import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/commercial' },
  {
    path: '/commercial',
    name: 'Commercial',
    component: () => import('../views/CommercialView.vue'),
  },
  {
    path: '/master-data',
    name: 'MasterData',
    component: () => import('../views/MasterDataView.vue'),
  },
  {
    path: '/executive',
    name: 'Executive',
    component: () => import('../views/ExecutiveView.vue'),
  },
  {
    path: '/competitor-products',
    name: 'CompetitorProducts',
    component: () => import('../views/CompetitorProductsView.vue'),
  },
  {
    path: '/gap-analysis',
    name: 'BrandGap',
    component: () => import('../views/BrandGapView.vue'),
  },
  {
    path: '/how-it-works',
    name: 'HowItWorks',
    component: () => import('../views/HowItWorksView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/commercial',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
