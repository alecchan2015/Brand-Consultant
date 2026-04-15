<template>
  <el-container class="app-layout">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <span class="logo-icon">🪑</span>
        <span class="logo-text">Your Brand Consultant</span>
      </div>
      <el-menu router :default-active="route.path" class="side-menu">
        <el-menu-item index="/dashboard">
          <el-icon><Grid /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/tasks/new">
          <el-icon><Plus /></el-icon>
          <span>新建任务</span>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-bottom">
        <div class="credits-badge">
          <el-icon><Coin /></el-icon>
          <span>{{ store.user?.credits ?? 0 }} 积分</span>
        </div>
        <el-button text size="small" @click="logout" style="color:#aaa">
          <el-icon><SwitchButton /></el-icon> 退出
        </el-button>
      </div>
    </el-aside>
    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <span class="page-title">Your Brand Consultant</span>
        </div>
        <div class="header-right">
          <el-tag type="success" effect="dark" v-if="store.isAdmin">管理员</el-tag>
          <span class="username">{{ store.user?.username }}</span>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../store'
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
.app-layout { height: 100vh; }
.sidebar {
  background: #1a1a2e;
  display: flex; flex-direction: column;
  position: fixed; height: 100vh; z-index: 100;
}
.logo {
  height: 64px; display: flex; align-items: center;
  padding: 0 20px; gap: 10px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.logo-icon { font-size: 26px; }
.logo-text { color: #fff; font-size: 16px; font-weight: 700; }
.side-menu { background: transparent; border: none; flex: 1; }
.side-menu :deep(.el-menu-item) { color: rgba(255,255,255,0.7); }
.side-menu :deep(.el-menu-item:hover),
.side-menu :deep(.el-menu-item.is-active) {
  background: rgba(255,255,255,0.1) !important;
  color: #fff !important;
}
.sidebar-bottom {
  padding: 16px 20px; border-top: 1px solid rgba(255,255,255,0.08);
  display: flex; flex-direction: column; gap: 8px;
}
.credits-badge {
  display: flex; align-items: center; gap: 6px;
  color: #f5c518; font-size: 13px; font-weight: 600;
}
.app-header {
  height: 64px; background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; margin-left: 220px;
}
.page-title { font-size: 15px; color: #666; }
.header-right { display: flex; align-items: center; gap: 12px; }
.username { font-size: 14px; color: #333; font-weight: 500; }
.app-main { margin-left: 220px; padding: 24px; background: #f0f2f5; min-height: calc(100vh - 64px); }
</style>
