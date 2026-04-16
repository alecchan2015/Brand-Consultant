<template>
  <el-container class="admin-layout">
    <el-aside width="220px" class="admin-sidebar">
      <div class="logo">
        <span class="logo-icon">⚙️</span>
        <span class="logo-text">管理后台</span>
      </div>
      <el-menu router :default-active="route.path" class="admin-menu">
        <el-menu-item index="/admin/dashboard">
          <el-icon><DataLine /></el-icon><span>数据概览</span>
        </el-menu-item>
        <el-menu-item index="/admin/llm">
          <el-icon><Setting /></el-icon><span>模型配置</span>
        </el-menu-item>
        <el-menu-item index="/admin/ppt-provider">
          <el-icon><Histogram /></el-icon><span>PPT 生成器</span>
        </el-menu-item>
        <el-menu-item index="/admin/knowledge">
          <el-icon><Reading /></el-icon><span>知识库管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon><span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/tasks">
          <el-icon><List /></el-icon><span>任务记录</span>
        </el-menu-item>
        <el-menu-item index="/admin/token-usage">
          <el-icon><Odometer /></el-icon><span>Token 用量</span>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-bottom">
        <el-button text size="small" @click="$router.push('/dashboard')" style="color:#aaa">
          <el-icon><ArrowLeft /></el-icon> 前台
        </el-button>
        <el-button text size="small" @click="logout" style="color:#aaa">
          <el-icon><SwitchButton /></el-icon> 退出
        </el-button>
      </div>
    </el-aside>
    <el-container>
      <el-header class="admin-header">
        <span class="admin-title">Your Brand Consultant · 管理后台</span>
        <el-tag type="danger" effect="dark" size="small">管理员: {{ store.user?.username }}</el-tag>
      </el-header>
      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../../store'
import { ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const store = useUserStore()

async function logout() {
  await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
  store.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-layout { height: 100vh; }
.admin-sidebar {
  background: #1a1a2e; display: flex; flex-direction: column;
  position: fixed; height: 100vh; z-index: 100;
}
.logo {
  height: 64px; display: flex; align-items: center;
  padding: 0 20px; gap: 10px; border-bottom: 1px solid rgba(255,255,255,0.1);
}
.logo-icon { font-size: 22px; }
.logo-text { color: #fff; font-size: 15px; font-weight: 700; }
.admin-menu { background: transparent; border: none; flex: 1; }
.admin-menu :deep(.el-menu-item) { color: rgba(255,255,255,0.65); }
.admin-menu :deep(.el-menu-item:hover),
.admin-menu :deep(.el-menu-item.is-active) {
  background: rgba(255,255,255,0.1) !important; color: #fff !important;
}
.sidebar-bottom {
  padding: 16px; border-top: 1px solid rgba(255,255,255,0.1);
  display: flex; gap: 8px;
}
.admin-header {
  height: 64px; background: #fff; margin-left: 220px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px;
}
.admin-title { font-size: 14px; color: #666; }
.admin-main { margin-left: 220px; padding: 24px; background: #f5f7fa; min-height: calc(100vh - 64px); }
</style>
