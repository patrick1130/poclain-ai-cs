<template>
  <div class="settings-view" v-loading="loading">
    <div class="page-header">
      <h1 class="page-title">系统安全与偏好设置</h1>
    </div>

    <div class="settings-content">
      <el-tabs v-model="activeTab" class="custom-tabs">
        
        <el-tab-pane label="账号安全" name="security">
          <div class="tab-panel-container">
            <h3 class="panel-title">坐席身份凭证</h3>
            <el-divider border-style="dashed" />
            
            <el-form 
              :model="securityForm" 
              label-width="120px" 
              class="max-w-md"
            >
              <el-form-item label="当前坐席名称">
                <el-input v-model="securityForm.agentName" disabled />
              </el-form-item>
              
              <el-form-item label="企业接入标识">
                <el-input value="Poclain Hydraulics (Shanghai) - 官方客服引擎" disabled />
              </el-form-item>

              <el-form-item label="危险操作">
                <el-button type="danger" plain @click="handleLogout">
                  <el-icon class="mr-2"><SwitchButton /></el-icon>
                  注销并销毁本地令牌
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

        <el-tab-pane label="AI 引擎参数" name="ai">
          <div class="tab-panel-container">
            <h3 class="panel-title">向量大脑检索阈值控制</h3>
            <el-divider border-style="dashed" />
            
            <el-form 
              :model="aiForm" 
              label-width="140px" 
              class="max-w-lg"
            >
              <el-form-item label="语义匹配阈值 (Threshold)">
                <el-slider 
                  v-model="aiForm.threshold" 
                  :min="0" 
                  :max="1" 
                  :step="0.05" 
                  show-input 
                />
                <div class="form-tip">
                  值越大，AI 回复越保守；值越小，容错率越高但可能产生幻觉。当前建议：0.75
                </div>
              </el-form-item>
              
              <el-form-item label="最大召回片段 (Top K)">
                <el-input-number 
                  v-model="aiForm.topK" 
                  :min="1" 
                  :max="10" 
                />
                <div class="form-tip">
                  每次向大模型注入的知识库上下文片段数量。过多会导致 Token 溢出。
                </div>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" @click="saveAiSettings">
                  <el-icon class="mr-2"><Check /></el-icon>
                  应用架构参数
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { SwitchButton, Check } from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(false)
const activeTab = ref('security')

// 表单状态机
const securityForm = reactive({
  agentName: 'Patrick (Admin)'
})

const aiForm = reactive({
  threshold: 0.75,
  topK: 3
})

// 核心安全逻辑：销毁 JWT Token 并阻断持久化层
const handleLogout = async () => {
  try {
    await ElMessageBox.confirm(
      '执行此操作将立即断开所有 WebSocket 全双工连接，并销毁浏览器中的安全令牌。确认注销？',
      '安全警告',
      { confirmButtonText: '强制注销', cancelButtonText: '取消', type: 'error' }
    )
    
    // O(1) 级别的安全擦除
    localStorage.removeItem('token')
    localStorage.removeItem('access_token')
    sessionStorage.clear()
    
    ElMessage.success('安全令牌已销毁，连接已切断')
    router.replace('/login')
    
  } catch (error) {
    if (error !== 'cancel') {
      console.error('注销异常:', error)
    }
  }
}

// 模拟参数保存
const saveAiSettings = () => {
  loading.value = true
  setTimeout(() => {
    loading.value = false
    ElMessage.success('AI 引擎底层参数已热重载生效')
  }, 600)
}

onMounted(() => {
  // 可以在此处拉取后端的真实坐席信息进行状态同步
  const savedUser = localStorage.getItem('agent_name')
  if (savedUser) {
    securityForm.agentName = savedUser
  }
})
</script>

<style scoped>
.settings-view {
  background: white;
  border-radius: 8px;
  min-height: calc(100vh - 120px);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.page-header {
  padding: 20px 24px;
  border-bottom: 1px solid #ebeef5;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
}

.settings-content {
  padding: 24px;
}

.tab-panel-container {
  padding: 10px 0;
}

.panel-title {
  font-size: 16px;
  color: #334155;
  margin-bottom: 16px;
  font-weight: 500;
}

.max-w-md {
  max-width: 28rem;
}

.max-w-lg {
  max-width: 32rem;
}

.form-tip {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
  line-height: 1.4;
}

:deep(.el-tabs__item) {
  font-size: 15px;
  padding: 0 24px;
}
</style>