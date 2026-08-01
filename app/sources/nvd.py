import httpx
from .base import OSINTSource

class NVDSource(OSINTSource):
    name = "nvd"
    supported_types = ["cve"]
    requires_key = False

    def _check_config(self):
        self.is_configured = True

    async def query(self, ioc_type: str, ioc_value: str) -> dict:
        if ioc_type != "cve":
            return {"error": "NVD only supports CVE lookups"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://services.nvd.nist.gov/rest/json/cves/2.0",
                params={"cveId": ioc_value.upper()}
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}"}
