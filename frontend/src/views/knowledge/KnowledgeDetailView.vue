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
        <h3 class="section-title">格式化语料内容</h3>
        <el-divider border-style="dashed" />
        <div class="doc-html-content markdown-body" v-html="safeHtmlContent"></div>
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
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Edit, Delete } from '@element-plus/icons-vue'
import axios from 'axios'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const route = useRoute()
const router = useRouter()
const docId = route.params.id
const loading = ref(false)
const document = ref(null)

const getToken = () => localStorage.getItem('access_token') || localStorage.getItem('token') || ''

const api = axios.create({ baseURL: '/api/v1', timeout: 15000 })
api.interceptors.request.use(config => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

const safeHtmlContent = computed(() => {
  if (!document.value || !document.value.content) return ''
  const rawHtml = marked.parse(document.value.content)
  return DOMPurify.sanitize(rawHtml)
})

const fetchDocumentDetail = async () => {
  if (!docId) return
  loading.value = true
  try {
    const res = await api.get(`/knowledge/docs/${docId}`)
    document.value = res.data
  } catch (error) {
    ElMessage.error('读取文档详情失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => router.push('/knowledge')
const goToEdit = () => router.push(`/knowledge/edit/${docId}`)

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm('确定要删除吗？', '警告', { type: 'error' })
    loading.value = true
    await api.delete(`/knowledge/docs/${docId}`)
    ElMessage.success('已擦除')
    router.replace('/knowledge')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  } finally {
    loading.value = false
  }
}

const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  })
}

onMounted(() => fetchDocumentDetail())
</script>

<style scoped>
.knowledge-detail-view { background: white; border-radius: 8px; padding: 24px; min-height: calc(100vh - 120px); box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1); }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #ebeef5; }
.header-left { display: flex; align-items: center; gap: 16px; }
.page-title { margin: 0; font-size: 20px; font-weight: 600; color: #1f2937; }
.meta-section { margin-bottom: 32px; }
:deep(.meta-label) { width: 120px; background-color: #f8fafc; color: #64748b; font-weight: 500; }
.content-section { margin-top: 24px; }
.section-title { font-size: 16px; color: #334155; margin-bottom: 16px; border-left: 4px solid #3b82f6; padding-left: 8px; }

/* 🚨 视觉重塑：手机端超长表格横向滚动与粘性表头适配 */
.doc-html-content {
  background-color: #ffffff;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  min-height: 300px;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
  overflow-x: hidden;
}

/* 核心：将 Table 转换为 block 并开启滚动 */
.doc-html-content :deep(table) {
  display: block;
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch; /* iOS 流畅滚动 */
  border-collapse: collapse;
  margin-bottom: 24px;
  border: 1px solid #e2e8f0;
}

/* 核心：固定表头 */
.doc-html-content :deep(thead) {
  position: sticky;
  top: 0;
  z-index: 2;
}

.doc-html-content :deep(th), 
.doc-html-content :deep(td) {
  border: 1px solid #cbd5e1;
  padding: 10px 14px;
  text-align: left;
  white-space: nowrap; /* 🚨 物理强制：单元格不换行，确保横向撑开滚动条 */
  min-width: 120px;
}

.doc-html-content :deep(th) {
  background-color: #f1f5f9; /* 必须设置背景色防止重叠 */
  font-weight: 600;
  color: #1e293b;
}

.doc-html-content :deep(tr:nth-child(even)) { background-color: #f8fafc; }
.doc-html-content :deep(tr:hover) { background-color: #f1f5f9; }

.doc-html-content :deep(h1), 
.doc-html-content :deep(h2), 
.doc-html-content :deep(h3) {
  margin-top: 24px;
  margin-bottom: 16px;
  font-weight: 600;
  color: #1e293b;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 8px;
}
</style>