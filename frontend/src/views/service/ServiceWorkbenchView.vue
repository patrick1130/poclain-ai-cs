<template>
  <div class="workbench-container" v-loading="loading">
    <div class="workbench-header">
      <div class="header-left">
        <h1 class="page-title">
          全双工客服工作台
          <el-tag 
            size="small" 
            :type="wsConnected ? 'success' : 'danger'" 
            effect="dark" 
            class="ml-3"
          >
            {{ wsConnected ? 'WS 实时引擎已连接' : 'WS 连接断开' }}
          </el-tag>
        </h1>
      </div>
      <div class="header-actions">
        <el-radio-group v-model="agentStatus" @change="handleStatusChange" size="default">
          <el-radio-button value="online">在线接客</el-radio-button>
          <el-radio-button value="busy">小休忙碌</el-radio-button>
        </el-radio-group>
        <el-button @click="fetchSessions" circle class="ml-4"><el-icon><Refresh /></el-icon></el-button>
      </div>
    </div>

    <div class="workbench-main">
      <el-tabs v-model="activeTab" class="session-tabs" @tab-change="handleTabChange">
        
        <el-tab-pane name="pending">
          <template #label>
            待接入队列
            <el-badge :value="pendingSessions.length" :hidden="pendingSessions.length === 0" type="danger" class="tab-badge" />
          </template>
          
          <div class="session-grid">
            <el-empty v-if="pendingSessions.length === 0" description="当前没有等待中的客户" />
            
            <el-card 
              v-for="session in pendingSessions" 
              :key="session.id" 
              class="session-card pending-card"
              shadow="hover"
            >
              <div class="card-header">
                <div class="user-info">
                  <el-avatar :size="40" :src="session.user_avatar || defaultAvatar" />
                  <div class="user-meta">
                    <span class="user-name">{{ session.user_name || '微信访客' }}</span>
                    <span class="time-ago">{{ formatTime(session.last_message_time || session.created_at) }}</span>
                  </div>
                </div>
                <el-tag size="small" :type="session.status === 'ai_handling' ? 'warning' : 'danger'">
                  {{ session.status === 'ai_handling' ? 'AI 托管中' : '排队等待' }}
                </el-tag>
              </div>
              <div class="card-body">
                <p class="last-message truncate-text">{{ session.last_message || '客户尚未发送消息...' }}</p>
              </div>
              <div class="card-footer">
                <el-button type="primary" class="w-full" @click="acceptSession(session.id)" :loading="actionLoading === session.id">
                  <el-icon class="mr-1"><Service /></el-icon> 立即接入
                </el-button>
              </div>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane name="active">
          <template #label>
            处理中会话
            <el-badge :value="activeSessions.length" :hidden="activeSessions.length === 0" type="primary" class="tab-badge" />
          </template>

          <div class="session-grid">
            <el-empty v-if="activeSessions.length === 0" description="当前没有正在处理的会话" />
            
            <el-card 
              v-for="session in activeSessions" 
              :key="session.id" 
              class="session-card active-card"
              shadow="hover"
              @click="enterSession(session.id)"
            >
              <div class="card-header">
                <div class="user-info">
                  <el-avatar :size="40" :src="session.user_avatar || defaultAvatar" />
                  <div class="user-meta">
                    <span class="user-name">{{ session.user_name || '微信访客' }}</span>
                    <span class="time-ago">{{ formatTime(session.last_message_time || session.created_at) }}</span>
                  </div>
                </div>
                <el-tag size="small" type="success" effect="plain">沟通中</el-tag>
              </div>
              <div class="card-body">
                <p class="last-message truncate-text">{{ session.last_message || '暂无消息' }}</p>
              </div>
              <div class="card-footer">
                <el-button type="success" plain class="w-full" @click.stop="enterSession(session.id)">
                  <el-icon class="mr-1"><ChatDotRound /></el-icon> 进入控制台
                </el-button>
              </div>
            </el-card>
          </div>
        </el-tab-pane>

      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Service, ChatDotRound, Refresh } from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const loading = ref(false)
const actionLoading = ref(null)
const wsConnected = ref(false)
const agentStatus = ref('online')
const activeTab = ref('pending')
const defaultAvatar = 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'

const sessionsList = ref([])
const sessionIndexMap = new Map()

const getToken = () => localStorage.getItem('access_token') || localStorage.getItem('token') || ''
const getServiceIdFromToken = () => {
  const token = getToken()
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.sub
  } catch (e) {
    return null
  }
}

const serviceId = getServiceIdFromToken()

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})
api.interceptors.request.use(config => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

const pendingSessions = computed(() => {
  return sessionsList.value.filter(s => s.status === 'pending' || s.status === 'ai_handling')
})

const activeSessions = computed(() => {
  return sessionsList.value.filter(s => s.status === 'active' && String(s.service_agent_id) === String(serviceId))
})

const fetchSessions = async () => {
  loading.value = true
  try {
    const res = await api.get('/service/sessions', {
      params: { limit: 100 }
    })
    
    sessionsList.value = res.data
    sessionIndexMap.clear()
    sessionsList.value.forEach(session => {
      sessionIndexMap.set(String(session.id), session)
    })
    
  } catch (error) {
    ElMessage.error('拉取会话列表失败')
  } finally {
    loading.value = false
  }
}

const handleStatusChange = async (val) => {
  try {
    await api.put('/service/status', { status: val })
    ElMessage.success(`客服状态已切换为: ${val === 'online' ? '在线' : '忙碌'}`)
  } catch (error) {
    ElMessage.error('状态切换失败')
    agentStatus.value = val === 'online' ? 'busy' : 'online'
  }
}

const acceptSession = async (sessionId) => {
  actionLoading.value = sessionId
  try {
    await api.put(`/service/sessions/${sessionId}/accept`)
    ElMessage.success('成功接管会话')
    const target = sessionIndexMap.get(String(sessionId))
    if (target) {
      target.status = 'active'
      target.service_agent_id = serviceId
    }
    activeTab.value = 'active'
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '接入失败，可能已被其他客服接管')
    fetchSessions()
  } finally {
    actionLoading.value = null
  }
}

const enterSession = (sessionId) => {
  router.push(`/service/session/${sessionId}`)
}

const handleTabChange = () => {}

// ==========================================
// 🚨 架构师重构：WebSocket 生命周期全局状态管理
// ==========================================
let ws = null;
let reconnectTimer = null;
let heartbeatTimer = null;
let lockReconnect = false;
let isDestroyed = false; // ✨ 核心开关：标记当前组件是否已死亡

const initWebSocket = () => {
  if (isDestroyed) return; // 幽灵拦截
  if (!serviceId) {
    ElMessage.error('无法初始化实时引擎：缺少坐席身份凭证');
    return;
  }

  // 物理清空历史残留
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    ws.onclose = null; 
    ws.onerror = null;
    ws.close(1000);    
  }

  clearTimeout(reconnectTimer);
  clearInterval(heartbeatTimer);

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = process.env.NODE_ENV === 'development' ? '127.0.0.1:8000' : window.location.host;
  const wsUrl = `${protocol}//${host}/ws/service/${serviceId}?token=${getToken()}`;

  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    console.error('WebSocket 实例创建失败:', e);
    reconnect();
    return;
  }

  ws.onopen = () => {
    if (isDestroyed) {
      ws.close(); return;
    }
    wsConnected.value = true;
    lockReconnect = false;
    console.log('✅ [架构日志] WebSocket 链路激活');
    
    heartbeatTimer = setInterval(() => {
      if (ws.readyState === 1) {
        ws.send(JSON.stringify({ type: 'heartbeat', data: 'ping' }));
      }
    }, 30000);
  };

  ws.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === 'heartbeat_res') return;
      handleWsEvent(payload);
    } catch (e) {
      console.error('WS Payload 解析失败:', e);
    }
  };

  ws.onclose = (e) => {
    if (isDestroyed) return; // 🚨 幽灵组件禁止在此大呼小叫！
    wsConnected.value = false;
    clearInterval(heartbeatTimer);
    console.warn(`❌ [架构日志] WebSocket 异常断开 (Code: ${e.code}, Reason: ${e.reason || '无'})`);
    reconnect();
  };

  ws.onerror = () => {
    if (isDestroyed) return;
    wsConnected.value = false;
    reconnect();
  };
};

const reconnect = () => {
  if (isDestroyed || lockReconnect) return;
  lockReconnect = true;
  
  console.log('🔄 [架构日志] 启动自动重连程序...');
  reconnectTimer = setTimeout(() => {
    lockReconnect = false;
    initWebSocket();
  }, 5000);
};

const handleWsEvent = (payload) => {
  const { type, data = {} } = payload
  if (type === 'new_message') {
    if (!data.session_id) return
    const targetSession = sessionIndexMap.get(String(data.session_id))
    if (targetSession) {
      targetSession.last_message = data.content
      targetSession.last_message_time = data.created_at
    } else {
      fetchSessions()
    }
  } 
  else if (type === 'session_update') {
    if (!data.id) return
    const targetSession = sessionIndexMap.get(String(data.id))
    if (targetSession) {
      targetSession.status = data.status
      if (data.service_agent_id !== undefined) {
        targetSession.service_agent_id = data.service_agent_id
      }
    } else {
      fetchSessions()
    }
  }
}

const formatTime = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  const now = new Date()
  const diffMinutes = Math.floor((now - date) / 60000)
  
  if (diffMinutes < 1) return '刚刚'
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`
  if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)} 小时前`
  
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

onMounted(() => {
  isDestroyed = false; // 挂载时重置存活状态
  fetchSessions();
  initWebSocket();
})

// 🚨 终极粉碎机：确保组件卸载时，绝不留下一根蛛丝马迹
onBeforeUnmount(() => {
  console.log('🧹 [架构日志] 组件卸载，执行物理级连接回收');
  isDestroyed = true; // 拉下死亡电闸，所有相关回调全部失效
  clearTimeout(reconnectTimer);
  clearInterval(heartbeatTimer);
  
  if (ws) {
    ws.onclose = null; // 重点：剥夺遗言权，防止触发 reconnect()
    ws.onerror = null;
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close(1000, 'Component unmounted');
    }
    ws = null;
  }
})
</script>

<style scoped>
/* [样式保持你原本的代码，未做删改] */
.workbench-container { padding: 0; height: calc(100vh - 80px); display: flex; flex-direction: column; }
.workbench-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; background: white; padding: 16px 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); }
.page-title { margin: 0; font-size: 20px; font-weight: 600; color: #1f2937; display: flex; align-items: center; }
.header-actions { display: flex; align-items: center; }
.workbench-main { flex: 1; background: white; border-radius: 8px; padding: 0 24px 24px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); overflow: hidden; display: flex; flex-direction: column; }
.session-tabs { flex: 1; display: flex; flex-direction: column; }
:deep(.el-tabs__content) { flex: 1; overflow-y: auto; padding-top: 16px; }
.tab-badge { margin-left: 4px; transform: translateY(-2px); }
.session-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; padding-bottom: 24px; }
.session-card { border-radius: 8px; transition: all 0.3s ease; border: 1px solid #e5e7eb; }
.session-card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05); }
.active-card { cursor: pointer; border-top: 4px solid #10b981; }
.pending-card { border-top: 4px solid #f43f5e; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.user-info { display: flex; align-items: center; gap: 12px; }
.user-meta { display: flex; flex-direction: column; }
.user-name { font-weight: 600; color: #1f2937; font-size: 15px; }
.time-ago { font-size: 12px; color: #6b7280; margin-top: 2px; }
.card-body { margin-bottom: 16px; min-height: 48px; background-color: #f9fafb; padding: 12px; border-radius: 6px; }
.last-message { margin: 0; font-size: 14px; color: #4b5563; line-height: 1.5; }
.truncate-text { display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; }
.w-full { width: 100%; }
.ml-3 { margin-left: 12px; }
.ml-4 { margin-left: 16px; }
.mr-1 { margin-right: 4px; }
</style>