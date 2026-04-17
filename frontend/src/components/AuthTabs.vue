<template>
  <div class="auth-tabs">
    <!-- Mode switcher: 登录 / 注册 -->
    <div class="mode-switch">
      <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
      <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
    </div>

    <!-- Channel tabs -->
    <div class="channel-tabs">
      <button
        v-for="ch in availableChannels"
        :key="ch.key"
        :class="{ active: activeChannel === ch.key }"
        @click="activeChannel = ch.key"
      >
        <span class="ch-icon">{{ ch.icon }}</span>
        <span>{{ ch.label }}</span>
      </button>
    </div>

    <!-- ── Username + Password ── -->
    <div v-if="activeChannel === 'username_password'" class="channel-body">
      <div class="field">
        <label>用户名</label>
        <input v-model="form.username" autocomplete="username" placeholder="请输入用户名" />
      </div>
      <div v-if="mode === 'register'" class="field">
        <label>邮箱</label>
        <input v-model="form.email" type="email" autocomplete="email" placeholder="your@email.com" />
      </div>
      <div class="field">
        <label>密码</label>
        <input v-model="form.password" type="password"
               :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
               placeholder="请输入密码" @keyup.enter="submit" />
      </div>
      <button class="submit" :disabled="loading" @click="submit">
        {{ loading ? '处理中…' : (mode === 'login' ? '登 录' : '注 册') }}
      </button>
    </div>

    <!-- ── Email OTP ── -->
    <div v-if="activeChannel === 'email_otp'" class="channel-body">
      <div class="field">
        <label>邮箱</label>
        <input v-model="form.email" type="email" autocomplete="email" placeholder="your@email.com" />
      </div>
      <div class="field otp-field">
        <label>验证码</label>
        <div class="otp-row">
          <input v-model="form.otp" inputmode="numeric" maxlength="6" placeholder="6 位验证码" />
          <button class="otp-btn" :disabled="otpCooldown > 0 || !form.email || otpSending" @click="sendOtp('email')">
            {{ otpSending ? '发送中…' : (otpCooldown > 0 ? `${otpCooldown}s` : '发送验证码') }}
          </button>
        </div>
      </div>
      <div v-if="mode === 'register'" class="field optional-block">
        <label class="toggle-company" @click="showCompany = !showCompany">
          <span>{{ showCompany ? '▾' : '▸' }}</span> 完善企业信息（选填）
        </label>
        <div v-if="showCompany" class="company-fields">
          <input v-model="profile.company_name" placeholder="公司名称" />
          <input v-model="profile.industry" placeholder="所在行业" />
          <input v-model="profile.position" placeholder="职位" />
          <select v-model="profile.company_size">
            <option value="">公司规模</option>
            <option value="1-10">1-10 人</option>
            <option value="11-50">11-50 人</option>
            <option value="51-200">51-200 人</option>
            <option value="201-1000">201-1000 人</option>
            <option value="1000+">1000+ 人</option>
          </select>
        </div>
      </div>
      <button class="submit" :disabled="loading" @click="submit">
        {{ loading ? '处理中…' : (mode === 'login' ? '登 录' : '完成注册') }}
      </button>
    </div>

    <!-- ── Phone SMS ── -->
    <div v-if="activeChannel === 'phone_sms'" class="channel-body">
      <div class="field">
        <label>手机号</label>
        <input v-model="form.phone" inputmode="numeric" maxlength="11" placeholder="11 位手机号" />
      </div>
      <div class="field otp-field">
        <label>验证码</label>
        <div class="otp-row">
          <input v-model="form.otp" inputmode="numeric" maxlength="6" placeholder="6 位验证码" />
          <button class="otp-btn" :disabled="otpCooldown > 0 || !isValidPhone || otpSending" @click="sendOtp('phone')">
            {{ otpSending ? '发送中…' : (otpCooldown > 0 ? `${otpCooldown}s` : '发送验证码') }}
          </button>
        </div>
      </div>
      <button class="submit" :disabled="loading" @click="submit">
        {{ loading ? '处理中…' : (mode === 'login' ? '登 录' : '完成注册') }}
      </button>
    </div>

    <!-- ── Google OAuth ── -->
    <div v-if="activeChannel === 'google_oauth'" class="channel-body google-body">
      <p class="google-hint">使用您的 Google 账号快速{{ mode === 'login' ? '登录' : '注册' }}</p>
      <button class="submit google-btn" :disabled="loading" @click="startGoogleAuth">
        <svg width="18" height="18" viewBox="0 0 18 18" style="margin-right:8px;">
          <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.17-1.84H9v3.48h4.84c-.21 1.12-.84 2.07-1.79 2.71v2.26h2.9c1.7-1.57 2.69-3.88 2.69-6.61z"/>
          <path fill="#34A853" d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.9-2.26c-.81.54-1.83.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33C2.44 15.98 5.48 18 9 18z"/>
          <path fill="#FBBC04" d="M3.95 10.7c-.18-.54-.28-1.12-.28-1.7s.1-1.16.28-1.7V4.96H.96C.35 6.17 0 7.55 0 9s.35 2.83.96 4.04l2.99-2.34z"/>
          <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0 5.48 0 2.44 2.02.96 4.96l2.99 2.34C4.66 5.17 6.65 3.58 9 3.58z"/>
        </svg>
        继续使用 Google
      </button>
    </div>

    <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
    <p v-if="pendingMsg" class="pending-msg">✓ {{ pendingMsg }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../store'
import { authAPI } from '../api'

const props = defineProps({
  initialMode: { type: String, default: 'login' },   // 'login' | 'register'
})
const emit = defineEmits(['success'])

const router = useRouter()
const store = useUserStore()

const mode = ref(props.initialMode)
const activeChannel = ref('username_password')

const form = ref({
  username: '',
  email: '',
  phone: '',
  password: '',
  otp: '',
})
const profile = ref({
  company_name: '',
  industry: '',
  position: '',
  company_size: '',
})
const showCompany = ref(false)

const loading = ref(false)
const errorMsg = ref('')
const pendingMsg = ref('')
const otpCooldown = ref(0)
const otpSending = ref(false)

// Public config — which channels to show
const allChannels = [
  { key: 'username_password', label: '账号密码', icon: '🔒' },
  { key: 'email_otp',         label: '邮箱',     icon: '📧' },
  { key: 'phone_sms',         label: '手机',     icon: '📱' },
  { key: 'google_oauth',      label: 'Google',   icon: '🌐' },
]
const enabledMethods = ref({
  username_password: true,
  email_otp: true,
  phone_sms: false,
  google_oauth: false,
})
const availableChannels = computed(() =>
  allChannels.filter(c => enabledMethods.value[c.key])
)

const isValidPhone = computed(() =>
  /^1[3-9]\d{9}$/.test(form.value.phone)
)

let cooldownTimer = null
function startCooldown(seconds = 60) {
  otpCooldown.value = seconds
  clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    otpCooldown.value--
    if (otpCooldown.value <= 0) clearInterval(cooldownTimer)
  }, 1000)
}

onMounted(async () => {
  try {
    const cfg = await authAPI.getPublicConfig()
    if (cfg?.methods) {
      enabledMethods.value = { ...enabledMethods.value, ...cfg.methods }
    }
    // If the current channel is disabled, switch to first enabled
    if (!enabledMethods.value[activeChannel.value]) {
      const first = availableChannels.value[0]
      if (first) activeChannel.value = first.key
    }
  } catch (e) {
    // ignore — defaults used
  }
})
onUnmounted(() => { if (cooldownTimer) clearInterval(cooldownTimer) })

async function sendOtp(channel) {
  errorMsg.value = ''
  const target = channel === 'email' ? form.value.email : form.value.phone
  if (!target) { errorMsg.value = channel === 'email' ? '请填写邮箱' : '请填写手机号'; return }
  if (channel === 'phone' && !isValidPhone.value) {
    errorMsg.value = '手机号格式不正确'; return
  }
  otpSending.value = true
  try {
    await authAPI.sendOtp({ channel, target, purpose: mode.value === 'login' ? 'login' : 'register' })
    startCooldown(60)
  } catch (e) {
    errorMsg.value = e.message || '发送失败'
  } finally {
    otpSending.value = false
  }
}

async function submit() {
  errorMsg.value = ''
  pendingMsg.value = ''
  loading.value = true
  try {
    let res
    if (activeChannel.value === 'username_password') {
      if (mode.value === 'login') {
        await store.login(form.value.username, form.value.password)
        res = { user: store.user }
      } else {
        res = await authAPI.register({
          username: form.value.username,
          email: form.value.email,
          password: form.value.password,
        })
      }
    } else if (activeChannel.value === 'email_otp') {
      if (mode.value === 'login') {
        res = await authAPI.loginEmailOtp({
          email: form.value.email,
          otp: form.value.otp,
        })
      } else {
        res = await authAPI.registerEmail({
          email:    form.value.email,
          otp:      form.value.otp,
          password: form.value.password || null,
          profile:  hasProfile.value ? { ...profile.value } : null,
        })
      }
    } else if (activeChannel.value === 'phone_sms') {
      if (mode.value === 'login') {
        res = await authAPI.loginPhoneOtp({
          phone: form.value.phone,
          otp: form.value.otp,
        })
      } else {
        res = await authAPI.registerPhone({
          phone:    form.value.phone,
          otp:      form.value.otp,
          password: form.value.password || null,
        })
      }
    }

    // Handle pending approval flow
    if (res?.pending_approval) {
      pendingMsg.value = res.message || '账号已创建，等待管理员审核'
      return
    }

    // If we got a fresh token back, persist it
    if (res?.access_token) {
      localStorage.setItem('token', res.access_token)
      store.token = res.access_token
      store.user = res.user
    }

    emit('success', res?.user || store.user)
  } catch (e) {
    errorMsg.value = e.message || '操作失败'
  } finally {
    loading.value = false
  }
}

async function startGoogleAuth() {
  errorMsg.value = ''
  try {
    const res = await authAPI.googleAuthUrl()
    if (res?.url) {
      sessionStorage.setItem('google_oauth_state', res.state)
      window.location.href = res.url
    }
  } catch (e) {
    errorMsg.value = e.message || 'Google 登录不可用'
  }
}

const hasProfile = computed(() =>
  showCompany.value && (
    profile.value.company_name ||
    profile.value.industry ||
    profile.value.position ||
    profile.value.company_size
  )
)
</script>

<style scoped>
.auth-tabs {
  width: 100%;
  color: #e4e4e7;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.mode-switch {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: rgba(255,255,255,0.04);
  border-radius: 10px;
  margin-bottom: 20px;
}
.mode-switch button {
  flex: 1;
  padding: 8px 0;
  background: transparent;
  border: none;
  color: #a1a1aa;
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.mode-switch button.active {
  background: #18181b;
  color: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}

.channel-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 20px;
  overflow-x: auto;
}
.channel-tabs button {
  flex: 1;
  min-width: 72px;
  padding: 10px 8px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  color: #a1a1aa;
  font-size: 12px;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
  font-family: inherit;
}
.channel-tabs button:hover { border-color: #6366f1; color: #e4e4e7; }
.channel-tabs button.active {
  background: rgba(99,102,241,0.12);
  border-color: #6366f1;
  color: #fff;
}
.ch-icon { font-size: 18px; }

.channel-body { display: flex; flex-direction: column; gap: 14px; }
.field label {
  display: block;
  font-size: 12px;
  color: #a1a1aa;
  margin-bottom: 6px;
  font-weight: 500;
}
.field input, .field select {
  width: 100%;
  padding: 11px 14px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 10px;
  color: #fff;
  font-size: 14px;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
.field input:focus, .field select:focus { border-color: #6366f1; }
.field input::placeholder { color: #52525b; }
.otp-row { display: flex; gap: 8px; }
.otp-row input { flex: 1; }
.otp-btn {
  padding: 0 16px;
  background: rgba(99,102,241,0.12);
  border: 1px solid rgba(99,102,241,0.25);
  color: #a5b4fc;
  font-size: 13px;
  border-radius: 10px;
  cursor: pointer;
  white-space: nowrap;
  font-family: inherit;
  transition: all 0.2s;
}
.otp-btn:hover:not(:disabled) { background: rgba(99,102,241,0.2); }
.otp-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.optional-block { margin-top: -4px; }
.toggle-company {
  display: inline-flex;
  gap: 4px;
  font-size: 12px;
  color: #71717a;
  cursor: pointer;
  user-select: none;
  margin-bottom: 8px;
}
.toggle-company:hover { color: #a5b4fc; }
.company-fields { display: flex; flex-direction: column; gap: 8px; }

.submit {
  width: 100%;
  padding: 12px;
  margin-top: 4px;
  border-radius: 10px;
  border: none;
  background: #6366f1;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: 0.2s;
}
.submit:hover:not(:disabled) { background: #818cf8; }
.submit:disabled { opacity: 0.5; cursor: not-allowed; }

.google-body { align-items: stretch; }
.google-hint {
  font-size: 13px;
  color: #a1a1aa;
  text-align: center;
  margin: 8px 0 16px;
}
.google-btn {
  background: #fff;
  color: #18181b;
  display: flex;
  align-items: center;
  justify-content: center;
}
.google-btn:hover:not(:disabled) { background: #f4f4f5; }

.error-msg {
  margin: 14px 0 0;
  padding: 10px 12px;
  background: rgba(248,113,113,0.1);
  border: 1px solid rgba(248,113,113,0.25);
  border-radius: 8px;
  color: #fca5a5;
  font-size: 13px;
  text-align: center;
}
.pending-msg {
  margin: 14px 0 0;
  padding: 10px 12px;
  background: rgba(34,197,94,0.1);
  border: 1px solid rgba(34,197,94,0.25);
  border-radius: 8px;
  color: #86efac;
  font-size: 13px;
  text-align: center;
}
</style>
