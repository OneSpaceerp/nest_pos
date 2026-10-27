import { createMemoryHistory, createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/sell' },
  { path: '/sell', name: 'sell', component: () => import('./views/SellView.vue') },
  { path: '/baskets', name: 'baskets', component: () => import('./views/BasketsView.vue') },
  { path: '/sales', name: 'sales', component: () => import('./views/SalesView.vue') },
  { path: '/shift', name: 'shift', component: () => import('./views/ShiftPage.vue') },
  { path: '/phone-scanner', name: 'pair', component: () => import('./views/PairView.vue') },
  { path: '/sync', name: 'sync', component: () => import('./views/SyncView.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/sell' },
]

/** PWA: real URLs under /nest-pos (deep links + refresh work). Desk: in-memory, so Desk's own router is untouched. */
export function makeRouter(mode: 'pwa' | 'desk') {
  return createRouter({ history: mode === 'pwa' ? createWebHistory('/nest-pos') : createMemoryHistory(), routes })
}
