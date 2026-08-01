# IoCLens — 项目任务跟踪

> 最后更新: 2026-08-01
> 当前版本: v1.5.3

## 已完成

### v1.0 - v1.3 (2026-07-30 ~ 07-31)
- [x] 初版：8源 + LLM Agent + 告警/日报/知识库
- [x] 代码审查修复：SPA 404、LLM Key校验、.gitignore、配置缓存、全局异常
- [x] 历史会话持久化 + Markdown渲染 + 情报源复选 + 微步在线 + Skill扩展
- [x] Slash 命令 + 思考强度选择（reasoning_effort 三档）
- [x] IoC 查询页：JSON清洗解析 + localStorage持久化 + 历史/收藏/复制MD/一键AI分析
- [x] BI 看板（ECharts 5图 + 操作日志流水 + operation_logs自动埋点7处）

### v1.4 (2026-07-31)
- [x] 告警引擎全面升级：20+规则（Web/系统/网络/通用4大类）
- [x] 日志格式自动检测（6种格式：nginx/linux_auth/suricata/windows/syslog/generic_web）
- [x] 文件上传端点 `POST /alert/upload` + 前端双输入模式（粘贴/拖拽上传）

### v1.5.x (2026-08-01)
- [x] IP基础信息源：ip-api.com（免费，中文）+ ipwho.is（备用）
- [x] 开源威胁情报Feed聚合：10个免费Feed（Abuse.ch/OpenPhish/Blocklist等）
- [x] Feed SQLite持久化：feed_cache.db（~60MB，3轮），启动恢复+自动清理
- [x] Feed设置API：保留轮次可调（1-10），DB大小显示
- [x] 设置页全面展示所有源（5分组：威胁情报/免费OSINT/IP信息/Feed/LLM）
- [x] 服务启动优化：Feed拉取改为后台执行，启动时间从~50s降至~3s
- [x] ChatView数据源按钮简化为"数据源(N)" + CSS限宽

---

## 待办 / 下一步

### 高优先级
- [ ] **Skill扩展标准化**：当前skill安装方式不符合标准，需参考GitHub标准skill格式
  - 需求：做成上传文件夹或zip包，而不是手动复制输入
  - 参考：标准manifest + entry point格式
  - 前端：SkillsView需要支持文件上传

### 中优先级
- [ ] ThreatBook Key配置后实测 `scene/quick_check` 返回
- [ ] 其余OSINT Key（VT/OTX/Shodan/Censys/AbuseIPDB）可选配置

### 低优先级
- [ ] 会话来源选择记忆（每会话记住勾选，当前全局默认全选）
- [ ] MITRE ATT&CK数据加载优化（30MB JSON，当前惰性加载）

---

## 环境信息

```bash
# 服务启动
cd /home/aznic/StudyWithHermes/安全agent
python run.py                    # → http://localhost:8020

# 前端构建
cd frontend && npm run build

# 测试
python -m pytest tests/ -q       # 5个测试

# 健康检查
curl -s localhost:8020/health

# 代理支持（可选）
HTTP_PROXY=http://127.0.0.1:10808 HTTPS_PROXY=http://127.0.0.1:10808 python run.py
```

## 关键文件

| 文件 | 用途 |
|------|------|
| `run.py` | 一键启动入口 |
| `config.py` | 配置（环境变量 + data/config.json） |
| `app/main.py` | FastAPI入口 + lifespan |
| `app/feeds/__init__.py` | FeedManager + 10个Feed解析器 + SQLite持久化 |
| `app/sources/feed_sources.py` | Feed LLM工具包装器 |
| `app/engines/alert_engine.py` | 告警引擎（20+规则，格式检测） |
| `app/api/skills.py` | Skill管理API |
| `app/skills/__init__.py` | Skill引擎（安装/卸载/执行） |
| `frontend/src/views/ChatView.vue` | AI对话 + 数据源选择 |
| `frontend/src/views/SettingsView.vue` | 设置页（5分组展示所有源） |
| `frontend/src/views/SkillsView.vue` | Skill管理页 |
| `docs/memory.md` | 开发记忆（踩坑记录） |
| `docs/plan.md` | 架构与实施记录 |
| `docs/todo.md` | 本文件（任务跟踪） |
