import httpx
from .base import OSINTSource

class PhishTankSource(OSINTSource):
    name = "phishtank"
    supported_types = ["url", "domain"]
    requires_key = False

    def _check_config(self):
        self.is_configured = True

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if ioc_type not in ("url", "domain"):
            return {"error": "PhishTank only supports URL/domain queries"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://checkurl.phishtank.com/checkurl/",
                data={"url": ioc_value, "format": "json", "app_key": "blue-team-agent"}
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}"}
