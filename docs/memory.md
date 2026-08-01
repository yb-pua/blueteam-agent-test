# 开发记忆 — IoCLens（蓝队威胁情报辅助平台）

> 本文件记录项目上下文、坑与决策，供后续会话快速接手。最后更新: 2026-08-01

## 项目一句话

**IoCLens** — 面向护网/攻防演练的 LLM 驱动威胁情报 Agent：FastAPI + Vue3 + SQLite，聚合 14 个 OSINT 源 + 10 个情报 Feed，AI（glm-5.2）通过 function calling 查源并输出自然语言研判。

## 快速启动

```bash
python run.py          # → http://localhost:8020
```

前端已构建进 `dist/`，改前端需 `cd frontend && npm run build`。浏览器看旧界面记得 **Ctrl+Shift+R 强刷**。

## 当前 LLM 配置（存 data/config.json，非硬编码）

| 项 | 值 |
|----|-----|
| LLM_BASE_URL | https://yuanyuaicloud.cn/v1 |
| LLM_MODEL | `glm-5.2`（**必须小写**）|
| LLM_API_KEY | sk-AVXIx...（勿外泄，已在 .gitignore）|

## 关键架构记忆

- **LLM 驱动**：每个 OSINT 源 = 一个 function tool `query_<name>`；`tools.py::build_tools(sources)` 可按用户勾选过滤
- **源声明**：`app/sources/*.py` 继承 `OSINTSource`，声明 `supported_types` + `requires_key`
- **`get_source()` 动态查找**：配置变更后无需重启服务（已删除固定 TOOL_MAP）
- **会话**：`chat_sessions`/`chat_messages` 表；`/ask` 带 `session_id` → 多轮上下文，返回 `(answer, session_id)`
- **配置**：`config.py` 环境变量优先，`data/config.json` 兜底，mtime 缓存；API 写入后调 `refresh_runtime_cache()`
- **前端 MD**：`MarkdownContent.vue`（marked + DOMPurify），所有 AI 回复都过它

## 情报源现状（14个）

| 源 | 类型 | 需Key | 备注 |
|----|------|-------|------|
| NVD | cve | 否 | 默认可用 |
| PhishTank | url/domain | 否 | 默认可用 |
| URLScan | ip/domain/url | 否* | *有 Key 更稳，默认可用 |
| VirusTotal | ip/domain/url/hash | 是 | 未配 |
| AbuseIPDB | ip | 是 | 未配 |
| OTX | ip/domain/hash/url | 是 | 未配 |
| Shodan | ip | 是 | 未配 |
| Censys | ip/domain | 是 | 未配 |
| **ThreatBook 微步** | ip/domain/url/hash | 是 | 已接入待配 Key |
| **IPInfo (ip-api.com)** | ip | 否 | 免费，45次/分钟，lang=zh-CN 中文 |
| **IPWhoIs (ipwho.is)** | ip | 否 | 备用，1000次/天，HTTPS |
| **FeedThreats** | ip/domain/url/hash/cidr | 否 | **聚合 8 个免费 Feed**（见下文） |
| **FeedVulns** | cve/technique | 否 | CISA KEV + MITRE ATT&CK |
| **FeedStats** | feed_info | 否 | Feed 缓存统计 |

## Feed 开源威胁情报源（10 个，自动拉取缓存）

| Feed | 内容 | 更新频率 | 规模 |
|------|------|---------|------|
| **sslbl_ip** | 恶意 SSL IP 黑名单 | 1h | ~0（需检查） |
| **sslbl_cert** | 恶意 SSL 证书指纹 | 1h | ~0 |
| **urlhaus** | 恶意软件下载 URL | 5min | ~66k |
| **threatfox** | 活跃恶意 IOC（IP/域名/URL） | 10min | ~4.8k |
| **openphish** | 钓鱼 URL 清单 | 12h | ~300 |
| **blocklist_de** | 暴力破解 IP（SSH/RDP/Web） | 1h | ~23k |
| **vxvault** | 恶意 URL / C2 基础设施 | 1h | ~100 |
| **spamhaus_drop** | 僵尸网络 IP 段 | 24h | ~1.6k |
| **cisa_kev** | 已知在野利用漏洞清单 | 24h | ~1.6k |
| **mitre_attack** | MITRE ATT&CK 框架数据 | 7d（惰性加载） | ~0 |

启动时从 DB 恢复 → 仅拉取过期的 Feed（智能刷新）。
每 30 分钟 `refresh_stale()` 检查并刷新过期 Feed。
**启动优化**：Feed 拉取改为后台 `asyncio.create_task()`，不阻塞服务启动（~3s 启动，Feed 后台慢慢拉取）。
代理支持：`HTTP_PROXY=http://127.0.0.1:10808 HTTPS_PROXY=http://127.0.0.1:10808 python run.py`

### SQLite 持久化（feed_cache.db）
- **feed_rounds 表**：记录每次刷新的元信息（feed_name, started_at, completed_at, ioc_count, status）
- **feed_cache 表**：存储每条 IOC（round_id, feed_name, ioc_type, ioc_value, detail_json）
- **保留 MAX_ROUNDS=3 轮**：新轮写入后自动删除第 4 轮及更旧数据
- **启动恢复**：从 DB 加载最近一轮到内存，跳过未过期的 Feed 拉取
- **DB 路径**：`data/feed_cache.db`（~60MB，3 轮 × 20MB）
- **查询历史**：`feed_manager.query_history(ioc_type, ioc_value, rounds=3)` 查多轮数据
- **保留轮次可调**：`POST /api/v1/feeds/settings?max_rounds=5`（1-10），stats API 返回当前值和 DB 大小

### Feed 查询逻辑
- `feed_threats`：IP/域名/URL/Hash 精确匹配 + CIDR 范围匹配
- `feed_vulns`：CVE 大小写不敏感（自动转大写）+ MITRE 技术 ID
- `query_history()`：多轮历史查询（按 round_id 分组）

### 设置页全面展示（/api/v1/sources/all）
5 个分组：
1. 🔒 需要 API Key 的威胁情报源（6个）
2. 🌐 免费 OSINT 源（6个）
3. 🌍 IP 基础信息源（2个）
4. 📡 开源威胁情报 Feed（10个，含 IoC 数量/更新时间/DB 大小/保留轮次）
5. 🤖 LLM 配置（3个）

前端可折叠展开，支持实时编辑 API Key 和 LLM 配置。

微步 Key 在 ⚙️ 配置页填 `THREATBOOK_API_KEY`。

## 踩坑记录（重要！）

1. **回滚陷阱**：本会话曾出现「上轮改动在后端丢失」—— `chat.py`、`chat_*` 表、orchestrator 会话逻辑一度全部回滚。**凡是重要改动先写进 docs/plan.md + memory.md**，并核对 `app/api/__init__.py` 的注册行。
2. **Edit 工具报"file modified"**：文件被 linter/其他进程改过，需重新 Read 再 Edit；若反复失败用 Write 整体重写。
3. **前端构建失败**：`apiDelete` 需先在 `client.js` 导出；组件目录 `src/components/` 曾为空，需重建 `MarkdownContent.vue`。
4. **SPA catch-all**：`app/main.py` 的 `/{full_path:path}` 必须对 `api/` 前缀返回 JSON 404，否则前端 API 错误被吞成 HTML。
5. **配置缓存**：`config.py` 用 mtime 缓存，**API 写配置后必须调 `refresh_runtime_cache()`**，否则读到旧值。
6. **NVD 采集**：`intel_collector.py` 已从 `utcnow()` 改 `datetime.now(timezone.utc)`。
7. **Slash 请求体编码**：前端 `apiPostJson` 对 `/skills/slash` 用 `Content-Type: text/plain;charset=UTF-8`——若显式 `application/json`，FastAPI 会把请求体预解析成 dict，`await request.json()` 再解析会失败。后端 `/skills/slash` 用 `request.body()` 手动 json.loads，params 支持 dict / JSON 字符串 / 缺省三种形态。
8. **reasoning_effort 实测通过**：yuanyuaicloud.cn 网关对 glm-5.2 的 `reasoning_effort: low/medium/high` 三档均接受（2026-07-31 实测返回 200）。

## 关键功能：Slash 命令 + 思考强度（v1.2）

### Slash 命令（输入框 `/` 呼出）
- `ChatView.vue`：`/` 开头且无空格 → 显示已安装 skill 面板（模糊匹配名称/描述）
- 键盘：`↑`/`↓` 选择、`Tab` 补全、`Enter` 选中插入 `/name `；点击外部关闭
- 发送 `/name 参数` → 前端解析 `parseSlashCommand` → `POST /api/v1/skills/slash` → **后端直接 `execute_skill()`，不经 LLM**
- 支持参数：`/skill {"a":1}`（JSON）或 `/skill 纯文本`（包装为 `{value: ...}`）
- 非 `/` 消息走原 `/ask` Agent 循环

### 思考强度选择
- 输入框旁下拉：低/中/高，默认中
- 前端 `thinking` 字段 → `/ask` → orchestrator → `chat_completion(thinking=...)` → body 追加 `reasoning_effort`
- 不影响 slash 直接执行（不走 LLM）

## 关键功能：BI 看板 + 操作日志（v1.3）

### operation_logs 表（自动埋点）
- 表结构：`id / action / detail(JSON) / risk / created_at`，索引 `created_at DESC` + `action`
- **埋点位置（7 处）**：
  - `ioc.py` analyze → `ioc_query`（type/value）
  - `alert.py` parse → `alert_parse`（attack_type/confidence，risk 级别）
  - `skills.py` slash → `skill_run`（name/ok）
  - `ask.py` ask_question → `chat_ask`（question 前50字/session_id）
  - `config.py` update → `config_update`（key/set，**不记录 Key 明文**）
  - `chat.py` create/delete → `session_create`/`session_delete`
  - `report.py` daily → `report_view`
- 写库：`db.log_operation(action, detail=None, risk=None)`；读：`db.get_recent_operations(limit)`

### report/daily 聚合结构（BI 数据源）
`{date, daily_ops{days, series[{name,data}]}, action_dist[], risk_dist[], ioc_types[], top_iocs[], recent_logs[], totals{total_ops,today_ops,sessions,messages,cache_items,skills}}`
- `_daily_ops` 近 14 天 × 核心动作（ioc_query/alert_parse/skill_run/chat_ask + other）堆叠
- 中文标签映射 `ACTION_LABELS` 在 `report_generator.py` 顶部

### 前端 BI 看板
- **ECharts 按需引入**：`import('echarts')` 动态加载（不阻塞首屏）；`manualChunks: {echarts: ['echarts']}` 独立分包（1.1MB）
- 5 个图表：14 天趋势(堆叠柱) / 操作类型(环) / 风险级别(环) / IoC 类型(横条) / Top IoC(横条)
- 图表 ref 数组逐个 init，window resize 重绘，onUnmounted dispose
- 指标卡 4 个：累计操作 / 今日操作 / 会话数 / 缓存情报
- 空数据（total_ops===0）显示引导页

## 关键功能：告警引擎 v1.4（2026-07-31）

### 日志格式自动检测（`detect_format()`）
- 按前 5~10 行启发式判断，返回格式名称：
  - `nginx_combined`：`$ip - $user [$time] "METHOD URI HTTP/" $status $bytes`
  - `linux_auth`：`sshd[pid]`、`pam_unix(sshd:`、`Failed password` 等
  - `suricata_eve`：`"event_type":"`、`"src_ip":"`、`"alert":{`
  - `windows_event`：`EventID:`、`<EventID>`
  - `generic_syslog`：`^\w{3}\s+\d+\s+\d+:\d+:\d+\s+\S+\s+\w+`
  - `generic_web`：`GET/POST /... HTTP/`
  - 均不匹配 → `unknown`（所有规则参与匹配）

### 规则库（20+ 种，按日志类型分组）
- **Web 攻击**（nginx_combined/generic_web/suricata_eve）：SQL Injection、XSS、RCE、Path Traversal、SSRF、LFI、WebShell、Malicious File Upload、Suspicious User-Agent、Directory Brute Force
- **系统攻击**（linux_auth/generic_syslog）：SSH Brute Force、SSH Login Success、Sudo Privilege Escalation、SSH User Enumeration
- **网络攻击**（suricata_eve/generic_syslog/generic_web）：Port Scan、DNS Tunneling、DGA Domain、C2 Communication
- **通用检测**（全部格式）：DDoS/Flooding、Suspicious Base64 Payload、Information Disclosure、Brute Force (Generic)

### 评分逻辑
- 逐行逐规则匹配，单规则单行命中 +10，同规则多行 +5/行，上限 100
- 按总分排序取 top 10 → `all_matches` 字段，主命中 `attack_type` 为最高分
- 格式筛选：`RULES` 中 `log_types` 为空列表的规则匹配所有格式，非空则只匹配指定格式

### 上传端点
- `POST /api/v1/alert/upload`：`UploadFile`（`.log/.txt/.csv/.json/.evtx`），读取全部内容，返回 `AlertParseResponse` + `file_info`（文件名/大小/行数）
- 依赖 `python-multipart`（已装 0.0.32）

### AlertParseResponse 扩展字段
- `detected_format: str | None` — 检测到的日志格式
- `all_matches: list[AlertMatchItem]` — 所有命中（attack_type/risk_level/confidence/mitre_id/mitre_name）
- `line_count: int | None` — 输入行数
- `match_count: int | None` — 命中规则数
- `file_info: dict | None` — 上传文件信息（仅 upload 端点）

### 前端 AlertParser.vue
- 双输入模式：粘贴文本 / 上传文件（tab 切换）
- 拖拽上传 + 点击选择文件
- 5 条示例覆盖：SQL注入、XSS、SSH暴力破解、路径遍历、文件上传
- 结果展示：格式徽章 + 行数/命中数/文件名 + 主命中卡片 + 其他命中折叠列表

### 踩坑记录（补充 v1.4）
16. **SSRF false positive**：内网 IP 正则 `(192\.168\.)` 无前缀限制会匹配正常请求的 `192.168.1.1 - - [...]` 中的源 IP。修复：SSRF 模式前面加 `(url=|redirect=|return=)` 等参数名前缀，仅匹配参数值中的内网地址；普通请求不误报。
17. **旧进程必须杀干净**：`pkill -f "python run.py"` 可能杀不干净（新进程启动时旧进程仍绑定端口）。验证方式：`lsof -i :8020 | grep LISTEN` 确认只有一个 PID，且是新 PID。
18. **upload 端点路由**：`POST /api/v1/alert/upload` 必须注册在 `api_router` 上，与 `parse` 同文件。若旧进程未重启，路由不生效返回 405。

9. **`ACTION_LABELS.get(a, a)` 兜底**：`_daily_ops` 里 `other` 列不在 ACTION_LABELS 中，直接索引会 KeyError——必须用 `.get()` 兜底。
10. **echarts 动态 import**：`import('echarts')` 返回的模块含 `.default`，需 `echarts.default || echarts` 兼容。
11. **vite 分包警告**：echarts 单包 1.1MB > 500KB，用 `manualChunks` 独立分包 + `chunkSizeWarningLimit: 500` 消除警告；ECharts 完整包（非按需 tree-shake）无法更小。
12. **改后端必须重启常驻服务**：浏览器访问的 8020 端口常驻服务加载旧代码——ASGI 内存冒烟（`ASGITransport`）加载的是新代码，容易误判"已验证通过"。**任何后端改动后：杀 8020 旧进程 → 重启 `python run.py` → curl 实测**。
13. **Vue ref 模板绑定**：`ref="chartRefs.trend.value"` 是非法写法（ref 指令值必须是字符串），图表容器拿不到 DOM → `ec.init(undefined)` 静默失败。必须用独立的 `ref="chartTrend"` 字符串。
14. **IoC 页 localStorage 键**：`ioc_last_result`（最近结果）/ `ioc_last_raw`（展开状态）/ `ioc_query_form`（输入记忆）/ `ioc_history`（30 条）/ `ioc_favorites`（50 条）；历史/收藏只存摘要，完整结果只存最近一条。
15. **跨页跳转自动提问**：IoC 页 `router.push({path:'/chat', query:{q}})` → ChatView onMounted 读 `route.query.q` → `ask()` 后 `router.replace({query:{}})` 清理参数，避免刷新重复触发。
16. **Feed 拉取阻塞启动**：`feed_manager.start()` 中 `await refresh_stale(force=True)` 会同步拉取所有 Feed（~50-60s），导致服务启动超时。修复：改为 `asyncio.create_task()` 后台执行，启动只做 DB 恢复（~1s），Feed 在后台慢慢拉取。服务 3 秒内启动完成。
17. **数据源按钮挤占输入框**：ChatView 的数据源选择按钮显示所有源名，宽度撑开导致输入框被挤压。修复：`selectedLabel()` 统一显示"数据源 (N)" + CSS `max-width: 140px` + `text-overflow: ellipsis`。

## 待办 / 下一步

- [x] Slash 命令（输入框 `/` 呼出已安装 skill，后端直接执行）+ 思考强度选择（reasoning_effort）✅ 2026-07-31
- [x] 情报日报 → BI 看板（ECharts 图表 + 操作日志流水）✅ 2026-07-31
- [x] IoC 查询页：localStorage 持久化 + 历史/收藏/复制MD/一键AI分析 ✅ 2026-07-31
- [x] Feed SQLite 持久化 + 设置 API（保留轮次可调/DB 大小显示）✅ 2026-08-01
- [x] 设置页全面展示所有源（5 分组：威胁情报/免费OSINT/IP信息/Feed/LLM）✅ 2026-08-01
- [x] ChatView 数据源按钮简化 + 服务启动优化（后台拉取 Feed）✅ 2026-08-01
- [ ] **Skill 扩展标准化**：当前 skill 安装方式不符合标准，需参考 GitHub 上的标准 skill 格式（manifest + entry point），做成上传文件夹或 zip 包
- [ ] ThreatBook Key 配置后实测 scene/quick_check 返回
- [ ] 其余 OSINT Key（VT/OTX/Shodan/Censys/AbuseIPDB）可选配置
- [ ] 会话来源选择记忆（每会话记住勾选，当前全局默认全选）

## 常用命令

```bash
cd frontend && npm run build          # 构建前端
python -m pytest tests/ -q            # 回归测试（5个）
curl -s localhost:8020/health         # 健康检查
curl -s localhost:8020/api/v1/sources # 情报源列表
```

## 文档索引

- `docs/memory.md` — 本文件，开发记忆与踩坑记录
- `docs/plan.md` — 架构与实施记录（API端点、文件结构、变更日志）
- `docs/todo.md` — 任务跟踪（已完成/待办/环境信息/关键文件）
