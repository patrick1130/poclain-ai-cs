// File: src/router/index.js

import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import LayoutView from '../views/LayoutView.vue'

// 路由组件映射
const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'layout',
    component: LayoutView,
    meta: { requiresAuth: true },
    redirect: '/service',
    children: [
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('../views/knowledge/KnowledgeBaseView.vue'),
        meta: { title: '知识库管理' }
      },
      {
        path: 'knowledge/detail/:id',
        name: 'knowledge-detail',
        component: () => import('../views/knowledge/KnowledgeDetailView.vue'),
        meta: { title: '文档详情' }
      },
      {
        path: 'knowledge/edit/:id?',
        name: 'knowledge-edit',
        component: () => import('../views/knowledge/KnowledgeEditView.vue'),
        meta: { title: '编辑文档' }
      },
      {
        path: 'service',
        name: 'service',
        component: () => import('../views/service/ServiceWorkbenchView.vue'),
        meta: { title: '客服工作台' }
      },
      {
        path: 'service/session/:id',
        name: 'session-detail',
        component: () => import('../views/service/SessionDetailView.vue'),
        meta: { title: '会话详情' }
      },
      {
        path: 'statistics',
        name: 'statistics',
        component: () => import('../views/statistics/StatisticsView.vue'),
        meta: { title: '数据统计' }
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('../views/settings/SettingsView.vue'),
        meta: { title: '系统设置' }
      }
    ]
  }
]

const router = createRouter({
  // 【修复】Vite 环境下使用 import.meta.env
  history: createWebHistory(import.meta.env.BASE_URL || '/'),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - 微信智能客服系统` : '微信智能客服系统'

  // 【架构与安全修复】兼容 OAuth2.0 标准与遗留系统的 Token 键名，彻底杜绝重定向死循环
  const token = localStorage.getItem('access_token') || localStorage.getItem('token')

  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!token) {
      // 未登录，拦截并记录来源路径
      next({ path: '/login', query: { redirect: to.fullPath } })
    } else {
      // 已登录，放行
      next()
    }
  } else if (to.path === '/login' && token) {
    // 已登录状态下禁止二次访问登录页，强制引流至工作台
    next('/service')
  } else {
    // 公共路由（白名单），直接放行
    next()
  }
})

export default router