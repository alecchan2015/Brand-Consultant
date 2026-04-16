<template>
  <div class="token-usage-page">
    <h2 class="page-title">Token 用量统计</h2>

    <!-- Summary cards -->
    <el-row :gutter="16" class="summary-row">
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">总调用次数</div>
          <div class="summary-value">{{ summary.totals.call_count.toLocaleString() }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">总 Token 消耗</div>
          <div class="summary-value">{{ summary.totals.total_tokens.toLocaleString() }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">Prompt Tokens</div>
          <div class="summary-value sub">{{ summary.totals.prompt_tokens.toLocaleString() }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">Completion Tokens</div>
          <div class="summary-value sub">{{ summary.totals.completion_tokens.toLocaleString() }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- By-model breakdown -->
    <el-card shadow="never" class="section-card" v-if="summary.by_model.length">
      <template #header><span class="section-title">按模型统计</span></template>
      <el-table :data="summary.by_model" size="small" border>
        <el-table-column prop="provider" label="供应商" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="providerTagType[row.provider] || 'info'">{{ row.provider }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" min-width="180" />
        <el-table-column label="调用次数" width="100" align="right">
          <template #default="{ row }">{{ row.call_count.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="Prompt" width="120" align="right">
          <template #default="{ row }">{{ row.prompt_tokens.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="Completion" width="120" align="right">
          <template #default="{ row }">{{ row.completion_tokens.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="Total" width="120" align="right">
          <template #default="{ row }">
            <span class="bold-num">{{ row.total_tokens.toLocaleString() }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Daily trend -->
    <el-card shadow="never" class="section-card" v-if="summary.by_date.length">
      <template #header><span class="section-title">每日用量趋势（近30天）</span></template>
      <div class="chart-area">
        <div class="bar-chart">
          <div
            v-for="d in reversedDates"
            :key="d.date"
            class="bar-item"
            :title="`${d.date}: ${d.total_tokens.toLocaleString()} tokens / ${d.call_count} 次`"
          >
            <div class="bar-fill" :style="{ height: barHeight(d.total_tokens) + '%' }"></div>
            <div class="bar-label">{{ d.date.slice(5) }}</div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Filters -->
    <el-card shadow="never" class="section-card">
      <template #header><span class="section-title">调用明细</span></template>
      <el-form :inline="true" class="filter-form" @submit.prevent="fetchRecords">
        <el-form-item label="用户">
          <el-select v-model="filters.user_id" clearable placeholder="全部用户" style="width: 140px">
            <el-option
              v-for="u in filterOptions.users"
              :key="u.id"
              :label="u.username"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="filters.model_name" clearable placeholder="全部模型" style="width: 200px">
            <el-option v-for="m in filterOptions.models" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="供应商">
          <el-select v-model="filters.provider" clearable placeholder="全部" style="width: 130px">
            <el-option v-for="p in filterOptions.providers" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="Agent">
          <el-select v-model="filters.agent_type" clearable placeholder="全部" style="width: 120px">
            <el-option label="战略" value="strategy" />
            <el-option label="品牌" value="brand" />
            <el-option label="运营" value="operations" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="~"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchRecords">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- Records table -->
      <el-table :data="records" v-loading="loading" border size="small" style="margin-top: 12px">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户" width="100" />
        <el-table-column label="Agent" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.agent_type" size="small" :type="agentTagType[row.agent_type] || 'info'">
              {{ agentNames[row.agent_type] || row.agent_type }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="供应商" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="providerTagType[row.provider] || 'info'">{{ row.provider }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" min-width="160" show-overflow-tooltip />
        <el-table-column label="Prompt" width="100" align="right">
          <template #default="{ row }">{{ row.prompt_tokens.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="Completion" width="100" align="right">
          <template #default="{ row }">{{ row.completion_tokens.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="Total" width="100" align="right">
          <template #default="{ row }">
            <span class="bold-num">{{ row.total_tokens.toLocaleString() }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="task_id" label="任务ID" width="80" align="center">
          <template #default="{ row }">{{ row.task_id || '-' }}</template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchRecords"
          @current-change="fetchRecords"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { adminAPI } from '../../api'

const loading = ref(false)
const records = ref([])
const dateRange = ref(null)

const filters = reactive({
  user_id: null,
  model_name: null,
  provider: null,
  agent_type: null,
})

const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const summary = reactive({
  totals: { call_count: 0, total_tokens: 0, prompt_tokens: 0, completion_tokens: 0 },
  by_model: [],
  by_date: [],
})

const filterOptions = reactive({ models: [], providers: [], users: [] })

const agentNames = { strategy: '战略', brand: '品牌', operations: '运营' }
const agentTagType = { strategy: 'primary', brand: 'success', operations: 'warning' }
const providerTagType = { openai: '', anthropic: 'warning', volcano: 'danger' }

const reversedDates = computed(() => [...summary.by_date].reverse())
const maxDailyTokens = computed(() => Math.max(...summary.by_date.map(d => d.total_tokens), 1))

function barHeight(tokens) {
  return Math.max(4, (tokens / maxDailyTokens.value) * 100)
}

function formatTime(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

function buildParams() {
  const p = { page: pagination.page, page_size: pagination.pageSize }
  if (filters.user_id) p.user_id = filters.user_id
  if (filters.model_name) p.model_name = filters.model_name
  if (filters.provider) p.provider = filters.provider
  if (filters.agent_type) p.agent_type = filters.agent_type
  if (dateRange.value && dateRange.value[0]) p.date_from = dateRange.value[0]
  if (dateRange.value && dateRange.value[1]) p.date_to = dateRange.value[1]
  return p
}

async function fetchRecords() {
  loading.value = true
  try {
    const res = await adminAPI.getTokenUsage(buildParams())
    records.value = res.items
    pagination.total = res.total
  } finally {
    loading.value = false
  }
}

async function fetchSummary() {
  const p = {}
  if (filters.user_id) p.user_id = filters.user_id
  if (dateRange.value && dateRange.value[0]) p.date_from = dateRange.value[0]
  if (dateRange.value && dateRange.value[1]) p.date_to = dateRange.value[1]
  try {
    const res = await adminAPI.getTokenUsageSummary(p)
    Object.assign(summary, res)
  } catch (e) {
    console.error('summary fetch error', e)
  }
}

async function fetchFilters() {
  try {
    const res = await adminAPI.getTokenUsageFilters()
    Object.assign(filterOptions, res)
  } catch (e) {
    console.error('filters fetch error', e)
  }
}

function resetFilters() {
  filters.user_id = null
  filters.model_name = null
  filters.provider = null
  filters.agent_type = null
  dateRange.value = null
  pagination.page = 1
  fetchRecords()
  fetchSummary()
}

onMounted(async () => {
  await Promise.all([fetchRecords(), fetchSummary(), fetchFilters()])
})
</script>

<style scoped>
.page-title { font-size: 20px; color: #1a1a2e; margin-bottom: 16px; }
.summary-row { margin-bottom: 16px; }
.summary-card { text-align: center; }
.summary-label { font-size: 13px; color: #909399; margin-bottom: 8px; }
.summary-value { font-size: 28px; font-weight: 700; color: #1a1a2e; }
.summary-value.sub { font-size: 22px; color: #606266; }
.section-card { margin-bottom: 16px; }
.section-title { font-size: 15px; font-weight: 600; color: #303133; }
.bold-num { font-weight: 600; color: #1a1a2e; }
.filter-form { display: flex; flex-wrap: wrap; gap: 4px 0; }
.pagination-wrap { margin-top: 16px; display: flex; justify-content: flex-end; }

/* Simple CSS bar chart */
.chart-area { padding: 8px 0; }
.bar-chart {
  display: flex; align-items: flex-end; gap: 4px;
  height: 140px; border-bottom: 1px solid #ebeef5; padding-bottom: 20px; position: relative;
}
.bar-item {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  height: 100%; justify-content: flex-end; position: relative; cursor: pointer;
}
.bar-fill {
  width: 70%; max-width: 28px; background: linear-gradient(180deg, #409eff 0%, #79bbff 100%);
  border-radius: 3px 3px 0 0; transition: height 0.3s ease; min-height: 3px;
}
.bar-item:hover .bar-fill { background: linear-gradient(180deg, #337ecc 0%, #409eff 100%); }
.bar-label {
  font-size: 10px; color: #909399; margin-top: 4px; position: absolute; bottom: -18px;
  white-space: nowrap;
}
</style>
