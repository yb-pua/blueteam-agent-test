"""
Feed-based OSINT 源包装器

每个 Feed 组（按功能分组）包装为一个 OSINTSource，
LLM Agent 可通过 function calling 调用。
"""

import asyncio
import httpx
from .base import OSINTSource
from ..feeds import feed_manager


class FeedThreatSource(OSINTSource):
    """
    通用恶意 IOC Feed 查询（SSLBL + URLhaus + ThreatFox + Blocklist.de + VXVault + OpenPhish + Spamhaus）。
    
    查询时从缓存中匹配 IoC，命中则返回详细信息。
    """
    name = "feed_threats"
    supported_types = ["ip", "domain", "url", "hash", "cidr"]
    requires_key = False

    def _check_config(self):
        self.is_configured = True  # 始终可用

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if ioc_type not in self.supported_types:
            return {"error": f"feed_threats 不支持查询 {ioc_type} 类型"}
        
        # 确保 Feed 已加载
        if not feed_manager._started:
            await feed_manager.start()

        matches = feed_manager.query(ioc_type, ioc_value)
        
        if matches:
            feeds_hit = [m.get("feed", "unknown") for m in matches]
            return {
                "found": True,
                "match_count": len(matches),
                "feeds": feeds_hit,
                "details": matches,
                "summary": f"在 {len(feeds_hit)} 个 Feed 中发现该 IoC: {', '.join(feeds_hit)}",
            }
        else:
            return {
                "found": False,
                "match_count": 0,
                "feeds": [],
                "details": [],
                "summary": "在所有 Feed 中未发现该 IoC",
            }


class FeedVulnSource(OSINTSource):
    """
    漏洞情报查询（CISA KEV + MITRE ATT&CK）。
    
    CISA KEV：已知在野利用漏洞清单，查询 CVE 是否在列表中。
    MITRE ATT&CK：攻击手法框架数据，查询技术 ID。
    """
    name = "feed_vulns"
    supported_types = ["cve", "technique"]
    requires_key = False

    def _check_config(self):
        self.is_configured = True

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if ioc_type not in self.supported_types:
            return {"error": f"feed_vulns 不支持查询 {ioc_type} 类型"}
        
        if not feed_manager._started:
            await feed_manager.start()

        matches = feed_manager.query(ioc_type, ioc_value)
        
        if matches:
            return {
                "found": True,
                "match_count": len(matches),
                "details": matches,
                "summary": f"找到 {len(matches)} 条匹配记录",
            }
        else:
            return {
                "found": False,
                "match_count": 0,
                "details": [],
                "summary": "未找到匹配记录",
            }


class FeedStatsSource(OSINTSource):
    """
    Feed 统计信息查询。返回各 Feed 的缓存状态和 IoC 数量。
    """
    name = "feed_stats"
    supported_types = ["feed_info"]
    requires_key = False

    def _check_config(self):
        self.is_configured = True

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if not feed_manager._started:
            await feed_manager.start()
        
        stats = feed_manager.stats()
        total_feeds = len(stats)
        total_ios = sum(s["total_ios"] for s in stats.values())
        
        return {
            "total_feeds": total_feeds,
            "total_ios": total_ios,
            "feeds": stats,
        }