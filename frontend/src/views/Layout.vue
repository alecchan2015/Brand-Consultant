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
            class="nav-item" :class="{ active: route.path === item.path }">
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
              <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" fill="none"/>
              <path d="M8 4v4l2.5 1.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <span>{{ store.user?.credits ?? 0 }}</span>
            <span class="credit-unit">积分</span>
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
                  <span v-else>普通用户</span>
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
          <el-tag v-if="store.isAdmin" type="danger" effect="dark" size="small" @click="$router.push('/admin')" style="cursor:pointer">
            管理后台 →
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
import { useUserStore } from '../store'
import { ElMessageBox } from 'element-plus'
import {
  Grid, Plus, PictureFilled, Picture, Star, Tickets, SwitchButton,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const store = useUserStore()

const mobileOpen = ref(false)
// Auto-close mobile drawer when navigating
watch(() => route.path, () => { mobileOpen.value = false })

const TIER_LABELS = { vip: 'VIP', vvip: 'VVIP', vvvip: 'VVVIP' }
const tierLabel = computed(() => TIER_LABELS[store.user?.tier] || '')

const navItems = computed(() => {
  const base = [
    { path: '/dashboard',  label: '工作台',   icon: markRaw(Grid) },
    { path: '/tasks/new',  label: '新建任务', icon: markRaw(Plus) },
    { path: '/logo',       label: 'Logo 生成', icon: markRaw(PictureFilled) },
    { path: '/poster',     label: '海报生成',  icon: markRaw(Picture) },
    {
      path: '/membership',
      label: '会员升级',
      icon: markRaw(Star),
      badge: tierLabel.value,
      badgeType: store.user?.tier,
    },
    { path: '/orders',     label: '我的订单', icon: markRaw(Tickets) },
  ]
  return base
})

const PAGE_TITLES = {
  '/dashboard':      '工作台',
  '/tasks/new':      '新建任务',
  '/logo':           'Logo 生成',
  '/poster':         '海报生成',
  '/membership':     '会员中心',
  '/orders':         '我的订单',
}
const pageTitle = computed(() => {
  if (route.path.startsWith('/tasks/') && route.path !== '/tasks/new') return '任务详情'
  if (route.path.startsWith('/payment/')) return '订单支付'
  return PAGE_TITLES[route.path] || 'Your Brand Consultant'
})

function toggleSidebar() { mobileOpen.value = !mobileOpen.value }

async function logout() {
  await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
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
