<template>
  <div class="auth-admin">
    <div class="page-header">
      <h2 class="page-title">注册策略管理</h2>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <el-alert type="info" show-icon :closable="false" style="margin-bottom:16px">
      统一管理用户注册入口：方式开关、服务商凭证、白/黑名单域名、按渠道积分、频率限制。
      配置即时生效，新注册用户立即受新规则约束。
    </el-alert>

    <el-tabs v-model="activeTab" v-loading="loading">
      <!-- TAB 1: METHODS -->
      <el-tab-pane label="注册方式开关" name="methods">
        <div class="section-card">
          <h3>注册 / 登录入口</h3>
          <p class="section-desc">控制前端登录页展示哪些方式。关闭后相关接口一并拒绝。</p>
          <div class="method-list">
            <div v-for="m in methodRows" :key="m.key" class="method-row">
              <div class="method-info">
                <span class="method-icon">{{ m.icon }}</span>
                <div>
                  <div class="method-label">{{ m.label }}</div>
                  <div class="method-hint">{{ m.hint }}</div>
                </div>
              </div>
              <el-switch
                v-model="config.methods[m.key]"
                :disabled="m.requiresSetup && !providerReady[m.key]"
              />
            </div>
          </div>
          <div v-if="!providerReady.email_otp && config.methods.email_otp" class="setup-hint warn">
            ⚠️ 邮箱注册已启用但 SMTP 未配置，请先在「邮件 SMTP」标签页填写凭证。
          </div>
          <div v-if="!providerReady.phone_sms && config.methods.phone_sms" class="setup-hint warn">
            ⚠️ 手机注册已启用但腾讯云 SMS 未配置，请先在「手机短信」标签页填写凭证。
          </div>
          <div v-if="!providerReady.google_oauth && config.methods.google_oauth" class="setup-hint warn">
            ⚠️ Google 登录已启用但 OAuth 未配置，请先在「Google OAuth」标签页填写凭证。
          </div>
        </div>

        <div class="section-card">
          <h3>审核制</h3>
          <p class="section-desc">启用后，新用户注册成功不会立即激活，需管理员在「用户管理 → 待审核」中批准。</p>
          <el-switch v-model="config.approval_required" active-text="需要人工审核" inactive-text="自动激活" />
        </div>

        <div class="section-card">
          <h3>各渠道默认积分</h3>
          <p class="section-desc">新注册用户的初始积分数量（按注册方式区分）。</p>
          <div class="credit-grid">
            <div v-for="m in methodRows" :key="m.key" class="credit-row">
              <span class="credit-label">{{ m.icon }} {{ m.label }}</span>
              <el-input-number
                v-model="config.credits_by_channel[m.key]"
                :min="0" :max="100000" :step="100"
              />
            </div>
          </div>
        </div>

        <div class="section-card">
          <h3>频率限制</h3>
          <p class="section-desc">防止恶意注册 + 验证码轰炸。</p>
          <div class="rate-grid">
            <div class="rate-row">
              <span>同 IP 每日注册上限</span>
              <el-input-number v-model="config.rate_limit.register_per_ip_per_day" :min="1" :max="100" />
            </div>
            <div class="rate-row">
              <span>同目标每小时验证码上限</span>
              <el-input-number v-model="config.rate_limit.otp_per_target_per_hour" :min="1" :max="30" />
            </div>
            <div class="rate-row">
              <span>验证码重发冷却 (秒)</span>
              <el-input-number v-model="config.rate_limit.otp_cooldown_seconds" :min="30" :max="600" :step="10" />
            </div>
          </div>
        </div>

        <div class="section-card">
          <h3>邮箱域名白 / 黑名单</h3>
          <p class="section-desc">白名单不为空时，仅允许列出域名注册；黑名单拦截指定域名。</p>
          <div class="domain-row">
            <label>白名单（用逗号分隔，如 <code>pbmba.com,company.com</code>）</label>
            <el-input v-model="whitelistText" placeholder="留空表示不限制" />
          </div>
          <div class="domain-row">
            <label>黑名单（用逗号分隔）</label>
            <el-input v-model="blacklistText" placeholder="留空表示不拦截" />
          </div>
        </div>

        <div class="save-bar">
          <el-button type="primary" :loading="savingConfig" @click="saveConfig">保存策略</el-button>
        </div>
      </el-tab-pane>

      <!-- TAB 2: EMAIL SMTP -->
      <el-tab-pane label="邮件 SMTP" name="email">
        <div class="section-card">
          <h3>SMTP 服务器</h3>
          <p class="section-desc">用于邮箱验证码发送。推荐阿里云邮件推送 / 腾讯企业邮箱 / SendGrid。</p>
          <div class="form-grid">
            <div class="form-row">
              <label>SMTP 地址</label>
              <el-input v-model="emailCfg.smtp_host" placeholder="smtp.qiye.aliyun.com" />
            </div>
            <div class="form-row">
              <label>端口</label>
              <el-input-number v-model="emailCfg.smtp_port" :min="1" :max="65535" />
            </div>
            <div class="form-row">
              <label>用户名 / 发件邮箱</label>
              <el-input v-model="emailCfg.smtp_user" placeholder="noreply@example.com" />
            </div>
            <div class="form-row">
              <label>密码 / 授权码</label>
              <el-input v-model="emailCfg.smtp_password" type="password" show-password :placeholder="emailCfg.smtp_password_set ? '已配置（留空保持不变）' : '请输入授权码'" />
            </div>
            <div class="form-row">
              <label>发件人显示名</label>
              <el-input v-model="emailCfg.from_name" placeholder="Your Brand Consultant" />
            </div>
            <div class="form-row">
              <label>发件地址（可选，默认同用户名）</label>
              <el-input v-model="emailCfg.from_email" placeholder="noreply@example.com" />
            </div>
            <div class="form-row">
              <label>使用 SSL (465)</label>
              <el-switch v-model="emailCfg.use_ssl" />
            </div>
          </div>
          <div class="save-bar">
            <el-button type="primary" :loading="savingEmail" @click="saveEmail">保存 SMTP</el-button>
            <el-button :loading="testingEmail" @click="openTestEmail">发送测试邮件</el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- TAB 3: TENCENT SMS -->
      <el-tab-pane label="手机短信 (腾讯云)" name="sms">
        <div class="section-card">
          <h3>腾讯云 SMS 凭证</h3>
          <p class="section-desc">
            需要在
            <a href="https://console.cloud.tencent.com/smsv2" target="_blank">腾讯云短信控制台</a>
            申请签名和模板，模板格式：「您的验证码是 {1}，10分钟内有效。」
          </p>
          <div class="form-grid">
            <div class="form-row">
              <label>SecretId</label>
              <el-input v-model="smsCfg.secret_id" :placeholder="smsCfg.secret_id_set ? '已配置（留空保持不变）' : 'AKID...'" />
            </div>
            <div class="form-row">
              <label>SecretKey</label>
              <el-input v-model="smsCfg.secret_key" type="password" show-password :placeholder="smsCfg.secret_key_set ? '已配置' : ''" />
            </div>
            <div class="form-row">
              <label>地区</label>
              <el-select v-model="smsCfg.region" style="width:100%">
                <el-option label="广州 (ap-guangzhou)" value="ap-guangzhou" />
                <el-option label="北京 (ap-beijing)" value="ap-beijing" />
                <el-option label="上海 (ap-shanghai)" value="ap-shanghai" />
                <el-option label="新加坡 (ap-singapore)" value="ap-singapore" />
              </el-select>
            </div>
            <div class="form-row">
              <label>SDK AppId</label>
              <el-input v-model="smsCfg.sdk_app_id" placeholder="140000xxxx" />
            </div>
            <div class="form-row">
              <label>签名</label>
              <el-input v-model="smsCfg.sign_name" placeholder="已报备的签名名称" />
            </div>
            <div class="form-row">
              <label>模板 ID</label>
              <el-input v-model="smsCfg.template_id" placeholder="17xxxxx" />
            </div>
          </div>
          <div class="save-bar">
            <el-button type="primary" :loading="savingSms" @click="saveSms">保存 SMS</el-button>
            <el-button :loading="testingSms" @click="openTestSms">发送测试短信</el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- TAB 4: GOOGLE OAUTH -->
      <el-tab-pane label="Google OAuth" name="google">
        <div class="section-card">
          <h3>Google Cloud OAuth 2.0</h3>
          <p class="section-desc">
            在
            <a href="https://console.cloud.google.com/apis/credentials" target="_blank">Google Cloud Console</a>
            创建 OAuth 2.0 客户端 ID。回调 URI 必须与下方填写的一致。
          </p>
          <div class="form-grid">
            <div class="form-row">
              <label>Client ID</label>
              <el-input v-model="googleCfg.client_id" placeholder="xxxxx.apps.googleusercontent.com" />
            </div>
            <div class="form-row">
              <label>Client Secret</label>
              <el-input v-model="googleCfg.client_secret" type="password" show-password :placeholder="googleCfg.client_secret_set ? '已配置' : ''" />
            </div>
            <div class="form-row">
              <label>回调 URI</label>
              <el-input v-model="googleCfg.redirect_uri" placeholder="https://yourdomain.com/auth/callback" />
            </div>
          </div>
          <el-alert type="warning" show-icon :closable="false" style="margin-top:12px">
            生产环境 Google 要求 HTTPS。开发环境可以用
            <code>http://localhost:端口/auth/callback</code>。
            当前站点可填
            <code>http://175.178.95.4:9080/auth/callback</code>
            （如无 HTTPS，Google 会拒绝生产 OAuth 请求）。
          </el-alert>
          <div class="save-bar">
            <el-button type="primary" :loading="savingGoogle" @click="saveGoogle">保存 OAuth</el-button>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminAPI } from '../../api'

const activeTab = ref('methods')
const loading = ref(false)

const config = reactive({
  methods: { username_password: true, email_otp: true, phone_sms: false, google_oauth: false },
  approval_required: false,
  email_whitelist_domains: [],
  email_blacklist_domains: [],
  credits_by_channel: { username_password: 100, email_otp: 500, phone_sms: 200, google_oauth: 1000 },
  rate_limit: { register_per_ip_per_day: 10, otp_per_target_per_hour: 5, otp_cooldown_seconds: 60 },
})

const whitelistText = ref('')
const blacklistText = ref('')

const emailCfg = reactive({
  smtp_host: '', smtp_port: 465, smtp_user: '', smtp_password: '',
  from_name: '', from_email: '', use_ssl: true,
  smtp_password_set: false,
})

const smsCfg = reactive({
  provider: 'tencent', secret_id: '', secret_key: '', region: 'ap-guangzhou',
  sdk_app_id: '', sign_name: '', template_id: '',
  secret_id_set: false, secret_key_set: false,
})

const googleCfg = reactive({
  client_id: '', client_secret: '', redirect_uri: '',
  client_secret_set: false,
})

const methodRows = [
  { key: 'username_password', label: '用户名 + 密码', icon: '🔒', hint: '传统注册，无需外部服务', requiresSetup: false },
  { key: 'email_otp',         label: '邮箱验证码',    icon: '📧', hint: '需配置 SMTP',            requiresSetup: true  },
  { key: 'phone_sms',         label: '手机短信',      icon: '📱', hint: '需配置腾讯云 SMS',      requiresSetup: true  },
  { key: 'google_oauth',      label: 'Google 账号',   icon: '🌐', hint: '需配置 Google OAuth',   requiresSetup: true  },
]

const providerReady = computed(() => ({
  username_password: true,
  email_otp:   !!emailCfg.smtp_host && (!!emailCfg.smtp_user) && (emailCfg.smtp_password_set || !!emailCfg.smtp_password),
  phone_sms:   !!smsCfg.sdk_app_id && !!smsCfg.sign_name && !!smsCfg.template_id && (smsCfg.secret_id_set || !!smsCfg.secret_id),
  google_oauth: !!googleCfg.client_id && !!googleCfg.redirect_uri && (googleCfg.client_secret_set || !!googleCfg.client_secret),
}))

const savingConfig = ref(false)
const savingEmail = ref(false)
const savingSms = ref(false)
const savingGoogle = ref(false)
const testingEmail = ref(false)
const testingSms = ref(false)

async function loadAll() {
  loading.value = true
  try {
    const [cfg, email, sms, google] = await Promise.all([
      adminAPI.getAuthConfig(),
      adminAPI.getEmailProvider(),
      adminAPI.getSmsProvider(),
      adminAPI.getGoogleOAuth(),
    ])
    Object.assign(config, cfg)
    whitelistText.value = (cfg.email_whitelist_domains || []).join(',')
    blacklistText.value = (cfg.email_blacklist_domains || []).join(',')
    Object.assign(emailCfg, email)
    emailCfg.smtp_password = ''   // mask — placeholder shown based on _set flag
    Object.assign(smsCfg, sms)
    smsCfg.secret_id = ''
    smsCfg.secret_key = ''
    Object.assign(googleCfg, google)
    googleCfg.client_secret = ''
  } catch (e) {
    ElMessage.error('加载失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

function parseDomainList(text) {
  return text.split(/[,，\s]+/).map(s => s.trim().toLowerCase()).filter(Boolean)
}

async function saveConfig() {
  savingConfig.value = true
  try {
    const patch = {
      methods: { ...config.methods },
      approval_required: config.approval_required,
      email_whitelist_domains: parseDomainList(whitelistText.value),
      email_blacklist_domains: parseDomainList(blacklistText.value),
      credits_by_channel: { ...config.credits_by_channel },
      rate_limit: { ...config.rate_limit },
    }
    await adminAPI.saveAuthConfig(patch)
    ElMessage.success('策略已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    savingConfig.value = false
  }
}

async function saveEmail() {
  savingEmail.value = true
  try {
    const patch = { ...emailCfg }
    delete patch.smtp_password_set
    // Don't send empty password — backend keeps existing
    if (!patch.smtp_password) delete patch.smtp_password
    const res = await adminAPI.saveEmailProvider(patch)
    Object.assign(emailCfg, res)
    emailCfg.smtp_password = ''
    ElMessage.success('SMTP 配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    savingEmail.value = false
  }
}

async function openTestEmail() {
  try {
    const { value } = await ElMessageBox.prompt('输入测试接收邮箱', '发送测试邮件', {
      inputPattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
      inputErrorMessage: '邮箱格式不正确',
    })
    testingEmail.value = true
    await adminAPI.testEmailProvider(value)
    ElMessage.success('测试邮件已发送')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('发送失败: ' + (e.message || e))
  } finally {
    testingEmail.value = false
  }
}

async function saveSms() {
  savingSms.value = true
  try {
    const patch = { ...smsCfg }
    delete patch.secret_id_set
    delete patch.secret_key_set
    if (!patch.secret_id) delete patch.secret_id
    if (!patch.secret_key) delete patch.secret_key
    const res = await adminAPI.saveSmsProvider(patch)
    Object.assign(smsCfg, res)
    smsCfg.secret_id = ''
    smsCfg.secret_key = ''
    ElMessage.success('SMS 配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    savingSms.value = false
  }
}

async function openTestSms() {
  try {
    const { value } = await ElMessageBox.prompt('输入测试接收手机号（11 位）', '发送测试短信', {
      inputPattern: /^1[3-9]\d{9}$/,
      inputErrorMessage: '手机号格式不正确',
    })
    testingSms.value = true
    await adminAPI.testSmsProvider(value)
    ElMessage.success('测试短信已发送')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('发送失败: ' + (e.message || e))
  } finally {
    testingSms.value = false
  }
}

async function saveGoogle() {
  savingGoogle.value = true
  try {
    const patch = { ...googleCfg }
    delete patch.client_secret_set
    if (!patch.client_secret) delete patch.client_secret
    const res = await adminAPI.saveGoogleOAuth(patch)
    Object.assign(googleCfg, res)
    googleCfg.client_secret = ''
    ElMessage.success('Google OAuth 配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    savingGoogle.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.auth-admin { max-width: 900px; }
.page-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}
.page-title { font-size: 20px; color: #1a1a2e; margin: 0; }
.section-card {
  background: #fff; border-radius: 12px; padding: 20px 24px;
  margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.section-card h3 {
  margin: 0 0 6px; font-size: 15px; color: #1a1a2e; font-weight: 600;
}
.section-desc {
  margin: 0 0 16px; font-size: 13px; color: #8a8a98;
}
.section-desc code {
  background: #f4f4f5; padding: 1px 5px; border-radius: 3px; font-size: 12px;
}

.method-list { display: flex; flex-direction: column; gap: 12px; }
.method-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px; border: 1px solid #e4e7ed; border-radius: 8px;
}
.method-info { display: flex; gap: 12px; align-items: center; }
.method-icon { font-size: 22px; }
.method-label { font-size: 14px; font-weight: 600; color: #222; }
.method-hint { font-size: 12px; color: #999; margin-top: 2px; }

.setup-hint.warn {
  margin-top: 12px; padding: 8px 12px;
  background: #fdf6ec; color: #b88230;
  border-radius: 6px; font-size: 13px;
}

.credit-grid, .rate-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.credit-row, .rate-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px; background: #fafafa; border-radius: 6px;
}
.credit-label, .rate-row > span { font-size: 13px; color: #555; }

.domain-row { margin-bottom: 12px; }
.domain-row label {
  display: block; font-size: 13px; color: #555; margin-bottom: 6px;
}

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-row label {
  display: block; font-size: 13px; color: #555; margin-bottom: 6px;
  font-weight: 500;
}

.save-bar {
  display: flex; gap: 8px; margin-top: 20px;
  padding-top: 16px; border-top: 1px solid #f0f0f0;
}

@media (max-width: 640px) {
  .form-grid, .credit-grid, .rate-grid { grid-template-columns: 1fr; }
}
</style>
