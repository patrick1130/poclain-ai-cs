<template>
  <div class="message-input">
    <div class="quick-replies" v-if="showQuickReplies && quickReplies.length > 0">
      <div class="quick-replies-header">
        <span class="text-sm font-medium">快捷回复</span>
        <el-button
          link
          size="small"
          @click="showQuickReplies = false"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
      <div class="quick-replies-list">
        <el-button
          v-for="(reply, index) in quickReplies"
          :key="index"
          size="small"
          type="default"
          plain
          @click="useQuickReply(reply)"
          class="quick-reply-item"
        >
          {{ reply }}
        </el-button>
      </div>
    </div>
    
    <div class="input-area">
      <div class="input-toolbar">
        <div class="input-tools">
          <el-button
            link
            size="small"
            @click="toggleQuickReplies"
            :class="{ 'active': showQuickReplies }"
          >
            <el-icon><ChatLineSquare /></el-icon>
          </el-button>
          
          <el-button
            link
            size="small"
            @click="insertEmoji"
          >
            <el-icon><SmileFilled /></el-icon>
          </el-button>
        </div>
        
        <div class="input-actions">
          <el-button
            type="primary"
            size="small"
            @click="sendMessage"
            :disabled="!messageText.trim()"
          >
            发送
          </el-button>
        </div>
      </div>
      
      <el-input
        v-model="messageText"
        type="textarea"
        :rows="3"
        placeholder="输入消息..."
        resize="none"
        @keydown.enter.prevent="handleEnterKey"
      />
    </div>
  </div>
</template>

<script>
import { ref, defineProps, defineEmits } from 'vue'
import { ElMessage } from 'element-plus'
import { Close, ChatLineSquare, SmileFilled } from '@element-plus/icons-vue'

export default {
  name: 'MessageInput',
  props: {
    disabled: {
      type: Boolean,
      default: false
    }
  },
  emits: ['send-message'],
  setup(props, { emit }) {
    const messageText = ref('')
    const showQuickReplies = ref(false)
    const quickReplies = ref([
      '您好，很高兴为您服务！',
      '请问有什么可以帮助您的吗？',
      '请稍等，我正在为您查询相关信息。',
      '感谢您的理解与支持！',
      '如有其他问题，随时可以咨询我们。',
      '祝您生活愉快！'
    ])

    // 发送消息
    const sendMessage = () => {
      if (!messageText.value.trim()) {
        ElMessage.warning('请输入消息内容')
        return
      }

      if (props.disabled) {
        ElMessage.warning('当前无法发送消息')
        return
      }

      emit('send-message', messageText.value.trim())
      messageText.value = ''
    }

    // 处理回车键
    const handleEnterKey = (event) => {
      // Shift+Enter 换行
      if (event.shiftKey) {
        return
      }
      // Enter 发送
      sendMessage()
    }

    // 切换快捷回复
    const toggleQuickReplies = () => {
      showQuickReplies.value = !showQuickReplies.value
    }

    // 使用快捷回复
    const useQuickReply = (reply) => {
      messageText.value = reply
      showQuickReplies.value = false
      // 聚焦到输入框
      setTimeout(() => {
        const textarea = document.querySelector('.message-input textarea')
        if (textarea) {
          textarea.focus()
        }
      }, 100)
    }

    // 插入表情
    const insertEmoji = () => {
      // 这里可以实现表情选择器
      // 简单示例：插入一个笑脸表情
      messageText.value += '😊'
    }

    return {
      messageText,
      showQuickReplies,
      quickReplies,
      sendMessage,
      handleEnterKey,
      toggleQuickReplies,
      useQuickReply,
      insertEmoji
    }
  }
}
</script>

<style scoped>
.message-input {
  border-top: 1px solid #e5e7eb;
  background: #fff;
}

.quick-replies {
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
}

.quick-replies-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid #e5e7eb;
}

.quick-replies-list {
  padding: 8px 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 120px;
  overflow-y: auto;
}

.quick-reply-item {
  margin: 0;
}

.input-area {
  padding: 16px;
}

.input-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.input-tools {
  display: flex;
  gap: 8px;
}

.input-actions {
  display: flex;
  gap: 8px;
}

.input-tools .el-button.active {
  color: #3b82f6;
  background-color: #eff6ff;
}

.input-tools .el-button:hover {
  background-color: #f3f4f6;
}

.el-textarea {
  width: 100%;
}

.el-textarea__inner {
  border-radius: 8px;
  resize: none;
}

.el-textarea__inner:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}
</style>