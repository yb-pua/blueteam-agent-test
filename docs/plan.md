# IoCLens — 蓝队威胁情报辅助平台

> 最后更新: 2026-08-01
>
> 当前状态: **v1.5.3** — 运行中，含 Feed 聚合引擎 + 设置页 + 服务启动优化

**目标:** 面向护网/攻防演练的 LLM 驱动威胁情报 Agent，聚合多源 OSINT + AI 分析

**架构:** LLM Agent (OpenAI兼容API) → Tool Calling → OSINT多源查询 → AI研判 → 自然语言结论

**技术栈:** Python 3.11+ / FastAPI / httpx / aiosqlite / APScheduler / Vue 3 + Vite / LLM API (glm-5.2)

---

## 架构图

```
用户(自然语言 + 情报源复选) ──→ POST /api/v1/ask
                                  │
                            ┌─────▼──────┐
                            │ LLM Agent  │  ← OpenAI兼容API (glm-5.2 @ yuanyuaicloud.cn)
                            │ Orchestrator│  ← 多轮上下文 + 会话持久化
                            └─────┬──────┘
                                  │  Tool Calling (最多5轮, 按所选源构建工具)
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
    ┌────────────────┐   ┌──────────────┐   ┌────────────────┐
    │ 无Key源(默认)   │   │ 需Key源(配置) │   │ 微步 ThreatBook │
    │ NVD / PhishTank│   │ VT/ABuseIPDB │   │ ip/域/url/hash  │
    │ URLScan        │   │ OTX/Shodan/  │   │ scene/quick_    │
    │ IPInfo/IPWhoIs │   │ Censys       │   │ check          │
    └────────────────┘   └──────────────┘   └────────────────┘
```

---

## API 端点

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/v1/analyze/{type}/{value}` | GET | 原始多源查询（无AI评分，仅返回数据）|
| `/api/v1/alert/parse` | POST | 告警正则解析（SQLi/XSS/RCE 等 20+ 种，自动格式检测）|
	| `/api/v1/alert/upload` | POST | **【v1.4】文件上传告警解析**（UploadFile → 格式检测 + 规则匹配）|
	| `/api/v1/ask` | POST | LLM Agent 分析。Body: `{question, session_id?, sources?}` |
	| `/api/v1/sources` | GET | 情报源列表（供 AI 对话复选下拉）|
	| `/api/v1/sources/all` | GET | **【v1.5】所有源完整状态**（按分组：威胁情报/免费OSINT/IP信息/Feed/LLM，含配置状态和 IoC 统计）|
	| `/api/v1/chat/sessions` | GET/POST | 会话列表 / 新建会话 |
| `/api/v1/chat/sessions/{id}/messages` | GET | 会话消息 |
| `/api/v1/chat/sessions/{id}/rename` | POST | 重命名会话 |
| `/api/v1/chat/sessions/{id}` | DELETE | 删除会话（级联删消息）|
| `/api/v1/report/daily` | GET | **【v1.3】BI 看板聚合数据**（近14天操作趋势/类型分布/风险分布/IoC类型/Top IoC/最近20条操作日志/总量指标）|
| `/api/v1/kb/techniques` | GET | 攻击手法知识库（10种ATT&CK）|
| `/api/v1/kb/playbooks` | GET | 应急SOP（4个场景）|
| `/api/v1/config` | GET/POST | 运行时API Key配置 |
| `/api/v1/skills` | GET/POST | **Skill 市场/安装**（扩展功能）|
| `/api/v1/skills/slash` | POST | **【v1.2】Slash 直接执行 skill**（不经 LLM），body `{name, params?}`，params 支持 dict / JSON 字符串 / 缺省 |
| `/api/v1/ask` | POST | **【v1.2】新增 `thinking` 字段**（low/medium/high → reasoning_effort）|
| `/api/v1/feeds/stats` | GET | **【v1.5】Feed 缓存统计**（各 Feed IoC 数量、DB 大小、保留轮次）|
| `/api/v1/feeds/refresh` | POST | **【v1.5】手动刷新所有 Feed** |
| `/api/v1/feeds/settings` | GET/POST | **【v1.5】Feed 设置**（max_rounds 保留轮次，1-10 可调）|
| `/health` | GET | 健康检查 |

---

## 项目文件结构

```
安全agent/
├── run.py                         # 一键启动入口
├── requirements.txt               # Python 依赖
├── pyproject.toml                 # pytest 配置
├── config.py                      # 配置（环境变量 + data/config.json 双源, mtime缓存）
├── app/
│   ├── main.py                    # FastAPI 入口（全局异常处理 + serve前端dist）
│   ├── llm/
│   │   └── client.py              # OpenAI兼容API客户端 + 系统提示词 + Key前置校验
│   ├── agent/
│   │   ├── tools.py               # OSINT源 → Tool定义(可过滤) + 动态执行
│   │   └── orchestrator.py        # Agent循环 + 会话持久化 + 多轮上下文
│   ├── api/
│   │   ├── __init__.py            # APIRouter + 路由注册
│   │   ├── ioc.py                 # 原始IoC查询
│   │   ├── alert.py               # 告警解析 + 文件上传
│   │   ├── ask.py                 # LLM Agent 接口（session_id + sources）
│   │   ├── report.py              # 情报日报
│   │   ├── kb.py                  # 知识库
│   │   ├── config.py              # 运行时API Key配置
│   │   ├── chat.py                # 会话 CRUD API
│   │   ├── sources.py             # 情报源列表 API
│   │   └── skills.py              # Skill 市场/安装 API
│   ├── engines/
│   │   ├── ioc_engine.py          # 精简版：仅路由+查询
│   │   ├── alert_engine.py        # 正则告警引擎（20+种攻击模式，自动格式检测）
│   │   ├── intel_collector.py     # CVE定时采集（每6小时, UTC时间修复）
│   │   └── report_generator.py    # 情报日报生成
│   ├── sources/                   # 9个OSINT源
│   │   ├── base.py                # 基类 + can_handle() + reload()
│   │   ├── virustotal.py / abuseipdb.py / otx.py / urlscan.py
│   │   ├── shodan.py / censys.py / nvd.py / phishtank.py
│   │   ├── threatbook.py          # 微步在线 (ip/domain/url/hash) 【新增】
	│   │   ├── ipinfo.py              # IP基础信息 (ip-api.com + ipwho.is) 【新增】
	│   │   └── feed_sources.py        # 【新增】Feed 威胁情报 LLM 工具包装器
	│   ├── feeds/                     # 【新增】开源威胁情报 Feed 聚合引擎
	│   │   └── __init__.py            # FeedManager + 10 个 Feed 解析器 + SQLite 持久化
	│   ├── skills/                    # 【新增】Skill 扩展引擎
│   │   ├── __init__.py
│   │   ├── manager.py             # 扫描/安装/卸载/执行 skill
│   │   └── store/                 # 已安装的 skill 定义（skills.json）
│   ├── models/
│   │   ├── database.py            # aiosqlite 异步DB（含 chat 表）
│   │   └── schemas.py             # Pydantic 模型
│   ├── kb/                        # 攻击手法 + 应急SOP
│   └── utils/
├── frontend/
│   ├── dist/                      # 构建产物（FastAPI直接 serve）
│   └── src/
│       ├── App.vue                # 导航栏
│       ├── router/index.js
│   │   ├── api/client.js          # API 客户端（apiGet/apiPost/apiDelete/apiUpload）
│       ├── components/MarkdownContent.vue  # marked + DOMPurify MD渲染
│       └── views/
│           ├── ChatView.vue       # AI分析（会话侧栏 + 情报源复选下拉 + MD渲染）
│           ├── IoCQuery.vue / AlertParser.vue / DailyBrief.vue
│           ├── KnowledgeBase.vue / SettingsView.vue
│           └── SkillsView.vue     # 【新增】Skill 管理页
├── data/
│   ├── config.json                # 运行时配置（含 API Key, 已 gitignore）
│   └── threat_intel.db            # SQLite（ioc_cache/alert_history/intel_articles/chat_*）
├── tests/
│   └── test_ioc_engine.py         # 5个测试
└── docs/
    ├── design.md
    ├── plan.md
    └── memory.md                  # 【新增】开发记忆
```

---

## 关键设计决策

### LLM 驱动（替代机械评分）
- 每个源声明 `supported_types`；`score_confidence()` 已移除（LLM 理解数据出结论）
- LLM 系统提示词要求客观分析，不误判良性基础设施（如 1.1.1.1 / 8.8.8.8）

### 类型路由（can_handle）
- 每个源声明 `supported_types`，引擎/LLM 只调用匹配类型的源

### 运行时配置（双层 + 缓存）
- API Key 通过配置页设置 → `data/config.json` → `refresh_all()` 刷新源
- `config.py` 带 **mtime 内存缓存**，配置写入后 `refresh_runtime_cache()` 强制刷新
- 环境变量优先级高于页面配置

### 历史会话持久化（v1.1）
- 表: `chat_sessions` + `chat_messages`（级联删除）
- `/ask` 携带 `session_id` 加载历史 → 多轮上下文；返回最新 `session_id`
- 首条问题自动生成会话标题；前端侧栏管理（新建/切换/删除）

### Markdown 渲染（v1.1）
- `MarkdownContent.vue`: marked 渲染 + DOMPurify 消毒（防 XSS）
- AI 回答按 Markdown 展示（标题/表格/代码块/引用）

### 情报源复选（v1.1）
- `ChatView` 输入栏旁下拉，`/api/v1/sources` 提供可用源
- 勾选结果通过 `/ask` 的 `sources` 参数 → 仅构建所选源的 function tools
- 支持全选/清空；不选 = 纯对话模式
- **【v1.2 修复】展示全部 9 个源**，未配置 Key 的源置灰 🔒（原先前端 filter 掉未配置源导致只剩 3 个）

### 微步在线 ThreatBook（v1.1）
- `app/sources/threatbook.py` 调用 `https://api.threatbook.cn/v3/scene/quick_check`
- 配置项 `THREATBOOK_API_KEY`，支持 ip/domain/url/hash

### Skill 扩展（v1.1）
- `app/skills/manager.py` 管理已安装 skill（`app/skills/store/skills.json`）
- 安装流程: 验证 manifest → 生成工具定义 → 注册到 Agent 工具集
- 每个 skill 成为新的 function tool，LLM 可按需调用
- 前端 SkillsView 页面：列出/安装/卸载

### Slash 命令 + 思考强度（v1.2）
- **Slash 命令**：输入框 `/` 开头且无空格 → 呼出已安装 skill 面板（参考 opencode/codex/zcode 交互）
  - `↑`/`↓` 选择、`Tab` 补全、`Enter` 选中插入 `/name `
  - 发送 `/name 参数` → `POST /api/v1/skills/slash` → **后端直接 `execute_skill()`**（不经 LLM，结果作 AI 消息渲染）
  - params 支持 dict / JSON 字符串 / 纯文本（`{value: ...}` 包装）三种形态
  - ⚠️ 前端用 `text/plain` Content-Type 发送，避免 FastAPI 预解析 body 导致 `request.json()` 二次解析失败
- **思考强度选择**：输入框旁下拉（低/中/高，默认中）
  - `/ask` 增加 `thinking` 字段 → orchestrator 透传 → `chat_completion(thinking=...)` → body 追加 `reasoning_effort`
  - 网关实测三档均接受（2026-07-31）
  - 仅对普通 AI 对话生效，slash 直接执行不涉及

### IoC 查询页清洗解析（v1.2）
- 每源 JSON 由专用解析器提取关键字段 → 键值表（按危险程度着色）
- 9 个源解析器：VT(引擎统计/ASN/信誉) / AbuseIPDB(置信度/举报) / OTX(pulse) / Shodan(端口/漏洞) / Censys(服务) / URLScan(判定) / PhishTank(入库) / NVD(CVSS/CWE) / ThreatBook(severity)
- 综合风险评级（bad/warn/good/info → 徽章）；「原始 JSON」按钮保留展开

### BI 看板 + 操作日志（v1.3）
- **operation_logs 自动埋点**（7 处 API：ioc/alert/skill/ask/config/chat×2/report）
- **report/daily 重写**为统计聚合（原 NVD CVE 日报废弃）
- **前端 DailyBrief 重写**：4 指标卡 + 5 个 ECharts 图 + 最近 20 条操作日志表格
  - 图表：14 天趋势(堆叠柱) / 操作类型(环) / 风险级别(环) / IoC 类型(横条) / Top IoC(横条)
  - ECharts 动态 `import()` + `manualChunks` 独立分包（1.1MB，不阻塞首屏）

### IoC 查询页增强（v1.3.x）
- **localStorage 持久化**：结果（`ioc_last_result`）/ 展开状态 / 输入记忆 切页不丢
- **查询历史**（30 条，去重，风险着色标签，点击重查/删除/清空）
- **收藏夹**（50 条，⭐ 收藏/取消）
- **复制为 Markdown**：自动生成含综合评级+各源键值表的报告格式
- **一键 AI 分析**：`/chat?q=分析威胁情报：...` 跳转并自动提问（ChatView 读 route.query.q）

### 单端口部署
- 前端 build 产物由 FastAPI serve；SPA catch-all 对 `/api/` 返回 JSON 404
- 全局异常处理器统一错误格式（HTTPException / ValidationError / 500）

---

## 环境变量

```bash
# OSINT API Keys
VT_API_KEY=              # VirusTotal
ABUSEIPDB_API_KEY=       # AbuseIPDB
SHODAN_API_KEY=          # Shodan
OTX_API_KEY=             # AlienVault OTX
URLSCAN_API_KEY=         # URLScan.io (可选)
CENSYS_API_ID=           # Censys
CENSYS_API_SECRET=       # Censys
THREATBOOK_API_KEY=      # 微步在线 【新增】

# LLM (OpenAI 兼容) — 当前配置
LLM_BASE_URL=https://yuanyuaicloud.cn/v1
LLM_API_KEY=sk-AVXIx...   # 存于 data/config.json
LLM_MODEL=glm-5.2         # 注意小写
```

---

## 构建与启动

```bash
# 首次
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

# 启动
python run.py
# → http://localhost:8020
# 浏览器如遇旧界面请 Ctrl+Shift+R 强刷
```

---

## 变更日志

| 日期 | 版本 | 内容 |
|------|------|------|
| 2026-07-30 | v1.0 | 初版：8源 + LLM Agent + 告警/日报/知识库 |
| 2026-07-31 | v1.0.x | 代码审查修复：SPA 404、LLM Key校验、.gitignore、配置缓存、全局异常、死代码清理 |
| 2026-07-31 | v1.1 | 历史会话持久化 + Markdown渲染 + 情报源复选 + 微步在线 + **Skill扩展** |
| 2026-07-31 | v1.2 | **Slash 命令**（输入框 `/` 呼出已安装 skill，后端 `/skills/slash` 直接执行）+ **思考强度选择**（reasoning_effort 三档）+ IoC 页 JSON 清洗解析 |
| 2026-07-31 | v1.3 | **情报日报 → BI 看板**（ECharts 5 图 + 操作日志流水 + operation_logs 自动埋点 7 处 + report/daily 聚合重写）|
| 2026-07-31 | v1.3.x | **IoC 查询页增强**：localStorage 持久化 + 查询历史/收藏夹/复制 Markdown/一键 AI 分析 |
| 2026-07-31 | **v1.4** | **告警引擎全面升级**：20+ 规则（Web/系统/网络/通用 4 大类）、日志格式自动检测（6 种格式）、多规则评分排序、文件上传端点 `POST /alert/upload`、前端双输入模式（粘贴/拖拽上传）|
| 2026-07-31 | v1.4.x | **IP 基础信息源**：ip-api.com（免费，45次/分钟，中文，国家/城市/ISP/ASN/坐标）+ ipwho.is（备用，1000次/天，HTTPS），前端解析器已适配 |
| 2026-08-01 | **v1.5** | **开源威胁情报 Feed 聚合引擎**：10 个免费 Feed（Abuse.ch 系列、OpenPhish、Blocklist.de、VXVault、Spamhaus DROP、CISA KEV、MITRE ATT&CK），FeedManager 内存缓存 + 定时刷新，LLM 3 个工具（feed_threats/feed_vulns/feed_stats），前端 3 个解析器，代理支持 `HTTP_PROXY` |
| 2026-08-01 | v1.5.1 | **Feed SQLite 持久化**：feed_cache.db（~60MB，3 轮），启动从 DB 恢复，新轮写入 + 自动清理旧轮，多轮历史查询，CVE 大小写兼容 |
| 2026-08-01 | v1.5.2 | **Feed 设置 API**：`GET/POST /feeds/settings` 保留轮次可调（1-10），`GET /feeds/stats` 返回 DB 大小和元信息，前端解析器适配 |
| 2026-08-01 | **v1.5.3** | **服务启动优化**：Feed 拉取改为后台执行（`asyncio.create_task`），启动时间从 ~50s 降至 ~3s；ChatView 数据源按钮简化为"数据源 (N)"+CSS 限宽 |
