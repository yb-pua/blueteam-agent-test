<script setup>
import { ref } from 'vue'
import { apiPost, apiUpload } from '../api/client.js'

// ----- 输入模式 -----
const inputMode = ref('paste') // 'paste' | 'upload'

const rawText = ref('')
const result = ref(null)
const loading = ref(false)

// 上传相关
const uploadFile = ref(null)
const dragOver = ref(false)

// ----- 示例 -----
const examples = [
  '192.168.1.1 - - [20/Jul/2026:10:15:30 +0800] "GET /product?id=1 UNION SELECT username,password FROM users HTTP/1.1" 500 1234',
  '10.0.0.1 - - [20/Jul/2026:11:22:33 +0800] "GET /search?q=%3Cscript%3Ealert(1)%3C/script%3E HTTP/1.1" 403 567',
  'Mar 15 09:22:17 webserver sshd[12345]: Failed password for root from 10.10.10.10 port 56234 ssh2',
  '192.168.1.1 - - [20/Jul/2026:14:05:00 +0800] "GET /index.php?page=../../etc/passwd HTTP/1.1" 200 2345',
  '10.0.0.1 - - [20/Jul/2026:08:12:44 +0800] "POST /upload.php HTTP/1.1" 200 789 "-" "Mozilla/5.0 (compatible; curl/7.68.0)"',
]

function loadExample(idx) {
  inputMode.value = 'paste'
  rawText.value = examples[idx]
  uploadFile.value = null
}

// ----- 提交 -----
async function submit() {
  loading.value = true
  result.value = null
  try {
    if (inputMode.value === 'upload' && uploadFile.value) {
      result.value = await apiUpload('/alert/upload', uploadFile.value)
    } else {
      if (!rawText.value.trim()) return
      result.value = await apiPost('/alert/parse', { raw_text: rawText.value })
    }
  } catch (e) {
    result.value = { error: e.message }
  } finally {
    loading.value = false
  }
}

// ----- 拖拽 -----
function onDragOver(e) {
  e.preventDefault()
  dragOver.value = true
}
function onDragLeave() {
  dragOver.value = false
}
function onDrop(e) {
  e.preventDefault()
  dragOver.value = false
  const files = e.dataTransfer.files
  if (files.length > 0) {
    uploadFile.value = files[0]
  }
}

function onFileSelect(e) {
  const files = e.target.files
  if (files.length > 0) {
    uploadFile.value = files[0]
  }
}

// ----- 辅助 -----
const riskColors = { critical: '#7f1d1d', high: '#7f1d1d', medium: '#713f12', low: '#1e3a5f' }
const riskTextColors = { critical: '#fca5a5', high: '#fca5a5', medium: '#fcd34d', low: '#93c5fd' }

function riskColor(level) {
  return riskColors[level] || '#334155'
}
function riskTextColor(level) {
  return riskTextColors[level] || '#94a3b8'
}
</script>

<template>
  <div class="card" style="margin-top: 20px;">
    <h2>告警解析</h2>

    <!-- 示例 -->
    <div class="mb-4">
      <span style="color: #94a3b8; font-size: 13px;">示例：</span>
      <button v-for="(_, i) in examples" :key="i" @click="loadExample(i)" class="btn btn-sm" style="margin-left: 8px;">
        {{ ['SQL注入', 'XSS', 'SSH暴力破解', '路径遍历', '文件上传'][i] }}
      </button>
    </div>

    <!-- 输入模式切换 -->
    <div class="tabs mb-4">
      <button :class="['tab', { active: inputMode === 'paste' }]" @click="inputMode = 'paste'">粘贴文本</button>
      <button :class="['tab', { active: inputMode === 'upload' }]" @click="inputMode = 'upload'">上传文件</button>
    </div>

    <!-- 粘贴文本 -->
    <div v-if="inputMode === 'paste'">
      <textarea v-model="rawText" placeholder="粘贴 WAF/IPS/EDR/NIDS 的原始告警文本，或系统日志..." rows="8"></textarea>
    </div>

    <!-- 上传文件 -->
    <div v-else>
      <div
        :class="['drop-zone', { 'drag-over': dragOver }]"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
        @drop="onDrop"
      >
        <div v-if="!uploadFile" class="drop-placeholder">
          <span style="font-size: 32px;">📂</span>
          <p>拖拽日志文件到此处，或点击选择</p>
          <p style="color: #64748b; font-size: 12px;">支持 .log .txt .csv .json .evtx</p>
        </div>
        <div v-else class="drop-file-info">
          <span style="font-size: 28px;">📄</span>
          <p><strong>{{ uploadFile.name }}</strong></p>
          <p style="color: #64748b; font-size: 12px;">{{ (uploadFile.size / 1024).toFixed(1) }} KB</p>
          <button class="btn btn-sm" @click="uploadFile = null">重新选择</button>
        </div>
      </div>
      <input type="file" accept=".log,.txt,.csv,.json,.evtx" style="display: none;" ref="fileInput" @change="onFileSelect" />
      <button class="btn btn-sm" @click="$refs.fileInput.click()" style="margin-top: 8px;">选择文件</button>
    </div>

    <!-- 提交按钮 -->
    <button
      class="btn btn-primary mt-4"
      @click="submit"
      :disabled="loading || (inputMode === 'paste' ? !rawText.trim() : !uploadFile)"
    >
      {{ loading ? '解析中...' : '解析告警' }}
    </button>
  </div>

  <!-- ===== 结果展示 ===== -->
  <div v-if="result && !result.error" class="card">
    <!-- 格式 & 文件信息 -->
    <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;">
      <span class="tag" style="background: #1e3a5f; color: #93c5fd;">
        📋 {{ result.detected_format || '未知格式' }}
      </span>
      <span v-if="result.line_count != null" class="tag" style="background: #1e293b;">
        📏 {{ result.line_count }} 行
      </span>
      <span v-if="result.match_count != null" class="tag" style="background: #1e293b;">
        🎯 {{ result.match_count }} 条命中
      </span>
      <span v-if="result.file_info" class="tag" style="background: #1e293b;">
        📄 {{ result.file_info.filename }}
      </span>
    </div>

    <!-- 主命中 -->
    <div
      class="match-card"
      :style="{ borderColor: riskColor(result.risk_level), background: riskColor(result.risk_level) + '15' }"
    >
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <h3 style="margin: 0;">{{ result.attack_type }}</h3>
        <span
          class="score-badge"
          :style="{ background: riskColor(result.risk_level), color: riskTextColor(result.risk_level) }"
        >
          {{ result.risk_level.toUpperCase() }}
        </span>
      </div>
      <p class="mt-4" style="line-height: 1.6;">{{ result.description }}</p>
      <div class="mt-4" style="display: flex; gap: 8px; flex-wrap: wrap;">
        <span v-if="result.mitre_id" class="tag" style="background: #312e81; color: #a5b4fc;">
          🛡️ MITRE: {{ result.mitre_id }} - {{ result.mitre_name }}
        </span>
        <span class="tag" style="background: #1e293b; color: #e2e8f0;">
          置信度: {{ result.confidence }}%
        </span>
      </div>
      <div class="highlight-box mt-4">
        <strong>处置建议：</strong>{{ result.recommendation }}
      </div>
    </div>

    <!-- 其他命中列表 -->
    <div v-if="result.all_matches && result.all_matches.length > 1" class="mt-4">
      <h3 style="font-size: 14px; color: #94a3b8;">其他命中（{{ result.all_matches.length - 1 }} 条）</h3>
      <div
        v-for="(m, i) in result.all_matches.slice(1)"
        :key="i"
        class="match-card-sm"
        :style="{ borderColor: riskColor(m.risk_level) }"
      >
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: 600;">{{ m.attack_type }}</span>
          <span>
            <span class="tag" :style="{ background: riskColor(m.risk_level), color: riskTextColor(m.risk_level), fontSize: '11px' }">
              {{ m.risk_level.toUpperCase() }}
            </span>
            <span class="tag" style="background: #1e293b; font-size: 11px; margin-left: 4px;">
              {{ m.confidence }}%
            </span>
          </span>
        </div>
        <div v-if="m.mitre_id" style="margin-top: 4px; font-size: 12px; color: #94a3b8;">
          MITRE: {{ m.mitre_id }} - {{ m.mitre_name }}
        </div>
      </div>
    </div>
  </div>

  <!-- 错误 -->
  <div v-if="result && result.error" class="card" style="border-color: #7f1d1d;">
    {{ result.error }}
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #334155;
}
.tab {
  padding: 8px 20px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.15s;
}
.tab.active {
  color: #60a5fa;
  border-bottom-color: #60a5fa;
}
.tab:hover {
  color: #94a3b8;
}

.drop-zone {
  border: 2px dashed #334155;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.15s;
}
.drop-zone:hover,
.drop-zone.drag-over {
  border-color: #60a5fa;
  background: #1e293b;
}
.drop-placeholder p {
  margin: 8px 0 0 0;
  color: #94a3b8;
}
.drop-file-info p {
  margin: 4px 0;
}

.match-card {
  border: 1px solid;
  border-radius: 8px;
  padding: 16px;
}
.match-card-sm {
  border: 1px solid;
  border-radius: 6px;
  padding: 10px 14px;
  margin-top: 8px;
  background: #0f172a;
}
</style>