import httpx
import time
import datetime
from app.models.database import get_db

class IntelCollector:
    async def collect_recent_cves(self, days: int = 1):
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        start = (now - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
        end = now.strftime("%Y-%m-%dT%H:%M:%S")
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://services.nvd.nist.gov/rest/json/cves/2.0",
                params={
                    "pubStartDate": start,
                    "pubEndDate": end,
                    "resultsPerPage": 20,
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                vulnerabilities = data.get("vulnerabilities", [])
                conn = await get_db()
                try:
                    for vuln in vulnerabilities:
                        cve = vuln.get("cve", {})
                        cve_id = cve.get("id", "")
                        desc = ""
                        for d in cve.get("descriptions", []):
                            if d.get("lang") == "en":
                                desc = d.get("value", "")
                                break
                        metrics = cve.get("metrics", {})
                        cvss = "N/A"
                        if "cvssMetricV31" in metrics:
                            cvss = str(metrics["cvssMetricV31"][0].get("cvssData", {}).get("baseScore", "N/A"))
                        await conn.execute(
                            """INSERT OR IGNORE INTO intel_articles
                               (title, url, source, summary, severity, published_at, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (cve_id, f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                             "NVD", desc[:500], cvss, cve.get("published", ""), time.time())
                        )
                    await conn.commit()
                finally:
                    await conn.close()

    async def run_once(self):
        await self.collect_recent_cves()
