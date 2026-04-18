<template>
  <div class="ybc-dark app-layout">
    <!-- Ambient background -->
    <div class="ambient-bg">
      <div class="glow glow-1"></div>
      <div class="glow glow-2"></div>
    </div>

    <!-- Mobile overlay -->
    <transition name="overlay-fade">
      <div v-if="mobileOpen" class="mobile-overlay" @click="mobileOpen = false"></div>
    </transition>

    <!-- Sidebar -->
    <aside class="sidebar" :class="{ open: mobileOpen }">
      <div class="sidebar-inner">
        <!-- Brand -->
        <router-link to="/" class="brand-row">
          <span class="brand-logo">YBC</span>
          <span class="brand-name">Your Brand Consultant</span>
        </router-link>

        <!-- Nav -->
        <nav class="nav">
          <router-link v-for="item in navItems" :key="item.path" :to="item.path"
            class="nav-item" :class="{ active: isNavActive(item.path) }">
            <span class="nav-icon"><el-icon><component :is="item.icon" /></el-icon></span>
            <span class="nav-label">{{ item.label }}</span>
            <span v-if="item.badge" class="nav-badge" :class="`tier-${item.badgeType}`">{{ item.badge }}</span>
          </router-link>
        </nav>

        <!-- Footer area -->
        <div class="sidebar-footer">
          <!-- Credits chip -->
          <div class="credit-chip">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M8 1.5l2 4.5 5 .5-3.8 3.2 1.2 4.8-4.4-2.5-4.4 2.5 1.2-4.8L1 6.5l5-.5 2-4.5z"
                fill="currentColor" stroke="currentColor" stroke-width="0.5" stroke-linejoin="round"/>
            </svg>
            <span>{{ store.user?.credits ?? 0 }}</span>
            <span class="credit-unit">{{ $t('common.credits') }}</span>
          </div>

          <!-- User info + logout -->
          <div class="user-row">
            <div class="user-info">
              <div class="avatar">{{ (store.user?.username || '?')[0].toUpperCase() }}</div>
              <div class="user-meta">
                <div class="uname">{{ store.user?.username }}</div>
                <div class="urole">
                  <span v-if="tierLabel" class="tier-pill" :class="`tier-${store.user?.tier}`">
                    {{ tierLabel }}
                  </span>
                  <span v-else>{{ $t('common.tier.regular') }}</span>
                </div>
              </div>
            </div>
            <button class="logout-btn" @click="logout" title="退出登录">
              <el-icon><SwitchButton /></el-icon>
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="main">
      <header class="topbar">
        <div class="topbar-left">
          <button class="menu-toggle" @click="toggleSidebar">
            <span></span><span></span><span></span>
          </button>
          <div class="page-title">{{ pageTitle }}</div>
        </div>
        <div class="topbar-right">
          <LangSwitch />
          <el-tag v-if="store.isAdmin" type="danger" effect="dark" size="small" @click="$router.push('/admin')" style="cursor:pointer">
            {{ $t('nav.adminConsole') }} →
          </el-tag>
        </div>
      </header>

      <section class="content">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, markRaw, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../store'
import { ElMessageBox } from 'element-plus'
import LangSwitch from '../components/LangSwitch.vue'
import {
  Grid, Plus, PictureFilled, Picture, Star, Tickets, SwitchButton,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const store = useUserStore()
const { t } = useI18n()

const mobileOpen = ref(false)
// Auto-close mobile drawer when navigating
watch(() => route.path, () => { mobileOpen.value = false })

const TIER_LABELS = { vip: 'VIP', vvip: 'VVIP', vvvip: 'VVVIP' }
const tierLabel = computed(() => TIER_LABELS[store.user?.tier] || '')

const navItems = computed(() => [
  { path: '/dashboard',  label: t('nav.dashboard'),  icon: markRaw(Grid) },
  { path: '/tasks/new',  label: t('nav.newTask'),    icon: markRaw(Plus) },
  { path: '/logo',       label: t('nav.logo'),       icon: markRaw(PictureFilled) },
  { path: '/poster',     label: t('nav.poster'),     icon: markRaw(Picture) },
  {
    path: '/membership',
    label: t('nav.membership'),
    icon: markRaw(Star),
    badge: tierLabel.value,
    badgeType: store.user?.tier,
  },
  { path: '/orders',     label: t('nav.orders'),     icon: markRaw(Tickets) },
])

const pageTitle = computed(() => {
  if (route.path.startsWith('/tasks/') && route.path !== '/tasks/new') return t('nav.pageTitles.taskDetail')
  if (route.path.startsWith('/payment/')) return t('nav.pageTitles.payment')
  const map = {
    '/dashboard':  t('nav.pageTitles.dashboard'),
    '/tasks/new':  t('nav.pageTitles.newTask'),
    '/logo':       t('nav.pageTitles.logo'),
    '/poster':     t('nav.pageTitles.poster'),
    '/membership': t('nav.pageTitles.membership'),
    '/orders':     t('nav.pageTitles.orders'),
  }
  return map[route.path] || t('common.appName')
})

function toggleSidebar() { mobileOpen.value = !mobileOpen.value }

function isNavActive(path) {
  const current = route.path
  if (current === path) return true
  // /tasks/:id and /tasks/new both highlight 工作台
  if (path === '/dashboard' && (current.startsWith('/tasks/') || current === '/tasks/new')) return true
  // /payment/:order_no highlights 我的订单
  if (path === '/orders' && current.startsWith('/payment/')) return true
  return false
}

async function logout() {
  await ElMessageBox.confirm(
    t('common.actions.logout') + '?',
    t('common.confirm'),
    { type: 'warning', confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel') }
  )
  store.logout()
  router.push('/')
}
</script>

<style scoped>
.app-layout {
  position: relative;
  min-height: 100vh;
  background: var(--ybc-bg);
  color: var(--ybc-text);
  display: flex;
}

/* ── Ambient glow backdrop ────────────────────────────────────────── */
.ambient-bg {
  position: fixed; inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.5;
}
.glow-1 {
  width: 480px; height: 480px;
  background: rgba(99, 102, 241, 0.15);
  top: -100px; left: -100px;
}
.glow-2 {
  width: 400px; height: 400px;
  background: rgba(168, 85, 247, 0.1);
  bottom: -80px; right: 20%;
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
.sidebar {
  position: fixed;
  top: 0; left: 0; bottom: 0;
  width: 240px;
  background: rgba(18, 18, 26, 0.8);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-right: 1px solid var(--ybc-border);
  z-index: 100;
  transition: transform 0.25s;
}
.sidebar-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px 14px;
}

.brand-row {
  display: flex; align-items: center; gap: 10px;
  padding: 4px 10px 20px;
  text-decoration: none;
  color: inherit;
}
.brand-logo {
  width: 34px; height: 34px;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--ybc-gradient-primary);
  border-radius: 10px;
  font-size: 12px; font-weight: 800; color: #fff;
  letter-spacing: -0.5px;
}
.brand-name {
  font-size: 14px; font-weight: 600;
  color: var(--ybc-text-strong);
  letter-spacing: -0.2px;
}

.nav {
  display: flex; flex-direction: column; gap: 2px;
  padding: 8px 0;
  border-top: 1px solid var(--ybc-border);
}
.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  text-decoration: none;
  color: var(--ybc-text-dim);
  font-size: 14px;
  transition: all 0.15s;
  position: relative;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--ybc-text-strong);
}
.nav-item.active {
  background: rgba(99, 102, 241, 0.12);
  color: var(--ybc-accent-light);
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0; top: 10px; bottom: 10px;
  width: 3px;
  background: var(--ybc-accent);
  border-radius: 0 2px 2px 0;
}
.nav-icon { display: inline-flex; font-size: 16px; }
.nav-label { flex: 1; }
.nav-badge {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 100px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.tier-vip   { background: linear-gradient(135deg, #3b82f6, #6366f1); color: #fff; }
.tier-vvip  { background: linear-gradient(135deg, #8b5cf6, #ec4899); color: #fff; }
.tier-vvvip { background: linear-gradient(135deg, #f59e0b, #ef4444); color: #fff; }

.sidebar-footer {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--ybc-border);
  display: flex; flex-direction: column; gap: 10px;
}

.credit-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 12px;
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(239, 68, 68, 0.08));
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: 10px;
  color: #fcd34d;
  font-size: 13px; font-weight: 600;
}
.credit-chip svg { flex-shrink: 0; }
.credit-unit { color: rgba(252, 211, 77, 0.6); font-weight: 400; font-size: 11px; }

.user-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  border: 1px solid var(--ybc-border);
}
.user-info {
  display: flex; align-items: center; gap: 10px;
  flex: 1; min-width: 0;
}
.avatar {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: var(--ybc-gradient-primary);
  color: #fff;
  font-size: 13px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.user-meta { min-width: 0; flex: 1; }
.uname {
  font-size: 13px; font-weight: 600;
  color: var(--ybc-text-strong);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.urole { font-size: 11px; color: var(--ybc-text-muted); margin-top: 2px; }
.tier-pill {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
}
.tier-pill.tier-vip   { background: linear-gradient(135deg, #3b82f6, #6366f1); color: #fff; }
.tier-pill.tier-vvip  { background: linear-gradient(135deg, #8b5cf6, #ec4899); color: #fff; }
.tier-pill.tier-vvvip { background: linear-gradient(135deg, #f59e0b, #ef4444); color: #fff; }

.logout-btn {
  width: 32px; height: 32px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--ybc-text-muted);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}
.logout-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #fca5a5;
}

/* ── Main content ───────────────────────────────────────────────── */
.main {
  flex: 1;
  margin-left: 240px;
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: 60px;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--ybc-border);
  background: rgba(10, 10, 15, 0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  position: sticky; top: 0;
  z-index: 10;
}
.topbar-left { display: flex; align-items: center; gap: 14px; }
.topbar-right { display: flex; align-items: center; gap: 12px; }
.page-title {
  font-size: 15px; font-weight: 600;
  color: var(--ybc-text-strong);
}

.menu-toggle {
  display: none;
  flex-direction: column; gap: 4px;
  background: none; border: none; cursor: pointer;
  padding: 6px;
}
.menu-toggle span {
  width: 20px; height: 2px; background: var(--ybc-text);
  border-radius: 2px;
}

.content {
  flex: 1;
  padding: 32px;
  animation: ybc-fade-up 0.3s;
}

/* Page transition */
.page-fade-enter-active, .page-fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.page-fade-enter-from { opacity: 0; transform: translateY(6px); }
.page-fade-leave-to { opacity: 0; transform: translateY(-6px); }

/* ── Responsive ─────────────────────────────────────────────────── */
.mobile-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  z-index: 99;
}
.overlay-fade-enter-active, .overlay-fade-leave-active { transition: opacity 0.2s; }
.overlay-fade-enter-from, .overlay-fade-leave-to { opacity: 0; }

@media (max-width: 1023px) {
  .sidebar {
    transform: translateX(-100%);
    box-shadow: 0 0 40px rgba(0, 0, 0, 0.5);
  }
  .sidebar.open { transform: translateX(0); }
  .main { margin-left: 0; }
  .menu-toggle { display: flex; }
  .content { padding: 20px; }
  .topbar { padding: 0 16px; }
}
@media (min-width: 1024px) {
  .mobile-overlay { display: none; }
}
</style>
