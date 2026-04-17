<template>
  <div class="admin-membership" v-loading="loading">
    <h2 class="page-title">套餐管理</h2>

    <el-tabs v-model="activeTab">
      <!-- Plans -->
      <el-tab-pane label="套餐列表" name="plans">
        <div class="toolbar">
          <el-button type="primary" :icon="Plus" @click="openCreate">新建套餐</el-button>
          <el-button :icon="Refresh" @click="loadPlans">刷新</el-button>
        </div>
        <el-table :data="plans" border>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column label="等级" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="tierType(row.tier)" size="small" effect="dark">{{ row.tier.toUpperCase() }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column label="时长" width="80" align="center">
            <template #default="{ row }">{{ row.duration_days }} 天</template>
          </el-table-column>
          <el-table-column label="价格" width="100" align="right">
            <template #default="{ row }">
              <b>¥{{ (row.price_cents / 100).toFixed(0) }}</b>
            </template>
          </el-table-column>
          <el-table-column label="开通赠送" width="100" align="center">
            <template #default="{ row }">{{ row.activation_credits }} 积分</template>
          </el-table-column>
          <el-table-column label="月度积分" width="100" align="center">
            <template #default="{ row }">{{ row.monthly_credits }}</template>
          </el-table-column>
          <el-table-column label="权益" min-width="200">
            <template #default="{ row }">
              <el-tag v-for="f in row.features" :key="f" size="small" style="margin-right:4px">{{ f }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '上架' : '下架' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" align="center">
            <template #default="{ row }">
              <el-button size="small" link @click="openEdit(row)">编辑</el-button>
              <el-button size="small" link type="danger" @click="deletePlan(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Tier features config -->
      <el-tab-pane label="等级权益配置" name="features">
        <div class="section-card">
          <h3>等级 → 权益映射</h3>
          <p class="section-desc">控制每个等级可访问的高级功能。修改后立即生效。</p>
          <div v-for="tier in ['vip', 'vvip', 'vvvip']" :key="tier" class="tier-row">
            <div class="tier-row-header">
              <el-tag :type="tierType(tier)" effect="dark">{{ tier.toUpperCase() }}</el-tag>
              <span class="tier-row-label">{{ membershipCfg.tier_labels?.[tier] || tier }}</span>
            </div>
            <el-checkbox-group v-model="membershipCfg.tier_features[tier]">
              <el-checkbox v-for="feat in Object.keys(membershipCfg.feature_labels || {})" :key="feat" :label="feat">
                {{ membershipCfg.feature_labels[feat] }}
              </el-checkbox>
            </el-checkbox-group>
          </div>
          <div class="save-bar">
            <el-button type="primary" :loading="savingCfg" @click="saveMembershipConfig">保存权益配置</el-button>
          </div>
        </div>

        <div class="section-card">
          <h3>专属服务联系方式</h3>
          <p class="section-desc">显示给对应等级的会员，留空则不显示</p>
          <div v-for="tier in ['vip', 'vvip', 'vvvip']" :key="tier" class="support-block">
            <h4>{{ tier.toUpperCase() }} 专属服务</h4>
            <div class="support-fields">
              <el-input v-model="membershipCfg.support_info[tier].name" placeholder="服务人员称谓" />
              <el-input v-model="membershipCfg.support_info[tier].wechat" placeholder="微信号" />
              <el-input v-model="membershipCfg.support_info[tier].phone" placeholder="电话" />
              <el-input v-model="membershipCfg.support_info[tier].email" placeholder="邮箱" />
            </div>
          </div>
          <div class="save-bar">
            <el-button type="primary" :loading="savingCfg" @click="saveMembershipConfig">保存服务信息</el-button>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- Plan edit dialog -->
    <el-dialog v-model="editDialogVisible" :title="editForm.id ? '编辑套餐' : '新建套餐'" width="500px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="等级">
          <el-select v-model="editForm.tier" style="width:100%">
            <el-option label="VIP" value="vip" />
            <el-option label="VVIP" value="vvip" />
            <el-option label="VVVIP" value="vvvip" />
          </el-select>
        </el-form-item>
        <el-form-item label="套餐名称">
          <el-input v-model="editForm.name" placeholder="如 VIP 月度" />
        </el-form-item>
        <el-form-item label="时长（天）">
          <el-input-number v-model="editForm.duration_days" :min="1" :max="3650" style="width:100%" />
        </el-form-item>
        <el-form-item label="价格（元）">
          <el-input-number v-model="editPriceYuan" :min="0" :step="10" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="开通赠送积分">
          <el-input-number v-model="editForm.activation_credits" :min="0" :step="500" style="width:100%" />
        </el-form-item>
        <el-form-item label="月度赠送积分">
          <el-input-number v-model="editForm.monthly_credits" :min="0" :step="1000" style="width:100%" />
        </el-form-item>
        <el-form-item label="权益">
          <el-checkbox-group v-model="editForm.features">
            <el-checkbox v-for="feat in Object.keys(membershipCfg.feature_labels || {})" :key="feat" :label="feat">
              {{ membershipCfg.feature_labels[feat] }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="editForm.sort_order" :min="0" :max="999" style="width:100%" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="上架">
          <el-switch v-model="editForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingPlan" @click="savePlan">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminAPI } from '../../api'

const activeTab = ref('plans')
const loading = ref(false)

const plans = ref([])
const membershipCfg = reactive({
  tier_labels: {},
  tier_features: { vip: [], vvip: [], vvvip: [] },
  feature_labels: {},
  support_info: {
    vip:   { name: '', wechat: '', phone: '', email: '' },
    vvip:  { name: '', wechat: '', phone: '', email: '' },
    vvvip: { name: '', wechat: '', phone: '', email: '' },
  },
})

const editDialogVisible = ref(false)
const savingPlan = ref(false)
const savingCfg = ref(false)
const editForm = reactive({
  id: null, tier: 'vip', name: '', duration_days: 30, price_cents: 9900,
  activation_credits: 0, monthly_credits: 0, features: [],
  description: '', is_active: true, sort_order: 0,
})

const editPriceYuan = computed({
  get: () => editForm.price_cents / 100,
  set: (v) => { editForm.price_cents = Math.round((v || 0) * 100) },
})

function tierType(t) {
  return { vip: 'primary', vvip: 'warning', vvvip: 'danger' }[t] || ''
}

async function loadPlans() {
  loading.value = true
  try { plans.value = await adminAPI.getPlans() }
  finally { loading.value = false }
}

async function loadMembershipCfg() {
  try {
    const cfg = await adminAPI.getMembershipConfig()
    // Ensure all tiers have defaults. NOTE: leading semicolon prevents ASI
    // from treating the array literal below as a property access on `cfg`.
    cfg.tier_features = cfg.tier_features || {}
    cfg.support_info = cfg.support_info || {}
    for (const t of ['vip', 'vvip', 'vvvip']) {
      if (!Array.isArray(cfg.tier_features[t])) cfg.tier_features[t] = []
      if (!cfg.support_info[t]) {
        cfg.support_info[t] = { name: '', wechat: '', phone: '', email: '' }
      }
    }
    Object.assign(membershipCfg, cfg)
  } catch (e) {
    ElMessage.error('加载配置失败: ' + e.message)
  }
}

async function saveMembershipConfig() {
  savingCfg.value = true
  try {
    await adminAPI.saveMembershipConfig({
      tier_features: membershipCfg.tier_features,
      support_info: membershipCfg.support_info,
    })
    ElMessage.success('权益配置已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    savingCfg.value = false
  }
}

function openCreate() {
  Object.assign(editForm, {
    id: null, tier: 'vip', name: '', duration_days: 30, price_cents: 9900,
    activation_credits: 0, monthly_credits: 0, features: [],
    description: '', is_active: true, sort_order: 0,
  })
  editDialogVisible.value = true
}

function openEdit(plan) {
  Object.assign(editForm, plan, { features: [...(plan.features || [])] })
  editDialogVisible.value = true
}

async function savePlan() {
  if (!editForm.name) { ElMessage.warning('请填写套餐名称'); return }
  savingPlan.value = true
  try {
    const payload = {
      tier: editForm.tier,
      name: editForm.name,
      duration_days: editForm.duration_days,
      price_cents: editForm.price_cents,
      activation_credits: editForm.activation_credits,
      monthly_credits: editForm.monthly_credits,
      features: editForm.features,
      description: editForm.description,
      is_active: editForm.is_active,
      sort_order: editForm.sort_order,
    }
    if (editForm.id) {
      await adminAPI.updatePlan(editForm.id, payload)
    } else {
      await adminAPI.createPlan(payload)
    }
    ElMessage.success('已保存')
    editDialogVisible.value = false
    await loadPlans()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    savingPlan.value = false
  }
}

async function deletePlan(plan) {
  try {
    await ElMessageBox.confirm(`确认删除套餐「${plan.name}」？存在历史订单时仅下架。`, '提示', { type: 'warning' })
    await adminAPI.deletePlan(plan.id)
    ElMessage.success('已处理')
    await loadPlans()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message)
  }
}

onMounted(() => {
  loadPlans()
  loadMembershipCfg()
})
</script>

<style scoped>
.admin-membership { max-width: 1100px; }
.page-title { font-size: 20px; color: #1a1a2e; margin: 0 0 16px; }
.toolbar { margin-bottom: 12px; display: flex; gap: 8px; }

.section-card {
  background: #fff; border-radius: 12px;
  padding: 20px 24px; margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.section-card h3 { margin: 0 0 6px; font-size: 15px; color: #1a1a2e; }
.section-desc { margin: 0 0 16px; font-size: 13px; color: #888; }

.tier-row { padding: 14px 0; border-top: 1px solid #f0f0f0; }
.tier-row:first-of-type { border-top: 0; padding-top: 0; }
.tier-row-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.tier-row-label { font-size: 14px; font-weight: 600; color: #333; }

.support-block { margin-top: 20px; }
.support-block h4 { margin: 0 0 10px; font-size: 14px; color: #555; }
.support-fields { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }

.save-bar { margin-top: 20px; padding-top: 16px; border-top: 1px solid #f0f0f0; }

@media (max-width: 640px) {
  .support-fields { grid-template-columns: 1fr; }
}
</style>
