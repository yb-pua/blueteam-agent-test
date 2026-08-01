<script setup>
import { ref, onMounted } from 'vue'
import { apiGet, apiPost } from '../api/client.js'

const groups = ref({})
const summary = ref({})
const configItems = ref([])
const loading = ref(true)
const saving = ref({})
const message = ref('')
const messageType = ref('')

// 展开/折叠
const expanded = ref({
  threat_intel: true,
  osint_free: true,
  ip_geo: true,
  feeds: false,
  llm: true,
})

function toggleGroup(key) {
  expanded.value[key] = !expanded.value[key]
}

function formatInterval(sec) {
  if (sec >= 86400) return `${sec / 86400}天`
  if (sec >= 3600) return `${sec / 3600}小时`
  return `${sec / 60}分钟`
}

function formatBytes(bytes) {
  if (!bytes) return '0 MB'
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(ts) {
  if (!ts) return '未加载'
  return new Date(ts * 1000).toLocaleString()
}

// 加载所有源信息
async function loadAll() {
  loading.value = true
  try {
    const data = await apiGet('/sources/all')
    groups.value = data.groups || {}
    summary.value = data.summary || {}
  } catch (e) {
    message.value = '加载失败: ' + e.message
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
}

// 加载配置项（用于 API Key 编辑）
async function loadConfig() {
  try {
    const data = await apiGet('/config')
    configItems.value = data.items || []
  } catch (e) {}
}

// 查找配置项
function findConfig(sourceName) {
  return configItems.value.find(i => i.source === sourceName)
}

// 配置编辑
function startEdit(item) {
  item.editing = true
  item.newValue = ''
}

function cancelEdit(item) {
  item.editing = false
  item.newValue = ''
}

async function saveConfig(item) {
  saving.value[item.key] = true
  message.value = ''
  try {
    const resp = await apiPost('/config', { key: item.key, value: item.newValue || '' })
    if (resp.status === 'ok') {
      item.is_set = resp.set
      message.value = resp.sources_refreshed?.length
        ? `已保存，情报源已刷新: ${resp.sources_refreshed.join(', ')}`
        : '已保存'
      messageType.value = 'success'
      await loadAll()
    }
  } catch (e) {
    message.value = '保存失败: ' + e.message
    messageType.value = 'error'
  } finally {
    saving.value[item.key] = false
    item.editing = false
    item.newValue = ''
  }
}

// LLM 配置编辑
function startEditLLM(item) {
  item.editing = true
  item.newValue = ''
}

function cancelEditLLM(item) {
  item.editing = false
  item.newValue = ''
}

async function saveLLMConfig(item) {
  saving.value[item.name] = true
  message.value = ''
  try {
    const resp = await apiPost('/config', { key: item.name, value: item.newValue || '' })
    if (resp.status === 'ok') {
      item.configured = !!item.newValue
      item.current_value = item.value_type === 'password' && item.newValue ? '******' : item.newValue
      message.value = '已保存'
      messageType.value = 'success'
      await loadAll()
    }
  } catch (e) {
    message.value = '保存失败: ' + e.message
    messageType.value = 'error'
  } finally {
    saving.value[item.name] = false
    item.editing = false
    item.newValue = ''
  }
}

onMounted(async () => {
  await Promise.all([loadAll(), loadConfig()])
})
</script>

<template>
  <div class="card" style="margin-top: 20px;">
    <h2>⚙️ 数据源配置</h2>

    <!-- 顶部摘要 -->
    <div v-if="!loading" class="summary-bar">
      <span class="summary-item">
        <span class="summary-num">{{ summary.total_sources || 0 }}</span> 个情报源
      </span>
      <span class="summary-item">
        <span class="summary-num">{{ summary.configured_sources || 0 }}</span> 个已配置
      </span>
      <span class="summary-item">
        <span class="summary-num">{{ (summary.feed_ios || 0).toLocaleString() }}</span> 条 Feed IoC
      </span>
    </div>

    <!-- 消息提示 -->
    <div v-if="message" class="msg" :class="messageType === 'error' ? 'msg-error' : 'msg-ok'">
      {{ message }}
    </div>

    <div v-if="loading" style="color: #94a3b8;">加载中...</div>

    <template v-else>
      <!-- ===== 需要 Key 的威胁情报源 ===== -->
      <div class="group-section" v-if="groups.threat_intel">
        <div class="group-header" @click="toggleGroup('threat_intel')">
          <span>{{ groups.threat_intel.label }}</span>
          <span class="toggle">{{ expanded.threat_intel ? '▼' : '▶' }}</span>
        </div>
        <p class="group-desc">{{ groups.threat_intel.description }}</p>
        <div v-if="expanded.threat_intel" class="source-list">
          <div v-for="s in groups.threat_intel.sources" :key="s.name" class="source-item">
            <div class="source-row">
              <div class="source-info">
                <span class="source-name">{{ s.label }}</span>
                <span class="tag" :class="s.configured ? 'tag-ok' : 'tag-off'">
                  {{ s.configured ? '✅ 已配置' : '❌ 未配置' }}
                </span>
                <span class="source-types">{{ s.supported_types.join(' / ') }}</span>
              </div>
              <div class="source-actions">
                <template v-if="findConfig(s.name)">
                  <button class="btn btn-sm" @click="startEdit(findConfig(s.name))">
                    {{ findConfig(s.name).is_set ? '修改' : '配置' }}
                  </button>
                  <a v-if="findConfig(s.name).doc" :href="findConfig(s.name).doc" target="_blank"
                     class="btn btn-sm" style="margin-left: 4px;">获取 Key</a>
                </template>
              </div>
            </div>
            <div v-if="findConfig(s.name)?.editing" class="edit-form">
              <input v-model="findConfig(s.name).newValue"
                     :placeholder="findConfig(s.name).is_set ? '输入新值' : '输入 API Key'"
                     type="password" />
              <button class="btn btn-primary btn-sm" @click="saveConfig(findConfig(s.name))"
                      :disabled="saving[findConfig(s.name)?.key]">
                {{ saving[findConfig(s.name)?.key] ? '保存中...' : '保存' }}
              </button>
              <button class="btn btn-sm" @click="cancelEdit(findConfig(s.name))">取消</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== 免费 OSINT 源 ===== -->
      <div class="group-section" v-if="groups.osint_free">
        <div class="group-header" @click="toggleGroup('osint_free')">
          <span>{{ groups.osint_free.label }}</span>
          <span class="toggle">{{ expanded.osint_free ? '▼' : '▶' }}</span>
        </div>
        <p class="group-desc">{{ groups.osint_free.description }}</p>
        <div v-if="expanded.osint_free" class="source-list">
          <div v-for="s in groups.osint_free.sources" :key="s.name" class="source-item">
            <div class="source-row">
              <div class="source-info">
                <span class="source-name">{{ s.label }}</span>
                <span class="source-types">{{ s.supported_types.join(' / ') }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== IP 基础信息源 ===== -->
      <div class="group-section" v-if="groups.ip_geo">
        <div class="group-header" @click="toggleGroup('ip_geo')">
          <span>{{ groups.ip_geo.label }}</span>
          <span class="toggle">{{ expanded.ip_geo ? '▼' : '▶' }}</span>
        </div>
        <p class="group-desc">{{ groups.ip_geo.description }}</p>
        <div v-if="expanded.ip_geo" class="source-list">
          <div v-for="s in groups.ip_geo.sources" :key="s.name" class="source-item">
            <div class="source-row">
              <div class="source-info">
                <span class="source-name">{{ s.label }}</span>
                <span class="source-types">{{ s.supported_types.join(' / ') }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== 开源 Feed ===== -->
      <div class="group-section" v-if="groups.feeds">
        <div class="group-header" @click="toggleGroup('feeds')">
          <span>{{ groups.feeds.label }}</span>
          <span class="toggle">{{ expanded.feeds ? '▼' : '▶' }}</span>
        </div>
        <p class="group-desc">{{ groups.feeds.description }}</p>
        <div v-if="expanded.feeds" class="source-list">
          <div v-if="groups.feeds.meta" class="feed-meta">
            <span>保留轮次: <strong>{{ groups.feeds.meta.max_rounds }}</strong></span>
            <span>DB 大小: <strong>{{ formatBytes(groups.feeds.meta.db_size_bytes) }}</strong></span>
            <span>IoC 总量: <strong>{{ groups.feeds.meta.total_ios?.toLocaleString() }}</strong></span>
          </div>
          <div v-for="s in groups.feeds.sources" :key="s.name"
               :class="['source-item', 'feed-item', s.configured ? '' : 'feed-empty']">
            <div class="source-row">
              <div class="source-info">
                <span class="source-name">{{ s.label }}</span>
                <span class="tag" :class="s.configured ? 'tag-ok' : 'tag-off'">
                  {{ s.total_ios || 0 }} IoC
                </span>
                <span class="source-types">{{ s.ioc_types.join(' / ') }}</span>
              </div>
              <span class="feed-time">{{ formatDate(s.last_fetch) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== LLM 配置 ===== -->
      <div class="group-section" v-if="groups.llm">
        <div class="group-header" @click="toggleGroup('llm')">
          <span>{{ groups.llm.label }}</span>
          <span class="toggle">{{ expanded.llm ? '▼' : '▶' }}</span>
        </div>
        <p class="group-desc">{{ groups.llm.description }}</p>
        <div v-if="expanded.llm" class="source-list">
          <div v-for="s in groups.llm.sources" :key="s.name" class="source-item">
            <div class="source-row">
              <div class="source-info">
                <span class="source-name">{{ s.label }}</span>
                <span class="tag" :class="s.configured ? 'tag-ok' : 'tag-off'">
                  {{ s.configured ? '✅ 已配置' : '❌ 未配置' }}
                </span>
                <span v-if="s.current_value" class="source-types" style="color: #64748b;">
                  {{ s.current_value }}
                </span>
              </div>
              <button class="btn btn-sm" @click="startEditLLM(s)">
                {{ s.configured ? '修改' : '配置' }}
              </button>
            </div>
            <div v-if="s.editing" class="edit-form">
              <input v-model="s.newValue"
                     :placeholder="s.configured ? '输入新值' : (s.value_type === 'password' ? '输入 API Key' : '输入 URL')"
                     :type="s.value_type === 'password' ? 'password' : 'text'" />
              <button class="btn btn-primary btn-sm" @click="saveLLMConfig(s)"
                      :disabled="saving[s.name]">
                {{ saving[s.name] ? '保存中...' : '保存' }}
              </button>
              <button class="btn btn-sm" @click="cancelEditLLM(s)">取消</button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.summary-bar {
  display: flex; gap: 24px; padding: 12px 16px; margin-bottom: 16px;
  background: #0f172a; border-radius: 8px; font-size: 14px; color: #94a3b8;
}
.summary-item { display: flex; align-items: center; gap: 4px; }
.summary-num { color: #60a5fa; font-weight: 700; font-size: 18px; }

.msg {
  padding: 8px 12px; margin-bottom: 12px; font-size: 13px; border-radius: 6px;
}
.msg-ok { background: #052e16; color: #86efac; border-left: 3px solid #22c55e; }
.msg-error { background: #1c1917; color: #fca5a5; border-left: 3px solid #ef4444; }

.group-section {
  margin-bottom: 16px; border: 1px solid #1e293b; border-radius: 8px; overflow: hidden;
}
.group-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; background: #0f172a; cursor: pointer; font-weight: 600;
  user-select: none;
}
.group-header:hover { background: #1e293b; }
.toggle { color: #64748b; font-size: 12px; }
.group-desc { padding: 0 16px; margin: 0; color: #64748b; font-size: 12px; }

.source-list { padding: 8px; }
.source-item {
  padding: 10px 12px; border-radius: 6px; margin-bottom: 4px;
  background: #0f172a; transition: background 0.1s;
}
.source-item:hover { background: #1e293b; }
.source-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.source-info { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.source-name { font-weight: 500; font-size: 14px; color: #e2e8f0; }
.source-types { font-size: 12px; color: #64748b; }
.source-actions { display: flex; gap: 4px; }

.tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; white-space: nowrap; }
.tag-ok { background: #052e16; color: #86efac; }
.tag-off { background: #1c1917; color: #fca5a5; }

.feed-meta {
  display: flex; gap: 24px; padding: 8px 12px; margin-bottom: 8px;
  background: #0f172a; border-radius: 6px; font-size: 12px; color: #94a3b8;
}
.feed-item.feed-empty { opacity: 0.5; }
.feed-time { font-size: 11px; color: #64748b; white-space: nowrap; }

.edit-form {
  display: flex; gap: 8px; margin-top: 8px; padding-top: 8px;
  border-top: 1px solid #1e293b;
}
.edit-form input { flex: 1; padding: 6px 10px; background: #1e293b; border: 1px solid #334155;
  border-radius: 4px; color: #e2e8f0; font-size: 13px; }
</style>