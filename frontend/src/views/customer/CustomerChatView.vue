<template>
  <div class="chat-container" v-loading="isAuthenticating">
    <header class="chat-header">
      <div class="header-content">
        <div class="brand">
          <span class="status-dot" :class="{ 'connected': wsConnected }"></span>
          <h1>Poclain Official Tech Support</h1>
        </div>
        <span class="status-text">{{ wsConnected ? 'Online' : 'Connecting...' }}</span>
      </div>
    </header>

    <main class="chat-main" ref="chatBox">
      <div class="message-list">
        <div class="message-wrapper ai">
          <img class="avatar" src="https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png" alt="AI">
          <div class="message-content">
            <div class="bubble">
              您好！我是波克兰 (Poclain) 官方智能助手。请问今天有什么我可以帮您？您可以直接向我咨询产品选型、技术参数、或售后维修事宜。
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
            <div class="role-tag" v-if="msg.sender === 'agent'">Poclain Tech Specialist</div>
            
            <div class="bubble">
              <div 
                v-if="msg.sender !== 'user'" 
                class="markdown-body" 
                v-html="renderMarkdown(msg.content)"
              ></div>
              <span v-else class="text-content">{{ msg.content }}</span>
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
          placeholder="Describe your issue..."
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
          Send
        </el-button>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const wsConnected = ref(false)
const inputText = ref('')
const messages = ref([])
const chatBox = ref(null)
const isAITyping = ref(false)
const isAuthenticating = ref(true)

const getStoredOpenid = () => localStorage.getItem('wx_openid')
let openid = getStoredOpenid()

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (content) => {
  if (!content) return ''
  const rawHtml = marked.parse(content)
  return DOMPurify.sanitize(rawHtml)
}

const initWechatAuth = async () => {
  openid = getStoredOpenid()
  if (openid && openid !== 'undefined') {
    isAuthenticating.value = false
    initWebSocket()
    return
  }
  
  const isLocalDev = import.meta.env.DEV || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  const urlParams = new URLSearchParams(window.location.search)
  const code = urlParams.get('code')

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
        const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname
        window.history.replaceState({ path: cleanUrl }, '', cleanUrl)
        isAuthenticating.value = false
        initWebSocket()
      }
    } catch (error) {
      console.error("Auth Failed:", error)
      isAuthenticating.value = false
    }
  } else if (isLocalDev) {
    openid = `test_user_${Math.random().toString(36).substr(2, 9)}`
    localStorage.setItem('wx_openid', openid)
    isAuthenticating.value = false
    initWebSocket()
  } else {
    if (!navigator.userAgent.toLowerCase().includes('micromessenger')) {
      openid = `h5_guest_${Date.now()}`
      localStorage.setItem('wx_openid', openid)
      isAuthenticating.value = false
      initWebSocket()
    } else {
      const WX_APPID = 'YOUR_REAL_WECHAT_APPID_HERE' 
      const redirectUri = encodeURIComponent(window.location.href)
      window.location.replace(`https://open.weixin.qq.com/connect/oauth2/authorize?appid=${WX_APPID}&redirect_uri=${redirectUri}&response_type=code&scope=snsapi_base&state=STATE#wechat_redirect`)
    }
  }
}

const scrollToBottom = async (behavior = 'auto') => {
  await nextTick()
  if (chatBox.value) {
    chatBox.value.scrollTo({ top: chatBox.value.scrollHeight, behavior: behavior })
  }
}

const sendMessage = () => {
  const text = inputText.value.trim()
  if (!text || !wsConnected.value || isAITyping.value) return

  messages.value.push({ id: Date.now(), sender: 'user', content: text, isStreaming: false })
  scrollToBottom('smooth')

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'user_message', content: text }))
  }
  inputText.value = ''
}

let ws = null
let reconnectTimer = null
let heartbeatTimer = null
let lockReconnect = false
let isDestroyed = false

const initWebSocket = () => {
  if (isDestroyed || !openid || openid === 'undefined') return
  if (ws) { ws.onclose = null; ws.onerror = null; ws.close() }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const currentHost = window.location.host 
  const wsUrl = `${protocol}//${currentHost}/ws/service/customer/${openid}`

  try {
    ws = new WebSocket(wsUrl)
    ws.onopen = () => {
      wsConnected.value = true
      lockReconnect = false
      if (heartbeatTimer) clearInterval(heartbeatTimer)
      heartbeatTimer = setInterval(() => {
        if (ws?.readyState === 1) ws.send(JSON.stringify({ type: 'heartbeat' }))
      }, 30000)
    }
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data)
      handleWsEvent(payload)
    }
    ws.onclose = () => { wsConnected.value = false; reconnect() }
    ws.onerror = () => { wsConnected.value = false; reconnect() }
  } catch (e) { reconnect() }
}

const reconnect = () => {
  if (isDestroyed || lockReconnect) return
  lockReconnect = true
  clearTimeout(reconnectTimer)
  reconnectTimer = setTimeout(() => { lockReconnect = false; initWebSocket() }, 3000)
}

const handleWsEvent = (payload) => {
  const { type, content } = payload
  switch (type) {
    case 'ai_stream_start':
      isAITyping.value = true
      messages.value.push({ id: Date.now(), sender: 'ai', content: '', isStreaming: true })
      scrollToBottom('auto')
      break
    case 'ai_stream_chunk':
      if (messages.value.length > 0) {
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg.isStreaming) {
          lastMsg.content += content
          scrollToBottom('auto')
        }
      }
      break
    case 'ai_stream_end':
      isAITyping.value = false
      if (messages.value.length > 0) messages.value[messages.value.length - 1].isStreaming = false
      scrollToBottom('smooth')
      break
    case 'ai_reply':
    case 'agent_reply':
      messages.value.push({ id: Date.now(), sender: type.split('_')[0], content: content, isStreaming: false })
      scrollToBottom('smooth')
      break
  }
}

onMounted(() => { isDestroyed = false; initWechatAuth() })
onBeforeUnmount(() => {
  isDestroyed = true
  clearTimeout(reconnectTimer)
  clearInterval(heartbeatTimer)
  if (ws) ws.close()
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  /* 🚨 架构师边界防御：针对 iPhone 14 无刘海设计，顶部紧贴边缘，底部使用 env 安全区防止 Home 条碰撞 */
  padding-top: 0; 
  padding-bottom: env(safe-area-inset-bottom);
  background-color: #f5f7fa;
}
.chat-header {
  background: #fff;
  padding: 12px 16px;
  border-bottom: 1px solid #eef2f7;
}
.header-content { display: flex; justify-content: space-between; align-items: center; }
.brand h1 { margin: 0; font-size: 16px; font-weight: 600; color: #1a202c; }
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e0;
  margin-right: 6px;
}
.status-dot.connected { background: #48bb78; box-shadow: 0 0 8px rgba(72,187,120,0.4); }
.chat-main {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #f8fafc;
}
.message-list { display: flex; flex-direction: column; gap: 20px; }
.message-wrapper { display: flex; gap: 12px; max-width: 88%; }
.message-wrapper.user { align-self: flex-end; flex-direction: row; }
.avatar { width: 38px; height: 38px; border-radius: 8px; flex-shrink: 0; }
.bubble {
  padding: 12px 16px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  font-size: 15px;
}
.user .bubble {
  background: #0052d9;
  color: #fff;
  border: none;
  border-top-right-radius: 2px;
}
.ai .bubble { border-top-left-radius: 2px; }
.markdown-body :deep(table) { width: 100%; border-collapse: collapse; margin: 10px 0; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid #e2e8f0; padding: 6px 10px; font-size: 13px; }
.markdown-body :deep(th) { background: #f7fafc; }
.chat-footer { padding: 12px 16px; background: #fff; border-top: 1px solid #eef2f7; }
.input-area { display: flex; gap: 10px; align-items: flex-end; }
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 16px;
  background: #0052d9;
  margin-left: 4px;
  animation: blink 1s infinite;
}
@keyframes blink { 50% { opacity: 0; } }
:deep(.el-textarea__inner) { border-radius: 20px; background: #f1f5f9; border: none; padding: 8px 16px; }
</style>