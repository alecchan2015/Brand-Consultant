<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">海报生成器配置</h2>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-alert type="info" show-icon :closable="false" style="margin-bottom:16px">
      <template #default>
        选择海报生成的主力服务商与回退服务商。当主力失败时自动降级到备选服务商，保证生成不中断。<br>
        <b>OpenAI / 豆包 (DALL-E / gpt-image-1)</b> 综合质量最佳；<b>FLUX via Replicate</b> 适合高质量复杂场景；<b>即梦 (ByteDance)</b> 中文场景理解强，适合节气/古风海报。
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
            :type="p.configured ? 'success' : 'info'"
            effect="light" size="small"
          >{{ p.configured ? '已配置' : '未配置' }}</el-tag>
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
            <el-option label="OpenAI / 豆包 (DALL-E / gpt-image-1)" value="openai" />
            <el-option label="FLUX via Replicate" value="flux" />
            <el-option label="即梦 (ByteDance)" value="jimeng" />
          </el-select>
        </el-form-item>
        <el-form-item label="回退服务商">
          <el-select v-model="form.fallback" style="width:320px">
            <el-option label="OpenAI / 豆包 (DALL-E / gpt-image-1)" value="openai" />
            <el-option label="FLUX via Replicate" value="flux" />
            <el-option label="即梦 (ByteDance)" value="jimeng" />
          </el-select>
          <div class="hint">主力失败时自动使用备选服务商</div>
        </el-form-item>

        <el-divider content-position="left">OpenAI / 豆包</el-divider>
        <el-form-item label="OpenAI API Key">
          <el-input
            v-model="form.openai_api_key"
            type="password" show-password
            :placeholder="form.openai_api_key_set ? '已保存，留空则不修改' : 'sk-...'"
            style="width:420px"
          />
          <div class="hint">用于 DALL-E 3 / gpt-image-1 图像生成</div>
        </el-form-item>
        <el-form-item label="模型名称">
          <el-select v-model="form.openai_model" style="width:320px">
            <el-option label="dall-e-3" value="dall-e-3" />
            <el-option label="gpt-image-1" value="gpt-image-1" />
          </el-select>
          <div class="hint">选择 DALL-E 3 或 gpt-image-1</div>
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input
            v-model="form.openai_base_url"
            placeholder="https://api.openai.com/v1"
            style="width:420px"
          />
          <div class="hint">使用豆包或代理时修改此地址，默认 https://api.openai.com/v1</div>
        </el-form-item>

        <el-divider content-position="left">FLUX via Replicate</el-divider>
        <el-form-item label="FLUX API Key">
          <el-input
            v-model="form.flux_api_key"
            type="password" show-password
            :placeholder="form.flux_api_key_set ? '已保存，留空则不修改' : 'r8_...'"
            style="width:420px"
          />
          <div class="hint">通过 Replicate 托管，适合高质量复杂场景，2-3 min/张</div>
        </el-form-item>
        <el-form-item label="FLUX 模型">
          <el-input
            v-model="form.flux_model"
            placeholder="black-forest-labs/flux-1.1-pro"
            style="width:420px"
          />
          <div class="hint">Replicate 上的模型路径，例如 black-forest-labs/flux-1.1-pro</div>
        </el-form-item>

        <el-divider content-position="left">即梦 (ByteDance)</el-divider>
        <el-form-item label="即梦 API Key">
          <el-input
            v-model="form.jimeng_api_key"
            type="password" show-password
            :placeholder="form.jimeng_api_key_set ? '已保存，留空则不修改' : 'jimeng-...'"
            style="width:420px"
          />
          <div class="hint">中文场景理解强，适合节气/古风海报</div>
        </el-form-item>
        <el-form-item label="即梦模型">
          <el-input
            v-model="form.jimeng_model"
            placeholder="jimeng-3.0"
            style="width:420px"
          />
          <div class="hint">例如 jimeng-3.0 等</div>
        </el-form-item>

        <el-divider content-position="left">通用设置</el-divider>
        <el-form-item label="默认尺寸">
          <el-select v-model="form.default_size" style="width:320px">
            <el-option label="竖版海报 portrait (2160×3840)" value="portrait" />
            <el-option label="故事版 story (1080×1920)" value="story" />
            <el-option label="正方形 square (2048×2048)" value="square" />
            <el-option label="横版 landscape (1920×1080)" value="landscape" />
            <el-option label="A3 (2480×3508)" value="a3" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认风格">
          <el-select v-model="form.default_style" style="width:320px">
            <el-option label="自然 (natural)" value="natural" />
            <el-option label="奢华 (luxury)" value="luxury" />
            <el-option label="现代 (modern)" value="modern" />
            <el-option label="活泼 (playful)" value="playful" />
            <el-option label="传统 (heritage)" value="heritage" />
          </el-select>
        </el-form-item>
        <el-form-item label="添加品牌底部信息栏">
          <el-switch v-model="form.add_footer" />
          <div class="hint">在海报底部自动添加品牌名称与 Slogan 信息栏</div>
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
  provider: 'openai',
  fallback: 'flux',
  openai_api_key: '',
  openai_api_key_set: false,
  openai_model: 'dall-e-3',
  openai_base_url: 'https://api.openai.com/v1',
  flux_api_key: '',
  flux_api_key_set: false,
  flux_model: 'black-forest-labs/flux-1.1-pro',
  jimeng_api_key: '',
  jimeng_api_key_set: false,
  jimeng_model: 'jimeng-3.0',
  default_size: 'portrait',
  default_style: 'natural',
  add_footer: true,
})

function iconOf(name) {
  return { openai: '\uD83C\uDFA8', flux: '\u26A1', jimeng: '\uD83C\uDF38' }[name] || '\uD83D\uDDBC\uFE0F'
}

async function load() {
  loading.value = true
  try {
    const data = await adminAPI.getPosterProvider()
    providers.value = data.providers
    form.value = {
      ...data.config,
      openai_api_key: '',
      flux_api_key: '',
      jimeng_api_key: '',
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
    const others = ['openai', 'flux', 'jimeng'].filter(n => n !== name)
    form.value.fallback = others[0]
  }
}

async function save() {
  saving.value = true
  try {
    const payload = { ...form.value }
    delete payload.openai_api_key_set
    delete payload.flux_api_key_set
    delete payload.jimeng_api_key_set
    // If user left key blank, omit it so backend preserves existing
    if (!payload.openai_api_key) delete payload.openai_api_key
    if (!payload.flux_api_key) delete payload.flux_api_key
    if (!payload.jimeng_api_key) delete payload.jimeng_api_key
    const data = await adminAPI.savePosterProvider(payload)
    providers.value = data.providers
    form.value = {
      ...data.config,
      openai_api_key: '',
      flux_api_key: '',
      jimeng_api_key: '',
    }
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function runTest(name) {
  testing[name] = true
  ElMessage.info('海报生成测试中，请耐心等待（最长 5 分钟）...')
  try {
    const res = await adminAPI.testPosterProvider(name)
    if (res.ok) {
      ElMessage.success(`${name} 连通正常`)
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
