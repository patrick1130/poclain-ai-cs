<template>
  <div class="placeholder-container">
    <el-empty 
      :image-size="200" 
      description="该业务模块正在进行架构升级或尚未开放"
    >
      <template #default>
        <div class="action-area">
          <p class="text-gray-500 text-sm mb-4">
            系统检测到当前路由节点尚未挂载有效的视图组件。
          </p>
          <el-button type="primary" @click="goBack">
            <el-icon class="mr-2"><ArrowLeft /></el-icon>
            返回安全工作区
          </el-button>
        </div>
      </template>
    </el-empty>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'

const router = useRouter()

// 算法复杂度：O(1) 路由出栈操作
const goBack = () => {
  router.replace('/service')
}
</script>

<style scoped>
.placeholder-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: calc(100vh - 120px);
  background-color: #ffffff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.action-area {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
</style>