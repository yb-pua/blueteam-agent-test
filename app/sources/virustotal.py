import httpx
import hashlib
import base64
from .base import OSINTSource
from config import settings

class VirusTotalSource(OSINTSource):
    name = "virustotal"
    supported_types = ["ip", "domain", "url", "hash"]
    requires_key = True

    def _check_config(self):
        self.is_configured = bool(settings.VIRUSTOTAL_API_KEY)
        self.api_key = settings.VIRUSTOTAL_API_KEY

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if not self.is_configured:
            return {"error": "API key not configured"}
        endpoint_map = {
            "ip": f"https://www.virustotal.com/api/v3/ip_addresses/{ioc_value}",
            "domain": f"https://www.virustotal.com/api/v3/domains/{ioc_value}",
            "url": f"https://www.virustotal.com/api/v3/urls/{self._url_to_id(ioc_value)}",
            "hash": f"https://www.virustotal.com/api/v3/files/{ioc_value}",
        }
        url = endpoint_map.get(ioc_type)
        if not url:
            return {"error": f"Unsupported type: {ioc_type}"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers={"x-apikey": self.api_key})
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:200]}

    @staticmethod
    def _url_to_id(url: str) -> str:
        raw = hashlib.sha256(url.encode()).digest()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")
