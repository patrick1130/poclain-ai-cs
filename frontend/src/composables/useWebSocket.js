import { ref, onUnmounted } from 'vue'

export function useWebSocket() {
  const socket = ref(null)
  const isConnected = ref(false)
  // 【内存修复】使用 Set 替代 Array，天然免疫同一个回调函数的重复注册
  const messageListeners = new Set()
  const reconnectTimer = ref(null)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000 // 3秒

  // 【架构补全】心跳计时器，防御 NAT 老化与 Nginx 静默断流
  const heartbeatTimer = ref(null)
  const HEARTBEAT_INTERVAL = 30000 // 30秒心跳脉冲

  // 连接WebSocket
  const connect = (url) => {
    // 【并发修复】如果已经处于连接或正在连接状态，直接拦截，防止握手风暴
    if (socket.value && (socket.value.readyState === WebSocket.OPEN || socket.value.readyState === WebSocket.CONNECTING)) {
      return
    }

    // 【安全修复】强行读取本地 Token 并在握手阶段注入，打破鉴权真空
    const token = localStorage.getItem('token')
    if (!token) {
      console.error('WebSocket 握手阻断: 缺少鉴权 Token，请先登录')
      return
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const separator = url.includes('?') ? '&' : '?'

    // ==========================================
    // 【核心修复：环境智能穿透】
    // 强制绕过 Vite 代理的劫持，开发环境下直连后端 8000 真实端口
    // ==========================================
    let wsHost = window.location.host
    if (wsHost.includes('5173') || wsHost.includes('localhost') || wsHost.includes('127.0.0.1')) {
      wsHost = '127.0.0.1:8000'
    }

    const wsUrl = `${wsProtocol}//${wsHost}${url}${separator}token=${token}`

    socket.value = new WebSocket(wsUrl)

    // 连接打开
    socket.value.onopen = () => {
      console.log('✅ WebSocket 连接已建立，鉴权通过，直连目标:', wsHost)
      isConnected.value = true
      reconnectAttempts.value = 0

      // 清除重连定时器
      if (reconnectTimer.value) {
        clearTimeout(reconnectTimer.value)
        reconnectTimer.value = null
      }

      // 【网络防线】连接成功后，立即启动心跳脉冲
      startHeartbeat()

      // 发送连接成功事件
      notifyListeners({
        type: 'connection',
        status: 'connected'
      })
    }

    // 接收消息
    socket.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) // 【安全修复】强制规范化反序列化

        // 拦截底层的 pong 心跳回执，不向业务层抛出，避免脏数据污染 UI
        if (data.type === 'pong') {
          return
        }

        notifyListeners(data)
      } catch (error) {
        console.error('解析 WebSocket 消息失败:', error)
      }
    }

    // 连接关闭
    socket.value.onclose = (event) => {
      console.log('⚠️ WebSocket 连接已关闭:', event.code, event.reason)
      isConnected.value = false

      // 【资源回收】连接断开必须停止心跳，防止内存泄漏
      stopHeartbeat()

      // 发送连接关闭事件
      notifyListeners({
        type: 'connection',
        status: 'disconnected',
        code: event.code,
        reason: event.reason
      })

      // 尝试重连 (非正常关闭时)
      if (event.code !== 1000 && reconnectAttempts.value < maxReconnectAttempts) {
        reconnect(url)
      }
    }

    // 连接错误
    socket.value.onerror = (error) => {
      console.error('❌ WebSocket 连接错误:', error)

      // 发送连接错误事件
      notifyListeners({
        type: 'connection',
        status: 'error',
        error: error
      })
    }
  }

  // 断开WebSocket连接
  const disconnect = () => {
    // 取消重连计时器
    if (reconnectTimer.value) {
      clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }

    // 彻底销毁心跳脉冲引擎
    stopHeartbeat()

    if (socket.value) {
      // 正常关闭连接
      socket.value.close(1000, 'Normal Closure')
      socket.value = null
    }
    isConnected.value = false
    messageListeners.clear() // 清空所有监听器
  }

  // 重连
  const reconnect = (url) => {
    if (reconnectTimer.value) {
      clearTimeout(reconnectTimer.value)
    }
    reconnectAttempts.value++
    console.log(`🔄 尝试重连 (${reconnectAttempts.value}/${maxReconnectAttempts})...`)

    reconnectTimer.value = setTimeout(() => {
      connect(url)
    }, reconnectDelay)
  }

  // 【核心补全】启动心跳引擎
  const startHeartbeat = () => {
    stopHeartbeat()
    heartbeatTimer.value = setInterval(() => {
      if (isConnected.value && socket.value) {
        // 与后端 service.py 约定的心跳探针协议
        sendMessage({ type: 'ping' })
      }
    }, HEARTBEAT_INTERVAL)
  }

  // 【核心补全】停止心跳引擎
  const stopHeartbeat = () => {
    if (heartbeatTimer.value) {
      clearInterval(heartbeatTimer.value)
      heartbeatTimer.value = null
    }
  }

  // 发送消息
  const sendMessage = (message) => {
    if (socket.value && isConnected.value) {
      try {
        const messageString = typeof message === 'string' ? message : JSON.stringify(message)
        socket.value.send(messageString)
        return true
      } catch (error) {
        console.error('发送 WebSocket 消息失败:', error)
        return false
      }
    } else {
      console.error('WebSocket 未连接，无法发送消息')
      return false
    }
  }

  // 添加消息监听器
  const onMessage = (callback) => {
    if (typeof callback === 'function') {
      messageListeners.add(callback)

      // 返回取消监听的函数
      return () => {
        messageListeners.delete(callback)
      }
    }
    return () => { }
  }

  // 通知所有监听器
  const notifyListeners = (data) => {
    messageListeners.forEach(callback => {
      try {
        callback(data)
      } catch (error) {
        console.error('执行 WebSocket 消息监听器失败:', error)
      }
    })
  }

  // 组件卸载时断开连接，彻底防备 OOM 内存泄漏
  onUnmounted(() => {
    disconnect()
  })

  return {
    socket,
    isConnected,
    connect,
    disconnect,
    sendMessage,
    onMessage
  }
}