"""情报来源列表 API — 供前端渲染复选下拉框 + 设置页全面展示。"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agent.tools import build_tools
from app.sources import ALL_SOURCES, get_configured_sources
from app.feeds import feed_manager, FEEDS

router = APIRouter()

SOURCE_LABELS = {
    "virustotal": "VirusTotal",
    "abuseipdb": "AbuseIPDB",
    "otx": "AlienVault OTX",
    "urlscan": "URLScan.io",
    "shodan": "Shodan",
    "censys": "Censys",
    "nvd": "NVD (CVE)",
    "phishtank": "PhishTank",
    "threatbook": "微步在线 ThreatBook",
    "ipinfo": "IPInfo (ip-api.com)",
    "ipwhois": "IPWhoIs (ipwho.is)",
    "feed_threats": "Feed 威胁情报聚合",
    "feed_vulns": "Feed 漏洞情报",
    "feed_stats": "Feed 统计",
}

FEED_LABELS = {
    "sslbl_ip": "SSLBL 恶意 SSL IP 黑名单",
    "sslbl_cert": "SSLBL 恶意证书指纹",
    "urlhaus": "URLhaus 恶意下载 URL",
    "threatfox": "ThreatFox 活跃恶意 IOC",
    "openphish": "OpenPhish 钓鱼 URL",
    "blocklist_de": "Blocklist.de 暴力破解 IP",
    "vxvault": "VXVault 恶意 URL",
    "spamhaus_drop": "Spamhaus DROP 僵尸网络段",
    "cisa_kev": "CISA KEV 在野利用漏洞",
    "mitre_attack": "MITRE ATT&CK 框架数据",
}


@router.get("/sources")
async def list_sources():
    """返回所有 OSINT 源的元信息与可用状态。"""
    items = []
    for source in ALL_SOURCES:
        items.append({
            "name": source.name,
            "label": SOURCE_LABELS.get(source.name, source.name),
            "supported_types": list(source.supported_types),
            "requires_key": source.requires_key,
            "configured": source.is_configured,
            "available": source.is_configured or not source.requires_key,
        })
    return {"items": items}


@router.get("/sources/all")
async def get_all_sources():
    """返回所有数据源的完整状态信息（按分组）。"""
    configured = {s.name for s in get_configured_sources()}

    groups = {
        "threat_intel": {
            "label": "🔒 需要 API Key 的威胁情报源",
            "description": "需要注册并配置 API Key 后使用",
            "sources": []
        },
        "osint_free": {
            "label": "🌐 免费 OSINT 源",
            "description": "无需 Key，开箱即用",
            "sources": []
        },
        "ip_geo": {
            "label": "🌍 IP 基础信息源",
            "description": "IP 地理位置、ISP、ASN 查询",
            "sources": []
        },
        "feeds": {
            "label": "📡 开源威胁情报 Feed",
            "description": "自动定时拉取，内存缓存 + SQLite 持久化",
            "sources": [],
            "meta": {}
        },
        "llm": {
            "label": "🤖 LLM 配置",
            "description": "AI 分析引擎，支持任何 OpenAI 兼容接口",
            "sources": []
        },
    }

    # 需要 Key 的源
    for s in ALL_SOURCES:
        if s.requires_key:
            groups["threat_intel"]["sources"].append({
                "name": s.name,
                "label": SOURCE_LABELS.get(s.name, s.name),
                "type": "api_key",
                "configured": s.is_configured,
                "supported_types": list(s.supported_types),
            })

    # 免费 OSINT 源
    for s in ALL_SOURCES:
        if not s.requires_key and s.name not in ("ipinfo", "ipwhois"):
            groups["osint_free"]["sources"].append({
                "name": s.name,
                "label": SOURCE_LABELS.get(s.name, s.name),
                "type": "free",
                "configured": s.is_configured,
                "supported_types": list(s.supported_types),
            })

    # IP 基础信息源
    for s in ALL_SOURCES:
        if s.name in ("ipinfo", "ipwhois"):
            groups["ip_geo"]["sources"].append({
                "name": s.name,
                "label": SOURCE_LABELS.get(s.name, s.name),
                "type": "free",
                "configured": s.is_configured,
                "supported_types": list(s.supported_types),
            })

    # Feed 源
    feed_stats = feed_manager.stats() if feed_manager._started else {}
    for feed in FEEDS:
        name = feed["name"]
        stats = feed_stats.get(name, {})
        groups["feeds"]["sources"].append({
            "name": name,
            "label": FEED_LABELS.get(name, name),
            "type": "feed",
            "configured": stats.get("total_ios", 0) > 0,
            "total_ios": stats.get("total_ios", 0),
            "last_fetch": stats.get("last_fetch"),
            "interval": feed["interval"],
            "ioc_types": feed["ioc_types"],
        })

    meta = feed_stats.get("_meta", {})
    groups["feeds"]["meta"] = {
        "max_rounds": meta.get("max_rounds", 3),
        "db_size_bytes": meta.get("db_size_bytes", 0),
        "total_ios": meta.get("total_ios", 0),
    }

    # LLM 配置
    llm_fields = [
        ("LLM_BASE_URL", "LLM API 地址", "text"),
        ("LLM_API_KEY", "LLM API Key", "password"),
        ("LLM_MODEL", "LLM 模型名", "text"),
    ]
    for key, label, typ in llm_fields:
        val = os.getenv(key, "")
        groups["llm"]["sources"].append({
            "name": key,
            "label": label,
            "type": "config",
            "configured": bool(val),
            "value_type": typ,
            "current_value": "******" if val and typ == "password" else val,
        })

    total_configured = len(configured)
    return {
        "groups": groups,
        "summary": {
            "total_sources": len(ALL_SOURCES),
            "configured_sources": total_configured,
            "feed_ios": meta.get("total_ios", 0),
        }
    }