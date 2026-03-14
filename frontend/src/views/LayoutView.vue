<template>
  <div class="layout-container">
    <el-container class="layout-main">
      <el-aside :width="isCollapse ? '64px' : '240px'" class="layout-sidebar">
        <div class="sidebar-header">
          <div class="sidebar-logo" :class="{ 'collapsed': isCollapse }">
            <div class="logo-placeholder" v-if="!isCollapse" style="width: 32px; height: 32px; background: #3b82f6; border-radius: 6px;"></div>
            <div class="logo-text" v-if="!isCollapse">微信AI客服</div>
          </div>
          <el-button
            link
            class="collapse-btn"
            @click="toggleCollapse"
          >
            <el-icon><component :is="isCollapse ? 'arrow-right' : 'arrow-left'" /></el-icon>
          </el-button>
        </div>
        
        <el-scrollbar class="sidebar-scrollbar">
          <el-menu
            :collapse="isCollapse"
            :default-active="activeMenu"
            class="sidebar-menu"
            @select="handleMenuSelect"
          >
            <el-menu-item index="/service">
              <el-icon><ChatDotRound /></el-icon>
              <template #title>客服工作台</template>
            </el-menu-item>
            
            <el-menu-item index="/knowledge">
              <el-icon><Document /></el-icon>
              <template #title>知识库管理</template>
            </el-menu-item>
            
            <el-menu-item index="/statistics">
              <el-icon><DataAnalysis /></el-icon>
              <template #title>数据统计</template>
            </el-menu-item>
            
            <el-menu-item index="/settings">
              <el-icon><Setting /></el-icon>
              <template #title>系统设置</template>
            </el-menu-item>
          </el-menu>
        </el-scrollbar>
      </el-aside>
      
      <el-container class="layout-content">
        <el-header class="layout-header">
          <div class="header-left">
            <div class="breadcrumb">
              <el-breadcrumb separator="/">
                <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
                <el-breadcrumb-item v-if="currentRoute.meta.title">{{ currentRoute.meta.title }}</el-breadcrumb-item>
              </el-breadcrumb>
            </div>
          </div>
          
          <div class="header-right">
            <div class="header-actions">
              <el-dropdown trigger="click" @command="handleDropdownCommand">
                <span class="user-profile">
                  <el-avatar :size="32" :src="serviceInfo?.avatar">
                    {{ serviceInfo?.name?.charAt(0) || 'S' }}
                  </el-avatar>
                  <span class="user-name" v-if="!isMobile">{{ serviceInfo?.name || '客服' }}</span>
                  <el-icon class="el-icon--right"><arrow-down /></el-icon>
                </span>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="profile">
                      <el-icon><User /></el-icon>
                      个人信息
                    </el-dropdown-item>
                    <el-dropdown-item command="changePassword">
                      <el-icon><Lock /></el-icon>
                      修改密码
                    </el-dropdown-item>
                    <el-dropdown-item divided command="logout">
                      <el-icon><SwitchButton /></el-icon>
                      退出登录
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </el-header>
        
        <el-main class="layout-main-content">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  ArrowLeft, ArrowRight, ChatDotRound, Document, 
  DataAnalysis, Setting, User, Lock, SwitchButton, ArrowDown 
} from '@element-plus/icons-vue'

export default {
  name: 'LayoutView',
  components: {
    ArrowLeft, ArrowRight, ChatDotRound, Document,
    DataAnalysis, Setting, User, Lock, SwitchButton, ArrowDown
  },
  setup() {
    const router = useRouter()
    const route = useRoute()
    const isCollapse = ref(false)
    const isMobile = ref(false)
    const serviceInfo = ref(null)
    
    // 计算当前激活的菜单
    const activeMenu = computed(() => {
      const path = route.path
      // 处理子路由，返回父路由路径
      const segments = path.split('/')
      if (segments.length > 2) {
        return `/${segments[1]}`
      }
      return path
    })
    
    // 获取当前路由信息
    const currentRoute = computed(() => route)
    
    // 切换侧边栏折叠状态
    const toggleCollapse = () => {
      isCollapse.value = !isCollapse.value
      localStorage.setItem('sidebarCollapsed', isCollapse.value)
    }
    
    // 处理菜单选择
    const handleMenuSelect = (key) => {
      router.push(key)
    }
    
    // 处理下拉菜单命令
    const handleDropdownCommand = async (command) => {
      switch (command) {
        case 'profile':
          ElMessage.info('个人信息功能开发中')
          break
          
        case 'changePassword':
          await handleChangePassword()
          break
          
        case 'logout':
          await handleLogout()
          break
      }
    }
    
    // 修改密码
    const handleChangePassword = async () => {
      try {
        const { value: newPassword } = await ElMessageBox.prompt(
          '请输入新密码',
          '修改密码',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            inputType: 'password',
            inputPlaceholder: '请输入新密码',
            inputValidator: (value) => {
              if (!value || value.length < 6) {
                return '密码长度不能少于6位'
              }
              return true
            }
          }
        )
        
        // 这里应该调用修改密码的API
        ElMessage.success('密码修改成功')
        
      } catch (error) {
        // 用户取消操作
        if (error !== 'cancel') {
          console.error('修改密码失败:', error)
        }
      }
    }
    
    // 退出登录
    const handleLogout = async () => {
      try {
        await ElMessageBox.confirm(
          '确定要退出登录吗？',
          '退出登录',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        // 清除本地存储
        localStorage.removeItem('token')
        localStorage.removeItem('serviceId')
        localStorage.removeItem('serviceInfo')
        
        // 跳转到登录页
        router.push('/login')
        
      } catch (error) {
        // 用户取消操作
        if (error !== 'cancel') {
          console.error('退出登录失败:', error)
        }
      }
    }
    
    // 检查是否为移动端
    const checkMobile = () => {
      isMobile.value = window.innerWidth < 768
      if (isMobile.value) {
        isCollapse.value = true
      }
    }
    
    // 加载客服信息
    const loadServiceInfo = () => {
      const savedInfo = localStorage.getItem('serviceInfo')
      if (savedInfo) {
        try {
          serviceInfo.value = JSON.parse(savedInfo)
        } catch (error) {
          console.error('解析客服信息失败:', error)
          // 如果解析失败，清除本地存储并跳转到登录页
          localStorage.removeItem('token')
          localStorage.removeItem('serviceId')
          localStorage.removeItem('serviceInfo')
          router.push('/login')
        }
      } else {
        // 如果没有客服信息，跳转到登录页
        router.push('/login')
      }
    }
    
    // 组件挂载时
    onMounted(() => {
      // 加载客服信息
      loadServiceInfo()
      
      // 检查是否为移动端
      checkMobile()
      
      // 监听窗口大小变化
      window.addEventListener('resize', checkMobile)
      
      // 从本地存储恢复侧边栏状态
      const savedCollapsed = localStorage.getItem('sidebarCollapsed')
      if (savedCollapsed !== null) {
        isCollapse.value = savedCollapsed === 'true'
      }
    })
    
    // 组件卸载时
    onUnmounted(() => {
      window.removeEventListener('resize', checkMobile)
    })
    
    return {
      isCollapse,
      isMobile,
      serviceInfo,
      activeMenu,
      currentRoute,
      toggleCollapse,
      handleMenuSelect,
      handleDropdownCommand
    }
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  overflow: hidden;
}

.layout-main {
  height: 100%;
}

/* 侧边栏样式 */
.layout-sidebar {
  background: #0f172a;
  transition: width 0.3s ease;
  box-shadow: 2px 0 6px rgba(0, 0, 0, 0.1);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #1e293b;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
}

.sidebar-logo.collapsed {
  justify-content: center;
  width: 100%;
}

.logo-image {
  width: 32px;
  height: 32px;
  border-radius: 6px;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #f8fafc;
}

.collapse-btn {
  color: #94a3b8;
  padding: 4px;
}

.collapse-btn:hover {
  color: #f8fafc;
  background-color: #1e293b;
}

.sidebar-scrollbar {
  height: calc(100vh - 65px);
}

.sidebar-menu {
  background: transparent;
  border-right: none;
}

.sidebar-menu .el-menu-item {
  color: #94a3b8;
  height: 52px;
  line-height: 52px;
  margin: 0;
}

.sidebar-menu .el-menu-item:hover {
  background-color: #1e293b;
  color: #f8fafc;
}

.sidebar-menu .el-menu-item.is-active {
  background-color: #3b82f6;
  color: #ffffff;
}

.sidebar-menu .el-menu-item__icon {
  margin-right: 8px;
}

/* 主内容区样式 */
.layout-content {
  background: #f8fafc;
}

.layout-header {
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  padding: 0 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  flex: 1;
}

.breadcrumb {
  font-size: 14px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.user-profile:hover {
  background-color: #f1f5f9;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.layout-main-content {
  padding: 24px;
  overflow-y: auto;
  height: calc(100vh - 60px);
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .layout-sidebar {
    position: fixed;
    z-index: 1000;
    height: 100vh;
    left: 0;
    top: 0;
  }
  
  .layout-header {
    padding: 0 16px;
  }
  
  .layout-main-content {
    padding: 16px;
  }
  
  .user-name {
    display: none;
  }
}

@media (max-width: 480px) {
  .layout-main-content {
    padding: 12px;
  }
}
</style>