<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">大模型配置</h2>
      <el-button type="primary" :icon="Plus" @click="openDialog()">添加模型配置</el-button>
    </div>

    <el-alert title="配置说明" type="info" show-icon :closable="false" style="margin-bottom:16px">
      <template #default>
        为每个 Agent 专家分别配置大模型；选择"图像生成"可接入 AI 绘图 API，用于自动生成品牌 Logo。<br>
        支持：OpenAI (GPT / DALL-E) / Anthropic (Claude) / 火山引擎 (豆包文本 &amp; 视觉) / Stability AI
      </template>
    </el-alert>

    <el-table :data="configs" v-loading="loading" border rounded>
      <el-table-column prop="name" label="配置名称" width="160" />
      <el-table-column label="供应商" width="120">
        <template #default="{ row }">
          <el-tag :type="providerType[row.provider]" effect="light">{{ providerLabel[row.provider] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="model_name" label="模型" width="180" />
      <el-table-column label="适用专家" width="140">
        <template #default="{ row }">
          <el-tag :type="agentTagType[row.agent_type]" size="small">{{ agentLabel[row.agent_type] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="API Base URL">
        <template #default="{ row }">
          <span class="text-sm text-gray">{{ row.base_url || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" align="center">
        <template #default="{ row }">
          <el-button size="small" link @click="openDialog(row)">编辑</el-button>
          <el-button size="small" link type="danger" @click="deleteConfig(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑模型配置' : '添加模型配置'" width="560px">
      <el-form :model="form" label-width="110px" label-position="left">
        <el-form-item label="配置名称">
          <el-input v-model="form.name" placeholder="例如：GPT-4战略专家" />
        </el-form-item>
        <el-form-item label="供应商">
          <el-select v-model="form.provider" style="width:100%" @change="onProviderChange">
            <el-option label="OpenAI (GPT / DALL-E)" value="openai" />
            <el-option label="Anthropic (Claude系列)" value="anthropic" />
            <el-option label="火山引擎 (豆包文本 & 视觉)" value="volcano" />
            <el-option label="Stability AI (图像生成)" value="stability" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名称">
          <el-select v-model="form.model_name" filterable allow-create style="width:100%">
            <el-option v-for="m in modelOptions[form.provider]" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" show-password placeholder="sk-..." />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" :placeholder="baseUrlPlaceholder[form.provider]" />
          <div class="hint">可选，火山引擎必填</div>
        </el-form-item>
        <el-form-item label="用途">
          <el-select v-model="form.agent_type" style="width:100%">
            <el-option label="全部专家（默认兜底）" value="all" />
            <el-option label="战略规划专家" value="strategy" />
            <el-option label="品牌设计专家" value="brand" />
            <el-option label="运营实施专家" value="operations" />
            <el-option label="🎨 图像生成（Logo AI绘图）" value="image_gen" />
          </el-select>
          <div v-if="form.agent_type === 'image_gen'" class="hint" style="color:#e6a23c">
            启用后，品牌设计任务将自动调用此 API 生成 Logo 图片，嵌入 PNG / PSD 文件中。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { adminAPI } from '../../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const configs = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editId = ref(null)
const saving = ref(false)

const form = ref({ name: '', provider: 'openai', api_key: '', model_name: '', base_url: '', agent_type: 'all' })

const providerLabel = { openai: 'OpenAI', anthropic: 'Anthropic', volcano: '火山引擎', stability: 'Stability AI' }
const providerType = { openai: 'primary', anthropic: 'success', volcano: 'warning', stability: 'danger' }
const agentLabel = { all: '全部', strategy: '战略规划', brand: '品牌设计', operations: '运营实施', image_gen: '图像生成' }
const agentTagType = { all: 'info', strategy: 'primary', brand: 'success', operations: 'warning', image_gen: 'danger' }

const modelOptions = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo', 'dall-e-3', 'dall-e-2'],
  anthropic: ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
  volcano: [
    'doubao-pro-32k', 'doubao-lite-32k', 'doubao-pro-4k',
    'doubao-seedream-3-0-t2i-250415', 'doubao-vision-pro-32k',
  ],
  stability: ['stable-diffusion-xl-1024-v1-0', 'stable-diffusion-v1-6'],
}

const baseUrlPlaceholder = {
  openai: '留空使用默认 https://api.openai.com/v1',
  anthropic: '留空使用默认 Anthropic API',
  volcano: 'https://ark.volces.com/api/v3',
  stability: '留空使用默认 https://api.stability.ai',
}

function onProviderChange() {
  form.value.model_name = ''
  if (form.value.provider === 'volcano') {
    form.value.base_url = 'https://ark.volces.com/api/v3'
  } else if (form.value.provider === 'stability') {
    form.value.base_url = ''
    if (form.value.agent_type !== 'image_gen') form.value.agent_type = 'image_gen'
  } else {
    form.value.base_url = ''
  }
}

function openDialog(row = null) {
  editId.value = row?.id || null
  if (row) {
    form.value = { name: row.name, provider: row.provider, api_key: '', model_name: row.model_name, base_url: row.base_url || '', agent_type: row.agent_type }
  } else {
    form.value = { name: '', provider: 'openai', api_key: '', model_name: '', base_url: '', agent_type: 'all' }
  }
  dialogVisible.value = true
}

async function saveConfig() {
  if (!form.value.name || !form.value.api_key || !form.value.model_name) {
    ElMessage.warning('请填写必填项')
    return
  }
  saving.value = true
  try {
    if (editId.value) {
      await adminAPI.updateLLMConfig(editId.value, form.value)
    } else {
      await adminAPI.createLLMConfig(form.value)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await loadConfigs()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function deleteConfig(id) {
  await ElMessageBox.confirm('确认删除此模型配置？', '警告', { type: 'warning' })
  await adminAPI.deleteLLMConfig(id)
  ElMessage.success('已删除')
  await loadConfigs()
}

async function loadConfigs() {
  loading.value = true
  try { configs.value = await adminAPI.getLLMConfigs() }
  finally { loading.value = false }
}

onMounted(loadConfigs)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { font-size: 20px; color: #1a1a2e; }
.hint { font-size: 12px; color: #aaa; margin-top: 4px; }
.text-sm { font-size: 12px; }
.text-gray { color: #888; }
</style>
