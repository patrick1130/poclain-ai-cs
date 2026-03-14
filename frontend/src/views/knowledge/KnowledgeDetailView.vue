<template>
  <div class="knowledge-detail-view" v-loading="loading">
    <div class="page-header">
      <div class="header-left">
        <el-button @click="goBack" icon="ArrowLeft" circle />
        <h1 class="page-title">文档详情</h1>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="goToEdit">
          <el-icon><Edit /></el-icon>
          编辑文档
        </el-button>
        <el-button type="danger" plain @click="handleDelete">
          <el-icon><Delete /></el-icon>
          彻底移除
        </el-button>
      </div>
    </div>

    <div class="detail-container" v-if="document">
      <div class="meta-section">
        <el-descriptions title="基础信息" :column="3" border>
          <el-descriptions-item label="文档标题" label-class-name="meta-label">
            <span class="font-bold text-gray-800">{{ document.title }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="业务分类" label-class-name="meta-label">
            <el-tag size="small" type="primary">{{ document.category }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="当前版本" label-class-name="meta-label">
            <el-tag size="small" type="info">v{{ document.version }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="入库时间" label-class-name="meta-label">
            {{ formatDateTime(document.create_time) }}
          </el-descriptions-item>
          <el-descriptions-item label="最后更新" label-class-name="meta-label">
            {{ formatDateTime(document.update_time || document.create_time) }}
          </el-descriptions-item>
          <el-descriptions-item label="系统标识" label-class-name="meta-label">
            UID-{{ document.id }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="content-section">
        <h3 class="section-title">原始语料内容</h3>
        <el-divider border-style="dashed" />
        <div class="doc-text-content">
          {{ document.content }}
        </div>
      </div>
    </div>

    <el-empty 
      v-if="!loading && !document" 
      description="未找到该文档，可能已被移除或网络异常" 
    >
      <el-button type="primary" @click="goBack">返回列表</el-button>
    </el-empty>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Edit, Delete } from '@element-plus/icons-vue'
import axios from 'axios'

// 路由与状态初始化
const route = useRoute()
const router = useRouter()
const docId = route.params.id
const loading = ref(false)
const document = ref(null)

// 鉴权配置
const getToken = () => localStorage.getItem('access_token') || localStorage.getItem('token') || ''

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000
})
api.interceptors.request.use(config => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 核心业务：拉取详情数据 (复杂度 O(1))
const fetchDocumentDetail = async () => {
  if (!docId) {
    ElMessage.error('缺少文档 ID 参数')
    return
  }
  loading.value = true
  try {
    const res = await api.get(`/knowledge/docs/${docId}`)
    document.value = res.data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '读取文档详情失败，请检查网络')
  } finally {
    loading.value = false
  }
}

// 路由导航
const goBack = () => {
  router.push('/knowledge')
}

const goToEdit = () => {
  router.push(`/knowledge/edit/${docId}`)
}

// 危险操作：删除
const handleDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要将文档【${document.value?.title}】彻底删除吗？AI 向量大脑将被同步擦除。`,
      '危险操作确认',
      { confirmButtonText: '强制删除', cancelButtonText: '取消', type: 'error' }
    )
    
    loading.value = true
    await api.delete(`/knowledge/docs/${docId}`)
    ElMessage.success('文档已彻底擦除')
    router.replace('/knowledge') // 删除后强制退回列表，防止停留在空页
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败，请重试')
    }
  } finally {
    loading.value = false
  }
}

// 日期格式化
const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
}

// 挂载钩子
onMounted(() => {
  fetchDocumentDetail()
})
</script>

<style scoped>
.knowledge-detail-view {
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

.meta-section {
  margin-bottom: 32px;
}

:deep(.meta-label) {
  width: 120px;
  background-color: #f8fafc;
  color: #64748b;
  font-weight: 500;
}

.content-section {
  margin-top: 24px;
}

.section-title {
  font-size: 16px;
  color: #334155;
  margin-bottom: 16px;
  border-left: 4px solid #3b82f6;
  padding-left: 8px;
}

.doc-text-content {
  font-size: 14px;
  line-height: 1.8;
  color: #334155;
  white-space: pre-wrap; /* 核心防御：防止 XSS 并保留换行排版 */
  word-wrap: break-word;
  background-color: #f8fafc;
  padding: 24px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  min-height: 300px;
}
</style>