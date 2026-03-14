<template>
  <div class="knowledge-edit-view" v-loading="loading">
    <div class="page-header">
      <div class="header-left">
        <el-button @click="goBack" icon="ArrowLeft" circle />
        <h1 class="page-title">编辑知识库文档</h1>
      </div>
      <div class="header-actions">
        <el-button @click="goBack">取消</el-button>
        <el-button type="primary" @click="submitUpdate" :loading="saving">
          <el-icon><Check /></el-icon>
          保存并重算向量
        </el-button>
      </div>
    </div>

    <div class="edit-container" v-if="editForm.id">
      <el-alert
        title="架构师警告：修改内容将触发底层 ChromaDB 向量数据库的切片重算与 I/O 覆写，请谨慎操作。"
        type="warning"
        show-icon
        :closable="false"
        class="warning-alert"
      />

      <el-form 
        :model="editForm" 
        :rules="rules" 
        ref="formRef" 
        label-position="top"
        class="main-form"
      >
        <el-row :gutter="24">
          <el-col :span="16">
            <el-form-item label="文档标题" prop="title">
              <el-input 
                v-model="editForm.title" 
                placeholder="请输入文档标题" 
                maxlength="100" 
                show-word-limit 
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="业务分类" prop="category">
              <el-autocomplete
                v-model="editForm.category"
                :fetch-suggestions="queryCategories"
                placeholder="输入或选择分类"
                class="w-full"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="原始语料内容 (TXT/Markdown)" prop="content">
          <el-input
            v-model="editForm.content"
            type="textarea"
            :rows="20"
            placeholder="在此编辑文档正文..."
            class="content-editor"
          />
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Check } from '@element-plus/icons-vue'
import axios from 'axios'

// 路由与状态初始化
const route = useRoute()
const router = useRouter()
const docId = route.params.id
const loading = ref(false)
const saving = ref(false)
const categories = ref([])
const formRef = ref(null)

// 响应式表单对象
const editForm = reactive({
  id: null,
  title: '',
  category: '',
  content: '',
  version: null
})

// 严格表单校验规则
const rules = {
  title: [{ required: true, message: '文档标题不能为空', trigger: 'blur' }],
  category: [{ required: true, message: '业务分类不能为空', trigger: 'blur' }],
  content: [{ required: true, message: '语料内容不能为空', trigger: 'blur' }]
}

// 鉴权配置
const getToken = () => localStorage.getItem('access_token') || localStorage.getItem('token') || ''
const api = axios.create({ baseURL: '/api/v1', timeout: 30000 }) // 放宽超时限制以应对向量运算
api.interceptors.request.use(config => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 核心业务：拉取详情进行回显
const fetchDocumentDetail = async () => {
  if (!docId) return
  loading.value = true
  try {
    const res = await api.get(`/knowledge/docs/${docId}`)
    const data = res.data
    editForm.id = data.id
    editForm.title = data.title
    editForm.category = data.category
    editForm.content = data.content
    editForm.version = data.version
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '读取文档失败，请检查网络')
    router.replace('/knowledge')
  } finally {
    loading.value = false
  }
}

// 核心业务：拉取全部分类供 Autocomplete 使用
const fetchCategories = async () => {
  try {
    const res = await api.get('/knowledge/categories')
    categories.value = res.data || []
  } catch (error) {
    console.error('获取分类失败:', error)
  }
}

const queryCategories = (queryString, cb) => {
  const results = queryString
    ? categories.value.filter(cat => cat.toLowerCase().includes(queryString.toLowerCase())).map(c => ({ value: c }))
    : categories.value.map(c => ({ value: c }))
  cb(results)
}

// 路由导航
const goBack = () => {
  // 如果内容被修改过，可以考虑在此处加入 unsaved changes 拦截
  router.go(-1)
}

// 核心业务：提交 PUT 更新，触发后端 Saga 向量覆写
const submitUpdate = () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    
    try {
      await ElMessageBox.confirm(
        '此操作将触发 AI 重新对文章进行切片并覆写底层向量数据，过程可能持续数秒。确认执行？',
        '向量覆写警告',
        { confirmButtonText: '执行重算', cancelButtonText: '取消', type: 'warning' }
      )
      
      saving.value = true
      const payload = {
        title: editForm.title,
        category: editForm.category,
        content: editForm.content
      }
      
      await api.put(`/knowledge/docs/${docId}`, payload)
      ElMessage.success('更新成功！新版本已同步至向量大脑。')
      
      // 更新完成后强制跳回详情页核对
      router.replace(`/knowledge/detail/${docId}`)
      
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error(error.response?.data?.detail || '更新或向量化失败，后端已触发自动回滚')
      }
    } finally {
      saving.value = false
    }
  })
}

// 挂载钩子
onMounted(() => {
  fetchDocumentDetail()
  fetchCategories()
})
</script>

<style scoped>
.knowledge-edit-view {
  background: white;
  border-radius: 8px;
  padding: 24px;
  min-height: calc(100vh - 120px);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
}

.warning-alert {
  margin-bottom: 24px;
}

.main-form {
  max-width: 1200px;
}

.w-full {
  width: 100%;
}

.content-editor :deep(.el-textarea__inner) {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
  background-color: #f8fafc;
  border: 1px solid #cbd5e1;
  padding: 16px;
}

.content-editor :deep(.el-textarea__inner:focus) {
  border-color: #3b82f6;
  background-color: #ffffff;
}
</style>