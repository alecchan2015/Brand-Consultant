<template>
  <div class="task-detail">
    <div class="page-header">
      <el-button text @click="$router.push('/dashboard')">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
      <div class="header-info">
        <h2>{{ task?.brand_name || '品牌策划' }}</h2>
        <el-tag :type="statusType[task?.status]" v-if="task">{{ statusLabel[task.status] }}</el-tag>
      </div>
      <div class="header-actions">
        <!-- Refresh button: only when completed or failed -->
        <el-button
          v-if="task?.status === 'completed' || task?.status === 'failed'"
          :icon="Refresh"
          :loading="regenerating"
          @click="handleRegenerate"
          round
        >重新生成</el-button>
      </div>
    </div>

    <el-card class="query-card" shadow="never">
      <div class="query-label">需求描述</div>
      <div class="query-text">{{ task?.query }}</div>
      <div class="query-meta">
        <el-tag v-for="a in task?.agents_selected" :key="a" :type="agentTagType[a]" size="small" effect="light">
          {{ agentNames[a] }}
        </el-tag>
        <span class="query-time">{{ task?.created_at ? new Date(task.created_at).toLocaleString('zh-CN') : '' }}</span>
      </div>
    </el-card>

    <!-- Agent Results -->
    <div class="results-section">
      <div v-for="agentType in orderedAgents" :key="agentType" class="agent-result-block">
        <div class="agent-result-header">
          <span class="agent-result-icon">{{ agentIcon[agentType] }}</span>
          <span class="agent-result-name">{{ agentNames[agentType] }}</span>
          <el-tag v-if="agentStatus[agentType] === 'streaming'" type="warning" effect="dark" size="small">
            <el-icon class="spin"><Loading /></el-icon> 生成中...
          </el-tag>
          <el-tag v-else-if="agentStatus[agentType] === 'done'" type="success" size="small">完成</el-tag>
          <el-tag v-else-if="agentStatus[agentType] === 'waiting'" type="info" size="small">等待中</el-tag>
        </div>

        <!-- Streaming or done content -->
        <div v-if="agentContents[agentType]" class="md-output" v-html="renderMd(agentContents[agentType])"></div>
        <div v-else-if="agentStatus[agentType] === 'waiting'" class="waiting-placeholder">
          等待前序专家完成分析...
        </div>

        <!-- Download Files -->
        <div v-if="agentFiles[agentType]?.length" class="file-section">
          <div class="file-section-title">📎 可下载文件</div>
          <div class="file-list">
            <div v-for="file in agentFiles[agentType]" :key="file.id" class="file-item">
              <span class="file-icon">{{ fileIcon[file.type] || '📁' }}</span>
              <span class="file-name">{{ file.name }}</span>
              <el-tag v-if="file.credits === 0" type="success" size="small" effect="light">免费</el-tag>
              <span v-else class="file-credits">{{ file.credits }} 积分</span>
              <el-button size="small" type="primary" plain @click="downloadFile(file)" :loading="file.downloading">
                下载
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error state -->
    <el-alert v-if="error" :title="error" type="error" show-icon style="margin-top:16px" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Loading, Refresh } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { tasksAPI, filesAPI } from '../api'
import { useUserStore } from '../store'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const store = useUserStore()

const task = ref(null)
const error = ref('')
const agentContents = ref({})
const agentStatus = ref({})   // waiting | streaming | done
const agentFiles = ref({})
const regenerating = ref(false)
let es = null

const agentNames = { strategy: '战略规划专家', brand: '品牌设计专家', operations: '运营实施专家' }
const agentIcon  = { strategy: '🎯', brand: '🎨', operations: '🚀' }
const agentTagType = { strategy: 'primary', brand: 'success', operations: 'warning' }
const statusType   = { pending: 'info', processing: 'warning', completed: 'success', failed: 'danger' }
const statusLabel  = { pending: '待处理', processing: '进行中', completed: '已完成', failed: '失败' }
const fileIcon     = { md: '📄', pdf: '📕', png: '🖼️', pptx: '📊', psd: '🎨' }

const orderedAgents = computed(() => {
  if (!task.value) return []
  return ['strategy', 'brand', 'operations'].filter(a => task.value.agents_selected.includes(a))
})

function renderMd(text) {
  return marked.parse(text || '', { breaks: true })
}

function initAgentStatuses() {
  orderedAgents.value.forEach(a => {
    agentStatus.value[a]   = 'waiting'
    agentContents.value[a] = ''
    agentFiles.value[a]    = []
  })
}

function loadExistingResults() {
  if (!task.value?.results?.length) return
  // Note: the backend DTO does NOT expose `file_path` (absolute server path,
  // withheld for security). A row is a FILE iff it has a `file_type`; otherwise
  // it's a content row whose `content` carries the markdown output.
  task.value.results.forEach(r => {
    if (r.file_type) {
      const files = agentFiles.value[r.agent_type] || []
      // Guard against duplicate pushes if loadExistingResults is called twice
      if (!files.some(f => f.id === r.id)) {
        files.push({
          id:       r.id,
          type:     r.file_type,
          name:     r.file_name,
          credits:  r.download_credits,
        })
      }
      agentFiles.value[r.agent_type] = files
    } else if (r.content) {
      agentContents.value[r.agent_type] = r.content
      agentStatus.value[r.agent_type]   = 'done'
    }
  })
}

function startStream() {
  if (es) { es.close(); es = null }
  const token = localStorage.getItem('token')
  es = new EventSource(`/api/tasks/${route.params.id}/stream?token=${token}`)

  es.onmessage = (e) => {
    const data = JSON.parse(e.data)

    if (data.type === 'agent_start') {
      agentStatus.value[data.agent] = 'streaming'

    } else if (data.type === 'chunk') {
      agentContents.value[data.agent] = (agentContents.value[data.agent] || '') + data.content

    } else if (data.type === 'agent_done') {
      agentStatus.value[data.agent] = 'done'
      if (data.files?.length) {
        agentFiles.value[data.agent] = data.files.map(f => ({
          id: f.id, type: f.type, name: f.name, credits: 0,
        }))
      }

    } else if (data.type === 'all_done') {
      task.value.status = 'completed'
      es.close()
      ElMessage.success('内容已生成并保存')

    } else if (data.type === 'error') {
      error.value = data.message
      task.value.status = 'failed'
      es.close()

    } else if (data.type === 'already_done') {
      // Task already completed on server but we called stream — reload results
      es.close()
      reloadResults()
    }
  }

  es.onerror = () => { es.close() }
}

async function reloadResults() {
  try {
    task.value = await tasksAPI.get(route.params.id)
    initAgentStatuses()
    loadExistingResults()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function handleRegenerate() {
  try {
    await ElMessageBox.confirm(
      '将清除当前所有生成内容并重新生成，确认继续？',
      '重新生成',
      { confirmButtonText: '确认重新生成', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return  // user cancelled
  }

  regenerating.value = true
  error.value = ''

  try {
    await tasksAPI.regenerate(route.params.id)
    task.value.status = 'pending'

    // Clear local state
    initAgentStatuses()

    // Start new stream
    startStream()
    ElMessage.info('开始重新生成...')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    regenerating.value = false
  }
}

async function downloadFile(file) {
  file.downloading = true
  try {
    const blob = await filesAPI.download(file.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    // If backend returned a ZIP (large file auto-compression), adjust filename
    let downloadName = file.name
    if (blob.type === 'application/zip' && !downloadName.endsWith('.zip')) {
      downloadName = downloadName.replace(/\.[^.]+$/, '.zip')
    }
    a.download = downloadName
    a.click()
    URL.revokeObjectURL(url)
    await store.fetchMe()
    ElMessage.success('下载成功')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    file.downloading = false
  }
}

onMounted(async () => {
  try {
    task.value = await tasksAPI.get(route.params.id)
    initAgentStatuses()

    if (task.value.status === 'completed' || task.value.status === 'failed') {
      loadExistingResults()
    } else if (task.value.status === 'processing') {
      // Task was being processed (or interrupted) — show any partial saved results, don't re-trigger
      loadExistingResults()
    } else {
      // Only 'pending' tasks start a fresh stream
      startStream()
    }
  } catch (e) {
    ElMessage.error(e.message)
    router.push('/dashboard')
  }
})

onUnmounted(() => { if (es) es.close() })
</script>

<style scoped>
.task-detail { max-width: 900px; margin: 0 auto; }

.page-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 20px;
}
.header-info { display: flex; align-items: center; gap: 10px; flex: 1; }
.header-info h2 { font-size: 20px; color: #1a1a2e; margin: 0; }
.header-actions { margin-left: auto; }

.query-card { margin-bottom: 20px; }
.query-label { font-size: 12px; color: #aaa; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 1px; }
.query-text { font-size: 15px; color: #333; line-height: 1.6; margin-bottom: 12px; }
.query-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.query-time { font-size: 12px; color: #aaa; margin-left: auto; }

.results-section { display: flex; flex-direction: column; gap: 20px; }
.agent-result-block {
  background: #fff; border-radius: 12px; overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.agent-result-header {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 20px; background: #f8f9fa; border-bottom: 1px solid #f0f0f0;
}
.agent-result-icon { font-size: 20px; }
.agent-result-name { font-size: 15px; font-weight: 600; color: #222; flex: 1; }

.md-output { padding: 20px 24px; line-height: 1.8; color: #333; }
.md-output :deep(h1) { font-size: 20px; color: #1a1a2e; margin: 16px 0 8px; }
.md-output :deep(h2) { font-size: 17px; color: #0f3460; margin: 14px 0 6px; border-left: 3px solid #409eff; padding-left: 8px; }
.md-output :deep(h3) { font-size: 15px; color: #333; margin: 10px 0 4px; }
.md-output :deep(p) { margin-bottom: 10px; }
.md-output :deep(ul), .md-output :deep(ol) { padding-left: 20px; margin-bottom: 10px; }
.md-output :deep(li) { margin-bottom: 4px; }
.md-output :deep(strong) { color: #1a1a2e; }
.md-output :deep(blockquote) { border-left: 3px solid #e0e0e0; padding-left: 12px; color: #888; }
.md-output :deep(code) { background: #f5f7fa; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
.md-output :deep(hr) { border: none; border-top: 1px solid #f0f0f0; margin: 16px 0; }

.waiting-placeholder { padding: 32px; text-align: center; color: #aaa; font-size: 14px; }

.file-section { padding: 16px 20px; border-top: 1px solid #f5f5f5; background: #fafbfc; }
.file-section-title { font-size: 13px; font-weight: 600; color: #666; margin-bottom: 10px; }
.file-list { display: flex; flex-direction: column; gap: 8px; }
.file-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; background: #fff; border-radius: 8px;
  border: 1px solid #f0f0f0;
}
.file-icon { font-size: 18px; }
.file-name { flex: 1; font-size: 13px; color: #333; }
.file-credits { font-size: 12px; color: #f5a623; font-weight: 600; background: #fff8e6; padding: 2px 8px; border-radius: 4px; }

@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 1s linear infinite; }
</style>
