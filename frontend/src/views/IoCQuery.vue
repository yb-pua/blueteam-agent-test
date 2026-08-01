<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiGet } from '../api/client.js'

const router = useRouter()

const queryType = ref('ip')
const queryValue = ref('')
const result = ref(null)
const loading = ref(false)
const error = ref('')
const copied = ref(false)

// 每个源是否展开原始 JSON
const rawOpen = ref({})

// ---- localStorage 工具 ----
const LS_LAST = 'ioc_last_result'
const LS_LAST_RAW = 'ioc_last_raw'
const LS_QUERY = 'ioc_query_form'
const LS_HISTORY = 'ioc_history'
const LS_FAVORITES = 'ioc_favorites'

function saveLS(key, val) {
  try { localStorage.setItem(key, JSON.stringify(val)) } catch { /* quota/隐私模式忽略 */ }
}
function loadLS(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch { return fallback }
}

// ---- 查询历史 & 收藏夹 ----
const history = ref(loadLS(LS_HISTORY, []))
const favorites = ref(loadLS(LS_FAVORITES, []))
const tabActive = ref('history')  // history | favorites

const TYPE_LABEL = { ip: 'IP', domain: '域名', url: 'URL', hash: 'Hash', cve: 'CVE' }

function addToHistory(item) {
  history.value = [item, ...history.value.filter(h => !(h.type === item.type && h.value === item.value))].slice(0, 30)
  saveLS(LS_HISTORY, history.value)
}

function removeHistory(i) {
  history.value = history.value.filter((_, idx) => idx !== i)
  saveLS(LS_HISTORY, history.value)
}

function clearHistory() {
  history.value = []
  saveLS(LS_HISTORY, history.value)
}

function isFavorite() {
  if (!result.value) return false
  return favorites.value.some(f => f.type === result.value.ioc_type && f.value === result.value.ioc_value)
}

function toggleFavorite() {
  if (!result.value) return
  const { ioc_type: type, ioc_value: value } = result.value
  if (isFavorite()) {
    favorites.value = favorites.value.filter(f => !(f.type === type && f.value === value))
  } else {
    favorites.value = [{ type, value, time: Date.now(), risk: summary.value?.level || 'info' },
                       ...favorites.value].slice(0, 50)
  }
  saveLS(LS_FAVORITES, favorites.value)
}

function removeFavorite(i) {
  favorites.value = favorites.value.filter((_, idx) => idx !== i)
  saveLS(LS_FAVORITES, favorites.value)
}

// ---- 查询 ----

async function submit() {
  if (!queryValue.value.trim()) return
  loading.value = true
  error.value = ''
  result.value = null
  rawOpen.value = {}
  try {
    const data = await apiGet(`/analyze/${queryType.value}/${encodeURIComponent(queryValue.value.trim())}`)
    result.value = data
    // 持久化：表单 + 结果 + 历史
    saveLS(LS_QUERY, { type: queryType.value, value: queryValue.value.trim() })
    saveLS(LS_LAST, data)
    saveLS(LS_LAST_RAW, {})
    addToHistory({ type: data.ioc_type, value: data.ioc_value, time: Date.now(), risk: summary.value?.level || 'info' })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// ---- 新功能 ----

function reQuery(item) {
  queryType.value = item.type
  queryValue.value = item.value
  submit()
}

function goAiAnalyze() {
  if (!result.value) return
  const { ioc_type: type, ioc_value: value } = result.value
  const q = `分析威胁情报：${TYPE_LABEL[type] || type} ${value}`
  router.push({ path: '/chat', query: { q } })
}

async function copyMarkdown() {
  if (!result.value || !summary.value) return
  const r = result.value
  const s = summary.value
  const lines = []
  lines.push(`# 威胁情报分析 - ${r.ioc_type.toUpperCase()} ${r.ioc_value}`)
  lines.push('')
  lines.push(`**综合评级**: ${s.meta.label}`)
  lines.push(`**查询时间**: ${new Date().toLocaleString()}`)
  lines.push('')
  for (const it of s.items) {
    lines.push(`## ${it.source}`)
    const verdictMap = { bad: '恶意', warn: '可疑', good: '未见异常', info: '未知', unknown: '未知' }
    lines.push(`**判定**: ${verdictMap[it.verdict] || '未知'}`)
    if (it.error) { lines.push(`错误: ${it.error}`) }
    else {
      lines.push('| 字段 | 值 |')
      lines.push('|------|-----|')
      for (const f of it.facts) {
        lines.push(`| ${f.k} | ${String(f.v).replace(/\|/g, '\\|')} |`)
      }
    }
    lines.push('')
  }
  const md = lines.join('\n')
  try {
    await navigator.clipboard.writeText(md)
  } catch {
    // fallback: 老式 copy
    const ta = document.createElement('textarea')
    ta.value = md
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}

function fmtHistoryTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const RISK_COLOR = { bad: '#dc2626', warn: '#d97706', good: '#16a34a', info: '#64748b', unknown: '#64748b' }

onMounted(() => {
  // 恢复表单输入
  const q = loadLS(LS_QUERY)
  if (q && q.type) queryType.value = q.type
  if (q && q.value) queryValue.value = q.value
  // 恢复上次查询结果（含展开状态）
  const last = loadLS(LS_LAST)
  if (last) {
    result.value = last
    rawOpen.value = loadLS(LS_LAST_RAW, {})
  }
})

// ================= 数据清洗：各源专用解析器 =================

function fmtDate(v) {
  if (v == null) return ''
  if (typeof v === 'number') {
    return v > 1e12 ? new Date(v).toLocaleString() : new Date(v * 1000).toLocaleString()
  }
  const s = String(v)
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10)
  return s
}

function flatten(obj, prefix = '', depth = 0, out = []) {
  if (!obj || typeof obj !== 'object') return out
  if (depth > 3 || out.length > 25) return out
  for (const [k, v] of Object.entries(obj)) {
    if (v == null || v === '' || v === false) continue
    const key = prefix ? `${prefix}.${k}` : k
    if (typeof v === 'object') {
      if (Array.isArray(v)) {
        const items = v.slice(0, 3)
        out.push({ k: key, v: items.map(i => (typeof i === 'object' ? JSON.stringify(i) : String(i))).join('; ') || '(空)' })
      } else {
        flatten(v, key, depth + 1, out)
      }
    } else {
      out.push({ k: key, v: String(v) })
    }
  }
  return out
}

// VirusTotal: data.attributes
function extractVT(d) {
  const a = d?.data?.attributes || {}
  const st = a.last_analysis_stats || {}
  const f = []
  const mal = st.malicious || 0, sus = st.suspicious || 0
  if (Object.keys(st).length) {
    f.push({ k: '引擎检测', v: `${mal} 恶意 / ${sus} 可疑 / ${st.harmless || 0} 无害 / ${st.undetected || 0} 未检出`,
             kind: mal > 0 ? 'bad' : (sus > 0 ? 'warn' : 'good') })
  }
  if (a.asn) f.push({ k: 'ASN', v: String(a.asn) })
  if (a.as_owner) f.push({ k: '所有者', v: a.as_owner })
  if (a.country) f.push({ k: '国家/地区', v: a.country })
  if (a.reputation !== undefined) f.push({ k: '信誉分', v: String(a.reputation), kind: a.reputation < 0 ? 'bad' : 'good' })
  if (a.last_analysis_date) f.push({ k: '最近分析', v: fmtDate(a.last_analysis_date) })
  if (a.creation_date) f.push({ k: '创建时间', v: fmtDate(a.creation_date) })
  if (a.registrar) f.push({ k: '注册商', v: a.registrar })
  if (a.type_description) f.push({ k: '文件类型', v: a.type_description })
  if (a.names?.length) f.push({ k: '文件名', v: a.names.slice(0, 3).join('、') })
  return { facts: f, verdict: mal > 0 ? 'bad' : (sus > 0 ? 'warn' : 'good') }
}

// AbuseIPDB: data.data
function extractAbuseIPDB(d) {
  const a = d?.data || {}
  const f = []
  const conf = a.abuseConfidenceScore
  if (conf !== undefined) f.push({ k: '滥用置信度', v: `${conf} / 100`, kind: conf >= 50 ? 'bad' : (conf >= 25 ? 'warn' : 'good') })
  if (a.isWhitelisted !== undefined) f.push({ k: '是否白名单', v: a.isWhitelisted ? '是' : '否', kind: a.isWhitelisted ? 'good' : 'info' })
  if (a.totalReports !== undefined) f.push({ k: '历史举报数', v: String(a.totalReports), kind: a.totalReports > 0 ? 'bad' : 'good' })
  if (a.numDistinctUsers !== undefined) f.push({ k: '举报来源数', v: String(a.numDistinctUsers) })
  if (a.countryCode) f.push({ k: '国家/地区', v: a.countryCode })
  if (a.usageType) f.push({ k: '用途类型', v: a.usageType })
  if (a.isp) f.push({ k: 'ISP', v: a.isp })
  if (a.domain) f.push({ k: '归属域名', v: a.domain })
  if (a.lastReportedAt) f.push({ k: '最近被举报', v: fmtDate(a.lastReportedAt), kind: 'bad' })
  if (a.reports?.length) {
    const r = a.reports[0]
    f.push({ k: '最新举报', v: `${r.comment || '无描述'}（${fmtDate(r.reportedAt)}）`, kind: 'warn' })
  }
  return { facts: f, verdict: conf >= 50 || a.totalReports > 0 ? 'bad' : (conf >= 25 ? 'warn' : 'good') }
}

// AlienVault OTX: pulse_info / pulses
function extractOTX(d) {
  const f = []
  const pi = d?.pulse_info || {}
  const pulses = d?.pulses || pi?.pulses || []
  if (pi.count !== undefined) f.push({ k: '关联 Pulse 数', v: String(pi.count), kind: pi.count > 0 ? 'bad' : 'good' })
  if (d?.type) f.push({ k: '类型', v: d.type })
  if (d?.indicator) f.push({ k: '指标', v: d.indicator })
  if (pulses.length) {
    const names = pulses.slice(0, 3).map(p => p.name || p.id).join('、')
    f.push({ k: '相关威胁情报', v: names, kind: 'bad' })
    const tags = [...new Set(pulses.flatMap(p => p.tags || []))].slice(0, 5)
    if (tags.length) f.push({ k: '标签', v: tags.join('、') })
  }
  return { facts: f, verdict: pi.count > 0 ? 'bad' : 'good' }
}

// Shodan: host 详情
function extractShodan(d) {
  const f = []
  if (d.ports?.length) f.push({ k: '开放端口', v: d.ports.join(', '), kind: d.ports.length ? 'warn' : 'info' })
  if (d.hostnames?.length) f.push({ k: '主机名', v: d.hostnames.join(', ') })
  if (d.os) f.push({ k: '操作系统', v: d.os })
  if (d.product) f.push({ k: '产品', v: d.product })
  if (d.org) f.push({ k: '组织', v: d.org })
  if (d.asn) f.push({ k: 'ASN', v: d.asn })
  if (d.isp) f.push({ k: 'ISP', v: d.isp })
  if (d.country_name) f.push({ k: '国家/地区', v: d.country_name })
  if (d.city) f.push({ k: '城市', v: d.city })
  if (d.vulns && Object.keys(d.vulns).length) {
    f.push({ k: '已知漏洞', v: Object.keys(d.vulns).slice(0, 5).join(', '), kind: 'bad' })
  }
  if (d.last_update) f.push({ k: '最近扫描', v: fmtDate(d.last_update) })
  return { facts: f, verdict: d.vulns && Object.keys(d.vulns).length ? 'bad' : 'info' }
}

// Censys: result.services
function extractCensys(d) {
  const r = d?.result || {}
  const f = []
  const services = r.services || []
  if (services.length) {
    f.push({ k: '开放服务', v: services.slice(0, 8).map(s => `${s.service_name || '?'}:${s.port}`).join(', '), kind: 'warn' })
  } else {
    f.push({ k: '开放服务', v: '未发现', kind: 'info' })
  }
  if (r.os) f.push({ k: '操作系统', v: r.os })
  if (r.ip) f.push({ k: 'IP', v: r.ip })
  const first = services[0]
  if (first?.products?.length) f.push({ k: '产品', v: first.products.join(', ') })
  if (first?.protocols?.length) f.push({ k: '协议', v: first.protocols.join(', ') })
  return { facts: f, verdict: services.length ? 'warn' : 'info' }
}

// URLScan: results[0]
function extractURLScan(d) {
  const f = []
  const total = d?.total
  const first = d?.results?.[0]
  if (total !== undefined) f.push({ k: '历史扫描记录', v: String(total) })
  if (first) {
    if (first.page?.url) f.push({ k: '扫描URL', v: first.page.url })
    if (first.page?.domain) f.push({ k: '域名', v: first.page.domain })
    if (first.page?.ip) f.push({ k: 'IP', v: first.page.ip })
    if (first.page?.server) f.push({ k: '服务器', v: first.page.server })
    const st = first.stats || {}
    if (st.malicious || st.suspicious) {
      f.push({ k: '检测统计', v: `${st.malicious || 0} 恶意 / ${st.suspicious || 0} 可疑`, kind: 'bad' })
    }
    const mal = first.verdicts?.overall?.malicious
    if (mal !== undefined) f.push({ k: '综合判定', v: mal ? '恶意' : '安全', kind: mal ? 'bad' : 'good' })
    if (first.task?.time) f.push({ k: '扫描时间', v: fmtDate(first.task.time) })
  } else {
    f.push({ k: '扫描记录', v: '无结果', kind: 'info' })
  }
  return { facts: f, verdict: first?.verdicts?.overall?.malicious ? 'bad' : (total ? 'good' : 'info') }
}

// PhishTank
function extractPhishTank(d) {
  const f = []
  if (d.in_error) {
    f.push({ k: '查询状态', v: '出错：' + (d.errormsg || '未知'), kind: 'warn' })
    return { facts: f, verdict: 'info' }
  }
  const r = d.results || {}
  if (r.in_database !== undefined) f.push({ k: '是否入库', v: r.in_database ? '是' : '否', kind: r.in_database ? 'bad' : 'good' })
  if (r.verified !== undefined) f.push({ k: '是否已验证', v: r.verified ? '是' : '否', kind: r.verified ? 'bad' : 'info' })
  if (r.valid !== undefined) f.push({ k: '当前有效', v: r.valid ? '是' : '否' })
  if (r.phish_id) f.push({ k: 'PhishID', v: String(r.phish_id) })
  if (r.verified_at) f.push({ k: '验证时间', v: fmtDate(r.verified_at) })
  if (r.details?.length) {
    const dts = r.details.slice(0, 3).map(x => x.url || x.ip_address || x.details || '').filter(Boolean)
    if (dts.length) f.push({ k: '关联详情', v: dts.join('、'), kind: 'warn' })
  }
  return { facts: f, verdict: r.in_database && r.verified ? 'bad' : (r.in_database ? 'warn' : 'good') }
}

// NVD CVE
function extractNVD(d) {
  const cve = d?.vulnerabilities?.[0]?.cve
  if (!cve) {
    return { facts: [{ k: '查询结果', v: '未找到该 CVE', kind: 'info' }], verdict: 'info' }
  }
  const f = []
  f.push({ k: 'CVE ID', v: cve.id, kind: 'bad' })
  const desc = cve.descriptions?.find(x => x.lang === 'en')?.value || ''
  if (desc) f.push({ k: '描述', v: desc.slice(0, 200), kind: 'info' })
  const cvss = cve.metrics?.cvssMetricV31?.[0]?.cvssData || cve.metrics?.cvssMetricV2?.[0]?.cvssData
  if (cvss?.baseScore !== undefined) {
    const s = cvss.baseScore
    f.push({ k: 'CVSS 评分', v: `${s}（${cvss.baseSeverity || cvss.severity || '-'}）`, kind: s >= 9 ? 'bad' : (s >= 7 ? 'warn' : 'info') })
  }
  if (cve.published) f.push({ k: '发布时间', v: fmtDate(cve.published) })
  if (cve.lastModified) f.push({ k: '最近修改', v: fmtDate(cve.lastModified) })
  if (cve.weaknesses?.length) {
    f.push({ k: 'CWE', v: cve.weaknesses.slice(0, 3).map(w => w.description?.[0]?.value).filter(Boolean).join('、') })
  }
  return { facts: f, verdict: (cvss?.baseScore || 0) >= 7 ? 'bad' : ((cvss?.baseScore || 0) >= 4 ? 'warn' : 'info') }
}

// 微步 ThreatBook
function extractThreatBook(d) {
  const a = d?.data || {}
  const f = []
  if (d.response_code !== undefined) f.push({ k: '响应码', v: String(d.response_code) })
  if (d.verbose_msg) f.push({ k: '状态', v: d.verbose_msg, kind: d.response_code === 0 ? 'good' : 'warn' })
  const sevMap = { info: '无害', low: '低危', medium: '中危', high: '高危' }
  if (a.severity) f.push({ k: '威胁等级', v: `${sevMap[a.severity] || a.severity}`, kind: a.severity === 'high' ? 'bad' : (a.severity === 'medium' ? 'warn' : (a.severity === 'low' ? 'warn' : 'good')) })
  if (a.is_ioc !== undefined) f.push({ k: '是否IoC', v: a.is_ioc ? '是' : '否', kind: a.is_ioc ? 'bad' : 'good' })
  if (a.judgments?.length) f.push({ k: '研判结论', v: a.judgments.slice(0, 5).join('、'), kind: 'warn' })
  if (a.tags?.length) f.push({ k: '标签', v: a.tags.slice(0, 8).join('、'), kind: 'warn' })
  if (a.scenario) f.push({ k: '场景', v: a.scenario })
  if (a.sources_count !== undefined) f.push({ k: '情报源数', v: String(a.sources_count) })
  if (a.first_seen) f.push({ k: '首次发现', v: fmtDate(a.first_seen) })
  if (a.last_seen) f.push({ k: '最近发现', v: fmtDate(a.last_seen) })
  return { facts: f, verdict: a.is_ioc || a.severity === 'high' ? 'bad' : (['medium', 'low'].includes(a.severity) ? 'warn' : 'good') }
}

// ip-api.com（IP 基础信息）
function extractIPInfo(d) {
  const f = []
  if (d.query) f.push({ k: '查询 IP', v: d.query })
  if (d.country) f.push({ k: '国家', v: `${d.country} (${d.countryCode || ''})` })
  if (d.regionName) f.push({ k: '省份/地区', v: d.regionName })
  if (d.city) f.push({ k: '城市', v: d.city })
  if (d.district) f.push({ k: '区县', v: d.district })
  if (d.zip) f.push({ k: '邮编', v: d.zip })
  if (d.isp) f.push({ k: 'ISP', v: d.isp })
  if (d.org) f.push({ k: '组织', v: d.org })
  if (d.as) f.push({ k: 'ASN', v: d.as })
  if (d.asname) f.push({ k: 'ASN 名称', v: d.asname })
  if (d.reverse) f.push({ k: '反向 DNS', v: d.reverse })
  if (d.lat !== undefined && d.lon !== undefined) f.push({ k: '坐标', v: `${d.lat}, ${d.lon}` })
  if (d.timezone) f.push({ k: '时区', v: d.timezone })
  if (d.mobile !== undefined) f.push({ k: '移动网络', v: d.mobile ? '是' : '否', kind: d.mobile ? 'info' : 'good' })
  if (d.proxy !== undefined) f.push({ k: '代理/VPN', v: d.proxy ? '⚠️ 是' : '否', kind: d.proxy ? 'warn' : 'good' })
  if (d.hosting !== undefined) f.push({ k: '托管/机房 IP', v: d.hosting ? '是' : '否', kind: d.hosting ? 'info' : 'good' })
  return { facts: f, verdict: d.proxy ? 'warn' : 'good' }
}

// ipwho.is（IP 基础信息备用）
function extractIPWhoIs(d) {
  const f = []
  if (d.ip) f.push({ k: '查询 IP', v: d.ip })
  if (d.country) f.push({ k: '国家', v: `${d.country} (${d.country_code || ''})` })
  if (d.region) f.push({ k: '省份/地区', v: d.region })
  if (d.city) f.push({ k: '城市', v: d.city })
  if (d.postal) f.push({ k: '邮编', v: d.postal })
  if (d.isp) f.push({ k: 'ISP', v: d.isp })
  if (d.org) f.push({ k: '组织', v: d.org })
  if (d.asn) f.push({ k: 'ASN', v: `AS${d.asn}` })
  if (d.latitude !== undefined && d.longitude !== undefined) f.push({ k: '坐标', v: `${d.latitude}, ${d.longitude}` })
  if (d.timezone) f.push({ k: '时区', v: d.timezone?.id || d.timezone })
  if (d.security) {
    const s = d.security
    if (s.proxy !== undefined) f.push({ k: '代理', v: s.proxy ? '⚠️ 是' : '否', kind: s.proxy ? 'warn' : 'good' })
    if (s.vpn !== undefined) f.push({ k: 'VPN', v: s.vpn ? '⚠️ 是' : '否', kind: s.vpn ? 'warn' : 'good' })
    if (s.tor !== undefined) f.push({ k: 'Tor', v: s.tor ? '⚠️ 是' : '否', kind: s.tor ? 'bad' : 'good' })
    if (s.hosting !== undefined) f.push({ k: '托管/机房 IP', v: s.hosting ? '是' : '否', kind: s.hosting ? 'info' : 'good' })
  }
  return { facts: f, verdict: d.security?.proxy || d.security?.vpn || d.security?.tor ? 'warn' : 'good' }
}

// Feed 威胁情报（SSLBL + URLhaus + ThreatFox + Blocklist + VXVault + OpenPhish + Spamhaus）
function extractFeedThreats(d) {
  const f = []
  if (d.found) {
    f.push({ k: '命中 Feed', v: d.feeds?.join('、') || '未知', kind: 'bad' })
    f.push({ k: '命中数', v: String(d.match_count), kind: 'bad' })
    f.push({ k: '摘要', v: d.summary || '', kind: 'bad' })
    // 展开每个命中的详情
    const details = d.details || []
    for (const m of details.slice(0, 5)) {
      const feed = m.feed || 'unknown'
      const type = m.type || m.threat_type || ''
      const src = m.source || ''
      if (type) f.push({ k: feed, v: `${type} (${src})`, kind: 'bad' })
      else if (m.description) f.push({ k: feed, v: m.description.slice(0, 100), kind: 'bad' })
      else f.push({ k: feed, v: '命中', kind: 'bad' })
    }
  } else {
    f.push({ k: '查询结果', v: '在所有 Feed 中未发现该 IoC', kind: 'good' })
  }
  return { facts: f, verdict: d.found ? 'bad' : 'good' }
}

// Feed 漏洞情报（CISA KEV + MITRE ATT&CK）
function extractFeedVulns(d) {
  const f = []
  if (d.found) {
    f.push({ k: '命中数', v: String(d.match_count), kind: 'bad' })
    const details = d.details || []
    for (const m of details.slice(0, 3)) {
      const src = m.source || ''
      if (src === 'cisa_kev') {
        f.push({ k: '来源', v: 'CISA KEV（已知在野利用）', kind: 'bad' })
        if (m.vendor) f.push({ k: '厂商', v: m.vendor })
        if (m.product) f.push({ k: '产品', v: m.product })
        if (m.description) f.push({ k: '描述', v: m.description.slice(0, 200) })
        if (m.known_ransomware) f.push({ k: '勒索软件利用', v: m.known_ransomware, kind: m.known_ransomware === 'Yes' ? 'bad' : 'info' })
        if (m.date_added) f.push({ k: '加入日期', v: m.date_added })
      } else if (src === 'mitre_attack') {
        f.push({ k: '来源', v: 'MITRE ATT&CK', kind: 'warn' })
        if (m.name) f.push({ k: '技术名称', v: m.name })
        if (m.tactics?.length) f.push({ k: '战术', v: m.tactics.join('、') })
        if (m.description) f.push({ k: '描述', v: m.description.slice(0, 200) })
      }
    }
  } else {
    f.push({ k: '查询结果', v: '未找到匹配记录', kind: 'info' })
  }
  return { facts: f, verdict: d.found ? 'bad' : 'info' }
}

// Feed 统计信息
function extractFeedStats(d) {
  const f = []
  // 元信息
  const meta = d._meta || {}
  if (meta.max_rounds) f.push({ k: '保留轮次', v: `最近 ${meta.max_rounds} 轮` })
  if (meta.db_size_bytes) {
    const mb = (meta.db_size_bytes / 1024 / 1024).toFixed(1)
    f.push({ k: 'SQLite 大小', v: `${mb} MB`, kind: 'warn' })
  }
  f.push({ k: 'Feed 总数', v: String(meta.total_feeds || 0) })
  f.push({ k: 'IoC 总量', v: String(meta.total_ios || 0) })
  const feeds = d.feeds || {}
  for (const [name, info] of Object.entries(feeds)) {
    if (!info.total_ios) continue
    const last = info.last_fetch ? new Date(info.last_fetch * 1000).toLocaleString() : '未加载'
    f.push({ k: name, v: `${info.total_ios} 条 | ${info.ioc_types.join('/')} | 更新: ${last}` })
  }
  return { facts: f, verdict: 'info' }
}

// 各源解析器映射
const EXTRACTORS = {
  virustotal: extractVT,
  abuseipdb: extractAbuseIPDB,
  otx: extractOTX,
  shodan: extractShodan,
  censys: extractCensys,
  urlscan: extractURLScan,
  phishtank: extractPhishTank,
  nvd: extractNVD,
  threatbook: extractThreatBook,
  ipinfo: extractIPInfo,
  ipwhois: extractIPWhoIs,
  feed_threats: extractFeedThreats,
  feed_vulns: extractFeedVulns,
  feed_stats: extractFeedStats,
}

const SOURCE_ICONS = {
  virustotal: '🦠', abuseipdb: '🚫', otx: '👽', shodan: '📡', censys: '🔭',
  urlscan: '🔍', phishtank: '🎣', nvd: '🛡️', threatbook: '📚',
  ipinfo: '🌍', ipwhois: '🌐',
  feed_threats: '🔥', feed_vulns: '💉', feed_stats: '📊',
}

function parseSource(s) {
  if (s.error) {
    return { ...s, parsed: null, facts: [{ k: '状态', v: s.error, kind: 'warn' }], verdict: 'unknown' }
  }
  const fn = EXTRACTORS[s.source]
  const parsed = fn ? fn(s.data || {}) : { facts: flatten(s.data || {}), verdict: 'info' }
  const facts = parsed.facts?.length ? parsed.facts : [{ k: '未提取到关键信息', v: '（数据为空或结构未知）', kind: 'info' }]
  return { ...s, parsed, facts, verdict: parsed.verdict || 'info' }
}

// 综合风险评级
const summary = computed(() => {
  if (!result.value) return null
  const items = result.value.sources.map(parseSource)
  const order = { bad: 3, warn: 2, info: 1, good: 0, unknown: 0 }
  let level = 'info'
  for (const it of items) {
    if (order[it.verdict] > order[level]) level = it.verdict
  }
  const meta = {
    bad:   { label: '高风险', cls: 'score-critical', desc: '多个情报源确认存在恶意行为，建议立即阻断相关流量。' },
    warn:  { label: '关注',   cls: 'score-high',    desc: '存在可疑信号，建议结合上下文进一步分析。' },
    good:  { label: '未见异常', cls: 'score-low',   desc: '各情报源未发现明显恶意标记。' },
    info:  { label: '待评估', cls: 'score-medium',  desc: '情报不足或需人工分析确认。' },
    unknown: { label: '未知', cls: 'score-medium', desc: '无法确定。' },
  }
  const m = meta[level] || meta.info
  const scored = items.filter(i => i.verdict === 'bad').length
  return { level, meta: m, items, scored }
})

function toggleRaw(name) {
  rawOpen.value[name] = !rawOpen.value[name]
  saveLS(LS_LAST_RAW, rawOpen.value)
}

function factKind(kind) {
  return { good: '#16a34a', bad: '#dc2626', warn: '#d97706', info: '#64748b' }[kind] || '#64748b'
}
</script>

<template>
  <div class="card" style="margin-top: 20px;">
    <h2>威胁情报 IoC 查询</h2>
    <div style="display: flex; gap: 8px; align-items: end;">
      <div style="flex: 0 0 120px;">
        <label>类型</label>
        <select v-model="queryType">
          <option value="ip">IP地址</option>
          <option value="domain">域名</option>
          <option value="url">URL</option>
          <option value="hash">文件Hash</option>
        </select>
      </div>
      <div style="flex: 1;">
        <label>值</label>
        <input v-model="queryValue" @keyup.enter="submit" placeholder="输入IP/域名/URL/Hash..." />
      </div>
      <button class="btn btn-primary" @click="submit" :disabled="loading">{{ loading ? '查询中...' : '查询' }}</button>
    </div>
  </div>

  <div v-if="error" class="card" style="border-color: #7f1d1d;">{{ error }}</div>

  <!-- 查询历史 / 收藏夹 -->
  <div class="card mt-4" v-if="history.length || favorites.length || tabActive === 'history'">
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
      <button
        class="btn btn-sm"
        :style="tabActive === 'history' ? activeTabStyle : inactiveTabStyle"
        @click="tabActive = 'history'"
      >🕘 查询历史 ({{ history.length }})</button>
      <button
        class="btn btn-sm"
        :style="tabActive === 'favorites' ? activeTabStyle : inactiveTabStyle"
        @click="tabActive = 'favorites'"
      >⭐ 收藏夹 ({{ favorites.length }})</button>
      <button v-if="tabActive === 'history' && history.length" class="btn btn-sm" style="margin-left: auto;" @click="clearHistory">清空</button>
    </div>

    <div v-if="tabActive === 'history'">
      <div v-if="history.length === 0" style="color: #64748b; font-size: 13px; padding: 8px 0;">
        暂无查询历史。查询过的 IoC 会保存在这里，切换页面也不丢失。
      </div>
      <div v-else class="ioc-list">
        <div v-for="(h, i) in history" :key="'h' + i" class="ioc-item" @click="reQuery(h)">
          <span class="tag" :style="'background:' + RISK_COLOR[h.risk] + '22;color:' + RISK_COLOR[h.risk]">{{ TYPE_LABEL[h.type] || h.type }}</span>
          <span class="ioc-value">{{ h.value }}</span>
          <span class="ioc-time">{{ fmtHistoryTime(h.time) }}</span>
          <button class="ioc-del" title="删除" @click.stop="removeHistory(i)">✕</button>
        </div>
      </div>
    </div>

    <div v-else>
      <div v-if="favorites.length === 0" style="color: #64748b; font-size: 13px; padding: 8px 0;">
        暂无收藏。点击结果卡片上的 ⭐ 收藏 可保存常用 IoC。
      </div>
      <div v-else class="ioc-list">
        <div v-for="(f, i) in favorites" :key="'f' + i" class="ioc-item" @click="reQuery(f)">
          <span class="tag" :style="'background:' + RISK_COLOR[f.risk] + '22;color:' + RISK_COLOR[f.risk]">{{ TYPE_LABEL[f.type] || f.type }}</span>
          <span class="ioc-value">{{ f.value }}</span>
          <span class="ioc-time">{{ fmtHistoryTime(f.time) }}</span>
          <button class="ioc-del" title="取消收藏" @click.stop="removeFavorite(i)">✕</button>
        </div>
      </div>
    </div>
  </div>

  <!-- 结果：综合评级 + 各源解析卡片 -->
  <div v-if="result" class="mt-4">
    <div class="card" style="border-color: #334155;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <h3 style="margin: 0;">
          {{ result.ioc_type.toUpperCase() }}: <code style="background:#0f172a;padding:2px 8px;border-radius:4px;">{{ result.ioc_value }}</code>
        </h3>
        <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
          <span class="score-badge" :class="summary.meta.cls">{{ summary.meta.label }}</span>
          <button class="btn btn-sm" :style="isFavorite() ? favActiveStyle : ''" @click="toggleFavorite">
            {{ isFavorite() ? '⭐ 已收藏' : '☆ 收藏' }}
          </button>
          <button class="btn btn-sm" @click="goAiAnalyze">🤖 AI 分析</button>
          <button class="btn btn-sm" @click="copyMarkdown" :disabled="copied">
            {{ copied ? '✅ 已复制' : '📋 复制 Markdown' }}
          </button>
        </div>
      </div>
      <p style="color: #94a3b8; font-size: 13px; margin-top: 8px;">
        {{ summary.meta.desc }} 已查询 {{ result.sources.length }} 个情报源，{{ summary.scored }} 个源判定恶意。
      </p>
      <div class="highlight-box mt-4">
        <strong>💡 深度分析：</strong>
        点击 <strong>🤖 AI 分析</strong> 将自动跳转到聊天页发起分析；<strong>📋 复制 Markdown</strong> 可把本结果导出为报告格式。
      </div>
    </div>

    <!-- 各源卡片 -->
    <div class="grid-2 mt-4">
      <div v-for="s in summary.items" :key="s.source" class="card" style="padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <h3 style="margin: 0; font-size: 15px;">
            {{ SOURCE_ICONS[s.source] || '📦' }} {{ s.source }}
            <span v-if="s.verdict === 'bad'" class="tag" style="background:#7f1d1d;color:#fca5a5;">恶意</span>
            <span v-else-if="s.verdict === 'warn'" class="tag" style="background:#713f12;color:#fcd34d;">可疑</span>
            <span v-else-if="s.verdict === 'good'" class="tag" style="background:#052e16;color:#86efac;">未见异常</span>
            <span v-else class="tag" style="background:#334155;color:#94a3b8;">未知</span>
          </h3>
          <button class="btn btn-sm" @click="toggleRaw(s.source)">
            {{ rawOpen[s.source] ? '隐藏原始' : '原始JSON' }}
          </button>
        </div>

        <div v-if="rawOpen[s.source]" class="code-block" style="margin-top: 10px;">
          {{ JSON.stringify(s.data, null, 2) }}
        </div>

        <table v-else class="fact-table">
          <tbody>
            <tr v-for="(f, i) in s.facts" :key="i">
              <td class="fact-key">{{ f.k }}</td>
              <td class="fact-val" :style="{ color: factKind(f.kind) }">{{ f.v }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fact-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
.fact-table td { padding: 6px 4px; border-bottom: 1px solid #1e293b; font-size: 13px; vertical-align: top; }
.fact-key { color: #64748b; white-space: nowrap; width: 96px; }
.fact-val { color: #e2e8f0; word-break: break-all; }

.activeTabStyle { background: #1e3a5f; border: 1px solid #2563eb; color: #93c5fd; }
.inactiveTabStyle { background: #334155; color: #94a3b8; }
.favActiveStyle { background: #452a1a; border-color: #b45309; color: #fbbf24; }

.ioc-list { display: flex; flex-direction: column; gap: 4px; }
.ioc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
  font-size: 13px;
}
.ioc-item:hover { background: #293548; }
.ioc-value { color: #e2e8f0; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ioc-time { color: #64748b; font-size: 12px; white-space: nowrap; }
.ioc-del {
  background: transparent; border: none; color: #64748b; cursor: pointer;
  font-size: 12px; padding: 2px 6px; border-radius: 4px; visibility: hidden; flex-shrink: 0;
}
.ioc-item:hover .ioc-del { visibility: visible; }
.ioc-del:hover { color: #fca5a5; background: #3f1d1d; }

@media (max-width: 768px) {
  .fact-key { width: 72px; }
}
</style>
