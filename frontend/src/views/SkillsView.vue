<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { apiGet, apiPost, apiDelete, apiUpload } from '../api/client.js'

const skills = ref([])
const stats = ref({})
const loading = ref(false)
const message = ref('')
const messageType = ref('')
const installMode = ref('zip')

// ---- ZIP 上传 ----
const uploading = ref(false)
const dragOver = ref(false)
const fileInput = ref(null)

// ---- 表单安装 ----
const showForm = ref(false)
const form = ref({ name: '', description: '', parameters: '', code: '' })
const installing = ref(false)

// ---- 详情面板 ----
const expandedSkill = ref(null)
const detailTab = ref('overview') // overview | code | edit
const detailInfo = ref(null)
const detailLoading = ref(false)
const editForm = ref({ description: '', parameters: '', code: '', skill_md: '' })
const savingEdit = ref(false)

const TEMPLATE_REPORT = `async def run(params):
    """将多源情报结果整理为格式化摘要。"""
    ioc = params.get("ioc", "")
    summary = params.get("summary", "")
    sources = params.get("sources", [])
    lines = [f"### 情报摘要 - {ioc}", ""]
    if summary:
        lines.append(f"**核心结论**: {summary}")
    if sources:
        lines.append("**涉及来源**:")
        for s in sources:
            lines.append(f"- {s}")
    lines.append("")
    lines.append("> 本摘要由 skill_report_summarizer 生成")
    return {"markdown": chr(10).join(lines), "ioc": ioc}`

// ---- 数据加载 ----

async function loadSkills() {
  loading.value = true
  try {
    const [skillData, statsData] = await Promise.all([
      apiGet('/skills'),
      apiGet('/skills/stats'),
    ])
    skills.value = skillData.items || []
    stats.value = statsData.stats || {}
  } catch (e) {
    setMessage('加载失败: ' + e.message, 'error')
  } finally {
    loading.value = false
  }
}

function setMessage(text, type = 'success') {
  message.value = text
  messageType.value = type
  setTimeout(() => { if (message.value === text) message.value = '' }, 4000)
}

// ---- ZIP 上传 ----

function onDragOver(e) { e.preventDefault(); dragOver.value = true }
function onDragLeave() { dragOver.value = false }
function onDrop(e) {
  e.preventDefault(); dragOver.value = false
  if (e.dataTransfer.files.length > 0) uploadZip(e.dataTransfer.files[0])
}
function triggerFileInput() { fileInput.value?.click() }
function onFileSelected(e) {
  if (e.target.files.length > 0) uploadZip(e.target.files[0])
  e.target.value = ''
}

async function uploadZip(file) {
  if (!file.name.toLowerCase().endsWith('.zip')) { setMessage('请上传 .zip 格式', 'error'); return }
  uploading.value = true; setMessage('')
  try {
    const resp = await apiUpload('/skills/install-zip', file)
    setMessage(`安装成功: ${resp.skill?.name || file.name}`)
    await loadSkills()
  } catch (e) { setMessage('安装失败: ' + e.message, 'error') }
  finally { uploading.value = false }
}

// ---- 表单安装 ----

function openForm() {
  showForm.value = true
  form.value = {
    name: '', description: '',
    parameters: JSON.stringify({ type: 'object', properties: {
      ioc: { type: 'string', description: 'IoC 值' },
      summary: { type: 'string', description: '核心结论' },
      sources: { type: 'array', items: { type: 'string' }, description: '情报来源' },
    }}, null, 2),
    code: TEMPLATE_REPORT,
  }
}

function useTemplate() {
  form.value = {
    name: 'report_summarizer',
    description: '将多源威胁情报结果整理为格式化摘要。',
    parameters: JSON.stringify({ type: 'object', properties: {
      ioc: { type: 'string', description: 'IoC 值' },
      summary: { type: 'string', description: '核心结论' },
      sources: { type: 'array', items: { type: 'string' }, description: '情报来源' },
    }}, null, 2),
    code: TEMPLATE_REPORT,
  }
}

async function install() {
  if (!form.value.name.trim()) { setMessage('请输入 skill 名称', 'error'); return }
  installing.value = true; setMessage('')
  try {
    let parameters = {}
    try { parameters = form.value.parameters ? JSON.parse(form.value.parameters) : {} }
    catch { setMessage('parameters 不是合法 JSON', 'error'); installing.value = false; return }
    await apiPost('/skills/install', {
      name: form.value.name.trim(), description: form.value.description,
      parameters, code: form.value.code,
    })
    setMessage(`安装成功: ${form.value.name.trim()}`)
    showForm.value = false; await loadSkills()
  } catch (e) { setMessage('安装失败: ' + e.message, 'error') }
  finally { installing.value = false }
}

// ---- 启用/禁用 ----

async function toggleEnabled(name, current) {
  try {
    await apiPut(`/skills/${name}/toggle`, { enabled: !current })
    await loadSkills()
    setMessage(`${name} 已${current ? '禁用' : '启用'}`)
  } catch (e) { setMessage('操作失败: ' + e.message, 'error') }
}

// ---- 详情面板 ----

async function toggleDetail(name) {
  if (expandedSkill.value === name) {
    expandedSkill.value = null; detailInfo.value = null; return
  }
  expandedSkill.value = name
  detailTab.value = 'overview'
  detailLoading.value = true
  try {
    detailInfo.value = await apiGet(`/skills/${name}/detail`)
    // 初始化编辑表单
    editForm.value = {
      description: detailInfo.value.description || '',
      parameters: detailInfo.value.skill_json?.parameters
        ? JSON.stringify(detailInfo.value.skill_json.parameters, null, 2) : '{}',
      code: detailInfo.value.handler_code || '',
      skill_md: detailInfo.value.skill_md || '',
    }
  } catch (e) { setMessage('加载详情失败: ' + e.message, 'error') }
  finally { detailLoading.value = false }
}

// ---- 编辑保存 ----

async function saveEdit(name) {
  savingEdit.value = true
  try {
    let parameters = {}
    try { parameters = editForm.value.parameters ? JSON.parse(editForm.value.parameters) : {} }
    catch { setMessage('parameters 不是合法 JSON', 'error'); savingEdit.value = false; return }
    await apiPut(`/skills/${name}`, {
      description: editForm.value.description,
      parameters,
      code: editForm.value.code,
      skill_md: editForm.value.skill_md,
    })
    setMessage(`${name} 已保存`)
    detailTab.value = 'overview'
    await loadSkills()
    // 重新加载详情
    detailInfo.value = await apiGet(`/skills/${name}/detail`)
  } catch (e) { setMessage('保存失败: ' + e.message, 'error') }
  finally { savingEdit.value = false }
}

// ---- 卸载 ----

async function removeSkill(name) {
  if (!confirm(`确定卸载 skill「${name}」吗？`)) return
  try {
    await apiDelete(`/skills/${name}`)
    if (expandedSkill.value === name) { expandedSkill.value = null; detailInfo.value = null }
    setMessage(`已卸载: ${name}`); await loadSkills()
  } catch (e) { setMessage('卸载失败: ' + e.message, 'error') }
}

// ---- 工具函数 ----

function apiPut(path, body) {
  return fetch(`/api/v1${path}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
}

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatMarkdown(md) {
  if (!md) return ''
  return md
    .replace(/^### (.+)$/gm, '<h3 style="color:#e2e8f0;margin:12px 0 6px;">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="color:#e2e8f0;margin:16px 0 8px;">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="color:#e2e8f0;margin:16px 0 8px;">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^> (.+)$/gm, '<blockquote style="color:#94a3b8;border-left:3px solid #334155;padding-left:12px;margin:8px 0;">$1</blockquote>')
    .replace(/\n/g, '<br>')
}

onMounted(loadSkills)
</script>

<template>
  <div class="card" style="margin-top: 20px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <h2 style="margin: 0;">🧩 Skill 管理</h2>
    </div>
    <p style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">
      管理 AI Agent 的可扩展函数工具。安装后 AI 分析时可调用，支持启用/禁用、编辑、查看执行统计。
    </p>

    <!-- 消息提示 -->
    <div v-if="message" :style="{
      padding: '8px 12px', marginBottom: '12px',
      background: messageType === 'error' ? '#1c1917' : '#052e16',
      borderLeft: '3px solid ' + (messageType === 'error' ? '#ef4444' : '#22c55e'),
      color: messageType === 'error' ? '#fca5a5' : '#86efac',
      fontSize: '13px', borderRadius: '4px',
    }">{{ message }}</div>

    <!-- 安装模式切换 -->
    <div style="display: flex; gap: 8px; margin-bottom: 16px;">
      <button class="btn" :class="installMode === 'zip' ? 'btn-primary' : ''"
              @click="installMode = 'zip'; showForm = false">📦 上传 ZIP</button>
      <button class="btn" :class="installMode === 'form' ? 'btn-primary' : ''"
              @click="installMode = 'form'; showForm = true">✏️ 粘贴安装</button>
    </div>

    <!-- ZIP 上传区 -->
    <div v-if="installMode === 'zip' && !showForm" class="card"
         @dragover.prevent="onDragOver" @dragleave="onDragLeave" @drop.prevent="onDrop"
         :style="{
           border: '2px dashed ' + (dragOver ? '#60a5fa' : '#334155'),
           background: dragOver ? '#172554' : '#0f172a',
           padding: '32px', textAlign: 'center', marginBottom: '16px', transition: 'all 0.2s',
         }">
      <input ref="fileInput" type="file" accept=".zip" style="display: none;" @change="onFileSelected" />
      <div v-if="uploading" style="color: #60a5fa;">
        <p style="font-size: 24px;">⏳</p><p>正在安装...</p>
      </div>
      <div v-else>
        <p style="font-size: 36px; margin: 0 0 8px 0;">📦</p>
        <p style="margin: 0 0 12px 0; color: #e2e8f0; font-size: 14px;">
          拖拽 ZIP 到此处，或 <a href="#" @click.prevent="triggerFileInput" style="color: #60a5fa;">点击选择</a>
        </p>
        <p style="margin: 0; color: #64748b; font-size: 12px;">ZIP 内须包含 SKILL.md + handler.py</p>
      </div>
    </div>

    <!-- 表单安装 -->
    <div v-if="installMode === 'form' && showForm" class="card" style="background: #0f172a; margin-bottom: 16px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <h3 style="margin: 0;">安装新 Skill</h3>
        <button class="btn btn-sm" @click="useTemplate">使用示例模板</button>
      </div>
      <label>名称（工具名 skill_&lt;name&gt;）</label>
      <input v-model="form.name" placeholder="如 report_summarizer" style="margin-bottom: 10px;" />
      <label>描述（LLM 据此判断何时调用）</label>
      <input v-model="form.description" placeholder="用自然语言描述功能" style="margin-bottom: 10px;" />
      <label>参数 Schema (JSON)</label>
      <textarea v-model="form.parameters" style="min-height: 120px; font-size: 12px; margin-bottom: 10px;"></textarea>
      <label>处理器源码（async def run(params) -> dict）</label>
      <textarea v-model="form.code" style="min-height: 200px; font-size: 12px; margin-bottom: 10px;"></textarea>
      <button class="btn btn-primary" @click="install" :disabled="installing">
        {{ installing ? '安装中...' : '安装' }}
      </button>
    </div>

    <!-- Skill 列表 -->
    <div v-if="loading" style="color: #94a3b8;">加载中...</div>
    <div v-else-if="skills.length === 0" style="color: #64748b; font-size: 13px; padding: 20px 0; text-align: center;">
      暂无已安装的 Skill。上传 ZIP 或点击「粘贴安装」添加。
    </div>

    <div v-else>
      <div v-for="s in skills" :key="s.name" class="card" style="padding: 12px; margin-bottom: 8px;">
        <!-- 列表项：名称 + 开关 + 统计摘要 -->
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
          <div style="flex: 1; min-width: 0; cursor: pointer;" @click="toggleDetail(s.name)">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <strong style="font-size: 14px; white-space: nowrap;">{{ s.name }}</strong>
              <span class="tag" style="font-size: 11px;">skill_{{ s.name }}</span>
              <span v-if="stats[s.name]" style="font-size: 11px; color: #64748b;">
                执行 {{ stats[s.name].total }} 次
                <span v-if="stats[s.name].fail > 0" style="color: #fca5a5;">({{ stats[s.name].fail }} 失败)</span>
              </span>
            </div>
            <p style="color: #94a3b8; font-size: 13px; margin: 4px 0 0 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              {{ s.description || '无描述' }}
            </p>
          </div>
          <!-- 启用/禁用开关 -->
          <div style="display: flex; align-items: center; gap: 12px; flex-shrink: 0;">
            <label class="toggle" :title="s.enabled !== false ? '已启用 - 点击禁用' : '已禁用 - 点击启用'">
              <input type="checkbox" :checked="s.enabled !== false"
                     @change.stop="toggleEnabled(s.name, s.enabled !== false)" />
              <span class="toggle-slider"></span>
            </label>
            <button class="btn btn-sm" style="color: #fca5a5; flex-shrink: 0;"
                    @click.stop="removeSkill(s.name)">卸载</button>
          </div>
        </div>

        <!-- 详情面板 -->
        <div v-if="expandedSkill === s.name" style="margin-top: 12px; border-top: 1px solid #1e293b; padding-top: 12px;">
          <div v-if="detailLoading" style="color: #64748b; font-size: 13px;">加载详情中...</div>
          <div v-else-if="detailInfo">
            <!-- Tab 切换 -->
            <div style="display: flex; gap: 4px; margin-bottom: 12px;">
              <button v-for="tab in [{key:'overview',label:'📋 概览'},{key:'code',label:'💻 代码'},{key:'edit',label:'✏️ 编辑'}]"
                      :key="tab.key" class="btn btn-sm"
                      :class="detailTab === tab.key ? 'btn-primary' : ''"
                      @click="detailTab = tab.key">{{ tab.label }}</button>
            </div>

            <!-- 概览 Tab -->
            <div v-if="detailTab === 'overview'">
              <table style="width: 100%; font-size: 13px; color: #94a3b8;">
                <tr><td style="padding: 4px 8px 4px 0; white-space: nowrap; color: #64748b;">名称</td>
                    <td style="padding: 4px 0;"><strong style="color: #e2e8f0;">{{ detailInfo.name }}</strong></td></tr>
                <tr><td style="padding: 4px 8px 4px 0; color: #64748b;">状态</td>
                    <td style="padding: 4px 0;">
                      <span :style="{ color: detailInfo.enabled !== false ? '#22c55e' : '#f59e0b' }">
                        {{ detailInfo.enabled !== false ? '✅ 已启用' : '⏸️ 已禁用' }}
                      </span>
                    </td></tr>
                <tr><td style="padding: 4px 8px 4px 0; color: #64748b;">描述</td>
                    <td style="padding: 4px 0; color: #e2e8f0;">{{ detailInfo.description || '-' }}</td></tr>
                <tr v-if="detailInfo.extra_files?.length">
                    <td style="padding: 4px 8px 4px 0; color: #64748b;">附加文件</td>
                    <td style="padding: 4px 0; color: #94a3b8; font-size: 12px;">{{ detailInfo.extra_files.join(', ') }}</td></tr>
              </table>
              <!-- SKILL.md 渲染 -->
              <div v-if="detailInfo.skill_md" style="margin-top: 12px;">
                <h4 style="color: #94a3b8; font-size: 13px; margin: 0 0 6px 0;">📄 SKILL.md</h4>
                <div class="skill-md-content"
                     style="background: #0f172a; padding: 12px; border-radius: 4px; font-size: 13px; color: #cbd5e1; max-height: 300px; overflow-y: auto;"
                     v-html="formatMarkdown(detailInfo.skill_md.replace(/^---[\s\S]*?---\n*/m, ''))"></div>
              </div>
              <!-- 执行统计 -->
              <div v-if="stats[s.name]" style="margin-top: 12px;">
                <h4 style="color: #94a3b8; font-size: 13px; margin: 0 0 6px 0;">📊 执行统计</h4>
                <div style="display: flex; gap: 16px; font-size: 13px;">
                  <span style="color: #e2e8f0;">总执行 <strong>{{ stats[s.name].total }}</strong> 次</span>
                  <span style="color: #22c55e;">成功 {{ stats[s.name].success }}</span>
                  <span v-if="stats[s.name].fail > 0" style="color: #fca5a5;">失败 {{ stats[s.name].fail }}</span>
                  <span style="color: #64748b;">最近 {{ formatTime(stats[s.name].last_run) }}</span>
                </div>
              </div>
              <div v-else style="margin-top: 12px; color: #64748b; font-size: 13px;">📊 暂无执行记录</div>
            </div>

            <!-- 代码 Tab -->
            <div v-if="detailTab === 'code'">
              <h4 style="color: #94a3b8; font-size: 13px; margin: 0 0 6px 0;">handler.py</h4>
              <pre style="background: #0f172a; padding: 12px; border-radius: 4px; font-size: 12px; color: #94a3b8; overflow-x: auto; max-height: 400px; overflow-y: auto; margin: 0;">{{ detailInfo.handler_code || '无代码' }}</pre>
            </div>

            <!-- 编辑 Tab -->
            <div v-if="detailTab === 'edit'">
              <label style="font-size: 13px; color: #94a3b8;">描述</label>
              <input v-model="editForm.description" style="margin-bottom: 10px; width: 100%;" />
              <label style="font-size: 13px; color: #94a3b8;">参数 Schema (JSON)</label>
              <textarea v-model="editForm.parameters" style="min-height: 100px; font-size: 12px; margin-bottom: 10px; width: 100%;"></textarea>
              <label style="font-size: 13px; color: #94a3b8;">处理器源码 (handler.py)</label>
              <textarea v-model="editForm.code" style="min-height: 200px; font-size: 12px; margin-bottom: 10px; width: 100%;"></textarea>
              <label style="font-size: 13px; color: #94a3b8;">SKILL.md</label>
              <textarea v-model="editForm.skill_md" style="min-height: 100px; font-size: 12px; margin-bottom: 10px; width: 100%;"></textarea>
              <div style="display: flex; gap: 8px;">
                <button class="btn btn-primary" @click="saveEdit(s.name)" :disabled="savingEdit">
                  {{ savingEdit ? '保存中...' : '💾 保存' }}
                </button>
                <button class="btn" @click="detailTab = 'overview'">取消</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Toggle switch */
.toggle {
  position: relative; display: inline-block; width: 40px; height: 22px; cursor: pointer; flex-shrink: 0;
}
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute; inset: 0; background: #334155; border-radius: 22px; transition: background 0.2s;
}
.toggle-slider::before {
  content: ''; position: absolute; width: 16px; height: 16px; left: 3px; bottom: 3px;
  background: #94a3b8; border-radius: 50%; transition: transform 0.2s, background 0.2s;
}
.toggle input:checked + .toggle-slider { background: #22c55e; }
.toggle input:checked + .toggle-slider::before { transform: translateX(18px); background: #fff; }
</style>
