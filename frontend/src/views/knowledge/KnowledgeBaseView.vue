<template>
  <div class="knowledge-base">
    <div class="page-header">
      <h1 class="page-title">知识库管理</h1>
      <div class="header-actions">
        <el-button type="primary" @click="handleUpload">
          <el-icon><Upload /></el-icon>
          上传文档
        </el-button>
        <el-button @click="handleRefresh" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="search-filters">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索文档标题或内容..."
            clearable
            @input="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="6">
          <el-select
            v-model="categoryFilter"
            placeholder="筛选业务分类"
            clearable
            @change="handleFilter"
          >
            <el-option label="全部" value="" />
            <el-option
              v-for="cat in categories"
              :key="cat"
              :label="cat"
              :value="cat"
            />
          </el-select>
        </el-col>
        <el-col :span="10">
          <div class="filter-info">
            <span class="text-sm text-gray-600">
              当前共检索到 <span class="text-blue-600 font-bold">{{ total }}</span> 份有效知识库文档
            </span>
          </div>
        </el-col>
      </el-row>
    </div>

    <div class="document-list">
      <el-table
        v-loading="loading"
        :data="documents"
        style="width: 100%"
        border
        stripe
      >
        <el-table-column
          prop="title"
          label="文档标题"
          min-width="250"
        >
          <template #default="scope">
            <div class="document-title">
              <el-icon class="document-icon"><Document /></el-icon>
              <span class="title-text">{{ scope.row.title }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column
          prop="category"
          label="业务分类"
          width="150"
          align="center"
        >
          <template #default="scope">
            <el-tag size="small" type="primary" effect="light">
              {{ scope.row.category }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column
          prop="version"
          label="版本迭代"
          width="100"
          align="center"
        >
          <template #default="scope">
            <el-tag size="small" type="info">v{{ scope.row.version }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column
          prop="create_time"
          label="入库时间"
          width="180"
          align="center"
        >
          <template #default="scope">
            {{ formatDateTime(scope.row.create_time) }}
          </template>
        </el-table-column>

        <el-table-column
          label="操作"
          width="180"
          align="center"
          fixed="right"
        >
          <template #default="scope">
            <el-button
              size="small"
              type="primary"
              plain
              @click="handleView(scope.row)"
            >
              <el-icon><View /></el-icon>
              查看
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="handleDelete(scope.row)"
            >
              <el-icon><Delete /></el-icon>
              移除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.currentPage"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <el-dialog
      v-model="uploadDialogVisible"
      title="上传知识库文档"
      width="500px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form :model="uploadForm" ref="uploadFormRef" label-width="80px">
        <el-form-item 
          label="文档分类" 
          prop="category" 
          :rules="[{ required: true, message: '请填写或选择文档分类', trigger: 'blur' }]"
        >
          <el-autocomplete
            v-model="uploadForm.category"
            :fetch-suggestions="queryCategories"
            placeholder="例如：MS18马达说明书、保修政策..."
            class="w-full"
          />
        </el-form-item>

        <el-form-item label="文档文件" required>
          <el-upload
            ref="uploadRef"
            class="upload-demo"
            :headers="{ Authorization: `Bearer ${getToken()}` }"
            :action="uploadUrl"
            :data="{ category: uploadForm.category }"
            :multiple="false"
            :limit="1"
            :auto-upload="false"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            accept=".txt,.md"
          >
            <template #trigger>
              <el-button type="primary" plain>
                <el-icon><Upload /></el-icon>选取文件
              </el-button>
            </template>
            <template #tip>
              <div class="el-upload__tip text-gray-500 mt-2">
                目前仅支持上传 .txt 或 .md 格式的纯文本文件。<br>
                单个文件大小严禁超过 10MB。上传后将自动切片并写入向量大脑。
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="uploadDialogVisible = false">取消</el-button>
          <el-button 
            type="primary" 
            @click="submitUpload" 
            :loading="uploading"
            :disabled="!hasFile"
          >
            开始入库
          </el-button>
        </span>
      </template>
    </el-dialog>

    <el-drawer
      v-model="drawerVisible"
      :title="currentDoc?.title || '文档详情'"
      size="50%"
      direction="rtl"
      destroy-on-close
    >
      <div v-loading="drawerLoading" class="drawer-content-wrapper">
        <template v-if="currentDoc">
          <div class="doc-meta-header">
            <el-tag size="small" type="primary">{{ currentDoc.category }}</el-tag>
            <el-tag size="small" type="info">v{{ currentDoc.version }}</el-tag>
            <span class="meta-time">入库时间: {{ formatDateTime(currentDoc.create_time) }}</span>
          </div>
          <el-divider border-style="dashed" />
          <div class="doc-text-content">
            {{ currentDoc.content }}
          </div>
        </template>
      </div>
    </el-drawer>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, Refresh, Search, View, Delete, Document
} from '@element-plus/icons-vue'
import axios from 'axios'

// 基础配置
const router = useRouter()
const uploadUrl = ref('/api/v1/knowledge/upload')

// 状态管理
const loading = ref(false)
const documents = ref([])
const total = ref(0)
const categories = ref([])

const searchKeyword = ref('')
const categoryFilter = ref('')

const pagination = reactive({
  currentPage: 1,
  pageSize: 10
})

// 上传表单管理
const uploadDialogVisible = ref(false)
const uploadRef = ref(null)
const uploadFormRef = ref(null)
const uploading = ref(false)
const hasFile = ref(false)
const uploadForm = reactive({
  category: ''
})

// 抽屉状态管理
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const currentDoc = ref(null)

// 工具函数：获取 Token
const getToken = () => {
  return localStorage.getItem('access_token') || localStorage.getItem('token') || ''
}

// 请求拦截封装
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000
})
api.interceptors.request.use(config => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ==========================================
// 核心业务逻辑
// ==========================================

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

const fetchDocuments = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.currentPage,
      page_size: pagination.pageSize
    }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (categoryFilter.value) params.category = categoryFilter.value

    const res = await api.get('/knowledge/docs', { params })
    documents.value = res.data
    total.value = res.data.length 
  } catch (error) {
    ElMessage.error('获取知识库列表失败，请检查网络')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要将知识库文档【${row.title}】彻底删除吗？这会同时擦除 AI 向量大脑中的记忆。`,
      '危险操作确认',
      {
        confirmButtonText: '强制删除',
        cancelButtonText: '取消',
        type: 'error'
      }
    )
    
    loading.value = true
    await api.delete(`/knowledge/docs/${row.id}`)
    ElMessage.success('文档及其向量数据已成功擦除')
    
    if (documents.value.length === 1 && pagination.currentPage > 1) {
      pagination.currentPage--
    }
    fetchDocuments()
    fetchCategories()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '擦除失败，请联系管理员')
    }
  } finally {
    loading.value = false
  }
}

// ==========================================
// 上传链路控制
// ==========================================

const handleUpload = () => {
  uploadForm.category = ''
  hasFile.value = false
  uploadDialogVisible.value = true
}

const handleFileChange = (file, fileList) => {
  hasFile.value = fileList.length > 0
}

const handleFileRemove = (file, fileList) => {
  hasFile.value = fileList.length > 0
}

const submitUpload = () => {
  uploadFormRef.value.validate((valid) => {
    if (valid) {
      if (!hasFile.value) {
        ElMessage.warning('请先选取要入库的 TXT 或 MD 文件')
        return
      }
      uploading.value = true
      uploadRef.value.submit()
    }
  })
}

const handleUploadSuccess = (response) => {
  uploading.value = false
  uploadDialogVisible.value = false
  ElMessage.success('知识库文档上传并向量化成功！AI 大脑已更新。')
  fetchDocuments()
  fetchCategories()
}

const handleUploadError = (error) => {
  uploading.value = false
  try {
    const errorData = JSON.parse(error.message)
    ElMessage.error(errorData.detail || '文档入库失败，可能是体积过大或向量库异常')
  } catch (e) {
    ElMessage.error('网络或服务器异常，入库失败')
  }
}

// ==========================================
// 交互事件绑定
// ==========================================

const handleSearch = () => {
  pagination.currentPage = 1
  fetchDocuments()
}

const handleFilter = () => {
  pagination.currentPage = 1
  fetchDocuments()
}

const handleRefresh = () => {
  fetchDocuments()
  fetchCategories()
}

const handleSizeChange = (size) => {
  pagination.pageSize = size
  fetchDocuments()
}

const handleCurrentChange = (current) => {
  pagination.currentPage = current
  fetchDocuments()
}

// 【核心修复】拉取详情数据并展开抽屉
const handleView = async (row) => {
  drawerVisible.value = true
  drawerLoading.value = true
  currentDoc.value = null
  try {
    const res = await api.get(`/knowledge/docs/${row.id}`)
    currentDoc.value = res.data
  } catch (error) {
    ElMessage.error('读取文档详情失败')
    drawerVisible.value = false
  } finally {
    drawerLoading.value = false
  }
}

const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

onMounted(() => {
  fetchCategories()
  fetchDocuments()
})
</script>

<style scoped>
.knowledge-base {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.search-filters {
  background: white;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.filter-info {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  height: 100%;
}

.document-list {
  background: white;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.pagination {
  background: white;
  padding: 16px;
  border-radius: 8px;
  display: flex;
  justify-content: flex-end;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.document-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.document-icon {
  font-size: 18px;
  color: #409eff;
}

.title-text {
  font-weight: 500;
  color: #1f2937;
}

:deep(.el-dialog__body) {
  padding-top: 10px;
}
:deep(.el-upload-list__item) {
  transition: none;
}

/* 抽屉样式修复 */
.drawer-content-wrapper {
  padding: 0 20px 20px;
  height: 100%;
  overflow-y: auto;
}

.doc-meta-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.meta-time {
  font-size: 13px;
  color: #909399;
  margin-left: auto;
}

.doc-text-content {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
  white-space: pre-wrap;
  word-wrap: break-word;
  background-color: #f8f9fa;
  padding: 16px;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}
</style>