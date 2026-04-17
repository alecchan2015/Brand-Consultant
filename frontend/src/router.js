import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from './store'

const routes = [
  { path: '/', component: () => import('./views/Home.vue'), meta: {} },
  { path: '/login', component: () => import('./views/Login.vue'), meta: { guest: true } },
  { path: '/register', component: () => import('./views/Register.vue'), meta: { guest: true } },
  { path: '/auth/callback', component: () => import('./views/AuthCallback.vue'), meta: {} },
  {
    path: '/app',
    component: () => import('./views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: '/dashboard', component: () => import('./views/Dashboard.vue') },
      { path: '/tasks/new', component: () => import('./views/NewTask.vue') },
      { path: '/tasks/:id', component: () => import('./views/TaskDetail.vue') },
      { path: '/logo', component: () => import('./views/LogoGenerator.vue') },
      { path: '/poster', component: () => import('./views/PosterGenerator.vue') },
      { path: '/membership', component: () => import('./views/Membership.vue') },
      { path: '/orders', component: () => import('./views/MyOrders.vue') },
      { path: '/payment/:order_no', component: () => import('./views/PaymentPage.vue') },
    ],
  },
  {
    path: '/admin',
    component: () => import('./views/admin/Layout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', component: () => import('./views/admin/Dashboard.vue') },
      { path: 'llm', component: () => import('./views/admin/LLMConfig.vue') },
      { path: 'ppt-provider', component: () => import('./views/admin/PPTProvider.vue') },
      { path: 'knowledge', component: () => import('./views/admin/Knowledge.vue') },
      { path: 'users', component: () => import('./views/admin/Users.vue') },
      { path: 'auth', component: () => import('./views/admin/Auth.vue') },
      { path: 'membership', component: () => import('./views/admin/Membership.vue') },
      { path: 'orders', component: () => import('./views/admin/Orders.vue') },
      { path: 'payment-providers', component: () => import('./views/admin/PaymentProviders.vue') },
      { path: 'credits-config', component: () => import('./views/admin/CreditsConfig.vue') },
      { path: 'tasks', component: () => import('./views/admin/Tasks.vue') },
      { path: 'token-usage', component: () => import('./views/admin/TokenUsage.vue') },
      { path: 'logo-provider', component: () => import('./views/admin/LogoProvider.vue') },
      { path: 'poster-provider', component: () => import('./views/admin/PosterProvider.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const store = useUserStore()
  if (store.token && !store.user) await store.fetchMe()

  if (to.meta.requiresAuth && !store.isLoggedIn) return '/login'
  if (to.meta.requiresAdmin && !store.isAdmin) return '/'
  if (to.meta.guest && store.isLoggedIn) return store.isAdmin ? '/admin/dashboard' : '/dashboard'
})

export default router
