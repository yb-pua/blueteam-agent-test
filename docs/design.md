# IoCLens — 蓝队威胁情报辅助平台

## 概述

面向护网/攻防演练场景的轻量级威胁情报 Web 平台，服务初级安全运维人员。单机部署、零硬件联动，通过聚合多个公开 OSINT 源提供快速威胁研判与告警分析能力。

## 架构

```
Web 前端 (Vue3 + Vite + Tailwind)
        │ REST API
FastAPI 后端服务
  ├─ IoC 分析引擎      并行查多源 OSINT
  ├─ 告警解析引擎       原始告警 → ATT&CK映射 → 处置建议
  ├─ 情报采集引擎       CVE/APT 定时采集
  ├─ 知识库引擎        攻击手法库 + 应急 SOP
  ├─ 报告生成引擎       PDF/Markdown 情报日报
  └─ 缓存/调度层       内存缓存 + APScheduler
数据层: SQLite (持久化)
外部 OSINT: VirusTotal / AbuseIPDB / Shodan / OTX / URLScan / Censys / NVD / PhishTank
```

## 核心模块

### 1. IoC 分析引擎
- 输入: IP / 域名 / URL / Hash (MD5/SHA1/SHA256)
- 多源并行查询，聚合评分 (0-100)
- 输出: 地理位置 / ASN / 威胁标签 / 历史恶意行为 / 关联样本 / 置信度评分
- 引导式输出: 自然语言研判小结 + 一键处置建议 (WAF规则/防火墙策略模板)

### 2. 告警解析引擎
- 输入: WAF/IPS/EDR/SIEM 原始告警文本
- 提取攻击类型 → MITRE ATT&CK 映射 → 风险评级 → 处置建议
- 关联历史同类告警 + 推荐知识库文章

### 3. 情报采集引擎
- 定时采集: 新增严重 CVE、活跃 APT 团伙动向、行业安全事件
- 生成每日情报日报 (Markdown → PDF)

### 4. 知识库
- 护网常见攻击手法库 (MITRE ATT&CK 映射)
- 应急响应 SOP (勒索/挖矿/Webshell/数据泄露)
- 常见端口/服务/威胁速查表
- 用户可自定义扩展

## 外部 API 策略 (渐进式)
| 层级 | 说明 | 示例 |
|------|------|------|
| 免费/无Key | 默认启用 | Censys免费查询、NVD、公开情报列表 |
| 免费注册Key | 配置可选 | AbuseIPDB、VirusTotal社区版、OTX |
| 付费API | 可选配置 | Shodan、VirusTotal企业版 |

## 技术栈
- 后端: Python 3.11+ / FastAPI / httpx / APScheduler / SQLite
- 前端: Vue 3 + Vite + Tailwind CSS
- 部署: 单机一键启动，pip install && cd frontend && npm install && npm run build && cd .. && python run.py
