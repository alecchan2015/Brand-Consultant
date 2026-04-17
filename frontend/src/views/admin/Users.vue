<template>
  <div>
    <h2 class="page-title">用户管理</h2>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane :label="`所有用户 (${users.length})`" name="all" />
      <el-tab-pane name="pending">
        <template #label>
          待审核
          <el-badge v-if="pendingUsers.length" :value="pendingUsers.length" class="pending-badge" />
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- All Users Table -->
    <el-table v-if="activeTab === 'all'" :data="users" v-loading="loading" border>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column label="联系方式" min-width="200">
        <template #default="{ row }">
          <div class="contact-cell">
            <div v-if="row.email" class="contact-row">📧 {{ row.email }}</div>
            <div v-if="row.phone" class="contact-row">📱 {{ row.phone }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="注册方式" width="110" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="providerTagType(row.auth_provider)">
            {{ providerLabel(row.auth_provider) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="角色" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'" size="small">{{ row.role === 'admin' ? '管理员' : '用户' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="积分" width="100" align="center">
        <template #default="{ row }">
          <span class="credits-val">{{ row.credits }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.pending_approval" type="warning" size="small">待审核</el-tag>
          <el-tag v-else :type="row.is_active ? 'success' : 'danger'" size="small">{{ row.is_active ? '正常' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" width="120">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleDateString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240" align="center">
        <template #default="{ row }">
          <el-button size="small" link @click="openProfileDialog(row)">详情</el-button>
          <el-button size="small" link @click="openCreditsDialog(row)">积分</el-button>
          <el-button size="small" link :type="row.is_active ? 'warning' : 'success'"
            @click="toggleStatus(row)">{{ row.is_active ? '禁用' : '启用' }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Pending Users Table -->
    <el-table v-if="activeTab === 'pending'" :data="pendingUsers" v-loading="loading" border>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column label="联系方式" min-width="180">
        <template #default="{ row }">
          <div v-if="row.email">📧 {{ row.email }}</div>
          <div v-if="row.phone">📱 {{ row.phone }}</div>
        </template>
      </el-table-column>
      <el-table-column label="注册方式" width="110" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="providerTagType(row.auth_provider)">
            {{ providerLabel(row.auth_provider) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="公司" min-width="160">
        <template #default="{ row }">
          <div v-if="row.company_name">{{ row.company_name }}</div>
          <div v-if="row.position" class="hint-text">{{ row.position }}</div>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" width="150">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" align="center">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="approve(row)">批准</el-button>
          <el-button size="small" type="danger" plain @click="reject(row)">拒绝</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Credits Dialog -->
    <el-dialog v-model="creditsVisible" title="调整用户积分" width="400px">
      <div class="credits-info">
        <span>当前积分：<strong>{{ editUser?.credits }}</strong></span>
      </div>
      <el-form :model="creditsForm" label-width="80px" style="margin-top:16px">
        <el-form-item label="新积分值">
          <el-input-number v-model="creditsForm.credits" :min="0" :max="999999" style="width:100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="creditsForm.reason" placeholder="调整原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="creditsVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCredits">确认</el-button>
      </template>
    </el-dialog>

    <!-- Profile Dialog (view + edit enterprise info) -->
    <el-dialog v-model="profileVisible" title="用户详情" width="520px">
      <div v-if="editUser" class="profile-form">
        <div class="profile-meta">
          <div><span class="meta-label">用户 ID</span> #{{ editUser.id }}</div>
          <div><span class="meta-label">用户名</span> {{ editUser.username }}</div>
          <div><span class="meta-label">注册方式</span> {{ providerLabel(editUser.auth_provider) }}</div>
          <div><span class="meta-label">注册时间</span> {{ new Date(editUser.created_at).toLocaleString('zh-CN') }}</div>
        </div>
        <el-divider />
        <el-form :model="profileForm" label-width="90px">
          <el-form-item label="邮箱">
            <el-input v-model="editUser.email" disabled />
          </el-form-item>
          <el-form-item label="手机号">
            <el-input v-model="profileForm.phone" placeholder="(未绑定)" />
          </el-form-item>
          <el-form-item label="公司名称">
            <el-input v-model="profileForm.company_name" />
          </el-form-item>
          <el-form-item label="所在行业">
            <el-input v-model="profileForm.industry" />
          </el-form-item>
          <el-form-item label="职位">
            <el-input v-model="profileForm.position" />
          </el-form-item>
          <el-form-item label="公司规模">
            <el-select v-model="profileForm.company_size" style="width:100%">
              <el-option label="(未填)" value="" />
              <el-option label="1-10 人" value="1-10" />
              <el-option label="11-50 人" value="11-50" />
              <el-option label="51-200 人" value="51-200" />
              <el-option label="201-1000 人" value="201-1000" />
              <el-option label="1000+ 人" value="1000+" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="profileVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveProfile">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminAPI } from '../../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const activeTab = ref('all')
const users = ref([])
const pendingUsers = ref([])
const loading = ref(false)
const saving = ref(false)

const creditsVisible = ref(false)
const profileVisible = ref(false)
const editUser = ref(null)
const creditsForm = ref({ credits: 0, reason: '' })
const profileForm = ref({
  phone: '', company_name: '', industry: '', position: '', company_size: '',
})

function providerLabel(p) {
  return {
    local:       '用户名',
    email_otp:   '邮箱',
    phone_sms:   '手机',
    google_oauth:'Google',
  }[p] || '用户名'
}
function providerTagType(p) {
  return {
    local:        '',
    email_otp:    'success',
    phone_sms:    'warning',
    google_oauth: 'info',
  }[p] || ''
}

function openCreditsDialog(user) {
  editUser.value = user
  creditsForm.value = { credits: user.credits, reason: '管理员调整' }
  creditsVisible.value = true
}

function openProfileDialog(user) {
  editUser.value = user
  profileForm.value = {
    phone:        user.phone || '',
    company_name: user.company_name || '',
    industry:     user.industry || '',
    position:     user.position || '',
    company_size: user.company_size || '',
  }
  profileVisible.value = true
}

async function saveCredits() {
  saving.value = true
  try {
    await adminAPI.updateUserCredits(editUser.value.id, creditsForm.value)
    ElMessage.success('积分已更新')
    creditsVisible.value = false
    await loadUsers()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function saveProfile() {
  saving.value = true
  try {
    await adminAPI.updateUserProfile(editUser.value.id, profileForm.value)
    ElMessage.success('用户资料已更新')
    profileVisible.value = false
    await loadUsers()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function toggleStatus(user) {
  const action = user.is_active ? '禁用' : '启用'
  await ElMessageBox.confirm(`确认${action}用户 ${user.username}？`, '操作确认', { type: 'warning' })
  await adminAPI.updateUserStatus(user.id, { is_active: !user.is_active })
  ElMessage.success(`已${action}`)
  await loadUsers()
}

async function approve(user) {
  await ElMessageBox.confirm(`批准用户 ${user.username}？批准后用户可立即登录。`, '审核确认', { type: 'success' })
  try {
    await adminAPI.approveUser(user.id)
    ElMessage.success('已批准')
    await loadAll()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function reject(user) {
  await ElMessageBox.confirm(`拒绝用户 ${user.username}？账号将被禁用（不删除）。`, '审核确认', { type: 'warning' })
  try {
    await adminAPI.rejectUser(user.id)
    ElMessage.success('已拒绝')
    await loadAll()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function loadUsers() {
  loading.value = true
  try { users.value = await adminAPI.getUsers() }
  finally { loading.value = false }
}

async function loadPending() {
  loading.value = true
  try { pendingUsers.value = await adminAPI.getPendingUsers() }
  finally { loading.value = false }
}

async function loadAll() {
  await Promise.all([loadUsers(), loadPending()])
}

function onTabChange(tab) {
  if (tab === 'pending') loadPending()
  else loadUsers()
}

onMounted(loadAll)
</script>

<style scoped>
.page-title { font-size: 20px; color: #1a1a2e; margin-bottom: 16px; }
.credits-val { font-weight: 700; color: #f5a623; }
.credits-info { font-size: 14px; color: #555; }
.contact-cell { display: flex; flex-direction: column; gap: 2px; }
.contact-row { font-size: 13px; }
.hint-text { font-size: 12px; color: #999; margin-top: 2px; }
.pending-badge { margin-left: 6px; }
.profile-meta {
  background: #f7f9fc; border-radius: 8px; padding: 12px 16px;
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px;
  font-size: 13px; color: #555;
}
.meta-label { color: #999; margin-right: 8px; }
</style>
