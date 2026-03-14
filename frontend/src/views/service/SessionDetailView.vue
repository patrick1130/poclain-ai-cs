<template>
  <div class="session-detail-container" v-loading="initialLoading">
    
    <div class="chat-header">
      <div class="header-left">
        <el-button @click="goBack" circle plain class="mr-4">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <el-avatar :size="44" :src="sessionInfo?.user_avatar || defaultAvatar" class="mr-3" />
        <div class="user-info">
          <h2 class="user-name">{{ sessionInfo?.user_name || '微信访客' }}</h2>
          <div class="session-status">
            <el-tag 
              size="small" 
              :type="getStatusType(sessionInfo?.status)" 
              effect="dark"
            >
              {{ getStatusText(sessionInfo?.status) }}
            </el-tag>
            <span class="system-time ml-3 text-xs text-gray-400">
              会话 ID: {{ sessionId }} | 接入时间: {{ formatTime(sessionInfo?.created_at) }}
            </span>
          </div>
        </div>
      </div>
      
      <div class="header-actions">
        <el-button 
          v-if="sessionInfo?.status === 'active'" 
          type="warning" 
          plain 
          @click="transferToAI"
        >
          <el-icon class="mr-1"><Cpu /></el-icon> 托管给 AI
        </el-button>
        
        <el-button 
          v-if="sessionInfo?.status === 'active'" 
          type="danger" 
          @click="closeSession"
        >
          <el-icon class="mr-1"><SwitchButton /></el-icon> 结束会话
        </el-button>

        <el-button 
          v-if="sessionInfo?.status === 'ai_handling' || sessionInfo?.status === 'pending'" 
          type="success" 
          @click="acceptSession"
        >
          <el-icon class="mr-1"><Service /></el-icon> 人工强行接管
        </el-button>
        
        <el-button @click="fetchSessionDetail" circle class="ml-2">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="chat-messages-area" ref="messagesContainer">
      <div v-if="messages.length === 0 && !initialLoading" class="empty-chat">
        <el-empty description="暂无历史消息，主动打个招呼吧" />
      </div>

      <div 
        v-for="(msg, index) in messages" 
        :key="msg.id || index" 
        :class="['message-wrapper', getMessageClass(msg.sender)]"
      >
        <div v-if="msg.sender === 'system'" class="system-message">
          <span class="system-text">{{ msg.content }}</span>
        </div>

        <template v-else>
          <el-avatar 
            v-if="msg.sender === 'user'" 
            :size="36" 
            :src="msg.user_avatar || defaultAvatar" 
            class="msg-avatar" 
          />
          
          <div class="message-content-block">
            <div class="message-meta" v-if="msg.sender === 'user'">
              {{ msg.user_name || '微信访客' }} <span class="meta-time">{{ formatTimeOnly(msg.created_at) }}</span>
            </div>
            <div class="message-meta meta-right" v-else>
              <span class="meta-time">{{ formatTimeOnly(msg.created_at) }}</span> {{ msg.sender === 'ai' ? 'AI 智能助手' : (msg.user_name || '人工坐席') }}
            </div>
            
            <div :class="['message-bubble', getBubbleClass(msg.sender)]">
              <span class="bubble-text">{{ msg.content }}</span>
            </div>
          </div>

          <el-avatar 
            v-if="msg.sender === 'service' || msg.sender === 'ai'" 
            :size="36" 
            :src="msg.sender === 'ai' ? aiAvatar : (msg.user_avatar || defaultServiceAvatar)" 
            class="msg-avatar" 
          />
        </template>
      </div>
    </div>

    <div class="chat-input-area">
      <div class="input-toolbar">
        <el-tooltip content="知识库检索预填" placement="top">
          <el-button circle size="small">
            <el-icon><Collection /></el-icon>
          </el-button>
        </el-tooltip>
        <span class="input-tip ml-auto text-xs text-gray-400">
          Enter 换行，Cmd+Enter / Ctrl+Enter 发送
        </span>
      </div>
      
      <div class="input-wrapper">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="3"
          placeholder="在此输入回复内容..."
          resize="none"
          class="custom-textarea"
          @keydown="handleKeydown"
          :disabled="sessionInfo?.status !== 'active'"
        />
        <el-button 
          type="primary" 
          class="send-btn" 
          :disabled="!inputText.trim() || sessionInfo?.status !== 'active'"
          :loading="sending"
          @click="sendMessage"
        >
          <el-icon class="mr-1"><Position /></el-icon> 发送
        </el-button>
      </div>
      
      <div v-if="!initialLoading && sessionInfo?.status !== 'active'" class="disabled-mask">
        <span class="mask-text">当前会话处于 [{{ getStatusText(sessionInfo?.status) }}] 状态，必须接管后方可发送消息</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Cpu, SwitchButton, Service, Position, Collection, Refresh } from '@element-plus/icons-vue'
import axios from 'axios'

const route = useRoute()
const router = useRouter()
const sessionId = route.params.id

// 基础状态机
const initialLoading = ref(true)
const sending = ref(false)
const sessionInfo = ref(null)
const messages = ref([])
const inputText = ref('')
const messagesContainer = ref(null)

// 静态资源预设
const defaultAvatar = 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'
const defaultServiceAvatar = 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png'
const aiAvatar = 'https://api.dicebear.com/7.x/bottts/svg?seed=PoclainAI'

// 鉴权解析
const getToken = () => localStorage.getItem('access_token') || localStorage.getItem('token') || ''
const getServiceIdFromToken = () => {
  const token = getToken()
  if (!token) return null
  try {
    return JSON.parse(atob(token.split('.')[1])).sub
  } catch (e) { return null }
}
const serviceId = getServiceIdFromToken()

const api = axios.create({ baseURL: '/api/v1', timeout: 15000 })
api.interceptors.request.use(config => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ==========================================
// 核心业务：渲染流同步与帧刷新
// ==========================================
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const fetchSessionDetail = async () => {
  try {
    // 【核心修复 1】将 limit 改回后端的安全线 100，彻底消灭 422 报错！
    const res = await api.get('/service/sessions', { params: { limit: 100 } })
    const target = res.data.find(s => String(s.id) === String(sessionId))
    if (!target) {
      ElMessage.error('找不到该会话，可能已被清理或超出最近 100 条限制')
      goBack()
      return
    }
    sessionInfo.value = target
  } catch (error) {
    ElMessage.error('获取会话详情失败，请检查网络')
  }
}

const fetchMessages = async () => {
  try {
    const res = await api.get(`/service/sessions/${sessionId}/messages`, {
      params: { limit: 100 }
    })
    messages.value = res.data
    scrollToBottom()
  } catch (error) {
    ElMessage.error('获取历史消息失败')
  }
}

// ==========================================
// 核心业务：全双工动作发射
// ==========================================
const sendMessage = async () => {
  const content = inputText.value.trim()
  if (!content) return

  sending.value = true
  const tempMsg = {
    id: `temp_${Date.now()}`,
    sender: 'service',
    content: content,
    created_at: new Date().toISOString(),
    user_name: '人工坐席'
  }
  messages.value.push(tempMsg)
  inputText.value = ''
  scrollToBottom()

  try {
    const res = await api.post(`/service/sessions/${sessionId}/messages`, {
      content: content
    })
    const index = messages.value.findIndex(m => m.id === tempMsg.id)
    if (index !== -1) {
      messages.value[index] = res.data
    }
  } catch (error) {
    ElMessage.error('消息发送失败，已从视图移除')
    messages.value = messages.value.filter(m => m.id !== tempMsg.id)
  } finally {
    sending.value = false
  }
}

const handleKeydown = (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    if (sessionInfo.value?.status === 'active' && inputText.value.trim()) {
      sendMessage()
    }
  }
}

// ==========================================
// 核心业务：状态机控制 (Transfer & Close)
// ==========================================
const acceptSession = async () => {
  try {
    await api.put(`/service/sessions/${sessionId}/accept`)
    ElMessage.success('已夺取会话控制权')
    await fetchSessionDetail() // 重新拉取最新状态解锁输入框
  } catch (error) { ElMessage.error('接管失败') }
}

const transferToAI = async () => {
  try {
    await ElMessageBox.confirm('将会话退回给 AI 托管？', '操作确认', { confirmButtonText: '转交 AI' })
    await api.put(`/service/sessions/${sessionId}/transfer-ai`)
    ElMessage.success('已转交 AI 引擎')
    await fetchSessionDetail()
  } catch (e) { if (e !== 'cancel') ElMessage.error('转交失败') }
}

const closeSession = async () => {
  try {
    await ElMessageBox.confirm('彻底关闭当前客户会话？', '结束服务', { type: 'warning' })
    await api.put(`/service/sessions/${sessionId}/close`)
    ElMessage.success('会话已关闭')
    goBack()
  } catch (e) { if (e !== 'cancel') ElMessage.error('关闭失败') }
}

const goBack = () => { router.push('/service') }

// ==========================================
// 核心层：作用域级 WebSocket 引擎
// ==========================================
let ws = null

const initWebSocket = () => {
  if (!serviceId) return
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = process.env.NODE_ENV === 'development' ? '127.0.0.1:8000' : window.location.host
  
  // 绕过 HTTP 403 拦截，直连原生 WS 网关
  ws = new WebSocket(`${protocol}//${host}/ws/service/${serviceId}?token=${getToken()}`)

  ws.onmessage = (event) => {
    try {
      // 【核心修复 2】容错解构，防止系统握手包没有 data 导致读取 undefined 引发全盘崩溃
      const payload = JSON.parse(event.data)
      const type = payload.type
      const data = payload.data || {} 

      if (String(data.session_id || data.id) !== String(sessionId)) return

      if (type === 'new_message') {
        if (!messages.value.some(m => m.id === data.id)) {
          messages.value.push(data)
          scrollToBottom()
        }
      } else if (type === 'session_update') {
        sessionInfo.value.status = data.status
        if (data.status === 'closed') {
          ElMessage.warning('用户或系统已结束该会话')
        }
      }
    } catch (e) { console.error('WS Data Parse Error', e) }
  }
}

// ==========================================
// UI 工具函数
// ==========================================
const getStatusType = (status) => {
  if (status === 'active') return 'success'
  if (status === 'ai_handling') return 'warning'
  if (status === 'pending') return 'danger'
  return 'info'
}

const getStatusText = (status) => {
  if (!status) return '加载中...'
  if (status === 'active') return '人工服务中'
  if (status === 'ai_handling') return 'AI 托管中'
  if (status === 'pending') return '排队等待中'
  if (status === 'closed') return '已结束'
  return '未知状态'
}

const getMessageClass = (sender) => {
  if (sender === 'user') return 'message-left'
  if (sender === 'system') return 'message-center'
  return 'message-right'
}

const getBubbleClass = (sender) => {
  if (sender === 'user') return 'bubble-user'
  if (sender === 'ai') return 'bubble-ai'
  return 'bubble-service'
}

const formatTime = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
const formatTimeOnly = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

// ==========================================
// 钩子绑定
// ==========================================
onMounted(async () => {
  await fetchSessionDetail()
  await fetchMessages()
  initialLoading.value = false
  initWebSocket()
})

onBeforeUnmount(() => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close(1000, 'Session detail unmounted')
    ws = null
  }
})
</script>

<style scoped>
.session-detail-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

/* 顶部控制台 */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background-color: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}
.header-left {
  display: flex;
  align-items: center;
}
.user-name {
  margin: 0 0 4px 0;
  font-size: 18px;
  color: #1e293b;
}

/* 流式渲染区 */
.chat-messages-area {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  background-color: #ffffff;
}

.empty-chat {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.message-wrapper {
  display: flex;
  margin-bottom: 24px;
  animation: fadeIn 0.3s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-left { justify-content: flex-start; }
.message-right { justify-content: flex-end; }
.message-center { justify-content: center; margin-bottom: 16px; }

.system-message {
  background-color: #f1f5f9;
  padding: 4px 12px;
  border-radius: 12px;
}
.system-text {
  font-size: 12px;
  color: #64748b;
}

.msg-avatar { flex-shrink: 0; }
.message-content-block {
  max-width: 65%;
  margin: 0 12px;
  display: flex;
  flex-direction: column;
}

.message-meta {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 4px;
}
.meta-right { text-align: right; }
.meta-time { margin: 0 4px; }

.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.bubble-text {
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 气泡着色器 */
.bubble-user {
  background-color: #f1f5f9;
  color: #334155;
  border-top-left-radius: 4px;
}
.bubble-service {
  background-color: #3b82f6; /* 微信蓝/企业蓝 */
  color: #ffffff;
  border-top-right-radius: 4px;
}
.bubble-ai {
  background-color: #10b981; /* 翠绿色 */
  color: #ffffff;
  border-top-right-radius: 4px;
}

/* 输入发射区 */
.chat-input-area {
  border-top: 1px solid #e2e8f0;
  padding: 12px 24px 24px;
  background-color: #f8fafc;
  position: relative;
}

.input-toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.input-wrapper {
  display: flex;
  gap: 16px;
  align-items: flex-end;
}

.custom-textarea :deep(.el-textarea__inner) {
  border-radius: 8px;
  box-shadow: none;
  border: 1px solid #cbd5e1;
  padding: 12px;
}
.custom-textarea :deep(.el-textarea__inner:focus) {
  border-color: #3b82f6;
  background-color: #ffffff;
}

.send-btn {
  height: 40px;
  padding: 0 24px;
  border-radius: 8px;
}

/* 冻结遮罩层 */
.disabled-mask {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: rgba(248, 250, 252, 0.85);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.mask-text {
  font-size: 14px;
  color: #64748b;
  font-weight: 500;
}

/* 原子类 */
.mr-1 { margin-right: 4px; }
.mr-2 { margin-right: 8px; }
.mr-3 { margin-right: 12px; }
.mr-4 { margin-right: 16px; }
.ml-2 { margin-left: 8px; }
.ml-3 { margin-left: 12px; }
.ml-auto { margin-left: auto; }
</style>