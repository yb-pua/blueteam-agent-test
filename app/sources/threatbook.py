import httpx
from .base import OSINTSource
from config import settings

class ThreatBookSource(OSINTSource):
    name = "threatbook"
    # 微步在线威胁情报：支持 ip / domain / url / hash
    supported_types = ["ip", "domain", "url", "hash"]
    requires_key = True

    def _check_config(self):
        self.is_configured = bool(settings.THREATBOOK_API_KEY)
        self.api_key = settings.THREATBOOK_API_KEY

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if not self.is_configured:
            return {"error": "API key not configured"}
        type_map = {
            "ip": "ip",
            "domain": "domain",
            "url": "url",
            "hash": "file",
        }
        threatbook_type = type_map.get(ioc_type)
        if not threatbook_type:
            return {"error": f"ThreatBook 不支持查询 {ioc_type} 类型"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.threatbook.cn/v3/scene/quick_check",
                data={
                    "apikey": self.api_key,
                    "resource": ioc_value,
                    "type": threatbook_type,
                }
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:300]}