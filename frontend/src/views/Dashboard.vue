<template>
  <div class="dashboard">
    <!-- Header hero -->
    <div class="hero">
      <div class="hero-content">
        <div class="hero-text">
          <h1>我的工作台</h1>
          <p>AI 品牌战略任务 · 实时生成 · 全流程协作</p>
        </div>
        <button class="btn-primary" @click="$router.push('/tasks/new')">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <span>新建任务</span>
        </button>
      </div>

      <!-- Quick stats -->
      <div class="stat-row">
        <div class="stat-chip">
          <span class="stat-num">{{ tasks.length }}</span>
          <span class="stat-label">总任务</span>
        </div>
        <div class="stat-chip">
          <span class="stat-num">{{ completedCount }}</span>
          <span class="stat-label">已完成</span>
        </div>
        <div class="stat-chip">
          <span class="stat-num">{{ processingCount }}</span>
          <span class="stat-label">进行中</span>
        </div>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="skeleton-grid">
      <div v-for="i in 3" :key="i" class="task-card skeleton">
        <div class="sk-line" style="width:40%"></div>
        <div class="sk-line" style="width:90%"></div>
        <div class="sk-line" style="width:75%"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!tasks.length" class="empty-state">
      <div class="empty-visual">
        <div class="empty-glow"></div>
        <span class="empty-emoji">🎯</span>
      </div>
      <h3>还没有任务</h3>
      <p>点击「新建任务」，让 AI 专家团队为您打造品牌战略</p>
      <button class="btn-primary" @click="$router.push('/tasks/new')">立即开始</button>
    </div>

    <!-- Task grid -->
    <div v-else class="task-grid">
      <div
        v-for="task in tasks" :key="task.id"
        class="task-card"
        @click="$router.push(`/tasks/${task.id}`)"
      >
        <div class="task-head">
          <div class="agents">
            <span v-for="a in task.agents_selected" :key="a"
              class="agent-chip" :class="`a-${a}`">
              <span class="agent-icon">{{ agentIcons[a] }}</span>
              <span>{{ agentNames[a] }}</span>
            </span>
          </div>
          <span class="status-dot" :class="`status-${task.status}`">
            <span class="dot"></span>
            {{ statusLabel[task.status] }}
          </span>
        </div>

        <div class="task-query">{{ task.query }}</div>

        <div class="task-foot">
          <div class="task-meta">
            <span v-if="task.brand_name" class="brand-badge">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 1h6l-1.5 4 1.5 4H2V1z" fill="currentColor"/>
              </svg>
              {{ task.brand_name }}
            </span>
            <span v-if="task.results?.length" class="files-badge">
              📄 {{ task.results.length }} 个文件
            </span>
          </div>
          <span class="task-time">{{ formatTime(task.created_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { tasksAPI } from '../api'

const tasks = ref([])
const loading = ref(false)

const agentNames = {
  strategy: '战略规划', brand: '品牌设计',
  operations: '运营实施', logo_design: 'Logo设计', poster_design: '海报设计',
}
const agentIcons = {
  strategy: '🎯', brand: '🎨', logo_design: '✨', poster_design: '🖼️', operations: '🚀',
}
const statusLabel = { pending: '待处理', processing: '进行中', completed: '已完成', failed: '失败' }

const completedCount = computed(() => tasks.value.filter(t => t.status === 'completed').length)
const processingCount = computed(() => tasks.value.filter(t => ['pending', 'processing'].includes(t.status)).length)

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

onMounted(async () => {
  loading.value = true
  try { tasks.value = await tasksAPI.list({ limit: 50 }) }
  finally { loading.value = false }
})
</script>

<style scoped>
.dashboard { color: var(--ybc-text); }

/* ── Hero ─────────────────────────────────────────────────────── */
.hero {
  position: relative;
  padding: 28px 32px;
  border: 1px solid var(--ybc-border);
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(168, 85, 247, 0.03));
  overflow: hidden;
  margin-bottom: 28px;
}
.hero::before {
  content: '';
  position: absolute; inset: 0;
  background: radial-gradient(ellipse 60% 80% at 80% 20%, rgba(99, 102, 241, 0.15), transparent);
  pointer-events: none;
}
.hero-content {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 20px;
  position: relative;
}
.hero-text h1 {
  font-size: 26px; font-weight: 800;
  color: var(--ybc-text-strong);
  letter-spacing: -0.5px;
  margin-bottom: 6px;
}
.hero-text p {
  font-size: 14px;
  color: var(--ybc-text-dim);
}

.btn-primary {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px;
  background: var(--ybc-gradient-primary);
  border: none;
  border-radius: 10px;
  color: #fff;
  font-size: 14px; font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
}

.stat-row {
  display: flex; gap: 10px;
  margin-top: 18px;
  position: relative;
}
.stat-chip {
  display: flex; align-items: baseline; gap: 6px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--ybc-border);
  border-radius: 100px;
}
.stat-num {
  font-size: 18px; font-weight: 700;
  color: var(--ybc-text-strong);
}
.stat-label {
  font-size: 12px;
  color: var(--ybc-text-dim);
}

/* ── Skeleton ────────────────────────────────────────────────── */
.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}
.task-card.skeleton {
  padding: 18px;
  display: flex; flex-direction: column; gap: 12px;
  pointer-events: none;
}
.sk-line {
  height: 12px;
  background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
  background-size: 200% 100%;
  animation: sk-shimmer 1.5s infinite;
  border-radius: 6px;
}
@keyframes sk-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Empty ────────────────────────────────────────────────────── */
.empty-state {
  text-align: center;
  padding: 80px 20px;
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 20px;
}
.empty-visual {
  position: relative;
  display: inline-flex;
  margin-bottom: 20px;
}
.empty-emoji { font-size: 56px; position: relative; z-index: 2; }
.empty-glow {
  position: absolute; inset: -20px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.3), transparent);
  filter: blur(24px);
}
.empty-state h3 {
  font-size: 18px; font-weight: 700;
  color: var(--ybc-text-strong);
  margin-bottom: 8px;
}
.empty-state p {
  color: var(--ybc-text-dim);
  margin-bottom: 24px;
}

/* ── Task grid ────────────────────────────────────────────────── */
.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}
.task-card {
  position: relative;
  padding: 18px 20px;
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
  overflow: hidden;
}
.task-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at top right, rgba(99, 102, 241, 0.08), transparent 60%);
  opacity: 0;
  transition: opacity 0.3s;
  pointer-events: none;
}
.task-card:hover {
  transform: translateY(-3px);
  border-color: rgba(99, 102, 241, 0.3);
  box-shadow: var(--ybc-shadow-md);
}
.task-card:hover::before { opacity: 1; }

.task-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.agents { display: flex; gap: 6px; flex-wrap: wrap; }
.agent-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--ybc-border);
  border-radius: 100px;
  font-size: 11px;
  color: var(--ybc-text-dim);
}
.agent-icon { font-size: 12px; }
.agent-chip.a-strategy   { border-color: rgba(59, 130, 246, 0.3); color: #93c5fd; background: rgba(59, 130, 246, 0.08); }
.agent-chip.a-brand      { border-color: rgba(168, 85, 247, 0.3); color: #d8b4fe; background: rgba(168, 85, 247, 0.08); }
.agent-chip.a-logo_design{ border-color: rgba(236, 72, 153, 0.3); color: #f9a8d4; background: rgba(236, 72, 153, 0.08); }
.agent-chip.a-poster_design { border-color: rgba(14, 165, 233, 0.35); color: #7dd3fc; background: rgba(14, 165, 233, 0.08); }
.agent-chip.a-operations { border-color: rgba(245, 158, 11, 0.3); color: #fcd34d; background: rgba(245, 158, 11, 0.08); }

.status-dot {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px;
  border-radius: 100px;
  font-size: 11px;
  white-space: nowrap;
}
.status-dot .dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.status-dot.status-pending    { background: rgba(255, 255, 255, 0.06); color: var(--ybc-text-muted); }
.status-dot.status-processing { background: rgba(245, 158, 11, 0.12); color: #fcd34d; }
.status-dot.status-processing .dot { animation: ybc-pulse-dot 1.2s infinite; }
.status-dot.status-completed  { background: rgba(34, 197, 94, 0.12); color: #86efac; }
.status-dot.status-failed     { background: rgba(239, 68, 68, 0.12); color: #fca5a5; }

.task-query {
  font-size: 14px;
  color: var(--ybc-text);
  line-height: 1.6;
  margin-bottom: 14px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 44px;
}

.task-foot {
  display: flex; justify-content: space-between; align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--ybc-border);
  font-size: 12px;
  gap: 8px;
}
.task-meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.brand-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  color: var(--ybc-accent-light);
  border-radius: 4px;
  font-weight: 600;
}
.files-badge {
  color: var(--ybc-text-muted);
}
.task-time {
  color: var(--ybc-text-faint);
  white-space: nowrap;
}

@media (max-width: 640px) {
  .hero { padding: 20px; }
  .hero-content { flex-direction: column; align-items: stretch; }
  .hero-text h1 { font-size: 22px; }
  .stat-row { overflow-x: auto; }
  .task-grid { grid-template-columns: 1fr; gap: 12px; }
}
</style>
