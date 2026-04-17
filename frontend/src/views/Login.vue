<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="brand">
        <div class="brand-logo">YBC</div>
        <h1>Your Brand Consultant</h1>
        <p>AI-Powered Brand Strategy Platform</p>
      </div>
      <AuthTabs :initial-mode="'login'" @success="handleSuccess" />
    </div>

    <div class="auth-bg-text">
      <div v-for="t in bgTexts" :key="t" class="bg-word">{{ t }}</div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useUserStore } from '../store'
import AuthTabs from '../components/AuthTabs.vue'

const router = useRouter()
const store = useUserStore()

const bgTexts = ['战略规划', '品牌设计', '运营实施', 'Brand Strategy', 'Visual Identity', 'Market Analysis', '家具品牌', 'AI Agent']

function handleSuccess(user) {
  // After successful login/register, navigate by role
  router.push(store.isAdmin ? '/admin' : '/dashboard')
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0a0f;
  position: relative;
  overflow: hidden;
  padding: 20px;
}
.auth-page::before {
  content: '';
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 60% 50% at 20% 30%, rgba(99,102,241,0.15), transparent),
    radial-gradient(ellipse 60% 50% at 80% 70%, rgba(168,85,247,0.12), transparent);
}
.auth-card {
  position: relative;
  width: 100%;
  max-width: 420px;
  background: #12121a;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  padding: 36px 32px;
  box-shadow: 0 24px 64px rgba(0,0,0,0.5);
  z-index: 10;
}
.brand { text-align: center; margin-bottom: 28px; }
.brand-logo {
  display: inline-flex; align-items: center; justify-content: center;
  width: 52px; height: 52px;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  border-radius: 14px;
  font-size: 18px; font-weight: 800; color: #fff;
  letter-spacing: -0.5px;
  margin-bottom: 12px;
}
.brand h1 {
  font-size: 22px; font-weight: 700; color: #fff;
  margin: 0; letter-spacing: -0.3px;
}
.brand p {
  font-size: 12px; color: #71717a;
  margin: 6px 0 0;
}
.auth-bg-text {
  position: absolute; inset: 0;
  display: flex; flex-wrap: wrap; align-items: center; justify-content: center;
  gap: 40px; padding: 40px;
  opacity: 0.03; pointer-events: none;
}
.bg-word { font-size: 36px; font-weight: 900; color: #fff; white-space: nowrap; }

@media (max-width: 480px) {
  .auth-card { padding: 28px 20px; border-radius: 16px; }
  .brand-logo { width: 44px; height: 44px; font-size: 15px; }
  .brand h1 { font-size: 18px; }
}
</style>
