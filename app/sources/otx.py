import httpx
from .base import OSINTSource
from config import settings

class OTXSource(OSINTSource):
    name = "otx"
    supported_types = ["ip", "domain", "hash", "url"]
    requires_key = True

    def _check_config(self):
        self.is_configured = bool(settings.OTX_API_KEY)
        self.api_key = settings.OTX_API_KEY

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if not self.is_configured:
            return {"error": "API key not configured"}
        type_map = {"ip": "IPv4", "domain": "domain", "hash": "file", "url": "url"}
        otx_type = type_map.get(ioc_type)
        if not otx_type:
            return {"error": f"Unsupported type: {ioc_type}"}
        async with httpx.AsyncClient(timeout=15, base_url="https://otx.alienvault.com") as client:
            resp = await client.get(
                f"/api/v1/indicators/{otx_type}/{ioc_value}/general",
                headers={"X-OTX-API-Key": self.api_key}
            )
            if resp.status_code == 200:
                pulses_resp = await client.get(
                    f"/api/v1/indicators/{otx_type}/{ioc_value}/pulses",
                    headers={"X-OTX-API-Key": self.api_key}
                )
                result = resp.json()
                if pulses_resp.status_code == 200:
                    result["pulses"] = pulses_resp.json().get("results", [])
                return result
            return {"error": f"HTTP {resp.status_code}"}
