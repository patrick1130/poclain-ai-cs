<template>
  <div class="statistics-view">
    <div class="page-header">
      <h1 class="page-title">数据统计</h1>
      <div class="header-actions">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          :shortcuts="dateShortcuts"
          @change="handleDateRangeChange"
        />
        <el-button @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="stats-cards">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-card shadow="hover" class="stats-card">
            <div class="card-content">
              <div class="card-value">{{ totalSessions }}</div>
              <div class="card-label">总会话数</div>
              <div class="card-trend" :class="{ positive: sessionTrend > 0, negative: sessionTrend < 0 }">
                <el-icon><component :is="sessionTrend > 0 ? 'trend-charts' : 'arrow-down'" /></el-icon>
                <span>{{ Math.abs(sessionTrend) }}%</span>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card shadow="hover" class="stats-card">
            <div class="card-content">
              <div class="card-value">{{ aiHandled }}</div>
              <div class="card-label">AI处理数 (包含历史)</div>
              <div class="card-trend" :class="{ positive: aiTrend > 0, negative: aiTrend < 0 }">
                <el-icon><component :is="aiTrend > 0 ? 'trend-charts' : 'arrow-down'" /></el-icon>
                <span>{{ Math.abs(aiTrend) }}%</span>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card shadow="hover" class="stats-card">
            <div class="card-content">
              <div class="card-value">{{ humanHandled }}</div>
              <div class="card-label">人工活跃接管数</div>
              <div class="card-trend" :class="{ positive: humanTrend < 0, negative: humanTrend > 0 }">
                <el-icon><component :is="humanTrend < 0 ? 'trend-charts' : 'arrow-down'" /></el-icon>
                <span>{{ Math.abs(humanTrend) }}%</span>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card shadow="hover" class="stats-card">
            <div class="card-content">
              <div class="card-value">{{ satisfactionRate.toFixed(1) }}%</div>
              <div class="card-label">客户满意度</div>
              <div class="card-trend" :class="{ positive: satisfactionTrend > 0, negative: satisfactionTrend < 0 }">
                <el-icon><component :is="satisfactionTrend > 0 ? 'trend-charts' : 'arrow-down'" /></el-icon>
                <span>{{ Math.abs(satisfactionTrend) }}%</span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <div class="charts-section">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-card shadow="hover" class="chart-card">
            <template #header>
              <div class="card-header">
                <span>会话趋势</span>
                <el-select v-model="chartInterval" size="small" @change="handleChartIntervalChange">
                  <el-option label="按小时" value="hour" />
                  <el-option label="按天" value="day" />
                  <el-option label="按周" value="week" />
                </el-select>
              </div>
            </template>
            <div class="chart-container">
              <canvas ref="sessionChartRef" height="300"></canvas>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="12">
          <el-card shadow="hover" class="chart-card">
            <template #header>
              <div class="card-header">
                <span>服务类型分布</span>
              </div>
            </template>
            <div class="chart-container">
              <canvas ref="serviceTypeChartRef" height="300"></canvas>
            </div>
          </el-card>
        </el-col>
      </el-row>
      
      <el-row :gutter="16" style="margin-top: 16px;">
        <el-col :span="12">
          <el-card shadow="hover" class="chart-card">
            <template #header>
              <div class="card-header">
                <span>热门问题TOP10</span>
              </div>
            </template>
            <div class="hot-questions">
              <el-table :data="hotQuestions" style="width: 100%">
                <el-table-column prop="rank" label="排名" width="60" align="center" />
                <el-table-column prop="question" label="问题内容" min-width="200" />
                <el-table-column prop="count" label="出现次数" width="100" align="center" />
                <el-table-column prop="ai_rate" label="AI解决率" width="120" align="center">
                  <template #default="scope">
                    <div class="progress-bar">
                      <div class="progress-fill" :style="{ width: scope.row.ai_rate + '%' }"></div>
                      <span class="progress-text">{{ scope.row.ai_rate }}%</span>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="12">
          <el-card shadow="hover" class="chart-card">
            <template #header>
              <div class="card-header">
                <span>客服绩效排行</span>
              </div>
            </template>
            <div class="chart-container">
              <canvas ref="servicePerformanceChartRef" height="300"></canvas>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, TrendCharts, ArrowDown } from '@element-plus/icons-vue'
import Chart from 'chart.js/auto'
// 【架构修复】引入 axios 用于拉取真实统计数据
import axios from 'axios'

export default {
  name: 'StatisticsView',
  components: {
    Refresh, TrendCharts, ArrowDown
  },
  setup() {
    // 图表引用
    const sessionChartRef = ref()
    const serviceTypeChartRef = ref()
    const servicePerformanceChartRef = ref()
    
    // 图表实例
    let sessionChart = null
    let serviceTypeChart = null
    let servicePerformanceChart = null
    
    // 状态管理
    const dateRange = ref([new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), new Date()])
    const chartInterval = ref('day')
    const loading = ref(false)
    
    // 统计数据 (已剥离硬编码，等待接口下发)
    const totalSessions = ref(0)
    const aiHandled = ref(0)
    const humanHandled = ref(0)
    const satisfactionRate = ref(0)
    
    // 趋势数据 (暂留 Mock 展示)
    const sessionTrend = ref(15)
    const aiTrend = ref(25)
    const humanTrend = ref(-12)
    const satisfactionTrend = ref(3.2)
    
    // 热门问题
    const hotQuestions = ref([
      { rank: 1, question: '如何申请退款？', count: 156, ai_rate: 92 },
      { rank: 2, question: '产品保修政策是什么？', count: 132, ai_rate: 88 },
      { rank: 3, question: '什么时候发货？', count: 118, ai_rate: 95 },
      { rank: 4, question: '如何修改收货地址？', count: 98, ai_rate: 90 },
      { rank: 5, question: '产品使用说明', count: 87, ai_rate: 85 },
      { rank: 6, question: '运费怎么计算？', count: 76, ai_rate: 93 },
      { rank: 7, question: '如何取消订单？', count: 65, ai_rate: 89 },
      { rank: 8, question: '售后服务联系方式', count: 54, ai_rate: 96 },
      { rank: 9, question: '产品规格参数', count: 43, ai_rate: 82 },
      { rank: 10, question: '会员积分规则', count: 38, ai_rate: 87 }
    ])
    
    // 日期快捷选项
    const dateShortcuts = [
      {
        text: '最近7天',
        value: () => {
          const end = new Date()
          const start = new Date()
          start.setTime(start.getTime() - 3600 * 1000 * 24 * 7)
          return [start, end]
        }
      },
      {
        text: '最近30天',
        value: () => {
          const end = new Date()
          const start = new Date()
          start.setTime(start.getTime() - 3600 * 1000 * 24 * 30)
          return [start, end]
        }
      },
      {
        text: '最近90天',
        value: () => {
          const end = new Date()
          const start = new Date()
          start.setTime(start.getTime() - 3600 * 1000 * 24 * 90)
          return [start, end]
        }
      }
    ]

    // 鉴权拦截器配置
    const getToken = () => localStorage.getItem('access_token') || localStorage.getItem('token') || ''
    const api = axios.create({ baseURL: '/api/v1', timeout: 15000 })
    api.interceptors.request.use(config => {
      const token = getToken()
      if (token) config.headers.Authorization = `Bearer ${token}`
      return config
    })
    
    // 初始化会话趋势图
    const initSessionChart = () => {
      if (!sessionChartRef.value) return
      
      const ctx = sessionChartRef.value.getContext('2d')
      
      // 销毁现有图表
      if (sessionChart) {
        sessionChart.destroy()
      }
      
      // 模拟数据
      const labels = ['1月', '2月', '3月', '4月', '5月', '6月', '7月']
      const aiData = [120, 150, 180, 200, 220, 240, 260]
      const humanData = [80, 75, 70, 65, 60, 55, 50]
      
      sessionChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'AI处理',
              data: aiData,
              borderColor: '#3b82f6',
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              tension: 0.4,
              fill: true
            },
            {
              label: '人工处理',
              data: humanData,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              tension: 0.4,
              fill: true
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top'
            }
          },
          scales: {
            y: {
              beginAtZero: true
            }
          }
        }
      })
    }
    
    // 初始化服务类型分布图
    const initServiceTypeChart = () => {
      if (!serviceTypeChartRef.value) return
      
      const ctx = serviceTypeChartRef.value.getContext('2d')
      
      // 销毁现有图表
      if (serviceTypeChart) {
        serviceTypeChart.destroy()
      }
      
      // 模拟数据
      const data = {
        labels: ['产品咨询', '订单问题', '退款售后', '技术支持', '其他'],
        datasets: [{
          data: [45, 25, 15, 10, 5],
          backgroundColor: [
            '#3b82f6',
            '#10b981',
            '#f59e0b',
            '#ef4444',
            '#8b5cf6'
          ]
        }]
      }
      
      serviceTypeChart = new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right'
            }
          }
        }
      })
    }
    
    // 初始化客服绩效图
    const initServicePerformanceChart = () => {
      if (!servicePerformanceChartRef.value) return
      
      const ctx = servicePerformanceChartRef.value.getContext('2d')
      
      // 销毁现有图表
      if (servicePerformanceChart) {
        servicePerformanceChart.destroy()
      }
      
      // 模拟数据
      const labels = ['客服A', '客服B', '客服C', '客服D', '客服E']
      const data = [85, 92, 78, 88, 95]
      
      servicePerformanceChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: '处理效率',
            data: data,
            backgroundColor: '#3b82f6'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              max: 100
            }
          }
        }
      })
    }
    
    // 获取统计数据 (【架构修复】接入真实后端 API 聚合数据)
    const fetchStatistics = async () => {
      loading.value = true
      try {
        const res = await api.get('/service/statistics')
        const data = res.data
        
        // 数据精准映射
        totalSessions.value = data.total_sessions
        // 人工接管的视为人工处理
        humanHandled.value = data.active_sessions
        // 剩余的算入历史或 AI 托管处理
        aiHandled.value = Math.max(0, data.total_sessions - data.active_sessions)
        
        // 满分 5 分，按比例换算为百分制呈现
        satisfactionRate.value = (data.satisfaction_rate / 5.0) * 100
        
      } catch (error) {
        ElMessage.error('获取真实统计数据失败，请检查网络')
        console.error('获取统计数据失败:', error)
      } finally {
        loading.value = false
      }
    }
    
    // 处理日期范围变化
    const handleDateRangeChange = () => {
      fetchStatistics()
    }
    
    // 处理图表时间间隔变化
    const handleChartIntervalChange = () => {
      nextTick(() => {
        initSessionChart()
      })
    }
    
    // 刷新数据
    const handleRefresh = () => {
      fetchStatistics()
    }
    
    // 组件挂载时初始化
    onMounted(async () => {
      await fetchStatistics()
      
      nextTick(() => {
        initSessionChart()
        initServiceTypeChart()
        initServicePerformanceChart()
      })
    })
    
    // 组件卸载时清理
    onUnmounted(() => {
      if (sessionChart) {
        sessionChart.destroy()
      }
      if (serviceTypeChart) {
        serviceTypeChart.destroy()
      }
      if (servicePerformanceChart) {
        servicePerformanceChart.destroy()
      }
    })
    
    return {
      // 图表引用
      sessionChartRef,
      serviceTypeChartRef,
      servicePerformanceChartRef,
      
      // 状态
      dateRange,
      chartInterval,
      loading,
      
      // 统计数据
      totalSessions,
      aiHandled,
      humanHandled,
      satisfactionRate,
      sessionTrend,
      aiTrend,
      humanTrend,
      satisfactionTrend,
      hotQuestions,
      dateShortcuts,
      
      // 方法
      handleDateRangeChange,
      handleChartIntervalChange,
      handleRefresh
    }
  }
}
</script>

<style scoped>
.statistics-view {
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
  align-items: center;
}

.stats-cards {
  margin-bottom: 24px;
}

.stats-card {
  height: 120px;
  border-radius: 8px;
}

.card-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 16px;
}

.card-value {
  font-size: 32px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 4px;
}

.card-label {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 8px;
}

.card-trend {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
}

.card-trend.positive {
  color: #10b981;
}

.card-trend.negative {
  color: #ef4444;
}

.charts-section {
  margin-bottom: 24px;
}

.chart-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.chart-container {
  position: relative;
  height: 300px;
}

.hot-questions {
  max-height: 300px;
  overflow-y: auto;
}

.progress-bar {
  position: relative;
  height: 20px;
  background-color: #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: #3b82f6;
  transition: width 0.3s ease;
}

.progress-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  font-weight: 500;
  color: #1f2937;
  text-shadow: 0 0 2px rgba(255, 255, 255, 0.8);
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .stats-cards .el-col {
    margin-bottom: 16px;
  }
  
  .charts-section .el-col {
    margin-bottom: 16px;
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .header-actions {
    width: 100%;
    justify-content: flex-end;
  }
  
  .stats-cards .el-col {
    margin-bottom: 16px;
  }
  
  .charts-section .el-col {
    margin-bottom: 16px;
  }
}
</style>