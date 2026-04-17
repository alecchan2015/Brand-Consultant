<template>
  <div class="new-task-page">
    <button class="back-btn" @click="$router.back()">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M10 4L6 8l4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>返回</span>
    </button>

    <div class="page-hero">
      <div class="hero-badge">
        <span class="dot"></span>
        <span>AI-Powered Task</span>
      </div>
      <h1>新建品牌策划任务</h1>
      <p>描述您的需求，选择 AI 专家，全流程自动化生成</p>
    </div>

    <div class="form-card">
      <!-- Brand Name -->
      <div class="form-section">
        <label class="section-label">
          <span>品牌名称</span>
          <span class="opt">· 选填</span>
        </label>
        <input v-model="form.brand_name" class="field-input"
          placeholder="例如：木语、原木家、品质居" maxlength="50" />
      </div>

      <!-- Query -->
      <div class="form-section">
        <label class="section-label">
          <span>您的需求</span>
          <span class="required">*</span>
        </label>
        <textarea v-model="form.query" class="field-input field-textarea"
          :rows="4" maxlength="1000"
          placeholder="例如：我想创建一个定位中高端消费者的北欧简约风格家具品牌，目标市场是25-40岁的城市精英群体..."></textarea>
        <div class="counter">{{ form.query.length }} / 1000</div>
      </div>

      <!-- Agent Selection -->
      <div class="form-section">
        <label class="section-label">
          <span>选择 AI 专家</span>
          <span class="required">*</span>
        </label>
        <p class="section-hint">可选单个或多个专家协作，多专家将按顺序分工合作</p>
        <div class="agent-grid">
          <div
            v-for="agent in agents" :key="agent.type"
            class="agent-card"
            :class="{ selected: form.agents_selected.includes(agent.type) }"
            @click="toggleAgent(agent.type)"
          >
            <div class="agent-icon">{{ agent.icon }}</div>
            <div class="agent-body">
              <div class="agent-name">{{ agent.name }}</div>
              <div class="agent-desc">{{ agent.desc }}</div>
            </div>
            <div class="check-box">
              <svg v-if="form.agents_selected.includes(agent.type)" width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M13 4.5L6 11.5L3 8.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
        </div>

        <div class="quick-row">
          <button class="quick-btn" @click="selectAll">全选（四专家协作）</button>
          <button class="quick-btn" @click="form.agents_selected = []">清空</button>
        </div>
      </div>

      <!-- Pipeline hint -->
      <transition name="fade">
        <div v-if="form.agents_selected.length > 1" class="pipeline-hint">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5"/>
            <path d="M8 5v4l2 1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span>多专家协作：{{ selectedAgentNames.join(' → ') }}</span>
        </div>
      </transition>

      <button
        class="submit-btn"
        :disabled="!form.query || !form.agents_selected.length || submitting"
        @click="submitTask"
      >
        <span v-if="submitting" class="spinner"></span>
        <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none">
          <path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>{{ submitting ? '启动中…' : '启动 AI 分析' }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { tasksAPI, agentsAPI } from '../api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const submitting = ref(false)

const form = ref({ query: '', brand_name: '', agents_selected: ['strategy', 'brand', 'operations'] })

const agents = ref([
  { type: 'strategy',      name: '战略规划专家', icon: '🎯', desc: '市场分析·竞争定位·品牌战略规划' },
  { type: 'brand',         name: '品牌设计专家', icon: '🎨', desc: 'Logo概念·色彩体系·视觉物料规范' },
  { type: 'logo_design',   name: 'Logo 设计专家', icon: '✨', desc: 'AI智能生成Logo，输出 PNG/PSD/SVG' },
  { type: 'poster_design', name: '海报设计专家', icon: '🖼️', desc: '节气/节日商业海报，9:16 竖版 2160×3840' },
  { type: 'operations',    name: '运营实施专家', icon: '🚀', desc: '渠道策略·营销计划·执行路径' },
])

const agentNames = {
  strategy: '战略规划', brand: '品牌设计',
  logo_design: 'Logo设计', poster_design: '海报设计', operations: '运营实施',
}

const selectedAgentNames = computed(() =>
  ['strategy', 'brand', 'logo_design', 'poster_design', 'operations']
    .filter(a => form.value.agents_selected.includes(a))
    .map(a => agentNames[a])
)

function toggleAgent(type) {
  const i = form.value.agents_selected.indexOf(type)
  if (i > -1) form.value.agents_selected.splice(i, 1)
  else form.value.agents_selected.push(type)
}
function selectAll() {
  form.value.agents_selected = agents.value.map(a => a.type)
}

async function submitTask() {
  if (!form.value.query.trim()) { ElMessage.warning('请输入需求'); return }
  if (!form.value.agents_selected.length) { ElMessage.warning('请选择至少一个专家'); return }
  submitting.value = true
  try {
    const task = await tasksAPI.create({
      query: form.value.query,
      brand_name: form.value.brand_name,
      agents_selected: form.value.agents_selected,
    })
    router.push(`/tasks/${task.id}`)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const list = await agentsAPI.list()
    if (list?.length) {
      const descMap = {
        strategy: '市场分析·竞争定位·品牌战略规划',
        brand: 'Logo概念·色彩体系·视觉物料规范',
        logo_design: 'AI智能生成Logo，输出 PNG/PSD/SVG',
        operations: '渠道策略·营销计划·执行路径',
      }
      agents.value = list.map(a => ({ ...a, desc: descMap[a.type] || '' }))
    }
  } catch {}
})
</script>

<style scoped>
.new-task-page {
  max-width: 760px;
  margin: 0 auto;
}

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
.back-btn:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--ybc-text);
}

/* ── Hero ─────────────────────────────────────────────────── */
.page-hero {
  text-align: center;
  margin-bottom: 28px;
  padding: 20px 0;
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 12px;
  border-radius: 100px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  color: var(--ybc-accent-light);
  font-size: 11px; font-weight: 500;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}
.hero-badge .dot {
  width: 5px; height: 5px;
  border-radius: 50%;
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

/* ── Form card ────────────────────────────────────────────── */
.form-card {
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 20px;
  padding: 28px 32px;
  box-shadow: var(--ybc-shadow-md);
}

.form-section { margin-bottom: 24px; }

.section-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600;
  color: var(--ybc-text);
  margin-bottom: 10px;
}
.section-label .opt { color: var(--ybc-text-faint); font-weight: 400; font-size: 11px; }
.section-label .required { color: var(--ybc-danger); }

.section-hint {
  font-size: 12px;
  color: var(--ybc-text-muted);
  margin: -6px 0 12px;
}

.field-input {
  width: 100%;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ybc-border);
  border-radius: 10px;
  color: var(--ybc-text-strong);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s, background 0.15s;
  font-family: inherit;
}
.field-input:focus {
  border-color: var(--ybc-accent);
  background: rgba(99, 102, 241, 0.04);
}
.field-input::placeholder { color: var(--ybc-text-faint); }
.field-textarea {
  resize: vertical;
  min-height: 100px;
  line-height: 1.6;
}
.counter {
  text-align: right;
  font-size: 11px;
  color: var(--ybc-text-faint);
  margin-top: 6px;
}

/* ── Agent cards ──────────────────────────────────────────── */
.agent-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.agent-card {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--ybc-border);
  border-radius: 12px;
  cursor: pointer;
  transition: 0.15s;
  user-select: none;
}
.agent-card:hover {
  border-color: rgba(99, 102, 241, 0.3);
  background: rgba(99, 102, 241, 0.04);
}
.agent-card.selected {
  border-color: var(--ybc-accent);
  background: rgba(99, 102, 241, 0.08);
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.2);
}
.agent-icon { font-size: 24px; flex-shrink: 0; }
.agent-body { flex: 1; min-width: 0; }
.agent-name {
  font-size: 13px; font-weight: 600;
  color: var(--ybc-text-strong);
  margin-bottom: 2px;
}
.agent-desc {
  font-size: 11px;
  color: var(--ybc-text-muted);
}
.check-box {
  width: 20px; height: 20px;
  border-radius: 6px;
  border: 1.5px solid var(--ybc-border);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  color: #fff;
  transition: 0.15s;
}
.agent-card.selected .check-box {
  background: var(--ybc-accent);
  border-color: var(--ybc-accent);
}

.quick-row {
  display: flex; gap: 8px;
  margin-top: 12px;
}
.quick-btn {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--ybc-border);
  border-radius: 8px;
  color: var(--ybc-text-dim);
  font-size: 12px;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
}
.quick-btn:hover {
  background: rgba(99, 102, 241, 0.1);
  color: var(--ybc-text);
  border-color: var(--ybc-accent-light);
}

.pipeline-hint {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px;
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 10px;
  color: var(--ybc-accent-light);
  font-size: 12px;
  margin-bottom: 18px;
}

/* ── Submit ─────────────────────────────────────────────── */
.submit-btn {
  width: 100%;
  padding: 14px;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  background: var(--ybc-gradient-primary);
  border: none;
  border-radius: 12px;
  color: #fff;
  font-size: 15px; font-weight: 600;
  cursor: pointer;
  transition: 0.2s;
  font-family: inherit;
}
.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 32px rgba(99, 102, 241, 0.4);
}
.submit-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 640px) {
  .form-card { padding: 20px; }
  .agent-grid { grid-template-columns: 1fr; }
  .page-hero h1 { font-size: 22px; }
}
</style>
