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
    path: '/:pathMatch(.*)*',
    redirect: '/commercial',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
