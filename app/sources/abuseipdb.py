import httpx
from .base import OSINTSource
from config import settings

class AbuseIPDBSource(OSINTSource):
    name = "abuseipdb"
    supported_types = ["ip"]
    requires_key = True

    def _check_config(self):
        self.is_configured = bool(settings.ABUSEIPDB_API_KEY)
        self.api_key = settings.ABUSEIPDB_API_KEY

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if ioc_type != "ip":
            return {"error": "AbuseIPDB only supports IP queries"}
        if not self.is_configured:
            return {"error": "API key not configured"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.abuseipdb.com/api/v2/check",
                params={"ipAddress": ioc_value, "maxAgeInDays": "90"},
                headers={"Key": self.api_key, "Accept": "application/json"}
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}"}
