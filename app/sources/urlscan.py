import httpx
from .base import OSINTSource
from config import settings

class URLScanSource(OSINTSource):
    name = "urlscan"
    supported_types = ["ip", "domain", "url"]
    requires_key = False

    def _check_config(self):
        self.api_key = settings.URLSCAN_API_KEY
        self.is_configured = True

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        endpoint = "search/"
        params = {}
        if ioc_type == "ip":
            params["q"] = f"ip:{ioc_value}"
        elif ioc_type == "domain":
            params["q"] = f"domain:{ioc_value}"
        elif ioc_type == "url":
            params["q"] = f"page.url:{ioc_value}"
        else:
            return {"error": f"Unsupported type: {ioc_type}"}
        headers = {}
        if self.api_key:
            headers["API-Key"] = self.api_key
        async with httpx.AsyncClient(timeout=15, base_url="https://urlscan.io/api/v1") as client:
            resp = await client.get(endpoint, params=params, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}"}
