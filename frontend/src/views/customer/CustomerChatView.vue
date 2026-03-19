<template>
  <div class="chat-container" v-loading="isAuthenticating">
    <header class="chat-header">
      <div class="header-content">
        <div class="brand">
          <span class="status-dot" :class="{ 'connected': wsConnected }"></span>
          <h1>Poclain 官方技术支持</h1>
        </div>
        <span class="status-text">{{ wsConnected ? '在线' : '连接中...' }}</span>
      </div>
    </header>

    <main class="chat-main" ref="chatBox">
      <div class="message-list">
        
        <div class="message-wrapper ai">
          <img class="avatar" src="https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png" alt="AI">
          <div class="message-content">
            <div class="bubble">
              您好！我是 Poclain (波克兰液压) 智能技术支持。请问您需要查询哪款马达的技术参数？（例如：MG02参数、MS05最大扭矩）
            </div>
          </div>
        </div>

        <div 
          v-for="(msg, index) in messages" 
          :key="msg.id || index"
          class="message-wrapper"
          :class="msg.sender"
        >
          <img 
            v-if="msg.sender !== 'user'" 
            class="avatar" 
            :src="msg.sender === 'agent' ? 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png' : 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'" 
            alt="avatar"
          >
          
          <div class="message-content">
            <div class="role-tag" v-if="msg.sender === 'agent'">波克兰技术专员</div>
            
            <div class="bubble">
              <span class="text-content">{{ msg.content }}</span>
              <span v-if="msg.isStreaming" class="typing-cursor"></span>
            </div>
          </div>

          <img v-if="msg.sender === 'user'" class="avatar user-avatar" src="https://cube.elemecdn.com/9/c2/f0ee8a3c7c9638a54940382568c9dpng.png" alt="User">
        </div>
      </div>
    </main>

    <footer class="chat-footer">
      <div class="input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="1"
          autosize
          placeholder="输入您的问题..."
          @keyup.enter.native.prevent="sendMessage"
          :disabled="!wsConnected || isAITyping || isAuthenticating"
        />
        <el-button 
          type="primary" 
          class="send-btn" 
          @click="sendMessage"
          :disabled="!inputText.trim() || !wsConnected || isAITyping || isAuthenticating"
          :loading="isAITyping"
        >
          发送
        </el-button>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'

// --- 状态管理 ---
const wsConnected = ref(false)
const inputText = ref('')
const messages = ref([])
const chatBox = ref(null)
const isAITyping = ref(false)
const isAuthenticating = ref(true)

let openid = localStorage.getItem('wx_openid')

// ==========================================
// 🚨 架构师加固：微信 OAuth2.0 智能环境嗅探与授权引擎
// ==========================================
const initWechatAuth = async () => {
  if (openid) {
    // 已经有身份令牌，直接放行启动长连接
    isAuthenticating.value = false
    initWebSocket()
    return
  }

  // 环境嗅探：判断当前是云端生产环境还是本地开发环境
  const isLocalDev = import.meta.env.DEV || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  
  const urlParams = new URLSearchParams(window.location.search)
  const code = urlParams.get('code')

  // 场景 A：从微信授权页跳回，带有 code
  if (code) {
    try {
      const res = await fetch('/api/v1/wechat/h5/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code })
      })
      const data = await res.json()
      
      if (data.openid) {
        openid = data.openid
        localStorage.setItem('wx_openid', openid)
        
        // 物理擦除 URL 上的 code，保持地址栏干净，防止用户分享带 code 的废弃链接
        const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname
        window.history.replaceState({ path: cleanUrl }, '', cleanUrl)
        
        isAuthenticating.value = false
        initWebSocket()
      } else {
        throw new Error('OpenID 换取失败')
      }
    } catch (error) {
      console.error('授权接口崩溃:', error)
      ElMessage.error('微信身份认证失败，请重新进入')
      isAuthenticating.value = false
    }
  } 
  // 场景 B：本地开发环境，无 code，触发沙盒降级模式
  else if (isLocalDev) {
    console.warn('⚠️ 架构师拦截：检测到本地开发环境，已切断微信 OAuth 真实跳转，启用沙盒 Mock 身份...')
    try {
      // 传入空 code，精准触发你在后端 wechat.py 预留的 test_user_ 后门
      const res = await fetch('/api/v1/wechat/h5/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: '' }) 
      })
      const data = await res.json()
      openid = data.openid
      localStorage.setItem('wx_openid', openid)
      isAuthenticating.value = false
      initWebSocket()
    } catch (error) {
      console.error('本地 Mock 身份生成失败:', error)
      isAuthenticating.value = false
    }
  } 
  // 场景 C：线上生产环境，首次访问无 code，强制重定向至微信官方静默授权页
  else {
    // 🚨 必须在此处填入你在微信公众平台申请的真实 AppID
    const WX_APPID = 'YOUR_REAL_WECHAT_APPID_HERE' 
    const redirectUri = encodeURIComponent(window.location.href)
    // snsapi_base 为静默授权，不弹窗，仅获取 openid，用户体验无缝
    const authUrl = `https://open.weixin.qq.com/connect/oauth2/authorize?appid=${WX_APPID}&redirect_uri=${redirectUri}&response_type=code&scope=snsapi_base&state=STATE#wechat_redirect`
    
    console.log('🔗 正在执行微信生产级静默授权重定向...')
    window.location.replace(authUrl)
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatBox.value) {
    chatBox.value.scrollTop = chatBox.value.scrollHeight
  }
}

const sendMessage = () => {
  const text = inputText.value.trim()
  if (!text || !wsConnected.value || isAITyping.value) return

  messages.value.push({
    id: Date.now(),
    sender: 'user',
    content: text,
    isStreaming: false
  })
  scrollToBottom()

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: 'user_message',
      content: text
    }))
  }
  inputText.value = ''
}

// ==========================================
// 🚨 WebSocket 物理直连引擎
// ==========================================
let ws = null
let reconnectTimer = null
let heartbeatTimer = null
let lockReconnect = false
let isDestroyed = false

const initWebSocket = () => {
  if (isDestroyed || !openid) return

  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    ws.onclose = null; ws.onerror = null; ws.close(1000)
  }
  clearTimeout(reconnectTimer)
  clearInterval(heartbeatTimer)

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  let host = window.location.host
  
  if (import.meta.env.DEV && (host.includes('5173') || host.includes('localhost'))) {
    host = '127.0.0.1:8000' 
  }
  const wsUrl = `${protocol}//${host}/ws/service/customer/${openid}`
  
  console.log('🚀 正在执行 WSS/WS 物理连接路由:', wsUrl)

  try {
    ws = new WebSocket(wsUrl)
  } catch (e) {
    console.error('WebSocket 创建失败:', e)
    reconnect()
    return
  }

  ws.onopen = () => {
    if (isDestroyed) { ws.close(); return }
    wsConnected.value = true
    lockReconnect = false
    console.log(`✅ [H5 架构日志] 客户身份 [${openid}] 长连接已激活`)
    
    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === 1) {
        ws.send(JSON.stringify({ type: 'heartbeat' }))
      }
    }, 30000)
  }

  ws.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data)
      handleWsEvent(payload)
    } catch (e) {
      console.error('报文解析失败:', e)
    }
  }

  ws.onclose = () => {
    if (isDestroyed) return
    wsConnected.value = false
    clearInterval(heartbeatTimer)
    reconnect()
  }

  ws.onerror = () => {
    if (isDestroyed) return
    wsConnected.value = false
    reconnect()
  }
}

const reconnect = () => {
  if (isDestroyed || lockReconnect) return
  lockReconnect = true
  console.log('🔄 [H5 架构日志] 尝试重连服务器...')
  reconnectTimer = setTimeout(() => {
    lockReconnect = false
    initWebSocket()
  }, 3000)
}

const handleWsEvent = (payload) => {
  const { type, content } = payload
  switch (type) {
    case 'ai_stream_start':
      isAITyping.value = true
      messages.value.push({
        id: Date.now(),
        sender: 'ai',
        content: '',
        isStreaming: true
      })
      scrollToBottom()
      break
    case 'ai_stream_chunk':
      if (messages.value.length > 0) {
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg.sender === 'ai' && lastMsg.isStreaming) {
          lastMsg.content += content
          scrollToBottom()
        }
      }
      break
    case 'ai_stream_end':
      isAITyping.value = false
      if (messages.value.length > 0) {
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg.sender === 'ai') lastMsg.isStreaming = false
      }
      break
    case 'ai_reply':
      messages.value.push({ id: Date.now(), sender: 'ai', content: content, isStreaming: false })
      scrollToBottom()
      break
    case 'agent_reply':
      messages.value.push({ id: Date.now(), sender: 'agent', content: content, isStreaming: false })
      scrollToBottom()
      break
  }
}

onMounted(() => {
  isDestroyed = false
  // 挂载时优先执行授权引擎嗅探
  initWechatAuth()
})

onBeforeUnmount(() => {
  isDestroyed = true
  clearTimeout(reconnectTimer)
  clearInterval(heartbeatTimer)
  if (ws) {
    ws.onclose = null; ws.onerror = null
    if (ws.readyState === WebSocket.OPEN) ws.close(1000)
    ws = null
  }
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f3f4f6;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
.chat-header {
  background-color: #ffffff;
  padding: 12px 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  z-index: 10;
}
.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.brand {
  display: flex;
  align-items: center;
}
.brand h1 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #ef4444;
  margin-right: 8px;
  transition: background-color 0.3s;
}
.status-dot.connected { background-color: #10b981; }
.status-text {
  font-size: 12px;
  color: #6b7280;
}
.chat-main {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  scroll-behavior: smooth;
}
.message-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 20px;
}
.message-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  max-width: 90%;
}
.message-wrapper.user {
  align-self: flex-end;
  flex-direction: row;
}
.message-wrapper.ai { align-self: flex-start; }
.message-wrapper.agent { align-self: flex-start; }
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 4px;
  flex-shrink: 0;
}
.message-content {
  display: flex;
  flex-direction: column;
}
.role-tag {
  font-size: 11px;
  color: #059669;
  background: #d1fae5;
  padding: 2px 6px;
  border-radius: 4px;
  align-self: flex-start;
  margin-bottom: 4px;
}
.bubble {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 15px;
  line-height: 1.5;
  position: relative;
  word-break: break-word;
}
.text-content {
  white-space: pre-wrap; 
}
.ai .bubble, .agent .bubble {
  background-color: #ffffff;
  color: #1f2937;
  border: 1px solid #e5e7eb;
  border-top-left-radius: 0;
}
.agent .bubble { border-color: #10b981; }
.user .bubble {
  background-color: #95ec69;
  color: #111827;
  border-top-right-radius: 0;
}
.user .message-content { align-items: flex-end; }
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 15px;
  background-color: #1f2937;
  margin-left: 2px;
  vertical-align: middle;
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.chat-footer {
  background-color: #f9fafb;
  padding: 12px 16px;
  border-top: 1px solid #e5e7eb;
}
.input-area {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.send-btn {
  height: 32px;
  padding: 0 16px;
}
:deep(.el-textarea__inner) {
  border-radius: 16px;
  padding: 8px 12px;
  font-size: 15px;
  resize: none;
  max-height: 100px;
}
</style>