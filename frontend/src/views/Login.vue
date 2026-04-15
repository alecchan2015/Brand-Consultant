<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="brand">
        <span class="brand-icon">🪑</span>
        <h1>Your Brand Consultant</h1>
        <p>AI-Powered Brand Strategy Platform</p>
      </div>

      <el-tabs v-model="tab" class="auth-tabs">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" @submit.prevent="handleLogin" label-position="top">
            <el-form-item label="用户名">
              <el-input v-model="loginForm.username" placeholder="请输入用户名" size="large" prefix-icon="User" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" size="large"
                prefix-icon="Lock" show-password @keyup.enter="handleLogin" />
            </el-form-item>
            <el-button type="primary" size="large" class="w-full" :loading="loading" @click="handleLogin">
              登 录
            </el-button>
          </el-form>
          <div class="hint">默认管理员账号：admin / Admin@123</div>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form :model="regForm" label-position="top">
            <el-form-item label="用户名">
              <el-input v-model="regForm.username" placeholder="3-20位字母数字" size="large" prefix-icon="User" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="regForm.email" placeholder="your@email.com" size="large" prefix-icon="Message" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="regForm.password" type="password" placeholder="至少6位" size="large"
                prefix-icon="Lock" show-password />
            </el-form-item>
            <el-button type="primary" size="large" class="w-full" :loading="loading" @click="handleRegister">
              注 册
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>

    <div class="auth-bg-text">
      <div v-for="t in bgTexts" :key="t" class="bg-word">{{ t }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../store'
import { authAPI } from '../api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const store = useUserStore()
const tab = ref('login')
const loading = ref(false)

const loginForm = ref({ username: '', password: '' })
const regForm = ref({ username: '', email: '', password: '' })

const bgTexts = ['战略规划', '品牌设计', '运营实施', 'Brand Strategy', 'Visual Identity', 'Market Analysis', '家具品牌', 'AI Agent']

async function handleLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    await store.login(loginForm.value.username, loginForm.value.password)
    ElMessage.success('登录成功')
    router.push(store.isAdmin ? '/admin' : '/dashboard')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!regForm.value.username || !regForm.value.email || !regForm.value.password) {
    ElMessage.warning('请填写完整信息')
    return
  }
  loading.value = true
  try {
    await authAPI.register(regForm.value)
    ElMessage.success('注册成功，请登录')
    tab.value = 'login'
    loginForm.value.username = regForm.value.username
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  position: relative;
  overflow: hidden;
}
.auth-card {
  width: 420px;
  background: rgba(255,255,255,0.97);
  border-radius: 16px;
  padding: 40px 36px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  z-index: 10;
}
.brand { text-align: center; margin-bottom: 28px; }
.brand-icon { font-size: 48px; display: block; margin-bottom: 8px; }
.brand h1 { font-size: 24px; font-weight: 700; color: #1a1a2e; }
.brand p { font-size: 13px; color: #888; margin-top: 4px; }
.auth-tabs { margin-top: 4px; }
.w-full { width: 100%; margin-top: 8px; }
.hint { text-align: center; font-size: 11px; color: #aaa; margin-top: 12px; }
.auth-bg-text {
  position: absolute; inset: 0;
  display: flex; flex-wrap: wrap; align-items: center; justify-content: center;
  gap: 40px; padding: 40px; opacity: 0.04; pointer-events: none;
}
.bg-word { font-size: 36px; font-weight: 900; color: #fff; white-space: nowrap; }
</style>
