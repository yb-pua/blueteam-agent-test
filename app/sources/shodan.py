import httpx
from .base import OSINTSource
from config import settings

class ShodanSource(OSINTSource):
    name = "shodan"
    supported_types = ["ip"]
    requires_key = True

    def _check_config(self):
        self.is_configured = bool(settings.SHODAN_API_KEY)
        self.api_key = settings.SHODAN_API_KEY

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if ioc_type != "ip":
            return {"error": "Shodan only supports IP queries"}
        if not self.is_configured:
            return {"error": "API key not configured"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.shodan.io/shodan/host/{ioc_value}",
                params={"key": self.api_key}
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}"}
