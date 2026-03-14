<template>
  <div class="session-list">
    <div class="session-header">
      <h3 class="header-title">会话列表</h3>
      <div class="session-stats">
        <span>总计: {{ totalSessions }}</span>
        <span class="stat-divider">|</span>
        <span class="stat-pending">待接入: {{ pendingSessions }}</span>
        <span class="stat-divider">|</span>
        <span class="stat-active">进行中: {{ activeSessions }}</span>
      </div>
    </div>
    
    <div class="session-filters">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索客户昵称 / 消息内容..."
        clearable
        size="small"
        class="filter-input"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      
      <el-select
        v-model="statusFilter"
        placeholder="全部分组"
        size="small"
        class="filter-select"
        clearable
      >
        <el-option label="全部" value="" />
        <el-option label="待接入 (Pending)" value="pending" />
        <el-option label="对话中 (Active)" value="active" />
        <el-option label="AI 托管 (AI)" value="ai_handling" />
        <el-option label="已结束 (Closed)" value="closed" />
      </el-select>
    </div>
    
    <div class="session-items" v-if="filteredSessions.length > 0">
      <div
        v-for="session in filteredSessions"
        :key="session.id"
        class="session-item"
        :class="{
          'active': String(selectedSessionId) === String(session.id),
          'is-pending': session.status === 'pending',
          'is-active': session.status === 'active',
          'is-ai': session.status === 'ai_handling',
          'is-closed': session.status === 'closed'
        }"
        @click="selectSession(session)"
      >
        <div class="session-info">
          <div class="session-user">
            <el-avatar :size="38" :src="session.user_avatar || defaultAvatar" class="user-avatar">
              {{ session.user_name?.charAt(0) || 'U' }}
            </el-avatar>
            <div class="session-user-info">
              <div class="session-user-name">{{ session.user_name || '匿名客户' }}</div>
              <div class="session-last-message">
                {{ getLastMessagePreview(session) }}
              </div>
            </div>
          </div>
          
          <div class="session-meta">
            <div class="session-time">
              {{ formatTime(session.last_message_time || session.created_at) }}
            </div>
            <div class="session-status">
              <el-tag v-if="session.status === 'pending'" size="small" type="warning" effect="light">待接入</el-tag>
              <el-tag v-else-if="session.status === 'active'" size="small" type="success" effect="light">对话中</el-tag>
              <el-tag v-else-if="session.status === 'ai_handling'" size="small" type="primary" effect="plain">AI 托管</el-tag>
              <el-tag v-else-if="session.status === 'closed'" size="small" type="info" effect="light">已结束</el-tag>
            </div>
          </div>
        </div>
        
        <div class="session-actions" v-if="session.status === 'pending' || session.status === 'ai_handling'">
          <el-button
            size="small"
            type="primary"
            @click.stop="acceptSession(session.id)"
            class="action-btn"
          >
            立即接入
          </el-button>
        </div>
      </div>
    </div>
    
    <div v-else class="empty-sessions">
      <el-empty description="暂无符合条件的会话" :image-size="80" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { acceptSession as apiAcceptSession } from '@/api/service'

const props = defineProps({
  sessions: {
    type: Array,
    default: () => []
  },
  selectedSessionId: {
    type: [String, Number],
    default: ''
  }
})

const emit = defineEmits(['select-session', 'refresh'])

const searchKeyword = ref('')
const statusFilter = ref('')
const defaultAvatar = 'https://api.dicebear.com/7.x/avataaars/svg?seed=user'

const filteredSessions = computed(() => {
  let result = [...(props.sessions || [])]

  if (statusFilter.value) {
    result = result.filter(session => session.status === statusFilter.value)
  }

  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(session => 
      (session.user_name && session.user_name.toLowerCase().includes(keyword)) ||
      (session.last_message && session.last_message.toLowerCase().includes(keyword))
    )
  }

  // 始终将“待接入”排在最前，其次按时间倒序
  return result.sort((a, b) => {
    if (a.status === 'pending' && b.status !== 'pending') return -1
    if (a.status !== 'pending' && b.status === 'pending') return 1
    const timeA = new Date(a.last_message_time || a.created_at)
    const timeB = new Date(b.last_message_time || b.created_at)
    return timeB - timeA
  })
})

const totalSessions = computed(() => (props.sessions || []).length)
const pendingSessions = computed(() => (props.sessions || []).filter(s => s.status === 'pending').length)
const activeSessions = computed(() => (props.sessions || []).filter(s => s.status === 'active' || s.status === 'ai_handling').length)

const selectSession = (session) => {
  emit('select-session', session)
}

const acceptSession = async (sessionId) => {
  try {
    await apiAcceptSession(sessionId)
    ElMessage.success('成功接入会话，您可以开始回复了')
    emit('refresh')
  } catch (error) {
    ElMessage.error('接入会话失败，请检查网络或权限')
    console.error('接入异常:', error)
  }
}

const getLastMessagePreview = (session) => {
  if (!session.last_message) return '暂无历史消息'
  return session.last_message.length > 18 
    ? session.last_message.substring(0, 18) + '...'
    : session.last_message
}

const formatTime = (timeString) => {
  if (!timeString) return ''
  const date = new Date(timeString)
  const now = new Date()
  
  // 如果是今天，显示具体时分
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  
  // 如果是昨天
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (date.toDateString() === yesterday.toDateString()) {
    return '昨天'
  }

  // 否则显示月日
  return `${date.getMonth() + 1}/${date.getDate()}`
}
</script>

<style scoped>
.session-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #ffffff;
}

.session-header {
  padding: 18px 16px 14px;
  border-bottom: 1px solid #f1f5f9;
}

.header-title {
  margin: 0;
  font-size: 16px;
  color: #1e293b;
}

.session-stats {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-divider {
  color: #cbd5e1;
}

.stat-pending {
  color: #f59e0b;
  font-weight: 500;
}

.stat-active {
  color: #10b981;
  font-weight: 500;
}

.session-filters {
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.filter-input :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #e2e8f0 inset;
}

.filter-select {
  width: 100%;
}

.session-items {
  flex: 1;
  overflow-y: auto;
}

.session-item {
  padding: 14px 16px;
  border-bottom: 1px solid #f8fafc;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.session-item:hover {
  background-color: #f8fafc;
}

.session-item.active {
  background-color: #eff6ff;
}

.session-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background-color: #3b82f6;
}

.session-item.is-pending::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background-color: #f59e0b;
}

.session-item.is-closed {
  opacity: 0.65;
}

.session-item.is-closed:hover {
  opacity: 0.8;
}

.session-info {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.session-user {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.user-avatar {
  background-color: #e2e8f0;
  color: #64748b;
  font-weight: 600;
}

.session-user-info {
  flex: 1;
  min-width: 0;
}

.session-user-name {
  font-weight: 500;
  font-size: 14px;
  color: #334155;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-last-message {
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  margin-left: 8px;
}

.session-time {
  font-size: 11px;
  color: #cbd5e1;
}

.session-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.action-btn {
  width: 100%;
}

.empty-sessions {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #fafafa;
}
</style>