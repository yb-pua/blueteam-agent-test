<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiGet, apiPost, apiDelete } from '../api/client.js'
import MarkdownContent from '../components/MarkdownContent.vue'

const route = useRoute()
const router = useRouter()

const question = ref('')
const messages = ref([])
const loading = ref(false)
const configError = ref(false)

// 会话状态
const sessions = ref([])
const currentSessionId = ref(null)
const sessionsLoading = ref(false)
const sessionsOpen = ref(true)  // 移动端可折叠

// 情报来源选择
const sources = ref([])          // 全部可用源元信息
const selectedSources = ref([])  // 用户勾选的源名（空=不查情报源）
const sourcesOpen = ref(false)   // 下拉面板展开
const sourcesLoading = ref(false)

// 思考强度（对接 OpenAI reasoning_effort: low/medium/high）
const thinkingOptions = [
  { value: 'low', label: '⚡ 低', hint: '快速响应' },
  { value: 'medium', label: '🎯 中', hint: '平衡' },
  { value: 'high', label: '🧠 高', hint: '深度推理' },
]
const thinking = ref('medium')
const thinkingOpen = ref(false)

// Slash 命令面板（/ 呼出已安装 skill）
const skills = ref([])
const slashOpen = ref(false)
const slashActive = ref(-1)

const examples = [
  '分析一下 1.1.1.1 这个 IP',
  '帮我看看这个告警：GET /product?id=1 UNION SELECT password FROM users',
  '查一下 example.com 有没有威胁',
]

const messagesBox = ref(null)
const inputBox = ref(null)
const inputWrap = ref(null)
const sourceWrap = ref(null)
const thinkingWrap = ref(null)

// ---- 会话列表 ----

async function loadSessions() {
  sessionsLoading.value = true
  try {
    const data = await apiGet('/chat/sessions')
    sessions.value = data.items || []
  } catch (e) {
    console.error('加载会话列表失败:', e.message)
  } finally {
    sessionsLoading.value = false
  }
}

async function loadSessionMessages(sessionId) {
  currentSessionId.value = sessionId
  messages.value = []
  try {
    const data = await apiGet(`/chat/sessions/${sessionId}/messages`)
    messages.value = data.items || []
    scrollToBottom()
  } catch (e) {
    messages.value = [{ role: 'assistant', content: `❌ 加载会话失败: ${e.message}` }]
  }
}

async function selectSession(sessionId) {
  await loadSessionMessages(sessionId)
}

async function newSession() {
  currentSessionId.value = null
  messages.value = []
  configError.value = false
  question.value = ''
  await loadSessions()
}

async function deleteSession(sessionId, e) {
  e.stopPropagation()
  if (!confirm('确定删除该会话吗？')) return
  try {
    await apiDelete(`/chat/sessions/${sessionId}`)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
      messages.value = []
    }
    await loadSessions()
  } catch (err) {
    alert('删除失败: ' + err.message)
  }
}

// ---- 情报来源 ----

async function loadSources() {
  sourcesLoading.value = true
  try {
    const data = await apiGet('/sources')
    // 显示全部情报源（未配置 Key 的源置灰不可选，与配置页一致）
    sources.value = data.items || []
    // 默认全选可用源（已配置 或 无需 Key）
    selectedSources.value = sources.value.filter(s => s.available).map(s => s.name)
  } catch (e) {
    console.error('加载情报源失败:', e.message)
  } finally {
    sourcesLoading.value = false
  }
}

function toggleSource(name) {
  const s = sources.value.find(x => x.name === name)
  if (s && !s.available) return  // 未配置 Key 的源不可勾选
  const i = selectedSources.value.indexOf(name)
  if (i >= 0) selectedSources.value.splice(i, 1)
  else selectedSources.value.push(name)
}

function selectAllSources() {
  selectedSources.value = sources.value.filter(s => s.available).map(s => s.name)
}

function selectNoneSources() {
  selectedSources.value = []
}

function sourceLabel(name) {
  const s = sources.value.find(x => x.name === name)
  return s ? s.label : name
}

function selectedLabel() {
  if (selectedSources.value.length === 0) return '纯对话'
  if (selectedSources.value.length === sources.value.length) return `数据源 (${selectedSources.value.length})`
  return `数据源 (${selectedSources.value.length})`
}

// ---- Slash 命令 ----

async function loadSkills() {
  try {
    const data = await apiGet('/skills')
    skills.value = data.items || []
  } catch (e) {
    console.error('加载 skill 列表失败:', e.message)
  }
}

function slashKeyword() {
  // 输入框以 "/" 开头且无空格时显示面板；有空格视为携带参数，关闭面板
  const text = question.value
  if (text.startsWith('/') && !text.includes(' ')) {
    return text.slice(1)
  }
  return null
}

function handleInput() {
  const kw = slashKeyword()
  if (kw !== null) {
    slashActive.value = -1
    slashOpen.value = true
  } else {
    slashOpen.value = false
  }
}

function filteredSkills() {
  const kw = slashKeyword()
  if (kw === null) return []
  const q = kw.toLowerCase()
  if (!q) return skills.value
  return skills.value.filter(s =>
    s.name.toLowerCase().includes(q) || (s.description || '').toLowerCase().includes(q)
  )
}

function selectSlashSkill(skill) {
  question.value = `/${skill.name} `
  slashOpen.value = false
  slashActive.value = -1
  inputBox.value?.focus()
}

function onKeydown(e) {
  const list = filteredSkills()
  // 方向键导航
  if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && slashOpen.value && list.length) {
    e.preventDefault()
    const step = e.key === 'ArrowDown' ? 1 : -1
    slashActive.value = (slashActive.value + step + list.length) % list.length
    return
  }
  // Tab 补全
  if (e.key === 'Tab' && slashOpen.value && list.length) {
    e.preventDefault()
    selectSlashSkill(list[slashActive.value >= 0 ? slashActive.value : 0])
    return
  }
  // Enter：面板打开时选中 skill，否则发送
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    if (slashOpen.value && list.length) {
      e.preventDefault()
      selectSlashSkill(list[slashActive.value >= 0 ? slashActive.value : 0])
      return
    }
    e.preventDefault()
    ask(question.value)
  }
}

function parseSlashCommand(text) {
  // /skill_name 参数...；参数可为 JSON 或纯文本
  const m = text.match(/^\/([^\s/]+)\s*([\s\S]*)$/)
  if (!m) return null
  const name = m[1]
  const rest = (m[2] || '').trim()
  let params = {}
  if (rest) {
    try {
      const parsed = JSON.parse(rest)
      params = (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) ? parsed : { value: parsed }
    } catch {
      params = { value: rest }
    }
  }
  return { name, params, skill: skills.value.find(s => s.name === name) || null }
}

function formatSlashOutput(output) {
  if (output == null) return '_（无输出）_'
  if (typeof output === 'string') return output
  if (typeof output === 'object') {
    if (output.markdown) return output.markdown
    return '```json\n' + JSON.stringify(output, null, 2) + '\n```'
  }
  return String(output)
}

async function runSlash(text, cmd) {
  messages.value.push({ role: 'user', content: text })
  if (!cmd.skill) {
    messages.value.push({
      role: 'assistant',
      content: `❌ 未找到 skill \`/${cmd.name}\`。在输入框输入 \`/\` 可查看已安装 Skill 列表。`,
    })
    scrollToBottom()
    return
  }
  loading.value = true
  scrollToBottom()
  try {
    const resp = await apiPost('/skills/slash', { name: cmd.name, params: cmd.params })
    const body = resp.ok
      ? `#### ⚡ Slash \`/${cmd.name}\`\n\n${formatSlashOutput(resp.output)}`
      : `#### ⚡ Slash \`/${cmd.name}\` 执行失败\n\n> ${resp.error || '未知错误'}`
    messages.value.push({ role: 'assistant', content: body })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: `❌ Slash 执行失败: ${e.message}` })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// ---- 提问 ----

async function ask(input) {
  const text = (input ?? '').trim()
  if (!text) return
  question.value = ''
  const cmd = parseSlashCommand(text)
  if (cmd) {
    // /命令 形式：直接执行 skill（不经 LLM）
    await runSlash(text, cmd)
    return
  }
  await normalAsk(text)
}

async function normalAsk(text) {
  messages.value.push({ role: 'user', content: text })
  loading.value = true
  configError.value = false
  sourcesOpen.value = false
  thinkingOpen.value = false
  scrollToBottom()

  try {
    const resp = await apiPost('/ask', {
      question: text,
      session_id: currentSessionId.value,
      sources: selectedSources.value.length > 0 ? selectedSources.value : null,
      thinking: thinking.value,  // low/medium/high → reasoning_effort
    })
    currentSessionId.value = resp.session_id
    messages.value.push({ role: 'assistant', content: resp.answer })
    await loadSessions()  // 刷新会话列表（新会话标题/时间）
    scrollToBottom()
  } catch (e) {
    if (e.message.includes('500') || e.message.includes('401')) {
      configError.value = true
      messages.value.push({
        role: 'assistant',
        content: '⚠️ LLM 未配置或配置有误。请在 **⚙️ 配置** 页面填写 LLM API Key / 地址 / 模型名，或设置环境变量后再试。',
      })
    } else {
      messages.value.push({ role: 'assistant', content: `❌ 请求失败: ${e.message}` })
    }
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesBox.value) messagesBox.value.scrollTop = messagesBox.value.scrollHeight
  })
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ---- 点击外部关闭下拉面板 ----

function onDocClick(e) {
  if (inputWrap.value && !inputWrap.value.contains(e.target)) slashOpen.value = false
  if (sourceWrap.value && !sourceWrap.value.contains(e.target)) sourcesOpen.value = false
  if (thinkingWrap.value && !thinkingWrap.value.contains(e.target)) thinkingOpen.value = false
}

onMounted(async () => {
  await Promise.all([loadSessions(), loadSources(), loadSkills()])
  document.addEventListener('click', onDocClick)
  // 若存在最近会话，自动载入最后一个
  if (sessions.value.length > 0) {
    await loadSessionMessages(sessions.value[0].id)
  }
  // 跨页跳转携带提问参数（如 IoC 页「一键 AI 分析」）
  const q = route.query.q
  if (q && typeof q === 'string' && q.trim()) {
    router.replace({ query: {} })  // 清理参数，避免刷新重复触发
    await ask(q.trim())
  }
})

onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
})
</script>

<template>
  <div class="chat-layout" style="margin-top: 20px;">
    <!-- 会话侧栏 -->
    <aside class="session-sidebar" :class="{ collapsed: !sessionsOpen }">
      <div style="display: flex; gap: 8px; margin-bottom: 12px;">
        <button class="btn btn-primary" style="flex: 1; justify-content: center;" @click="newSession">＋ 新会话</button>
      </div>
      <div style="font-size: 12px; color: #64748b; margin-bottom: 6px; display: flex; justify-content: space-between;">
        <span>历史会话</span>
        <span v-if="sessionsLoading">加载中...</span>
      </div>
      <div class="session-list">
        <div v-if="sessions.length === 0 && !sessionsLoading" style="color: #64748b; font-size: 13px; padding: 12px; text-align: center;">
          暂无历史会话
        </div>
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === currentSessionId }"
          @click="selectSession(s.id)"
        >
          <div style="flex: 1; min-width: 0;">
            <div class="session-title">{{ s.title }}</div>
            <div class="session-meta">
              {{ formatTime(s.updated_at) }} · {{ s.msg_count }} 条
            </div>
          </div>
          <button class="session-del" title="删除" @click="deleteSession(s.id, $event)">✕</button>
        </div>
      </div>
    </aside>

    <!-- 主对话区 -->
    <div class="card chat-main" style="margin: 0;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h2 style="margin: 0;">AI 威胁分析</h2>
        <button class="btn btn-sm" @click="sessionsOpen = !sessionsOpen">
          {{ sessionsOpen ? '收起会话' : '展开会话' }}
        </button>
      </div>
      <p style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
        用自然语言描述你要查询的威胁情报，AI 会自动查询所选情报源并给出专业分析。输入 <code style="background:#1e293b;padding:1px 5px;border-radius:4px;">/</code> 可呼出已安装的 Skill 命令。会话历史自动保存。
      </p>

      <div v-if="configError" class="card" style="border-color: #713f12; background: #1c1917; margin-bottom: 16px; padding: 12px;">
        <p style="color: #fcd34d; font-size: 13px;">
          ⚠️ LLM 服务未配置。请前往 <router-link to="/settings">⚙️ 配置</router-link> 页面设置 LLM API Key 与地址。
        </p>
      </div>

      <div ref="messagesBox" class="messages-box">
        <div v-if="messages.length === 0 && !loading" class="empty-state">
          <div style="font-size: 48px; margin-bottom: 16px;">🛡️</div>
          <p style="margin-bottom: 16px; color: #475569;">输入问题开始分析，例如：</p>
          <div style="display: flex; flex-direction: column; gap: 8px; width: 100%; max-width: 420px;">
            <button
              v-for="ex in examples"
              :key="ex"
              @click="ask(ex)"
              class="btn"
              style="background: #1e293b; border: 1px solid #334155; color: #94a3b8; padding: 10px; text-align: left;"
            >{{ ex }}</button>
          </div>
        </div>

        <div
          v-for="(msg, i) in messages"
          :key="i"
          class="msg"
          :class="msg.role === 'user' ? 'msg-user' : 'msg-ai'"
        >
          <div class="msg-label">{{ msg.role === 'user' ? '🧑‍💻 你' : '🤖 AI 分析师' }}</div>
          <MarkdownContent v-if="msg.role === 'assistant'" :content="msg.content" />
          <div v-else class="msg-user-text">{{ msg.content }}</div>
        </div>

        <div v-if="loading" class="msg msg-ai">
          <div class="msg-label">🤖 AI 分析师</div>
          <div style="color: #94a3b8;">正在查询情报源<span class="dots"><i>.</i><i>.</i><i>.</i></span></div>
        </div>
      </div>

      <!-- 输入区：输入框(+Slash面板) + 思考强度 + 情报源复选 + 发送 -->
      <div style="display: flex; gap: 8px; margin-top: 12px;">
        <div ref="inputWrap" class="input-wrap" style="position: relative; flex: 1; display: flex;">
          <input
            ref="inputBox"
            v-model="question"
            @input="handleInput"
            @keydown="onKeydown"
            placeholder="输入问题... 输入 / 呼出 Skill"
            :disabled="loading"
            style="flex: 1; width: 100%;"
          />
          <!-- Slash 命令面板 -->
          <div v-if="slashOpen" class="slash-panel">
            <div class="slash-header">
              <span style="font-weight: 600;">Slash 命令</span>
              <span class="slash-hint">Tab 补全 · ↑↓ 选择 · Enter 执行</span>
            </div>
            <div v-if="skills.length === 0" class="slash-empty">
              暂无已安装 Skill，可到 <router-link to="/skills" style="color:#60a5fa;">🧩 Skill 页</router-link> 安装
            </div>
            <div v-else-if="filteredSkills().length === 0" class="slash-empty">
              没有匹配的 Skill：<code>/{{ slashKeyword() }}</code>
            </div>
            <div v-else class="slash-list">
              <div
                v-for="(s, i) in filteredSkills()"
                :key="s.name"
                class="slash-item"
                :class="{ active: i === slashActive }"
                @mousedown.prevent="selectSlashSkill(s)"
              >
                <span class="slash-name">/{{ s.name }}</span>
                <span class="slash-desc">{{ s.description }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 思考强度选择 -->
        <div ref="thinkingWrap" class="thinking-select" style="position: relative;">
          <button
            class="btn thinking-toggle"
            :disabled="loading"
            @click="thinkingOpen = !thinkingOpen"
          >
            {{ (thinkingOptions.find(o => o.value === thinking) || thinkingOptions[1]).label }}
            <span class="caret">{{ thinkingOpen ? '▲' : '▼' }}</span>
          </button>
          <div v-if="thinkingOpen" class="thinking-panel">
            <div style="font-size: 11px; color: #64748b; margin-bottom: 6px;">思考强度（reasoning_effort）</div>
            <div
              v-for="opt in thinkingOptions"
              :key="opt.value"
              class="thinking-item"
              :class="{ active: opt.value === thinking }"
              @click="thinking = opt.value; thinkingOpen = false"
            >
              <span>{{ opt.label }}</span>
              <span class="thinking-hint">{{ opt.hint }}</span>
            </div>
          </div>
        </div>

        <div ref="sourceWrap" class="source-select" style="position: relative;">
          <button
            class="btn source-toggle"
            :disabled="loading || sourcesLoading"
            @click="sourcesOpen = !sourcesOpen"
          >
            🛰️ {{ selectedLabel() }}
            <span class="caret">{{ sourcesOpen ? '▲' : '▼' }}</span>
          </button>
          <div v-if="sourcesOpen" class="source-panel">
            <div class="source-actions">
              <button class="btn btn-sm" @click="selectAllSources">全选</button>
              <button class="btn btn-sm" @click="selectNoneSources">清空</button>
              <span style="font-size: 11px; color: #64748b; margin-left: auto;">AI 仅查询勾选的源</span>
            </div>
            <div class="source-list">
              <label
                v-for="s in sources"
                :key="s.name"
                class="source-item"
                :class="{ disabled: !s.available }"
                :title="s.available ? '' : '未配置 API Key，到 ⚙️ 配置 页添加后可启用'"
              >
                <input
                  type="checkbox"
                  :checked="selectedSources.includes(s.name)"
                  :disabled="!s.available"
                  @change="toggleSource(s.name)"
                />
                <span>{{ s.label }}</span>
                <span v-if="!s.available" class="source-lock">🔒 未配置</span>
                <span v-else class="source-types">{{ s.supported_types.join(' / ') }}</span>
              </label>
              <div v-if="sources.length === 0 && !sourcesLoading" style="color: #64748b; font-size: 12px; padding: 8px;">
                暂无情报源，请在 ⚙️ 配置 页面添加 API Key。
              </div>
            </div>
          </div>
        </div>

        <button class="btn btn-primary" @click="ask(question)" :disabled="loading || !question.trim()">
          {{ loading ? '分析中...' : '发送' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex;
  gap: 16px;
  align-items: stretch;
  min-height: calc(100vh - 160px);
}

.session-sidebar {
  flex: 0 0 240px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 160px);
}
.session-sidebar.collapsed { flex-basis: 0; padding: 16px 8px; overflow: hidden; }

.session-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
}
.session-item:hover { background: #293548; }
.session-item.active { background: #1e3a5f; border-color: #2563eb; }
.session-title {
  font-size: 13px;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-meta { font-size: 11px; color: #64748b; margin-top: 2px; }
.session-del {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
  border-radius: 4px;
  flex-shrink: 0;
  visibility: hidden;
}
.session-item:hover .session-del { visibility: visible; }
.session-del:hover { color: #fca5a5; background: #3f1d1d; }

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.messages-box {
  flex: 1;
  overflow-y: auto;
  min-height: 320px;
  max-height: calc(100vh - 320px);
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 320px;
}
.msg {
  padding: 12px 16px;
  margin-bottom: 10px;
  border-radius: 8px;
  border: 1px solid #334155;
  line-height: 1.7;
  font-size: 14px;
}
.msg-user { background: #1e3a5f; border-left: 3px solid #2563eb; }
.msg-ai { background: #1e293b; border-left: 3px solid #059669; }
.msg-label { font-size: 12px; color: #94a3b8; margin-bottom: 6px; }
.msg-user-text { white-space: pre-wrap; }
.dots i {
  display: inline-block;
  width: 4px; height: 4px;
  margin: 0 1px;
  background: #60a5fa;
  border-radius: 50%;
  animation: blink 1.4s infinite;
}
.dots i:nth-child(2) { animation-delay: 0.2s; }
.dots i:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.2; } 40% { opacity: 1; } }

/* 通用下拉按钮 */
.caret { font-size: 10px; margin-left: 4px; color: #64748b; }
.thinking-toggle, .source-toggle {
  white-space: nowrap;
  background: #1e293b;
  border: 1px solid #334155;
  color: #e2e8f0;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Slash 命令面板 */
.slash-panel {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px);
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.45);
  z-index: 60;
  padding: 8px;
}
.slash-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #e2e8f0;
  padding: 4px 6px 8px;
  border-bottom: 1px solid #334155;
  margin-bottom: 6px;
}
.slash-hint { font-size: 11px; color: #64748b; }
.slash-empty {
  color: #94a3b8;
  font-size: 13px;
  padding: 14px 8px;
  text-align: center;
}
.slash-list {
  max-height: 260px;
  overflow-y: auto;
}
.slash-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
}
.slash-item:hover { background: #293548; }
.slash-item.active { background: #1e3a5f; border-color: #2563eb; }
.slash-name { font-size: 13px; color: #7dd3fc; font-weight: 600; }
.slash-desc {
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 思考强度面板 */
.thinking-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  width: 200px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.45);
  z-index: 50;
  padding: 10px;
}
.thinking-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #e2e8f0;
}
.thinking-item:hover { background: #293548; }
.thinking-item.active { background: #1e3a5f; border-color: #2563eb; color: #93c5fd; }
.thinking-hint { font-size: 11px; color: #64748b; }

/* 情报源下拉 */
.source-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  width: 340px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.45);
  z-index: 50;
  padding: 12px;
}
.source-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #334155;
}
.source-list {
  max-height: 260px;
  overflow-y: auto;
}
.source-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 4px;
  cursor: pointer;
  font-size: 13px;
  color: #e2e8f0;
  border-radius: 4px;
}
.source-item:hover { background: #293548; }
.source-item.disabled { opacity: 0.45; cursor: not-allowed; }
.source-item.disabled:hover { background: transparent; }
.source-item input[type="checkbox"] { width: auto; accent-color: #2563eb; }
.source-types { font-size: 11px; color: #64748b; margin-left: auto; }
.source-lock { font-size: 11px; color: #94a3b8; margin-left: auto; white-space: nowrap; }

@media (max-width: 768px) {
  .chat-layout { flex-direction: column; }
  .session-sidebar { flex-basis: auto; max-height: 200px; }
  .source-panel { width: 280px; }
  .thinking-panel { width: 160px; }
}
</style>
