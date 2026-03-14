<template>
  <div class="login-container">
    <div class="login-form-wrapper">
      <div class="login-header">
        <h1 class="login-title">微信AI客服系统</h1>
        <p class="login-subtitle">客服登录</p>
      </div>
      
      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        label-position="top"
        class="login-form"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            autocomplete="username"
          />
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        
        <div class="login-options">
          <el-checkbox v-model="loginForm.remember">记住我</el-checkbox>
          <el-button type="text" @click="handleForgotPassword">忘记密码？</el-button>
        </div>
        
        <el-form-item>
          <el-button
            type="primary"
            :loading="loading"
            @click="handleLogin"
            class="login-button"
            :disabled="loading"
          >
            {{ loading ? '登录中...' : '登录' }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-footer">
        <p class="login-tips">提示：请使用系统初始化生成的管理员密码登录</p>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { login } from '@/api/service'

export default {
  name: 'LoginView',
  setup() {
    const router = useRouter()
    const route = useRoute()
    const loginFormRef = ref()
    const loading = ref(false)
    
    const loginForm = reactive({
      username: '',
      password: '',
      remember: false
    })
    
    const loginRules = reactive({
      username: [
        { required: true, message: '请输入用户名', trigger: 'blur' },
        { min: 3, max: 20, message: '用户名长度在 3 到 20 个字符', trigger: 'blur' }
      ],
      password: [
        { required: true, message: '请输入密码', trigger: 'blur' },
        { min: 6, max: 72, message: '密码长度在 6 到 72 个字符', trigger: 'blur' }
      ]
    })
    
    // 处理登录
    const handleLogin = async () => {
      if (!loginFormRef.value) return
      
      try {
        await loginFormRef.value.validate()
        
        loading.value = true
        
        // 调用登录API
        const response = await login(loginForm.username, loginForm.password)
        
        // 保存token和用户信息
        const { access_token, service } = response
        
        localStorage.setItem('token', access_token)
        localStorage.setItem('serviceId', service.id)
        localStorage.setItem('serviceInfo', JSON.stringify(service))
        
        // 记住密码（可选功能）
        if (loginForm.remember) {
          localStorage.setItem('rememberedUsername', loginForm.username)
        } else {
          localStorage.removeItem('rememberedUsername')
        }
        
        ElMessage.success('登录成功')
        
        // 跳转到之前访问的页面或首页
        const redirect = route.query.redirect || '/service'
        router.push(redirect)
        
      } catch (error) {
        if (error.response && error.response.status === 401) {
          ElMessage.error('用户名或密码错误')
        } else {
          ElMessage.error('登录失败，请稍后重试')
          console.error('登录失败:', error)
        }
      } finally {
        loading.value = false
      }
    }
    
    // 处理忘记密码
    const handleForgotPassword = () => {
      ElMessageBox.alert(
        '请联系系统管理员重置密码',
        '忘记密码',
        {
          confirmButtonText: '确定',
          type: 'info'
        }
      )
    }
    
    // 自动填充记住的用户名
    const rememberedUsername = localStorage.getItem('rememberedUsername')
    if (rememberedUsername) {
      loginForm.username = rememberedUsername
      loginForm.remember = true
    }
    
    return {
      loginFormRef,
      loginForm,
      loginRules,
      loading,
      handleLogin,
      handleForgotPassword
    }
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.login-form-wrapper {
  background: white;
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 420px;
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-title {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.login-subtitle {
  font-size: 16px;
  color: #6b7280;
  margin: 0;
}

.login-form {
  width: 100%;
}

.login-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.login-button {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 8px;
}

.login-footer {
  text-align: center;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

.login-tips {
  font-size: 12px;
  color: #6b7280;
  margin: 4px 0;
}

/* 响应式设计 */
@media (max-width: 480px) {
  .login-form-wrapper {
    padding: 32px 24px;
    margin: 16px;
  }
  
  .login-title {
    font-size: 20px;
  }
  
  .login-subtitle {
    font-size: 14px;
  }
}

/* 输入框样式优化 */
.el-input__wrapper {
  border-radius: 8px;
}

.el-input__inner {
  height: 44px;
  border-radius: 8px;
}

.el-input__prefix-inner {
  margin-right: 8px;
}

/* 按钮样式优化 */
.el-button--primary {
  background-color: #3b82f6;
  border-color: #3b82f6;
}

.el-button--primary:hover {
  background-color: #2563eb;
  border-color: #2563eb;
}

.el-button--primary.is-loading {
  background-color: #3b82f6;
  border-color: #3b82f6;
}
</style>