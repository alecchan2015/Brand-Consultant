<template>
  <div class="task-detail">
    <!-- Loading skeleton -->
    <div v-if="!task" class="skeleton-wrap">
      <div class="sk-top-bar">
        <div class="sk-line sk-back"></div>
        <div class="sk-line sk-title"></div>
      </div>
      <div class="sk-card">
        <div class="sk-line sk-label"></div>
        <div class="sk-line sk-text-long"></div>
        <div class="sk-line sk-text-mid"></div>
        <div class="sk-chips">
          <span class="sk-chip"></span><span class="sk-chip"></span><span class="sk-chip"></span>
        </div>
      </div>
      <div class="sk-card" v-for="i in 2" :key="i">
        <div class="sk-result-head">
          <div class="sk-line sk-label"></div>
          <div class="sk-line sk-badge"></div>
        </div>
        <div class="sk-line sk-text-long"></div>
        <div class="sk-line sk-text-long"></div>
        <div class="sk-line sk-text-short"></div>
      </div>
    </div>

    <template v-else>
    <!-- Top bar -->
    <div class="top-bar">
      <button class="back-btn" @click="$router.push('/dashboard')">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
          <path d="M10 4L6 8l4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>{{ $t('common.backToDashboard') }}</span>
      </button>
      <div class="title-row">
        <h1>{{ task?.brand_name || $t('taskDetail.defaultBrandName') }}</h1>
        <span v-if="task" class="status-pill" :class="`status-${task.status}`">
          <span class="dot"></span>{{ statusLabel[task.status] }}
        </span>
      </div>
      <div class="action-row">
        <button v-if="task?.status === 'completed' || task?.status === 'failed'"
          class="btn-ghost" :disabled="regenerating" @click="handleRegenerate">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" :style="{ animation: regenerating ? 'spin 1s linear infinite' : '' }">
            <path d="M13 3v4h-4M3 13v-4h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M4.2 6a5 5 0 018-1.5L13 7M11.8 10a5 5 0 01-8 1.5L3 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>{{ regenerating ? $t('taskDetail.regenerating') : $t('taskDetail.regenerate') }}</span>
        </button>
      </div>
    </div>

    <!-- Query card -->
    <div class="query-card">
      <div class="query-head">
        <span class="query-label">{{ $t('taskDetail.queryLabel') }}</span>
        <span v-if="task?.created_at" class="query-time">
          {{ new Date(task.created_at).toLocaleString('zh-CN') }}
        </span>
      </div>
      <div class="query-text">{{ task?.query }}</div>
      <div class="query-meta">
        <span v-for="a in task?.agents_selected" :key="a"
          class="agent-chip" :class="`a-${a}`">
          <span>{{ agentIcon[a] }}</span>
          <span>{{ agentNames[a] }}</span>
        </span>
      </div>
    </div>

    <!-- Results -->
    <div class="results">
      <div v-for="agentType in orderedAgents" :key="agentType" class="result-block">
        <div class="result-head">
          <span class="result-icon">{{ agentIcon[agentType] }}</span>
          <span class="result-name">{{ agentNames[agentType] }}</span>

          <span v-if="agentStatus[agentType] === 'streaming'" class="stage-badge streaming">
            <span class="live-dot"></span>{{ $t('taskDetail.generatingLabel') }}
          </span>
          <span v-else-if="agentStatus[agentType] === 'done'" class="stage-badge done">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M2 5l2 2 4-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            {{ $t('taskDetail.doneLabel') }}
          </span>
          <span v-else class="stage-badge waiting">{{ $t('taskDetail.waitingLabel') }}</span>
        </div>

        <!-- Content -->
        <div v-if="agentContents[agentType]" class="md-output" v-html="renderMd(agentContents[agentType])"></div>
        <div v-else-if="agentStatus[agentType] === 'waiting'" class="placeholder">
          <div class="placeholder-icon">⏳</div>
          <div>{{ $t('taskDetail.waitingPlaceholder') }}</div>
        </div>

        <!-- Files -->
        <div v-if="agentFiles[agentType]?.length" class="file-section">
          <div class="file-head">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
              <path d="M4 2h6l4 4v8H4V2z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
              <path d="M10 2v4h4" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
            </svg>
            <span>{{ $t('taskDetail.filesTitle') }}</span>
          </div>
          <div class="file-list">
            <div v-for="file in agentFiles[agentType]" :key="file.id" class="file-row">
              <span class="file-icon">{{ fileIcon[file.type] || '📁' }}</span>
              <span class="file-name">{{ file.name }}</span>
              <span v-if="file.credits === 0" class="cost-pill cost-free">{{ $t('common.free') }}</span>
              <span v-else class="cost-pill cost-paid">{{ $t('common.creditsUnit', { n: file.credits }) }}</span>
              <button class="download-btn" @click="downloadFile(file)">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                  <path d="M8 2v9M4 7l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M3 14h10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                </svg>
                {{ $t('common.actions.download') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="error-banner">
      <span>⚠️</span>
      <span>{{ error }}</span>
    </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import { tasksAPI, filesAPI } from '../api'
import { useUserStore } from '../store'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const store = useUserStore()

const task = ref(null)
const error = ref('')
const agentContents = ref({})
const agentStatus = ref({})
const agentFiles = ref({})
const regenerating = ref(false)
let es = null

const agentNames = computed(() => ({
  strategy: t('common.agent.strategyFull'),
  brand: t('common.agent.brandFull'),
  logo_design: t('common.agent.logoDesignFull'),
  poster_design: t('common.agent.posterDesignFull'),
  operations: t('common.agent.operationsFull'),
}))
const agentIcon  = { strategy: '🎯', brand: '🎨', logo_design: '✨', poster_design: '🖼️', operations: '🚀' }
const statusLabel = computed(() => ({
  pending: t('common.status.pending'),
  processing: t('common.status.processing'),
  completed: t('common.status.completed'),
  failed: t('common.status.failed'),
}))
const fileIcon = { md: '📄', pdf: '📕', png: '🖼️', pptx: '📊', psd: '🎨' }

const orderedAgents = computed(() => {
  if (!task.value) return []
  return ['strategy', 'brand', 'logo_design', 'poster_design', 'operations'].filter(a => task.value.agents_selected.includes(a))
})

function renderMd(text) { return marked.parse(text || '', { breaks: true }) }

function initAgentStatuses() {
  orderedAgents.value.forEach(a => {
    agentStatus.value[a] = 'waiting'
    agentContents.value[a] = ''
    agentFiles.value[a] = []
  })
}

function loadExistingResults() {
  if (!task.value?.results?.length) return
  task.value.results.forEach(r => {
    if (r.file_type) {
      const files = agentFiles.value[r.agent_type] || []
      if (!files.some(f => f.id === r.id)) {
        files.push({ id: r.id, type: r.file_type, name: r.file_name, credits: r.download_credits })
      }
      agentFiles.value[r.agent_type] = files
    } else if (r.content) {
      agentContents.value[r.agent_type] = r.content
      agentStatus.value[r.agent_type] = 'done'
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
      ElMessage.success(t('taskDetail.allDone'))
    } else if (data.type === 'error') {
      error.value = data.message
      task.value.status = 'failed'
      es.close()
    } else if (data.type === 'already_done') {
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
  } catch (e) { ElMessage.error(e.message) }
}

async function handleRegenerate() {
  try {
    await ElMessageBox.confirm(t('taskDetail.confirmRegenerate'), t('taskDetail.confirmTitle'),
      { confirmButtonText: t('taskDetail.confirmBtn'), cancelButtonText: t('common.cancel'), type: 'warning' })
  } catch { return }
  regenerating.value = true
  error.value = ''
  try {
    await tasksAPI.regenerate(route.params.id)
    task.value.status = 'pending'
    initAgentStatuses()
    startStream()
    ElMessage.info(t('taskDetail.startedRegen'))
  } catch (e) { ElMessage.error(e.message) }
  finally { regenerating.value = false }
}

function downloadFile(file) {
  const a = document.createElement('a')
  a.href = filesAPI.downloadUrl(file.id)
  a.download = file.name
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  ElMessage.success(t('taskDetail.downloadStarted'))
  setTimeout(() => { store.fetchMe().catch(() => {}) }, 1500)
}

onMounted(async () => {
  try {
    task.value = await tasksAPI.get(route.params.id)
    initAgentStatuses()
    if (task.value.status === 'completed' || task.value.status === 'failed') {
      loadExistingResults()
    } else if (task.value.status === 'processing') {
      loadExistingResults()
    } else {
      // pending — ensure status grid renders immediately before streaming
      initAgentStatuses()
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
.task-detail { max-width: 920px; margin: 0 auto; }

/* ── Top bar ──────────────────────────────────────────────── */
.top-bar {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.back-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--ybc-border);
  border-radius: 8px;
  color: var(--ybc-text-dim);
  font-size: 13px; cursor: pointer;
  transition: 0.15s; font-family: inherit;
}
.back-btn:hover { background: rgba(255, 255, 255, 0.04); color: var(--ybc-text); }

.title-row {
  display: flex; align-items: center; gap: 10px;
  flex: 1; min-width: 0;
  max-width: calc(100% - 160px);  /* leave room for status pill + action */
}
.title-row h1 {
  font-size: 22px; font-weight: 800;
  color: var(--ybc-text-strong);
  letter-spacing: -0.3px;
  margin: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  min-width: 0;
  flex: 1;
}

/* ── Loading skeleton ───────────────────────────────────── */
.skeleton-wrap {
  display: flex; flex-direction: column; gap: 16px;
  animation: ybc-fade-up 0.25s;
}
.sk-top-bar {
  display: flex; align-items: center; gap: 14px;
}
.sk-card {
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 16px;
  padding: 20px;
  display: flex; flex-direction: column; gap: 12px;
}
.sk-result-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 4px;
}
.sk-line {
  height: 14px;
  background: linear-gradient(
    90deg,
    rgba(255,255,255,0.04) 25%,
    rgba(255,255,255,0.09) 50%,
    rgba(255,255,255,0.04) 75%
  );
  background-size: 200% 100%;
  border-radius: 4px;
  animation: sk-shimmer 1.5s infinite linear;
}
.sk-back { width: 60px; }
.sk-title { width: 180px; height: 22px; }
.sk-label { width: 80px; height: 11px; }
.sk-badge { width: 56px; height: 20px; border-radius: 100px; }
.sk-text-long { width: 92%; }
.sk-text-mid  { width: 72%; }
.sk-text-short { width: 55%; }
.sk-chips { display: flex; gap: 6px; margin-top: 6px; }
.sk-chip {
  width: 64px; height: 20px;
  border-radius: 100px;
  background: rgba(255,255,255,0.04);
  animation: sk-shimmer 1.5s infinite linear;
  background: linear-gradient(
    90deg,
    rgba(255,255,255,0.04) 25%,
    rgba(255,255,255,0.08) 50%,
    rgba(255,255,255,0.04) 75%
  );
  background-size: 200% 100%;
}
@keyframes sk-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.status-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px;
  border-radius: 100px;
  font-size: 11px; font-weight: 600;
  white-space: nowrap;
}
.status-pill .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.status-pill.status-pending    { background: rgba(255, 255, 255, 0.06); color: var(--ybc-text-muted); }
.status-pill.status-processing { background: rgba(245, 158, 11, 0.15); color: #fcd34d; }
.status-pill.status-processing .dot { animation: ybc-pulse-dot 1s infinite; }
.status-pill.status-completed  { background: rgba(34, 197, 94, 0.15); color: #86efac; }
.status-pill.status-failed     { background: rgba(239, 68, 68, 0.15); color: #fca5a5; }

.btn-ghost {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px;
  background: transparent;
  border: 1px solid var(--ybc-border);
  border-radius: 8px;
  color: var(--ybc-text);
  font-size: 13px; cursor: pointer;
  transition: 0.15s; font-family: inherit;
}
.btn-ghost:hover:not(:disabled) {
  border-color: var(--ybc-accent-light);
  color: var(--ybc-accent-light);
  background: rgba(99, 102, 241, 0.06);
}
.btn-ghost:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Query card ───────────────────────────────────────────── */
.query-card {
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 16px;
  padding: 18px 22px;
  margin-bottom: 20px;
}
.query-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px;
}
.query-label {
  font-size: 11px; font-weight: 600;
  color: var(--ybc-text-muted);
  letter-spacing: 1px;
  text-transform: uppercase;
}
.query-time { font-size: 11px; color: var(--ybc-text-faint); }

.query-text {
  font-size: 14px;
  color: var(--ybc-text);
  line-height: 1.7;
  margin-bottom: 14px;
}
.query-meta { display: flex; gap: 6px; flex-wrap: wrap; }

.agent-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--ybc-border);
  border-radius: 100px;
  font-size: 11px;
  color: var(--ybc-text-dim);
}
.agent-chip.a-strategy   { border-color: rgba(59, 130, 246, 0.3); color: #93c5fd; background: rgba(59, 130, 246, 0.08); }
.agent-chip.a-brand      { border-color: rgba(168, 85, 247, 0.3); color: #d8b4fe; background: rgba(168, 85, 247, 0.08); }
.agent-chip.a-logo_design{ border-color: rgba(236, 72, 153, 0.3); color: #f9a8d4; background: rgba(236, 72, 153, 0.08); }
.agent-chip.a-poster_design { border-color: rgba(14, 165, 233, 0.35); color: #7dd3fc; background: rgba(14, 165, 233, 0.08); }
.agent-chip.a-operations { border-color: rgba(245, 158, 11, 0.3); color: #fcd34d; background: rgba(245, 158, 11, 0.08); }

/* ── Results ───────────────────────────────────────────────── */
.results { display: flex; flex-direction: column; gap: 16px; }

.result-block {
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 16px;
  overflow: hidden;
}

.result-head {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 20px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid var(--ybc-border);
}
.result-icon { font-size: 20px; }
.result-name {
  flex: 1;
  font-size: 14px; font-weight: 600;
  color: var(--ybc-text-strong);
}

.stage-badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 10px;
  border-radius: 100px;
  font-size: 11px; font-weight: 500;
}
.stage-badge.waiting { background: rgba(255, 255, 255, 0.05); color: var(--ybc-text-muted); }
.stage-badge.streaming { background: rgba(245, 158, 11, 0.12); color: #fcd34d; }
.stage-badge.done { background: rgba(34, 197, 94, 0.12); color: #86efac; }
.live-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: ybc-pulse-dot 1s infinite;
}

/* ── Markdown output ─────────────────────────────────────── */
.md-output {
  padding: 22px 24px;
  line-height: 1.8;
  color: var(--ybc-text);
  font-size: 14px;
}
.md-output :deep(h1) {
  font-size: 20px; font-weight: 700;
  color: var(--ybc-text-strong);
  margin: 18px 0 10px;
  letter-spacing: -0.3px;
}
.md-output :deep(h2) {
  font-size: 17px; font-weight: 700;
  color: #fff;
  margin: 20px 0 8px;
  padding-left: 12px;
  border-left: 3px solid var(--ybc-accent);
}
.md-output :deep(h3) {
  font-size: 15px; font-weight: 600;
  color: var(--ybc-text-strong);
  margin: 14px 0 6px;
}
.md-output :deep(h4) { font-size: 14px; color: var(--ybc-text-strong); margin: 12px 0 4px; }
.md-output :deep(p) { margin-bottom: 12px; }
.md-output :deep(ul), .md-output :deep(ol) { padding-left: 22px; margin-bottom: 12px; }
.md-output :deep(li) { margin-bottom: 6px; }
.md-output :deep(li::marker) { color: var(--ybc-accent-light); }
.md-output :deep(strong) { color: var(--ybc-text-strong); font-weight: 600; }
.md-output :deep(em) { color: var(--ybc-accent-light); font-style: normal; }
.md-output :deep(blockquote) {
  border-left: 3px solid var(--ybc-border);
  padding: 6px 14px;
  color: var(--ybc-text-dim);
  margin: 10px 0;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 0 8px 8px 0;
}
.md-output :deep(code) {
  background: rgba(99, 102, 241, 0.1);
  color: var(--ybc-accent-light);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}
.md-output :deep(pre) {
  background: #0a0a0f;
  border: 1px solid var(--ybc-border);
  border-radius: 8px;
  padding: 14px;
  overflow-x: auto;
  margin: 12px 0;
}
.md-output :deep(pre code) {
  background: transparent;
  color: var(--ybc-text);
  padding: 0;
}
.md-output :deep(hr) {
  border: none;
  height: 1px;
  background: var(--ybc-border);
  margin: 20px 0;
}
.md-output :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}
.md-output :deep(th), .md-output :deep(td) {
  border: 1px solid var(--ybc-border);
  padding: 8px 12px;
  text-align: left;
}
.md-output :deep(th) {
  background: rgba(255, 255, 255, 0.04);
  color: var(--ybc-text-strong);
  font-weight: 600;
}
.md-output :deep(a) { color: var(--ybc-accent-light); text-decoration: none; }
.md-output :deep(a:hover) { text-decoration: underline; }

.placeholder {
  padding: 60px 20px;
  text-align: center;
  color: var(--ybc-text-muted);
  font-size: 13px;
}
.placeholder-icon { font-size: 32px; margin-bottom: 12px; opacity: 0.6; }

/* ── File section ──────────────────────────────────────── */
.file-section {
  padding: 16px 20px;
  border-top: 1px solid var(--ybc-border);
  background: rgba(255, 255, 255, 0.02);
}
.file-head {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600;
  color: var(--ybc-text-muted);
  margin-bottom: 10px;
  letter-spacing: 0.5px;
}
.file-list { display: flex; flex-direction: column; gap: 6px; }
.file-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ybc-border);
  border-radius: 10px;
  transition: 0.15s;
}
.file-row:hover { border-color: rgba(99, 102, 241, 0.3); }
.file-icon { font-size: 18px; }
.file-name {
  flex: 1;
  font-size: 13px;
  color: var(--ybc-text);
  word-break: break-all;
}
.cost-pill {
  padding: 2px 8px;
  border-radius: 100px;
  font-size: 10px; font-weight: 600;
  white-space: nowrap;
}
.cost-pill.cost-free {
  background: rgba(34, 197, 94, 0.12);
  color: #86efac;
}
.cost-pill.cost-paid {
  background: rgba(245, 158, 11, 0.12);
  color: #fcd34d;
}

.download-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 5px 10px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: 8px;
  color: var(--ybc-accent-light);
  font-size: 12px;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
}
.download-btn:hover {
  background: var(--ybc-accent);
  color: #fff;
  border-color: var(--ybc-accent);
}

.error-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px;
  margin-top: 16px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 10px;
  color: #fca5a5;
  font-size: 13px;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
