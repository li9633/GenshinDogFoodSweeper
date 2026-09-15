import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/DashBoard.vue'),
    meta: { title: '仪表盘', icon: 'fa-gauge-high' }
  },
  {
    path: '/artifacts',
    name: 'ArtifactList',
    component: () => import('@/views/ArtifactList.vue'),
    meta: { title: '圣遗物列表', icon: 'fa-gem' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SystemSettings.vue'),
    meta: { title: '设置', icon: 'fa-gear' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
