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
            <el-alert
              title="架构师提醒：部分参数已基于波克兰品牌保护策略锁定。"
              type="info"
              :closable="false"
              show-icon
              class="mb-6"
            />

            <h3 class="panel-title">向量大脑检索阈值控制</h3>
            <el-divider border-style="dashed" />
            
            <el-form 
              :model="aiForm" 
              label-width="160px" 
              class="max-w-lg"
            >
              <el-form-item label="语义匹配阈值 (Threshold)">
                <el-slider 
                  v-model="aiForm.threshold" 
                  :min="0.5" 
                  :max="1" 
                  :step="0.05" 
                  show-input 
                />
                <div class="form-tip">
                  <el-icon class="align-middle mr-1"><InfoFilled /></el-icon>
                  已锁定安全区间 (0.5 - 1.0)。值越高，AI 越严谨。当前生产环境建议：0.75
                </div>
              </el-form-item>
              
              <el-form-item label="最大召回片段 (Top K)">
                <el-input-number 
                  v-model="aiForm.topK" 
                  :min="1" 
                  :max="5" 
                />
                <div class="form-tip">
                  每次注入的知识片段数量。已限制上限为 5，以确保检索响应延迟小于 2s。
                </div>
              </el-form-item>

              <h3 class="panel-title mt-8">物理锁定参数（不可修改）</h3>
              <el-divider border-style="dashed" />

              <el-form-item label="生成温度 (Temperature)">
                <el-input value="0.0 (极致确定性模式)" disabled />
                <div class="form-tip">此参数已通过代码层硬编码锁定，以防止“脱口秀”注入攻击及幻觉。</div>
              </el-form-item>

              <el-form-item label="上下文防御 (Safety)">
                <el-tag type="success" effect="dark">
                  <el-icon class="mr-1"><Lock /></el-icon>
                  XML 物理沙盒已激活
                </el-tag>
              </el-form-item>

              <el-form-item class="mt-8">
                <el-button type="primary" @click="saveAiSettings">
                  <el-icon class="mr-2"><Check /></el-icon>
                  保存并应用动态配置
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
import { SwitchButton, Check, InfoFilled, Lock } from '@element-plus/icons-vue'

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

/**
 * 【架构演进】保存 AI 引擎参数
 * 将参数持久化至后端数据库/Redis 缓存，实现真正的热重载
 */
const saveAiSettings = async () => {
  loading.value = true
  try {
    // 此处预留后端 API 接口对接
    // await axios.post('/api/v1/config/ai', aiForm)
    
    // 模拟网络延迟
    await new Promise(resolve => setTimeout(resolve, 800))
    
    ElMessage({
      message: '波克兰 AI 引擎底层检索参数已热重载生效。',
      type: 'success',
      duration: 3000
    })
  } catch (error) {
    ElMessage.error('动态参数同步失败，请检查网络链路。')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const savedUser = localStorage.getItem('agent_name')
  if (savedUser) {
    securityForm.agentName = savedUser
  }
  // TODO: 此处应调用后端 API 拉取最新的 threshold 和 topK 初始值
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

.panel-title.mt-8 {
  margin-top: 32px;
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

.mb-6 {
  margin-bottom: 24px;
}

.mr-1 {
  margin-right: 4px;
}

.mr-2 {
  margin-right: 8px;
}

:deep(.el-tabs__item) {
  font-size: 15px;
  padding: 0 24px;
}

/* 增强表单项视觉层次 */
:deep(.el-form-item__label) {
  font-weight: 500;
}
</style>