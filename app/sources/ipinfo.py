import httpx
from .base import OSINTSource
from config import settings


class IPInfoSource(OSINTSource):
    """
    IP 基础信息查询，使用 ip-api.com（免费、无需 Key、支持 lang=zh-CN）。
    
    返回数据：国家/城市/ISP/ASN/ORG/坐标等。
    免费额度：45 次/分钟/IP，无月限制。
    """
    name = "ipinfo"
    supported_types = ["ip"]
    requires_key = False

    def _check_config(self):
        self.is_configured = True  # 始终可用，无需 Key

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if ioc_type != "ip":
            return {"error": "IPInfo only supports IP queries"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ioc_value}",
                params={"lang": "zh-CN", "fields": "status,message,country,countryCode,regionName,city,district,zip,lat,lon,timezone,isp,org,as,asname,reverse,mobile,proxy,hosting,query"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "fail":
                    return {"error": data.get("message", "Query failed")}
                return data
            return {"error": f"HTTP {resp.status_code}"}


class IPWhoIsSource(OSINTSource):
    """
    IP 基础信息查询备用源，使用 ipwho.is（免费、无需 Key、HTTPS）。
    
    返回数据：国家/城市/ISP/ASN/ORG/坐标/安全检测。
    免费额度：1000 次/天。
    """
    name = "ipwhois"
    supported_types = ["ip"]
    requires_key = False

    def _check_config(self):
        self.is_configured = True  # 始终可用，无需 Key

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if ioc_type != "ip":
            return {"error": "IPWhoIs only supports IP queries"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://ipwho.is/{ioc_value}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") is False:
                    return {"error": data.get("message", "Query failed")}
                return data
            return {"error": f"HTTP {resp.status_code}"}