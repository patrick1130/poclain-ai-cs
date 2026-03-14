<template>
  <div class="message-list">
    <div v-if="messages.length === 0" class="empty-messages">
      <el-empty description="暂无消息" />
      <div class="empty-tips">
        <p class="text-sm text-gray-500">开始与用户的对话吧</p>
      </div>
    </div>
    
    <div v-else class="messages-container" ref="messagesContainer">
      <div
        v-for="(message, index) in messages"
        :key="message.id || index"
        class="message-item"
        :class="{
          'user-message': message.sender === 'user',
          'service-message': message.sender === 'service',
          'ai-message': message.sender === 'ai',
          'system-message': message.sender === 'system'
        }"
      >
        <!-- 系统消息 -->
        <div v-if="message.sender === 'system'" class="system-message-content">
          <div class="system-message-text">
            {{ message.content }}
          </div>
          <div class="system-message-time">
            {{ formatTime(message.created_at) }}
          </div>
        </div>
        
        <!-- 用户消息 -->
        <div v-else-if="message.sender === 'user'" class="message-content">
          <div class="message-avatar">
            <el-avatar :size="36" :src="message.user_avatar || defaultAvatar">
              {{ message.user_name?.charAt(0) || 'U' }}
            </el-avatar>
          </div>
          <div class="message-body">
            <div class="message-user">{{ message.user_name || '用户' }}</div>
            <div class="message-text">{{ message.content }}</div>
            <div class="message-time">{{ formatTime(message.created_at) }}</div>
          </div>
        </div>
        
        <!-- 客服消息 -->
        <div v-else-if="message.sender === 'service'" class="message-content">
          <div class="message-body service-body">
            <div class="message-user">我 (客服)</div>
            <div class="message-text service-text">{{ message.content }}</div>
            <div class="message-time">{{ formatTime(message.created_at) }}</div>
          </div>
          <div class="message-avatar">
            <el-avatar :size="36" :src="serviceAvatar">
              {{ serviceName?.charAt(0) || 'S' }}
            </el-avatar>
          </div>
        </div>
        
        <!-- AI消息 -->
        <div v-else-if="message.sender === 'ai'" class="message-content">
          <div class="message-body ai-body">
            <div class="message-user">AI助手</div>
            <div class="message-text ai-text">{{ message.content }}</div>
            <div class="message-time">{{ formatTime(message.created_at) }}</div>
          </div>
          <div class="message-avatar">
            <el-avatar :size="36" :src="aiAvatar">
              AI
            </el-avatar>
          </div>
        </div>
      </div>
      
      <!-- 正在输入指示器 -->
      <div v-if="isTyping" class="typing-indicator">
        <div class="message-content">
          <div class="message-avatar">
            <el-avatar :size="36" :src="typingAvatar">
              {{ typingSender === 'ai' ? 'AI' : (serviceName?.charAt(0) || 'S') }}
            </el-avatar>
          </div>
          <div class="message-body">
            <div class="message-text typing-text">
              <span class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, watch, nextTick, onMounted } from 'vue'

export default {
  name: 'MessageList',
  props: {
    messages: {
      type: Array,
      default: () => []
    },
    isTyping: {
      type: Boolean,
      default: false
    },
    typingSender: {
      type: String,
      default: 'ai'
    },
    serviceName: {
      type: String,
      default: ''
    },
    serviceAvatar: {
      type: String,
      default: ''
    }
  },
  setup(props) {
    const messagesContainer = ref(null)
    const defaultAvatar = 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'
    const aiAvatar = 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png'

    // 格式化时间
    const formatTime = (timeString) => {
      if (!timeString) return ''
      const date = new Date(timeString)
      return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
      })
    }

    // 滚动到底部
    const scrollToBottom = () => {
      nextTick(() => {
        if (messagesContainer.value) {
          messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
        }
      })
    }

    // 监听消息变化，自动滚动到底部
    watch(() => props.messages.length, () => {
      scrollToBottom()
    })

    // 监听正在输入状态
    watch(() => props.isTyping, () => {
      if (props.isTyping) {
        scrollToBottom()
      }
    })

    // 组件挂载时滚动到底部
    onMounted(() => {
      scrollToBottom()
    })

    return {
      messagesContainer,
      defaultAvatar,
      aiAvatar,
      formatTime,
      scrollToBottom
    }
  }
}
</script>

<style scoped>
.message-list {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-messages {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
}

.empty-tips {
  margin-top: 16px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-item {
  display: flex;
  flex-direction: column;
}

.system-message-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 16px;
  margin: 8px 0;
}

.system-message-text {
  background-color: #f3f4f6;
  color: #6b7280;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  text-align: center;
}

.system-message-time {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 4px;
}

.message-content {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.user-message .message-content {
  flex-direction: row;
}

.service-message .message-content,
.ai-message .message-content {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.message-body {
  max-width: 70%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.service-body,
.ai-body {
  align-items: flex-end;
}

.message-user {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}

.message-text {
  background-color: #f3f4f6;
  padding: 8px 12px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.4;
  word-wrap: break-word;
  white-space: pre-wrap;
}

.service-text {
  background-color: #3b82f6;
  color: white;
}

.ai-text {
  background-color: #10b981;
  color: white;
}

.message-time {
  font-size: 11px;
  color: #9ca3af;
}

.typing-indicator {
  opacity: 0.7;
}

.typing-text {
  background-color: #f3f4f6;
  padding: 8px 12px;
  border-radius: 16px;
  font-size: 14px;
}

.typing-dots {
  display: flex;
  gap: 2px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  background-color: #6b7280;
  border-radius: 50%;
  animation: typing 1.4s infinite both;
}

.typing-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

/* 滚动条样式 */
.messages-container::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: #a1a1a1;
}
</style>