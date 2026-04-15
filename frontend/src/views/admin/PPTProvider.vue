<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">PPT 生成器配置</h2>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-alert type="info" show-icon :closable="false" style="margin-bottom:16px">
      <template #default>
        选择 PPT 生成的主力服务商与回退服务商。当主力失败时自动降级，最终始终回落到本地 python-pptx 渲染器，保证生成不中断。<br>
        <b>Gamma API</b> 提供接近商业级视觉的云端生成；<b>Presenton</b> 可私有化部署；<b>本地 python-pptx</b> 无需外部 Key、零延迟。
      </template>
    </el-alert>

    <!-- Provider status cards -->
    <div class="provider-grid" v-loading="loading">
      <el-card
        v-for="p in providers"
        :key="p.name"
        class="provider-card"
        :class="{ active: p.role === 'primary', fallback: p.role === 'fallback' }"
        shadow="hover"
      >
        <div class="pc-header">
          <span class="pc-icon">{{ iconOf(p.name) }}</span>
          <div class="pc-title">
            <div class="pc-label">{{ p.label }}</div>
            <div class="pc-name">{{ p.name }}</div>
          </div>
          <el-tag
            v-if="p.role === 'primary'"
            type="success" effect="dark" size="small"
          >主力</el-tag>
          <el-tag
            v-else-if="p.role === 'fallback'"
            type="warning" size="small"
          >备选</el-tag>
        </div>
        <div class="pc-status">
          <el-tag
            :type="p.available ? 'success' : 'info'"
            effect="light" size="small"
          >{{ p.available ? '已配置' : '未配置' }}</el-tag>
        </div>
        <div class="pc-actions">
          <el-button
            size="small"
            type="primary"
            :disabled="form.provider === p.name"
            @click="setRole(p.name, 'provider')"
          >设为主力</el-button>
          <el-button
            size="small"
            :disabled="form.fallback === p.name || form.provider === p.name"
            @click="setRole(p.name, 'fallback')"
          >设为备选</el-button>
          <el-button
            size="small"
            :loading="testing[p.name]"
            @click="runTest(p.name)"
          >连通测试</el-button>
        </div>
      </el-card>
    </div>

    <!-- Detail form -->
    <el-card class="form-card" shadow="never">
      <template #header>
        <span class="card-title">参数配置</span>
      </template>

      <el-form :model="form" label-width="160px" label-position="left">
        <el-form-item label="主力服务商">
          <el-select v-model="form.provider" style="width:320px">
            <el-option label="本地 python-pptx" value="local" />
            <el-option label="Gamma API (云端)" value="gamma" />
            <el-option label="Presenton (自托管)" value="presenton" />
          </el-select>
        </el-form-item>
        <el-form-item label="回退服务商">
          <el-select v-model="form.fallback" style="width:320px">
            <el-option label="本地 python-pptx" value="local" />
            <el-option label="Gamma API (云端)" value="gamma" />
            <el-option label="Presenton (自托管)" value="presenton" />
          </el-select>
          <div class="hint">主力失败时自动使用；最终总会回退到 local</div>
        </el-form-item>

        <el-divider content-position="left">Gamma</el-divider>
        <el-form-item label="Gamma API Key">
          <el-input
            v-model="form.gamma_api_key"
            type="password" show-password
            :placeholder="form.gamma_api_key_set ? '已保存，留空则不修改' : 'sk-gamma-...'"
            style="width:420px"
          />
          <div class="hint">从 https://gamma.app/settings 获取，按量计费</div>
        </el-form-item>
        <el-form-item label="Gamma Theme 名称">
          <el-input
            v-model="form.gamma_theme_name"
            placeholder="可选，例如 Oasis / Night Sky / Chisel"
            style="width:420px"
          />
          <div class="hint">Gamma 官方主题名（区分大小写），留空走默认主题</div>
        </el-form-item>
        <el-form-item label="页数 numCards">
          <el-input-number v-model="form.gamma_num_cards" :min="5" :max="60" />
          <div class="hint">Pro 账户上限 60，Ultra 上限 75</div>
        </el-form-item>

        <el-divider content-position="left">Presenton</el-divider>
        <el-form-item label="Presenton Endpoint">
          <el-input
            v-model="form.presenton_endpoint"
            placeholder="http://localhost:5000"
            style="width:420px"
          />
          <div class="hint">自托管 Presenton 服务的基础 URL</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
          <el-button @click="load">撤销</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { adminAPI } from '../../api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const saving  = ref(false)
const testing = reactive({})

const providers = ref([])
const form = ref({
  provider: 'local',
  fallback: 'local',
  gamma_api_key: '',
  gamma_api_key_set: false,
  gamma_theme_name: '',
  gamma_num_cards: 16,
  presenton_endpoint: 'http://localhost:5000',
})

function iconOf(name) {
  return { local: '🖥️', gamma: '✨', presenton: '🧩' }[name] || '📊'
}

async function load() {
  loading.value = true
  try {
    const data = await adminAPI.getPPTProvider()
    providers.value = data.providers
    // Do NOT overwrite the masked key into the input
    form.value = {
      ...data.config,
      gamma_api_key: '', // user must re-enter to change
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function setRole(name, role) {
  form.value[role] = name
  if (role === 'provider' && form.value.fallback === name) {
    // primary == fallback is allowed but pointless; swap to local
    form.value.fallback = 'local'
  }
}

async function save() {
  saving.value = true
  try {
    const payload = { ...form.value }
    delete payload.gamma_api_key_set
    // If user left key blank, omit it so backend preserves existing
    if (!payload.gamma_api_key) delete payload.gamma_api_key
    const data = await adminAPI.savePPTProvider(payload)
    providers.value = data.providers
    form.value = { ...data.config, gamma_api_key: '' }
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function runTest(name) {
  testing[name] = true
  if (name === 'gamma') {
    ElMessage.info('Gamma 生成通常需要 1-5 分钟，请耐心等待...')
  }
  try {
    const res = await adminAPI.testPPTProvider(name)
    if (res.ok) {
      const size = res.file_size ? ` (${(res.file_size/1024/1024).toFixed(1)} MB)` : ''
      ElMessage.success(`${name} 连通正常${size}`)
    } else {
      ElMessage.error(`${name} 测试失败: ${res.error || '未知错误'}`)
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    testing[name] = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { font-size: 20px; color: #1a1a2e; }
.card-title { font-size: 15px; font-weight: 600; color: #1a1a2e; }
.hint { font-size: 12px; color: #aaa; margin-top: 4px; }

.provider-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 16px; margin-bottom: 20px;
}
.provider-card { border: 2px solid transparent; transition: all .2s; }
.provider-card.active    { border-color: #67c23a; background: #f0f9eb; }
.provider-card.fallback  { border-color: #e6a23c; background: #fdf6ec; }

.pc-header { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.pc-icon { font-size: 28px; }
.pc-title { flex: 1; }
.pc-label { font-size: 15px; font-weight: 600; color: #1a1a2e; }
.pc-name { font-size: 12px; color: #888; margin-top: 2px; }
.pc-status { margin-bottom: 12px; }
.pc-actions { display: flex; gap: 6px; flex-wrap: wrap; }

.form-card { margin-top: 8px; }
</style>
