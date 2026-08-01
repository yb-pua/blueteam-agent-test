<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { apiGet } from '../api/client.js'

const brief = ref(null)
const loading = ref(true)

// ECharts 实例引用：单个 ref 对象，模板用 ref="chartTrend" 绑定
const chartTrend = ref(null)
const chartAction = ref(null)
const chartRisk = ref(null)
const chartIocType = ref(null)
const chartTopIoc = ref(null)
const chartInstances = {}

// 动作图标映射
const ACTION_ICONS = {
  ioc_query: '🔍', alert_parse: '⚠️', skill_run: '⚡', chat_ask: '💬',
  config_update: '⚙️', session_create: '➕', session_delete: '🗑️', report_view: '📊',
}

// 风险级别颜色
const RISK_COLORS = { critical: '#dc2626', high: '#ea580c', medium: '#d97706', low: '#2563eb', info: '#64748b' }

async function loadData() {
  loading.value = true
  try {
    brief.value = await apiGet('/report/daily')
    await nextTick()
    initCharts()
  } catch (e) {
    brief.value = { error: e.message }
  } finally {
    loading.value = false
  }
}

// ---- ECharts 初始化 ----

function initCharts() {
  if (!brief.value || brief.value.error) return
  import('echarts').then(echarts => {
    const ec = echarts.default || echarts
    registerCharts(ec)
  })
}

function getChart(name) {
  return { trend: chartTrend, action: chartAction, risk: chartRisk, iocType: chartIocType, topIoc: chartTopIoc }[name]
}

function registerCharts(ec) {
  for (const key of ['trend', 'action', 'risk', 'iocType', 'topIoc']) {
    const ref = getChart(key)
    if (!ref?.value) {
      console.warn('图表容器未找到:', key)
      continue
    }
    if (chartInstances[key]) chartInstances[key].dispose()
    chartInstances[key] = ec.init(ref.value)
    callDrawFn(key, ec, chartInstances[key])
  }
}

function callDrawFn(key, ec, chart) {
  const fns = {
    trend: () => drawTrendChart(ec, chart),
    action: () => drawPieChart(ec, chart, 'action_dist'),
    risk: () => drawPieChart(ec, chart, 'risk_dist'),
    iocType: () => drawBarChart(ec, chart, 'ioc_types'),
    topIoc: () => drawHorizontalBar(ec, chart, 'top_iocs'),
  }
  const fn = fns[key]
  if (fn) fn()
}

function drawTrendChart(ec, chart) {
  const d = brief.value
  if (!d?.daily_ops?.days?.length) { chart.setOption({ title: { text: '暂无数据', textStyle: { color: '#64748b', fontSize: 14 } } }); return }

  const themeColors = ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#64748b']
  const series = (d.daily_ops.series || []).map((s, i) => ({
    ...s, type: 'bar', stack: 'total',
    itemStyle: { color: themeColors[i % themeColors.length] },
    emphasis: { focus: 'series' },
  }))

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#1e293b',
      borderColor: '#334155',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
    },
    legend: {
      data: (d.daily_ops.series || []).map(s => s.name),
      textStyle: { color: '#94a3b8', fontSize: 11 },
      bottom: 0,
    },
    grid: { left: 40, right: 20, top: 10, bottom: 40 },
    xAxis: {
      type: 'category',
      data: d.daily_ops.days,
      axisLabel: { color: '#64748b', fontSize: 11 },
      axisLine: { lineStyle: { color: '#334155' } },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#64748b', fontSize: 11 },
      splitLine: { lineStyle: { color: '#1e293b' } },
    },
    series,
  })
}

function drawPieChart(ec, chart, field, title) {
  const data = brief.value?.[field]
  if (!data?.length) { chart.setOption({ title: { text: '暂无数据', textStyle: { color: '#64748b', fontSize: 14 } } }); return }

  const themeColors = ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444', '#64748b']
  chart.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1e293b',
      borderColor: '#334155',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: '{b}: {c} ({d}%)',
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 4,
        borderColor: '#0f172a',
        borderWidth: 2,
      },
      label: { color: '#94a3b8', fontSize: 11, formatter: '{b}' },
      emphasis: { label: { show: true, fontWeight: 'bold', color: '#e2e8f0' } },
      data: data.map((d, i) => ({ ...d, itemStyle: { color: themeColors[i % themeColors.length] } })),
    }],
  })
}

function drawBarChart(ec, chart, field, title) {
  const data = brief.value?.[field]
  if (!data?.length) { chart.setOption({ title: { text: '暂无数据', textStyle: { color: '#64748b', fontSize: 14 } } }); return }

  chart.setOption({
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#e2e8f0', fontSize: 12 },
    },
    grid: { left: 80, right: 20, top: 10, bottom: 20 },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#64748b', fontSize: 11 },
      splitLine: { lineStyle: { color: '#1e293b' } },
    },
    yAxis: {
      type: 'category',
      data: data.map(d => d.name).reverse(),
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      axisLine: { lineStyle: { color: '#334155' } },
    },
    series: [{
      type: 'bar',
      data: data.map(d => d.value).reverse(),
      itemStyle: { color: '#3b82f6', borderRadius: [0, 4, 4, 0] },
    }],
  })
}

function drawHorizontalBar(ec, chart, field, title) {
  const data = brief.value?.[field]
  if (!data?.length) { chart.setOption({ title: { text: '暂无数据', textStyle: { color: '#64748b', fontSize: 14 } } }); return }

  chart.setOption({
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#e2e8f0', fontSize: 12 },
    },
    grid: { left: 20, right: 60, top: 10, bottom: 20 },
    yAxis: {
      type: 'category',
      data: data.map(d => d.name).reverse(),
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      axisLine: { lineStyle: { color: '#334155' } },
    },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#64748b', fontSize: 11, formatter: '{value}' },
      splitLine: { lineStyle: { color: '#1e293b' } },
    },
    series: [{
      type: 'bar',
      data: data.map(d => d.value).reverse(),
      itemStyle: { color: '#f59e0b', borderRadius: [0, 4, 4, 0] },
      label: {
        show: true, position: 'right', color: '#94a3b8', fontSize: 11,
        formatter: '{c}',
      },
    }],
  })
}

// ---- 工具函数 ----

function detailText(detail) {
  if (!detail || typeof detail !== 'object') return String(detail || '')
  if (detail.attack_type) return `${detail.attack_type} (置信度: ${detail.confidence}%)`
  if (detail.question) return `"${detail.question}"`
  if (detail.name) return detail.name
  if (detail.type) return `${detail.type}:${detail.value || ''}`
  if (detail.key) return `${detail.key} → ${detail.set ? '已设置' : '已清除'}`
  if (detail.session_id) return `会话 #${detail.session_id}`
  return JSON.stringify(detail)
}

// 窗口 resize 重绘
function onResize() {
  for (const inst of Object.values(chartInstances)) {
    inst?.resize()
  }
}

onMounted(async () => {
  await loadData()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  for (const inst of Object.values(chartInstances)) {
    inst?.dispose()
  }
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <div class="page" style="margin-top: 20px;">
    <!-- 标题 -->
    <div class="card" style="padding: 16px;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <h2 style="margin: 0;">📊 运营看板</h2>
        <span v-if="brief && !brief.error" style="color: #64748b; font-size: 13px;">{{ brief.date }} 更新</span>
      </div>
      <p style="color: #94a3b8; font-size: 13px; margin-top: 6px;">
        平台操作统计与 BI 分析。操作日志自动记录所有用户动作。
      </p>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="card" style="text-align: center; color: #94a3b8;">加载中...</div>

    <!-- 错误 -->
    <div v-else-if="brief && brief.error" class="card" style="border-color: #7f1d1d;">{{ brief.error }}</div>

    <!-- 空数据引导 -->
    <div v-else-if="brief && brief.totals && brief.totals.total_ops === 0" class="card" style="text-align: center; padding: 40px;">
      <div style="font-size: 56px; margin-bottom: 16px;">📊</div>
      <h3 style="margin-bottom: 10px;">暂无操作数据</h3>
      <p style="color: #94a3b8; font-size: 14px;">
        使用 AI 分析、IoC 查询、告警解析等功能后，操作数据将自动出现在这里。操作日志会自动记录，无需手动开启。
      </p>
    </div>

    <!-- 数据内容 -->
    <template v-if="brief && !brief.error && brief.totals && brief.totals.total_ops > 0">
      <!-- 指标卡 -->
      <div class="grid-4 mt-4">
        <div class="card metric-card">
          <div class="metric-icon">📈</div>
          <div class="metric-value">{{ brief.totals.total_ops }}</div>
          <div class="metric-label">累计操作</div>
        </div>
        <div class="card metric-card">
          <div class="metric-icon">📅</div>
          <div class="metric-value">{{ brief.totals.today_ops }}</div>
          <div class="metric-label">今日操作</div>
        </div>
        <div class="card metric-card">
          <div class="metric-icon">💬</div>
          <div class="metric-value">{{ brief.totals.sessions }}</div>
          <div class="metric-label">会话数</div>
        </div>
        <div class="card metric-card">
          <div class="metric-icon">📦</div>
          <div class="metric-value">{{ brief.totals.cache_items }}</div>
          <div class="metric-label">缓存情报</div>
        </div>
      </div>

      <!-- BI 图表区 -->
      <div class="grid-2 mt-4">
        <div class="card chart-card">
          <h3>近 14 天操作趋势</h3>
          <div ref="chartTrend" class="chart-box"></div>
        </div>
        <div class="card chart-card">
          <h3>操作类型分布</h3>
          <div ref="chartAction" class="chart-box"></div>
        </div>
        <div class="card chart-card">
          <h3>风险级别分布</h3>
          <div ref="chartRisk" class="chart-box"></div>
        </div>
        <div class="card chart-card">
          <h3>IoC 类型分布</h3>
          <div ref="chartIocType" class="chart-box"></div>
        </div>
        <div class="card chart-card" style="grid-column: span 2;">
          <h3>Top IoC 查询</h3>
          <div ref="chartTopIoc" class="chart-box" style="height: 200px;"></div>
        </div>
      </div>

      <!-- 操作日志 -->
      <div class="card mt-4">
        <h3>📋 最近操作日志</h3>
        <div class="log-table-wrap">
          <table class="log-table">
            <thead>
              <tr>
                <th style="width: 140px;">时间</th>
                <th style="width: 100px;">动作</th>
                <th>详情</th>
                <th style="width: 80px;">风险</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in brief.recent_logs" :key="log.id">
                <td class="log-time">{{ log.time_str }}</td>
                <td>
                  <span class="log-action">
                    {{ ACTION_ICONS[log.action] || '📌' }}
                    {{ log.action_label }}
                  </span>
                </td>
                <td class="log-detail">{{ detailText(log.detail) }}</td>
                <td>
                  <span v-if="log.risk" class="tag" :style="{ background: RISK_COLORS[log.risk] + '22', color: RISK_COLORS[log.risk], border: '1px solid ' + RISK_COLORS[log.risk] + '44' }">
                    {{ log.risk }}
                  </span>
                  <span v-else style="color: #475569;">—</span>
                </td>
              </tr>
              <tr v-if="!brief.recent_logs?.length">
                <td colspan="4" style="text-align: center; color: #64748b; padding: 20px;">暂无日志记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.metric-card {
  padding: 16px;
  text-align: center;
}
.metric-icon { font-size: 28px; margin-bottom: 6px; }
.metric-value { font-size: 28px; font-weight: 700; color: #f1f5f9; }
.metric-label { font-size: 12px; color: #64748b; margin-top: 4px; }

.chart-card {
  padding: 14px;
}
.chart-card h3 { font-size: 14px; margin-bottom: 8px; }
.chart-box {
  width: 100%;
  height: 240px;
}

.log-table-wrap {
  overflow-x: auto;
  margin-top: 8px;
}
.log-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.log-table th {
  text-align: left;
  padding: 8px 10px;
  color: #64748b;
  font-weight: 500;
  border-bottom: 1px solid #334155;
  white-space: nowrap;
}
.log-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #1e293b;
  vertical-align: middle;
}
.log-table tr:hover td { background: #1e293b40; }
.log-time { color: #94a3b8; white-space: nowrap; font-size: 12px; }
.log-action { white-space: nowrap; }
.log-detail { color: #e2e8f0; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

@media (max-width: 768px) {
  .grid-4 { grid-template-columns: repeat(2, 1fr); }
  .grid-2 { grid-template-columns: 1fr; }
  .chart-card[style*="grid-column: span 2"] { grid-column: span 1 !important; }
}
</style>