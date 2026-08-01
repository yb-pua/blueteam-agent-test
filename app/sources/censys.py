import httpx
import base64 as b64
from .base import OSINTSource
from config import settings

class CensysSource(OSINTSource):
    name = "censys"
    supported_types = ["ip", "domain"]
    requires_key = True

    def _check_config(self):
        self.is_configured = bool(settings.CENSYS_API_ID and settings.CENSYS_API_SECRET)
        auth_str = f"{settings.CENSYS_API_ID}:{settings.CENSYS_API_SECRET}"
        self.auth = b64.b64encode(auth_str.encode()).decode()

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if ioc_type not in ("ip", "domain"):
            return {"error": "Censys only supports IP and domain queries"}
        if not self.is_configured:
            return {"error": "API credentials not configured"}
        index = "hosts" if ioc_type == "ip" else "certificates"
        async with httpx.AsyncClient(timeout=15, base_url="https://search.censys.io/api/v2") as client:
            resp = await client.get(
                f"/{index}/{ioc_value}",
                headers={"Authorization": f"Basic {self.auth}"}
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}"}
