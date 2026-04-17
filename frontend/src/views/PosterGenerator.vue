<template>
  <div class="poster-page">
    <!-- Top -->
    <button class="back-btn" @click="$router.push('/dashboard')">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M10 4L6 8l4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>工作台</span>
    </button>

    <div class="page-hero">
      <div class="hero-badge">
        <span class="dot"></span>
        <span>AI Poster Studio</span>
      </div>
      <h1>海报智能生成</h1>
      <p>输入节气关键词，AI 自动生成专业级商业海报 · 默认 2160×3840 · 9:16 竖版</p>
    </div>

    <!-- Form (when no active generation) -->
    <div v-if="!generationId || generationError" class="form-card">
      <!-- Brand + event row -->
      <div class="row-2">
        <div class="field">
          <label>品牌名称 <span class="req">*</span></label>
          <input v-model="form.brandName" class="field-input" placeholder="例：木语" maxlength="40" />
        </div>
        <div class="field">
          <label>节气/节日关键词 <span class="req">*</span></label>
          <input v-model="form.eventKeyword" class="field-input" placeholder="例：谷雨、中秋" maxlength="20" />
        </div>
      </div>

      <!-- Headline + subline row (optional) -->
      <div class="row-2">
        <div class="field">
          <label>主标题（选填，留空自动用节气名）</label>
          <input v-model="form.headline" class="field-input" placeholder="例：春雨润万物" maxlength="30" />
        </div>
        <div class="field">
          <label>副标题（选填）</label>
          <input v-model="form.subline" class="field-input" placeholder="例：美好肆意生长" maxlength="60" />
        </div>
      </div>

      <!-- Industry + size + style row -->
      <div class="row-3">
        <div class="field">
          <label>所属行业</label>
          <select v-model="form.industry" class="field-input">
            <option value="">（自动推断）</option>
            <option value="家居家具">家居家具</option>
            <option value="美妆护肤">美妆护肤</option>
            <option value="科技智能">科技智能</option>
            <option value="食品饮料">食品饮料</option>
            <option value="服装时尚">服装时尚</option>
            <option value="教育培训">教育培训</option>
            <option value="医疗健康">医疗健康</option>
          </select>
        </div>
        <div class="field">
          <label>尺寸</label>
          <select v-model="form.size" class="field-input">
            <option value="portrait">9:16 竖版（2160×3840）</option>
            <option value="story">9:16 Story（1080×1920）</option>
            <option value="square">1:1 方形（2048×2048）</option>
            <option value="landscape">16:9 横版（1920×1080）</option>
            <option value="a3">A3 印刷（2480×3508）</option>
          </select>
        </div>
        <div class="field">
          <label>主色（选填）</label>
          <div class="color-input-row">
            <input type="color" v-model="form.primaryColor" class="color-swatch" />
            <input v-model="form.primaryColor" class="field-input color-hex" placeholder="#6366f1" maxlength="7" />
          </div>
        </div>
      </div>

      <!-- Style picker -->
      <div class="field">
        <label>视觉风格</label>
        <div class="style-grid">
          <div
            v-for="s in styles" :key="s.value"
            class="style-card"
            :class="{ selected: form.style === s.value }"
            @click="form.style = s.value"
          >
            <span class="style-icon">{{ s.icon }}</span>
            <span class="style-label">{{ s.label }}</span>
          </div>
        </div>
      </div>

      <!-- Credit info -->
      <div class="credit-row">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5"/>
          <path d="M8 4v4l2.5 1.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span>本次生成消耗 <b>{{ creditCost }}</b> 积分 · 当前余额 <b>{{ userCredits }}</b></span>
        <span v-if="userCredits < creditCost" class="insufficient">余额不足</span>
      </div>

      <button class="generate-btn" :disabled="!canGenerate || generating" @click="handleGenerate">
        <span v-if="generating" class="spinner"></span>
        <svg v-else width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M9 1L11 6L16 7L12 11L13 16L9 13.5L5 16L6 11L2 7L7 6L9 1Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
        </svg>
        <span>{{ generating ? '生成中…' : '✨ 开始生成海报' }}</span>
      </button>
    </div>

    <!-- Progress -->
    <div v-if="generationId && !generationDone && !generationError" class="progress-card">
      <div class="progress-head">
        <div class="pulse"></div>
        <span>正在生成海报，请耐心等待…</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: progress.percent + '%' }"></div>
      </div>
      <div class="progress-steps">
        <div v-for="(step, idx) in progressSteps" :key="idx"
          class="progress-step"
          :class="{ active: progress.percent >= step.at && progress.percent < (progressSteps[idx + 1]?.at || 101),
                    done:   progress.percent >= (progressSteps[idx + 1]?.at || 101) }">
          <span class="step-dot" />
          <span class="step-label">{{ step.label }}</span>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="generationError" class="error-banner">
      <span>⚠️</span><span>{{ generationError }}</span>
      <button class="clear-btn" @click="generationError = ''">✕</button>
    </div>

    <!-- Result -->
    <div v-if="generationDone && variants.length" class="result-card">
      <div class="result-head">
        <h3>海报生成结果</h3>
        <button class="ghost-btn" @click="handleReset">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M13 3v4h-4M3 13v-4h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M4.2 6a5 5 0 018-1.5L13 7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          重新生成
        </button>
      </div>

      <div class="variant-wrapper">
        <div v-for="(v, idx) in variants" :key="idx" class="variant-item"
          :class="{ selected: selectedVariant === idx }"
          @click="selectedVariant = idx">
          <div class="variant-preview">
            <img :src="posterImgUrl(v)" :alt="`方案 ${idx + 1}`" />
          </div>
          <div class="variant-label">方案 {{ idx + 1 }}</div>
        </div>
      </div>

      <div class="download-row">
        <button class="download-btn primary" @click="handleDownload">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 2v9M4 7l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M3 14h10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
          下载 PNG
        </button>
      </div>
    </div>

    <!-- History -->
    <div class="history-card">
      <div class="history-head">
        <h3>📋 生成历史</h3>
        <button class="ghost-btn small" @click="loadHistory">刷新</button>
      </div>
      <div v-if="!history.length && !historyLoading" class="history-empty">
        还没有生成记录
      </div>
      <div v-else class="history-list">
        <div v-for="item in history" :key="item.id" class="history-item"
          @click="viewHistory(item)">
          <div class="history-preview">
            <img v-if="item.variants?.[0]?.png_url" :src="historyImgUrl(item)" :alt="item.brand_name" />
            <div v-else class="history-placeholder">
              {{ item.status === 'processing' ? '⏳' : '❌' }}
            </div>
          </div>
          <div class="history-info">
            <div class="history-title">{{ item.brand_name }} · {{ item.event_keyword }}</div>
            <div class="history-meta">
              <span class="status-chip" :class="`s-${item.status}`">
                {{ item.status === 'done' ? '完成' : (item.status === 'failed' ? '失败' : '生成中') }}
              </span>
              <span>{{ styleLabel(item.style) }}</span>
              <span class="time">{{ formatTime(item.created_at) }}</span>
            </div>
          </div>
          <button v-if="item.status === 'done'" class="history-dl" @click.stop="downloadHistory(item)">
            下载
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../store'
import { posterAPI } from '../api'

const store = useUserStore()
const userCredits = computed(() => store.user?.credits ?? 0)

const form = reactive({
  brandName: '',
  eventKeyword: '',
  headline: '',
  subline: '',
  industry: '',
  size: 'portrait',
  style: 'natural',
  primaryColor: '',
})

const styles = [
  { value: 'natural',  icon: '🌿', label: '自然写实' },
  { value: 'luxury',   icon: '💎', label: '奢华高端' },
  { value: 'modern',   icon: '🔲', label: '现代简约' },
  { value: 'playful',  icon: '🎈', label: '活泼趣味' },
  { value: 'heritage', icon: '🏮', label: '东方古韵' },
]

const creditCost = computed(() => 5)
const canGenerate = computed(() =>
  form.brandName.trim() && form.eventKeyword.trim() && userCredits.value >= creditCost.value
)

// Generation state
const generating = ref(false)
const generationId = ref('')
const generationDone = ref(false)
const generationError = ref('')
const variants = ref([])
const selectedVariant = ref(0)
const progress = reactive({ percent: 0, label: '' })
let eventSource = null

const progressSteps = [
  { label: '准备提示词', at: 5 },
  { label: '生成背景',   at: 30 },
  { label: '合成图层',   at: 70 },
  { label: '完成',       at: 100 },
]

async function handleGenerate() {
  if (!canGenerate.value) return
  generating.value = true
  generationDone.value = false
  generationError.value = ''
  variants.value = []
  progress.percent = 0

  try {
    const res = await posterAPI.generate({
      brand_name:    form.brandName,
      event_keyword: form.eventKeyword,
      headline:      form.headline || null,
      subline:       form.subline || null,
      industry:      form.industry || null,
      size:          form.size,
      style:         form.style,
      primary_color: form.primaryColor || null,
    })
    generationId.value = res.generation_id
    store.fetchMe().catch(() => {})
    startProgressPolling(res.generation_id)
  } catch (e) {
    generationError.value = e.message || '生成请求失败'
    ElMessage.error(generationError.value)
  } finally {
    generating.value = false
  }
}

function startProgressPolling(id) {
  closeEventSource()
  const token = localStorage.getItem('token')
  eventSource = new EventSource(posterAPI.progressUrl(id, token))

  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.type === 'progress') {
        progress.percent = data.percent ?? progress.percent
        progress.label = data.label ?? ''
      } else if (data.type === 'done') {
        progress.percent = 100
        generationDone.value = true
        variants.value = data.variants || []
        selectedVariant.value = 0
        closeEventSource()
        loadHistory()
        ElMessage.success('海报生成完成')
      } else if (data.type === 'error') {
        generationError.value = data.message || '生成失败'
        closeEventSource()
        ElMessage.error(generationError.value)
      }
    } catch { /* skip */ }
  }
  eventSource.onerror = () => {
    closeEventSource()
    if (!generationDone.value && !generationError.value) {
      generationError.value = '连接中断，请刷新页面重试'
    }
  }
}

function closeEventSource() {
  if (eventSource) { eventSource.close(); eventSource = null }
}

function posterImgUrl(v) {
  // Backend returns png_url like "/api/poster/file/{fname}"
  const token = localStorage.getItem('token') || ''
  if (!v?.png_url) return ''
  // If url is already an /api path, append token
  const sep = v.png_url.includes('?') ? '&' : '?'
  return `${v.png_url}${sep}_t=${encodeURIComponent(token.slice(0, 8))}`
}

function historyImgUrl(item) {
  const token = localStorage.getItem('token') || ''
  const url = item.variants?.[0]?.png_url || ''
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}_t=${encodeURIComponent(token.slice(0, 8))}`
}

function handleDownload() {
  if (!generationId.value) return
  const a = document.createElement('a')
  a.href = posterAPI.downloadUrl(generationId.value)
  a.download = `${form.brandName}_${form.eventKeyword}_poster.png`
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  ElMessage.success('已开始下载')
}

function handleReset() {
  generationId.value = ''
  generationDone.value = false
  generationError.value = ''
  variants.value = []
  progress.percent = 0
  selectedVariant.value = 0
}

// History
const history = ref([])
const historyLoading = ref(false)

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await posterAPI.history(1, 12)
    history.value = res.items || []
  } finally { historyLoading.value = false }
}

function viewHistory(item) {
  if (item.status === 'done' && item.variants?.length) {
    generationId.value = item.id
    generationDone.value = true
    variants.value = item.variants
    selectedVariant.value = 0
    generationError.value = ''
    progress.percent = 100
    form.brandName = item.brand_name
    form.eventKeyword = item.event_keyword
  } else if (item.status === 'processing') {
    generationId.value = item.id
    generationDone.value = false
    startProgressPolling(item.id)
  }
}

function downloadHistory(item) {
  const a = document.createElement('a')
  a.href = posterAPI.downloadUrl(item.id)
  a.download = `${item.brand_name}_${item.event_keyword}_poster.png`
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

function styleLabel(v) {
  return styles.find(s => s.value === v)?.label || v || ''
}
function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  store.fetchMe().catch(() => {})
  loadHistory()
})
onUnmounted(closeEventSource)
</script>

<style scoped>
.poster-page { max-width: 960px; margin: 0 auto; color: var(--ybc-text); }

.back-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--ybc-border);
  border-radius: 8px;
  color: var(--ybc-text-dim);
  font-size: 13px;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
  margin-bottom: 20px;
}
.back-btn:hover { background: rgba(255,255,255,0.04); color: var(--ybc-text); }

/* Hero */
.page-hero { text-align: center; margin-bottom: 28px; padding: 12px 0; }
.hero-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 12px;
  border-radius: 100px;
  background: rgba(236, 72, 153, 0.08);
  border: 1px solid rgba(236, 72, 153, 0.2);
  color: #f9a8d4;
  font-size: 11px; font-weight: 500;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}
.hero-badge .dot {
  width: 5px; height: 5px; border-radius: 50%;
  background: #22c55e;
  animation: ybc-pulse-dot 2s infinite;
}
.page-hero h1 {
  font-size: 28px; font-weight: 800;
  color: var(--ybc-text-strong);
  letter-spacing: -0.5px;
  margin-bottom: 8px;
}
.page-hero p {
  font-size: 14px;
  color: var(--ybc-text-dim);
}

/* Form */
.form-card, .progress-card, .result-card, .history-card {
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 20px;
  padding: 28px 32px;
  margin-bottom: 18px;
  box-shadow: var(--ybc-shadow-md);
}

.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px; }
.row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin-bottom: 16px; }

.field { margin-bottom: 16px; }
.field label {
  display: block;
  font-size: 12px; font-weight: 600;
  color: var(--ybc-text);
  margin-bottom: 6px;
}
.req { color: var(--ybc-danger); }

.field-input {
  width: 100%;
  padding: 11px 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ybc-border);
  border-radius: 10px;
  color: var(--ybc-text-strong);
  font-size: 14px;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
}
.field-input:focus { border-color: var(--ybc-accent); background: rgba(99, 102, 241, 0.04); }
.field-input::placeholder { color: var(--ybc-text-faint); }

select.field-input {
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%2371717a'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}
select.field-input option { background: #12121a; color: var(--ybc-text); }

.color-input-row { display: flex; gap: 8px; align-items: center; }
.color-swatch {
  width: 38px; height: 38px;
  padding: 0; border: 1px solid var(--ybc-border);
  border-radius: 8px; cursor: pointer; background: transparent;
}
.color-hex { flex: 1; font-family: 'SF Mono', Menlo, monospace; }

/* Style grid */
.style-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}
.style-card {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 12px 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ybc-border);
  border-radius: 10px;
  cursor: pointer;
  transition: 0.15s;
}
.style-card:hover { border-color: rgba(236, 72, 153, 0.35); background: rgba(236, 72, 153, 0.05); }
.style-card.selected {
  border-color: #ec4899;
  background: rgba(236, 72, 153, 0.1);
  box-shadow: 0 0 0 1px rgba(236, 72, 153, 0.25);
}
.style-icon { font-size: 22px; }
.style-label { font-size: 11px; font-weight: 600; color: var(--ybc-text); }

/* Credits */
.credit-row {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px;
  background: rgba(245, 158, 11, 0.06);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: 10px;
  color: #fcd34d;
  font-size: 13px;
  margin: 8px 0 16px;
}
.credit-row b { color: #fde68a; font-weight: 700; }
.insufficient {
  margin-left: auto;
  padding: 2px 8px;
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
  border-radius: 100px;
  font-size: 11px;
}

/* Buttons */
.generate-btn {
  width: 100%;
  padding: 14px;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  background: linear-gradient(135deg, #ec4899 0%, #a855f7 50%, #6366f1 100%);
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 15px; font-weight: 600;
  cursor: pointer;
  transition: 0.2s;
  font-family: inherit;
}
.generate-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 32px rgba(236, 72, 153, 0.35);
}
.generate-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Progress */
.progress-head {
  display: flex; align-items: center; gap: 10px;
  font-size: 15px; font-weight: 600;
  color: var(--ybc-text-strong);
  margin-bottom: 14px;
}
.pulse {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: #ec4899;
  animation: ybc-pulse-dot 1s infinite;
}
.progress-track {
  height: 8px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 100px;
  overflow: hidden;
  margin-bottom: 16px;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #ec4899, #a855f7, #6366f1);
  background-size: 200% 100%;
  animation: stripe 2s linear infinite;
  transition: width 0.5s ease;
}
@keyframes stripe {
  0% { background-position: 0 0; }
  100% { background-position: 200% 0; }
}
.progress-steps { display: flex; justify-content: space-between; gap: 8px; }
.progress-step {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  flex: 1; opacity: 0.4; transition: 0.3s;
}
.progress-step.active, .progress-step.done { opacity: 1; }
.step-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
}
.progress-step.active .step-dot {
  background: #ec4899;
  box-shadow: 0 0 12px rgba(236, 72, 153, 0.6);
  animation: ybc-pulse-dot 1.2s infinite;
}
.progress-step.done .step-dot { background: #22c55e; }
.step-label { font-size: 11px; color: var(--ybc-text-dim); text-align: center; }

/* Error */
.error-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 12px;
  color: #fca5a5;
  font-size: 14px;
  margin-bottom: 18px;
}
.clear-btn {
  margin-left: auto; background: none; border: none;
  color: inherit; cursor: pointer; font-size: 16px;
  font-family: inherit;
}

/* Result */
.result-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--ybc-border);
}
.result-head h3 {
  font-size: 18px; font-weight: 700;
  color: var(--ybc-text-strong);
}
.ghost-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px;
  background: transparent;
  border: 1px solid var(--ybc-border);
  border-radius: 8px;
  color: var(--ybc-text);
  font-size: 13px;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
}
.ghost-btn:hover { border-color: var(--ybc-accent-light); color: var(--ybc-accent-light); }
.ghost-btn.small { padding: 5px 10px; font-size: 12px; }

.variant-wrapper {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}
.variant-item {
  cursor: pointer;
  border-radius: 12px;
  overflow: hidden;
  border: 2px solid var(--ybc-border);
  transition: 0.2s;
  background: rgba(255, 255, 255, 0.02);
}
.variant-item:hover { transform: translateY(-2px); border-color: rgba(236, 72, 153, 0.4); }
.variant-item.selected {
  border-color: #ec4899;
  box-shadow: 0 0 0 2px rgba(236, 72, 153, 0.25);
}
.variant-preview {
  aspect-ratio: 9 / 16;
  background: #000;
  display: flex; align-items: center; justify-content: center;
}
.variant-preview img { width: 100%; height: 100%; object-fit: cover; }
.variant-label {
  padding: 8px; text-align: center;
  font-size: 12px; color: var(--ybc-text-dim);
  background: var(--ybc-surface-2);
}

.download-row {
  display: flex; gap: 10px;
  padding-top: 16px;
  border-top: 1px solid var(--ybc-border);
}
.download-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--ybc-border);
  border-radius: 10px;
  color: var(--ybc-text);
  font-size: 14px; font-weight: 500;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
}
.download-btn:hover { background: rgba(99, 102, 241, 0.1); border-color: var(--ybc-accent-light); }
.download-btn.primary {
  background: var(--ybc-gradient-primary);
  border: none;
  color: #fff;
}
.download-btn.primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
}

/* History */
.history-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 14px;
}
.history-head h3 {
  font-size: 15px; font-weight: 700;
  color: var(--ybc-text-strong);
}
.history-empty {
  padding: 40px;
  text-align: center;
  color: var(--ybc-text-muted);
  font-size: 13px;
}
.history-list { display: flex; flex-direction: column; gap: 8px; }
.history-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--ybc-border);
  border-radius: 10px;
  cursor: pointer;
  transition: 0.15s;
}
.history-item:hover { background: rgba(99, 102, 241, 0.04); border-color: rgba(99, 102, 241, 0.2); }
.history-preview {
  width: 56px; height: 96px;
  border-radius: 6px;
  background: #000;
  overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.history-preview img { width: 100%; height: 100%; object-fit: cover; }
.history-placeholder { font-size: 22px; color: var(--ybc-text-muted); }

.history-info { flex: 1; min-width: 0; }
.history-title {
  font-size: 14px; font-weight: 600;
  color: var(--ybc-text-strong);
  margin-bottom: 4px;
}
.history-meta {
  display: flex; align-items: center; gap: 8px;
  font-size: 11px;
  color: var(--ybc-text-muted);
  flex-wrap: wrap;
}
.history-meta .time { color: var(--ybc-text-faint); }
.status-chip {
  padding: 1px 8px;
  border-radius: 100px;
  font-weight: 600;
}
.status-chip.s-done       { background: rgba(34, 197, 94, 0.12); color: #86efac; }
.status-chip.s-processing { background: rgba(245, 158, 11, 0.12); color: #fcd34d; }
.status-chip.s-failed     { background: rgba(239, 68, 68, 0.12); color: #fca5a5; }

.history-dl {
  padding: 5px 10px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: 8px;
  color: var(--ybc-accent-light);
  font-size: 11px;
  cursor: pointer;
  font-family: inherit;
  flex-shrink: 0;
}
.history-dl:hover { background: var(--ybc-accent); color: #fff; border-color: var(--ybc-accent); }

@media (max-width: 760px) {
  .row-2, .row-3 { grid-template-columns: 1fr; }
  .style-grid { grid-template-columns: repeat(3, 1fr); }
  .form-card, .progress-card, .result-card, .history-card { padding: 20px; }
  .page-hero h1 { font-size: 22px; }
}
</style>
