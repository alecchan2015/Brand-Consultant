<template>
  <div class="callback-page">
    <div class="callback-card">
      <div v-if="state === 'loading'">
        <div class="spinner"></div>
        <h2>正在完成 Google 登录…</h2>
        <p>请稍候</p>
      </div>
      <div v-else-if="state === 'pending'" class="pending">
        <div class="check-icon">⏳</div>
        <h2>注册成功</h2>
        <p>您的账号正在等待管理员审核，审核通过后即可登录。</p>
        <button class="btn" @click="$router.push('/')">返回首页</button>
      </div>
      <div v-else-if="state === 'error'" class="error">
        <div class="check-icon">❌</div>
        <h2>登录失败</h2>
        <p>{{ errorMsg }}</p>
        <button class="btn" @click="$router.push('/')">返回首页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../store'
import { authAPI } from '../api'

const router = useRouter()
const route = useRoute()
const store = useUserStore()

const state = ref('loading')     // 'loading' | 'pending' | 'error'
const errorMsg = ref('')

onMounted(async () => {
  const code = route.query.code
  const stateParam = route.query.state
  const savedState = sessionStorage.getItem('google_oauth_state')

  if (!code || !stateParam) {
    state.value = 'error'
    errorMsg.value = '缺少必要的回调参数'
    return
  }

  if (savedState && stateParam !== savedState) {
    state.value = 'error'
    errorMsg.value = 'state 不匹配（可能是 CSRF 或会话过期）'
    return
  }

  sessionStorage.removeItem('google_oauth_state')

  try {
    const res = await authAPI.googleCallback({ code, state: stateParam })
    if (res.pending_approval) {
      state.value = 'pending'
      return
    }
    if (res.access_token) {
      localStorage.setItem('token', res.access_token)
      store.token = res.access_token
      store.user = res.user
      router.push(store.isAdmin ? '/admin' : '/dashboard')
    } else {
      state.value = 'error'
      errorMsg.value = '未收到有效的登录凭证'
    }
  } catch (e) {
    state.value = 'error'
    errorMsg.value = e.message || 'Google 认证失败'
  }
})
</script>

<style scoped>
.callback-page {
  min-height: 100vh;
  background: #0a0a0f;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.callback-card {
  max-width: 440px; width: 100%;
  background: #12121a;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  padding: 48px 32px;
  text-align: center;
  color: #e4e4e7;
  box-shadow: 0 24px 64px rgba(0,0,0,0.5);
}
.callback-card h2 {
  margin: 20px 0 8px; font-size: 20px; color: #fff; font-weight: 700;
}
.callback-card p {
  font-size: 14px; color: #a1a1aa; line-height: 1.6; margin: 0;
}
.check-icon { font-size: 48px; margin-bottom: 8px; }
.spinner {
  width: 48px; height: 48px; margin: 0 auto;
  border: 3px solid rgba(99,102,241,0.2);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.btn {
  margin-top: 20px;
  padding: 10px 28px;
  background: #6366f1; color: #fff; border: none; border-radius: 10px;
  font-size: 14px; font-weight: 500; cursor: pointer;
  font-family: inherit;
}
.btn:hover { background: #818cf8; }
</style>
