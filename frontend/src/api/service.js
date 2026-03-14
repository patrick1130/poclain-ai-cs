import axios from 'axios'

// 创建axios实例
const service = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  response => {
    const res = response.data
    return res
  },
  error => {
    console.error('响应错误:', error)
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('serviceId')
      localStorage.removeItem('serviceInfo')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const login = (username, password) => {
  const params = new URLSearchParams()
  params.append('username', username)
  params.append('password', password)
  return service.post('/service/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  })
}

export const getSessions = (params) => {
  return service.get('/service/sessions', { params })
}

export const getSessionMessages = (sessionId) => {
  return service.get(`/service/sessions/${sessionId}/messages`)
}

export const sendServiceMessage = (sessionId, content) => {
  return service.post(`/service/sessions/${sessionId}/messages`, { content })
}

export const closeSession = (sessionId) => {
  return service.put(`/service/sessions/${sessionId}/close`)
}

export const acceptSession = (sessionId) => {
  return service.put(`/service/sessions/${sessionId}/accept`)
}

export const transferToAI = (sessionId) => {
  return service.put(`/service/sessions/${sessionId}/transfer-ai`)
}

export const updateServiceStatus = (status) => {
  return service.put('/service/status', { status })
}

export const getServiceStatistics = () => {
  return service.get('/service/statistics')
}

export const getKnowledgeDocs = () => {
  return service.get('/knowledge/documents')
}

export const deleteKnowledgeDoc = (id) => {
  return service.delete(`/knowledge/documents/${id}`)
}

export default service
