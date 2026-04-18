<template>
  <div class="home-page" :class="{ 'mobile': isMobile }">
    <!-- Navigation Bar -->
    <nav class="nav-bar">
      <div class="nav-inner">
        <div class="nav-brand" @click="scrollToTop">
          <span class="nav-logo">YBC</span>
          <span class="nav-title">Your Brand Consultant</span>
        </div>
        <div class="nav-actions">
          <LangSwitch />
          <template v-if="store.isLoggedIn">
            <span class="nav-user">{{ store.user?.username }}</span>
            <button class="btn-nav" @click="goToDashboard">{{ $t('nav.dashboard') }}</button>
            <button class="btn-nav btn-ghost" @click="handleLogout">{{ $t('common.actions.logout') }}</button>
          </template>
          <template v-else>
            <button class="btn-nav" @click="showLoginDialog = true">{{ $t('common.actions.login') }}</button>
            <button class="btn-nav btn-primary-nav" @click="showRegisterDialog = true">{{ $t('common.actions.freeSignup') }}</button>
          </template>
        </div>
        <!-- Mobile menu -->
        <button class="mobile-menu-btn" @click="mobileMenuOpen = !mobileMenuOpen">
          <span></span><span></span><span></span>
        </button>
      </div>
      <!-- Mobile dropdown -->
      <transition name="slide-down">
        <div v-if="mobileMenuOpen" class="mobile-menu">
          <div class="mobile-lang-wrap"><LangSwitch /></div>
          <template v-if="store.isLoggedIn">
            <button @click="goToDashboard; mobileMenuOpen = false">{{ $t('nav.dashboard') }}</button>
            <button @click="handleLogout; mobileMenuOpen = false">{{ $t('common.actions.logout') }}</button>
          </template>
          <template v-else>
            <button @click="showLoginDialog = true; mobileMenuOpen = false">{{ $t('common.actions.login') }}</button>
            <button @click="showRegisterDialog = true; mobileMenuOpen = false">{{ $t('common.actions.freeSignup') }}</button>
          </template>
        </div>
      </transition>
    </nav>

    <!-- Hero Section -->
    <section class="hero">
      <div class="hero-bg">
        <div class="hero-gradient"></div>
        <div class="hero-grid"></div>
        <div class="hero-glow hero-glow-1"></div>
        <div class="hero-glow hero-glow-2"></div>
        <div class="hero-glow hero-glow-3"></div>
        <!-- Floating particles -->
        <div class="particles">
          <div v-for="i in 20" :key="i" class="particle" :style="particleStyle(i)"></div>
        </div>
      </div>

      <div class="hero-content">
        <div class="hero-badge">
          <span class="badge-dot"></span>
          {{ $t('home.badge') }}
        </div>
        <h1 class="hero-title">
          <span class="title-line">{{ $t('home.heroLine1') }}</span>
          <span class="title-line title-highlight">{{ $t('home.heroLine2') }}</span>
        </h1>
        <p class="hero-subtitle">
          {{ $t('home.subtitle') }}
        </p>

        <!-- Main Input Area -->
        <div class="input-area">
          <div class="input-card">
            <div class="input-brand-row">
              <div class="input-brand-toggle" @click="showBrandInput = !showBrandInput">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M8 1v14M1 8h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span>{{ showBrandInput ? $t('home.hideBrand') : $t('home.addBrand') }}</span>
              </div>
            </div>
            <transition name="expand">
              <div v-if="showBrandInput" class="brand-input-wrap">
                <input
                  v-model="form.brand_name"
                  class="brand-input"
                  :placeholder="$t('home.brandPlaceholder')"
                  maxlength="50"
                />
              </div>
            </transition>
            <div class="main-input-wrap">
              <textarea
                ref="queryInput"
                v-model="form.query"
                class="main-input"
                :rows="isMobile ? 3 : 2"
                :placeholder="$t('home.queryPlaceholder')"
                maxlength="1000"
                @keydown.enter.ctrl="handleSubmit"
                @keydown.enter.meta="handleSubmit"
              ></textarea>
              <button class="submit-btn" :class="{ loading: submitting }" :disabled="!form.query.trim() || submitting" @click="handleSubmit">
                <span v-if="!submitting" class="submit-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </span>
                <span v-else class="submit-spinner"></span>
              </button>
            </div>
            <div class="input-footer">
              <span class="char-count">{{ form.query.length }}/1000</span>
              <span class="shortcut-hint">{{ isMobile ? $t('home.shortcutHintMobile') : $t('home.shortcutHint') }}</span>
            </div>
          </div>
        </div>

        <!-- Agent Selection -->
        <div class="agent-section">
          <div class="agent-section-header">
            <span class="agent-section-title">{{ $t('home.selectAgent') }}</span>
            <button class="select-all-btn" @click="toggleSelectAll">
              {{ allSelected ? $t('home.deselectAll') : $t('home.selectAll') }}
            </button>
          </div>
          <div class="agent-cards">
            <div
              v-for="agent in agents"
              :key="agent.type"
              class="agent-chip"
              :class="{ selected: form.agents_selected.includes(agent.type) }"
              @click="toggleAgent(agent.type)"
            >
              <span class="agent-chip-icon">{{ agent.icon }}</span>
              <div class="agent-chip-info">
                <span class="agent-chip-name">{{ agent.name }}</span>
                <span class="agent-chip-desc">{{ agent.desc }}</span>
              </div>
              <div class="agent-chip-check">
                <svg v-if="form.agents_selected.includes(agent.type)" width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M13.3 4.3L6 11.6L2.7 8.3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
            </div>
          </div>
          <transition name="fade">
            <div v-if="form.agents_selected.length > 1" class="pipeline-hint">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5"/>
                <path d="M8 5v3M8 10.5v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
              {{ $t('home.pipelineHint', { chain: selectedAgentNames.join(' → ') }) }}
            </div>
          </transition>
          <transition name="fade">
            <div v-if="inlineError" class="inline-error">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5"/>
                <path d="M8 5v3M8 10v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
              {{ inlineError }}
            </div>
          </transition>
        </div>
      </div>
    </section>

    <!-- Features Section -->
    <section class="features">
      <div class="features-inner">
        <h2 class="section-heading">{{ $t('home.features.title') }}</h2>
        <p class="section-sub">{{ $t('home.features.subtitle') }}</p>
        <div class="features-grid">
          <div class="feature-card" v-for="f in features" :key="f.title">
            <div class="feature-icon">{{ f.icon }}</div>
            <h3>{{ f.title }}</h3>
            <p>{{ f.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- How it works -->
    <section class="how-it-works">
      <div class="how-inner">
        <h2 class="section-heading">{{ $t('home.steps.title') }}</h2>
        <div class="steps">
          <div class="step" v-for="(s, i) in steps" :key="i">
            <div class="step-num">{{ i + 1 }}</div>
            <h3>{{ s.title }}</h3>
            <p>{{ s.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="cta-section">
      <div class="cta-inner">
        <h2>{{ $t('home.cta.title') }}</h2>
        <p>{{ $t('home.cta.subtitle') }}</p>
        <button class="btn-cta" @click="scrollToInput">{{ $t('home.cta.button') }}</button>
      </div>
    </section>

    <!-- Footer -->
    <footer class="site-footer">
      <div class="footer-inner">
        <div class="footer-brand">
          <span class="nav-logo">YBC</span>
          <span>Your Brand Consultant</span>
        </div>
        <p class="footer-copy">{{ $t('footer.copyright', { year: new Date().getFullYear() }) }}</p>
      </div>
    </footer>

    <!-- Login Dialog -->
    <!-- Unified Auth Modal (login + register via AuthTabs) -->
    <teleport to="body">
      <transition name="modal">
        <div v-if="showLoginDialog || showRegisterDialog" class="modal-overlay" @click.self="closeAuthModals">
          <div class="modal-card auth-modal-card">
            <button class="modal-close" @click="closeAuthModals">&times;</button>
            <div class="modal-header">
              <span class="nav-logo modal-logo">YBC</span>
              <h2>{{ showRegisterDialog ? $t('auth.modalTitleRegister') : $t('auth.modalTitleLogin') }}</h2>
              <p>{{ $t('auth.modalSub') }}</p>
            </div>
            <AuthTabs
              :initial-mode="showRegisterDialog ? 'register' : 'login'"
              @success="onAuthSuccess"
            />
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useUserStore } from '../store'
import { authAPI, tasksAPI, agentsAPI } from '../api'
import AuthTabs from '../components/AuthTabs.vue'
import LangSwitch from '../components/LangSwitch.vue'

const { t, locale } = useI18n()

const router = useRouter()
const store = useUserStore()

// Responsive
const isMobile = ref(false)
const mobileMenuOpen = ref(false)

function checkMobile() {
  isMobile.value = window.innerWidth < 768
}
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})
onUnmounted(() => window.removeEventListener('resize', checkMobile))

// Form state
const form = ref({ query: '', brand_name: '', agents_selected: ['strategy', 'brand', 'operations'] })
const showBrandInput = ref(false)
const submitting = ref(false)
const queryInput = ref(null)

// Agents
const agents = computed(() => [
  { type: 'strategy',      icon: '🎯', name: t('common.agent.strategy'),     desc: t('home.agentDesc.strategy') },
  { type: 'brand',         icon: '🎨', name: t('common.agent.brand'),        desc: t('home.agentDesc.brand') },
  { type: 'logo_design',   icon: '✨', name: t('common.agent.logoDesign'),   desc: t('home.agentDesc.logo_design') },
  { type: 'poster_design', icon: '🖼️', name: t('common.agent.posterDesign'), desc: t('home.agentDesc.poster_design') },
  { type: 'operations',    icon: '🚀', name: t('common.agent.operations'),   desc: t('home.agentDesc.operations') },
])

const selectedAgentNames = computed(() => {
  const nameMap = {
    strategy:      t('common.agent.strategy'),
    brand:         t('common.agent.brand'),
    logo_design:   t('common.agent.logoDesign'),
    poster_design: t('common.agent.posterDesign'),
    operations:    t('common.agent.operations'),
  }
  return ['strategy', 'brand', 'logo_design', 'poster_design', 'operations']
    .filter(a => form.value.agents_selected.includes(a))
    .map(a => nameMap[a])
})
const allSelected = computed(() => form.value.agents_selected.length === agents.value.length)

function toggleAgent(type) {
  const idx = form.value.agents_selected.indexOf(type)
  if (idx > -1) form.value.agents_selected.splice(idx, 1)
  else form.value.agents_selected.push(type)
}
function toggleSelectAll() {
  if (allSelected.value) form.value.agents_selected = []
  else form.value.agents_selected = agents.value.map(a => a.type)
}

// Auth dialogs — unified AuthTabs modal
const showLoginDialog = ref(false)
const showRegisterDialog = ref(false)

function closeAuthModals() {
  showLoginDialog.value = false
  showRegisterDialog.value = false
}

async function onAuthSuccess(user) {
  closeAuthModals()
  // If a task submit was pending before login, continue it
  if (pendingSubmit.value) {
    pendingSubmit.value = false
    await doSubmitTask()
  }
}

function handleLogout() {
  store.logout()
  mobileMenuOpen.value = false
}

// Submit task
const pendingSubmit = ref(false)
const inlineError = ref('')

function handleSubmit() {
  inlineError.value = ''
  if (!form.value.query.trim()) { inlineError.value = t('home.errorNoQuery'); return }
  if (!form.value.agents_selected.length) {
    inlineError.value = t('home.errorNoAgent')
    return
  }
  if (!store.isLoggedIn) {
    pendingSubmit.value = true
    showLoginDialog.value = true
    return
  }
  doSubmitTask()
}

async function doSubmitTask() {
  submitting.value = true
  try {
    const task = await tasksAPI.create({
      query: form.value.query,
      brand_name: form.value.brand_name,
      agents_selected: form.value.agents_selected,
      locale: locale.value,
    })
    router.push(`/tasks/${task.id}`)
  } catch (e) {
    inlineError.value = e.message || t('home.errorCreate')
  } finally {
    submitting.value = false
  }
}

function goToDashboard() {
  router.push(store.isAdmin ? '/admin' : '/dashboard')
}

// Particles
function particleStyle(i) {
  const seed = i * 137.508
  return {
    left: `${(seed * 3.7) % 100}%`,
    top: `${(seed * 2.3) % 100}%`,
    animationDelay: `${(i * 0.5) % 8}s`,
    animationDuration: `${6 + (i % 5) * 2}s`,
    width: `${2 + (i % 4)}px`,
    height: `${2 + (i % 4)}px`,
    opacity: 0.15 + (i % 5) * 0.08,
  }
}

// Scroll helpers
function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
function scrollToInput() {
  queryInput.value?.focus()
  document.querySelector('.input-area')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

// Features data
const features = computed(() => [
  { icon: '🎯', title: t('home.features.strategy.title'), desc: t('home.features.strategy.desc') },
  { icon: '🎨', title: t('home.features.brand.title'),    desc: t('home.features.brand.desc') },
  { icon: '✨', title: t('home.features.logo.title'),     desc: t('home.features.logo.desc') },
  { icon: '🚀', title: t('home.features.ops.title'),      desc: t('home.features.ops.desc') },
])

const steps = computed(() => [
  { title: t('home.steps.s1.title'), desc: t('home.steps.s1.desc') },
  { title: t('home.steps.s2.title'), desc: t('home.steps.s2.desc') },
  { title: t('home.steps.s3.title'), desc: t('home.steps.s3.desc') },
])

// Load agents from API
onMounted(async () => {
  try {
    const list = await agentsAPI.list()
    if (list?.length) {
      agents.value = list.map(a => ({
        ...a,
        desc: {
          strategy: '市场分析·竞争定位·品牌战略',
          brand: 'VI体系·色彩规范·视觉物料',
          logo_design: 'AI生成Logo·多格式输出',
          poster_design: '节气商业海报·9:16 竖版',
          operations: '渠道策略·营销计划·执行路径',
        }[a.type] || ''
      }))
    }
  } catch {}
})
</script>

<style scoped>
/* ============ Reset & Base ============ */
.home-page {
  --color-bg: #0a0a0f;
  --color-surface: #12121a;
  --color-border: rgba(255,255,255,0.08);
  --color-text: #e4e4e7;
  --color-text-dim: #71717a;
  --color-accent: #6366f1;
  --color-accent-light: #818cf8;
  --color-accent-glow: rgba(99,102,241,0.3);
  --nav-height: 64px;
  --max-width: 1100px;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  min-height: 100vh;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
  /* WeChat compatibility */
  -webkit-overflow-scrolling: touch;
  -webkit-tap-highlight-color: transparent;
}

/* ============ Navigation ============ */
.nav-bar {
  position: fixed; top: 0; left: 0; right: 0;
  z-index: 100;
  background: rgba(10,10,15,0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--color-border);
  height: var(--nav-height);
}
.nav-inner {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 0 24px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.nav-brand {
  display: flex; align-items: center; gap: 10px; cursor: pointer;
}
.nav-logo {
  display: inline-flex; align-items: center; justify-content: center;
  width: 36px; height: 36px;
  background: linear-gradient(135deg, var(--color-accent), #a855f7);
  border-radius: 10px;
  font-size: 13px; font-weight: 800; color: #fff;
  letter-spacing: -0.5px;
  flex-shrink: 0;
}
.nav-title {
  font-size: 15px; font-weight: 600; color: #fff;
  letter-spacing: -0.3px;
}
.nav-actions {
  display: flex; align-items: center; gap: 8px;
}
.nav-user {
  font-size: 13px; color: var(--color-text-dim); margin-right: 4px;
}
.btn-nav {
  padding: 7px 16px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.btn-nav:hover { border-color: var(--color-accent-light); color: #fff; }
.btn-primary-nav {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: #fff;
}
.btn-primary-nav:hover { background: var(--color-accent-light); }
.btn-ghost { border-color: transparent; }

.mobile-menu-btn {
  display: none;
  flex-direction: column; gap: 5px;
  background: none; border: none; cursor: pointer; padding: 8px;
}
.mobile-menu-btn span {
  display: block; width: 20px; height: 2px; background: #fff; border-radius: 2px;
  transition: 0.2s;
}
.mobile-menu {
  position: absolute; top: var(--nav-height); left: 0; right: 0;
  background: rgba(10,10,15,0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--color-border);
  padding: 12px 24px;
  display: flex; flex-direction: column; gap: 4px;
}
.mobile-menu button {
  background: none; border: none; color: var(--color-text);
  padding: 12px 0; font-size: 15px; text-align: left;
  cursor: pointer; font-family: inherit;
  border-bottom: 1px solid var(--color-border);
}
.mobile-menu button:last-child { border: none; }

/* ============ Hero ============ */
.hero {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: calc(var(--nav-height) + 40px) 24px 60px;
}
.hero-bg {
  position: absolute; inset: 0; overflow: hidden;
}
.hero-gradient {
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99,102,241,0.15), transparent),
    radial-gradient(ellipse 60% 40% at 80% 50%, rgba(168,85,247,0.08), transparent),
    radial-gradient(ellipse 60% 40% at 20% 80%, rgba(59,130,246,0.08), transparent);
}
.hero-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
  background-size: 60px 60px;
  mask-image: radial-gradient(ellipse 70% 60% at 50% 40%, black, transparent);
  -webkit-mask-image: radial-gradient(ellipse 70% 60% at 50% 40%, black, transparent);
}
.hero-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  animation: glow-drift 12s ease-in-out infinite;
}
.hero-glow-1 {
  width: 400px; height: 400px;
  background: rgba(99,102,241,0.12);
  top: 10%; left: 20%;
}
.hero-glow-2 {
  width: 300px; height: 300px;
  background: rgba(168,85,247,0.1);
  top: 50%; right: 15%;
  animation-delay: -4s;
}
.hero-glow-3 {
  width: 350px; height: 350px;
  background: rgba(59,130,246,0.08);
  bottom: 10%; left: 40%;
  animation-delay: -8s;
}
@keyframes glow-drift {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -20px) scale(1.1); }
  66% { transform: translate(-20px, 30px) scale(0.9); }
}

.particles { position: absolute; inset: 0; }
.particle {
  position: absolute;
  background: rgba(99,102,241,0.6);
  border-radius: 50%;
  animation: float-particle linear infinite;
}
@keyframes float-particle {
  0% { transform: translateY(0) translateX(0); opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { transform: translateY(-100px) translateX(30px); opacity: 0; }
}

.hero-content {
  position: relative; z-index: 2;
  max-width: var(--max-width);
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 16px;
  border-radius: 100px;
  background: rgba(99,102,241,0.1);
  border: 1px solid rgba(99,102,241,0.2);
  font-size: 12px; font-weight: 500;
  color: var(--color-accent-light);
  margin-bottom: 24px;
  letter-spacing: 0.5px;
}
.badge-dot {
  width: 6px; height: 6px;
  background: #22c55e;
  border-radius: 50%;
  animation: pulse-dot 2s infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.hero-title {
  font-size: clamp(32px, 5vw, 56px);
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -1px;
  margin-bottom: 20px;
}
.title-line { display: block; color: #fff; }
.title-highlight {
  background: linear-gradient(135deg, var(--color-accent-light), #c084fc, #60a5fa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-subtitle {
  font-size: clamp(14px, 2vw, 17px);
  color: var(--color-text-dim);
  max-width: 600px;
  line-height: 1.7;
  margin-bottom: 40px;
}

/* ============ Input Area ============ */
.input-area {
  width: 100%;
  max-width: 680px;
  margin-bottom: 32px;
}
.input-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  padding: 16px;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.input-card:focus-within {
  border-color: rgba(99,102,241,0.4);
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1), 0 8px 32px rgba(0,0,0,0.3);
}
.input-brand-row {
  margin-bottom: 8px;
}
.input-brand-toggle {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--color-text-dim);
  cursor: pointer; padding: 4px 0;
  transition: color 0.2s;
}
.input-brand-toggle:hover { color: var(--color-accent-light); }
.input-brand-toggle svg { width: 12px; height: 12px; }
.brand-input-wrap { margin-bottom: 8px; }
.brand-input {
  width: 100%;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 10px 14px;
  color: #fff;
  font-size: 14px;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
.brand-input:focus { border-color: rgba(99,102,241,0.4); }
.brand-input::placeholder { color: #52525b; }
.main-input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.main-input {
  flex: 1;
  background: transparent;
  border: none;
  color: #fff;
  font-size: 15px;
  line-height: 1.6;
  resize: none;
  outline: none;
  font-family: inherit;
  padding: 4px 0;
}
.main-input::placeholder { color: #52525b; }
.submit-btn {
  width: 44px; height: 44px;
  border-radius: 12px;
  border: none;
  background: var(--color-accent);
  color: #fff;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
}
.submit-btn:hover:not(:disabled) {
  background: var(--color-accent-light);
  transform: scale(1.05);
}
.submit-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.submit-spinner {
  width: 18px; height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.input-footer {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 8px; padding-top: 8px;
  border-top: 1px solid var(--color-border);
}
.char-count, .shortcut-hint {
  font-size: 11px; color: #52525b;
}

/* ============ Agent Section ============ */
.agent-section {
  width: 100%;
  max-width: 680px;
}
.agent-section-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px;
}
.agent-section-title {
  font-size: 13px; font-weight: 600; color: var(--color-text-dim);
  letter-spacing: 0.5px; text-transform: uppercase;
}
.select-all-btn {
  background: none; border: none;
  color: var(--color-accent-light);
  font-size: 12px; cursor: pointer;
  font-family: inherit;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.2s;
}
.select-all-btn:hover { background: rgba(99,102,241,0.1); }

.agent-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.agent-chip {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 14px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
  -webkit-user-select: none;
}
.agent-chip:hover {
  border-color: rgba(99,102,241,0.3);
  background: rgba(99,102,241,0.05);
}
.agent-chip.selected {
  border-color: var(--color-accent);
  background: rgba(99,102,241,0.08);
  box-shadow: 0 0 0 1px rgba(99,102,241,0.2);
}
.agent-chip-icon { font-size: 24px; flex-shrink: 0; }
.agent-chip-info { flex: 1; min-width: 0; }
.agent-chip-name {
  display: block;
  font-size: 13px; font-weight: 600; color: #fff;
  margin-bottom: 2px;
}
.agent-chip-desc {
  display: block;
  font-size: 11px; color: var(--color-text-dim);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.agent-chip-check {
  width: 20px; height: 20px;
  border-radius: 6px;
  border: 1.5px solid var(--color-border);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
  color: var(--color-accent-light);
}
.agent-chip.selected .agent-chip-check {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: #fff;
}
.pipeline-hint {
  display: flex; align-items: center; gap: 6px;
  margin-top: 10px; padding: 8px 12px;
  background: rgba(99,102,241,0.06);
  border: 1px solid rgba(99,102,241,0.12);
  border-radius: 8px;
  font-size: 12px; color: var(--color-accent-light);
}
.inline-error {
  display: flex; align-items: center; gap: 6px;
  margin-top: 10px; padding: 8px 12px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 8px;
  font-size: 12px; color: #fca5a5;
}

/* ============ Features ============ */
.features {
  padding: 80px 24px;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
}
.features-inner, .how-inner, .cta-inner {
  max-width: var(--max-width);
  margin: 0 auto;
}
.section-heading {
  text-align: center;
  font-size: clamp(24px, 3vw, 36px);
  font-weight: 800;
  color: #fff;
  margin-bottom: 8px;
  letter-spacing: -0.5px;
}
.section-sub {
  text-align: center;
  font-size: 15px; color: var(--color-text-dim);
  margin-bottom: 48px;
}
.features-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
.feature-card {
  padding: 28px 24px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  transition: all 0.3s;
}
.feature-card:hover {
  border-color: rgba(99,102,241,0.2);
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0,0,0,0.3);
}
.feature-icon { font-size: 32px; margin-bottom: 16px; }
.feature-card h3 {
  font-size: 16px; font-weight: 700; color: #fff;
  margin-bottom: 8px;
}
.feature-card p {
  font-size: 13px; color: var(--color-text-dim);
  line-height: 1.6;
}

/* ============ How it Works ============ */
.how-it-works {
  padding: 80px 24px;
}
.steps {
  display: flex; gap: 24px;
  justify-content: center;
}
.step {
  flex: 1; max-width: 280px;
  text-align: center;
  padding: 32px 24px;
}
.step-num {
  width: 48px; height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--color-accent), #a855f7);
  color: #fff;
  font-size: 20px; font-weight: 800;
  display: inline-flex; align-items: center; justify-content: center;
  margin-bottom: 20px;
}
.step h3 {
  font-size: 17px; font-weight: 700; color: #fff;
  margin-bottom: 8px;
}
.step p {
  font-size: 13px; color: var(--color-text-dim);
  line-height: 1.6;
}

/* ============ CTA ============ */
.cta-section {
  padding: 80px 24px;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  text-align: center;
}
.cta-inner h2 {
  font-size: clamp(24px, 3vw, 36px);
  font-weight: 800; color: #fff;
  margin-bottom: 12px;
}
.cta-inner p {
  font-size: 15px; color: var(--color-text-dim);
  margin-bottom: 32px;
}
.btn-cta {
  padding: 14px 40px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, var(--color-accent), #a855f7);
  color: #fff;
  font-size: 16px; font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  font-family: inherit;
}
.btn-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(99,102,241,0.4);
}

/* ============ Footer ============ */
.site-footer {
  padding: 32px 24px;
  border-top: 1px solid var(--color-border);
}
.footer-inner {
  max-width: var(--max-width);
  margin: 0 auto;
  display: flex; justify-content: space-between; align-items: center;
}
.footer-brand {
  display: flex; align-items: center; gap: 10px;
  font-size: 14px; font-weight: 600; color: var(--color-text-dim);
}
.footer-copy {
  font-size: 12px; color: #3f3f46;
}

/* ============ Modal ============ */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.modal-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 20px;
  padding: 36px;
  width: 100%;
  max-width: 400px;
  position: relative;
}
.modal-close {
  position: absolute; top: 16px; right: 16px;
  background: none; border: none;
  color: var(--color-text-dim);
  font-size: 24px; cursor: pointer;
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 8px;
  transition: 0.2s;
}
.modal-close:hover { background: rgba(255,255,255,0.05); color: #fff; }
.modal-header {
  text-align: center; margin-bottom: 28px;
}
.modal-logo { margin-bottom: 16px; }
.modal-header h2 {
  font-size: 22px; font-weight: 700; color: #fff;
  margin: 12px 0 6px;
}
.modal-header p {
  font-size: 13px; color: var(--color-text-dim);
}
.modal-form { display: flex; flex-direction: column; gap: 16px; }
.form-group label {
  display: block; font-size: 13px; font-weight: 500;
  color: var(--color-text-dim); margin-bottom: 6px;
}
.form-group input {
  width: 100%;
  padding: 11px 14px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  color: #fff;
  font-size: 14px;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
.form-group input:focus { border-color: var(--color-accent); }
.form-group input::placeholder { color: #52525b; }
.btn-modal-submit {
  width: 100%;
  padding: 12px;
  border-radius: 10px;
  border: none;
  background: var(--color-accent);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 4px;
  font-family: inherit;
  transition: 0.2s;
}
.btn-modal-submit:hover:not(:disabled) { background: var(--color-accent-light); }
.btn-modal-submit:disabled { opacity: 0.5; cursor: not-allowed; }
.modal-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: var(--color-text-dim);
}
.modal-footer a {
  color: var(--color-accent-light);
  cursor: pointer;
  text-decoration: none;
  font-weight: 500;
}
.modal-footer a:hover { text-decoration: underline; }

/* ============ Transitions ============ */
.modal-enter-active, .modal-leave-active { transition: opacity 0.25s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-card { animation: modal-in 0.25s; }
@keyframes modal-in {
  from { transform: scale(0.95) translateY(10px); opacity: 0; }
  to { transform: scale(1) translateY(0); opacity: 1; }
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.expand-enter-active, .expand-leave-active { transition: all 0.2s; overflow: hidden; }
.expand-enter-from, .expand-leave-to { max-height: 0; opacity: 0; margin-bottom: 0; }
.expand-enter-to, .expand-leave-from { max-height: 60px; opacity: 1; }
.slide-down-enter-active, .slide-down-leave-active { transition: all 0.2s; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-8px); }

/* ============ Mobile Responsive ============ */
@media (max-width: 767px) {
  .nav-actions { display: none; }
  .mobile-menu-btn { display: flex; }
  .nav-title { font-size: 13px; }

  .hero {
    min-height: auto;
    padding: calc(var(--nav-height) + 24px) 16px 40px;
  }
  .hero-badge { font-size: 11px; margin-bottom: 16px; }
  .hero-title { margin-bottom: 14px; }
  .hero-subtitle { font-size: 14px; margin-bottom: 28px; }

  .input-area { max-width: 100%; }
  .input-card { padding: 12px; }

  .agent-cards {
    grid-template-columns: 1fr;
  }
  .agent-chip { padding: 10px 12px; }

  .features { padding: 48px 16px; }
  .features-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  .feature-card { padding: 20px 16px; }
  .feature-icon { font-size: 26px; margin-bottom: 10px; }
  .feature-card h3 { font-size: 14px; }
  .feature-card p { font-size: 12px; }

  .how-it-works { padding: 48px 16px; }
  .steps { flex-direction: column; align-items: center; }
  .step { max-width: 100%; padding: 20px 16px; }

  .cta-section { padding: 48px 16px; }
  .btn-cta { width: 100%; padding: 14px 24px; }

  .footer-inner { flex-direction: column; gap: 8px; text-align: center; }

  .modal-card { padding: 24px 20px; margin: 16px; }
}

/* Tablet */
@media (min-width: 768px) and (max-width: 1023px) {
  .features-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* WeChat / iOS safe area */
@supports (padding-bottom: env(safe-area-inset-bottom)) {
  .site-footer {
    padding-bottom: calc(32px + env(safe-area-inset-bottom));
  }
  .nav-bar {
    padding-top: env(safe-area-inset-top);
    height: calc(var(--nav-height) + env(safe-area-inset-top));
  }
}
</style>
