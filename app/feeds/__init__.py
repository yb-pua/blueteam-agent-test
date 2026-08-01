"""
FeedManager — 开源威胁情报 Feed 统一管理器

功能：
1. 从 10 个免费 Feed URL 拉取数据
2. 写入 SQLite 持久化（feed_cache 表），保留最近 N 轮
3. 内存缓存供零延迟查询，服务重启从 DB 恢复
4. 定时刷新 stale Feed，自动清理旧轮

存储策略：
- feed_cache 表：每轮刷新写入，带 round_id 标记
- feed_rounds 表：记录每轮刷新的元信息
- 保留最近 MAX_ROUNDS 轮（默认 3），超出的自动清理
- 每条 IOC 约 100-500 字节，urlhaus 6.6 万条约 30MB，3 轮约 90MB

代理：自动读取 HTTP_PROXY / HTTPS_PROXY 环境变量
"""

import os
import json
import time
import ipaddress
import csv
import io
import asyncio
import aiosqlite
import httpx
from typing import Any

# ---------- 配置 ----------

MAX_ROUNDS = 3  # 保留最近几轮（可通过 API 调整）

# ---------- Feed 定义 ----------

TEXT_ONE_PER_LINE = "text_line"
CSV_FORMAT = "csv"
JSON_FORMAT = "json"


def _parse_sslbl_ip(raw: str) -> dict:
    result = {}
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        result[line] = {"source": "sslbl", "type": "malicious_ssl_ip"}
    return {"ip": result}


def _parse_sslbl_cert(raw: str) -> dict:
    result = {}
    reader = csv.reader(io.StringIO(raw))
    for row in reader:
        if len(row) < 3 or row[0].startswith("#"):
            continue
        sha1 = row[0].strip()
        if len(sha1) == 40:
            result[sha1.lower()] = {
                "source": "sslbl", "type": "malicious_cert",
                "date": row[1].strip(), "reason": row[2].strip(),
            }
    return {"hash": result}


def _parse_urlhaus(raw: str) -> dict:
    result = {}
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 1)
        url = parts[0].strip().strip('"')
        if url.startswith("http"):
            result[url] = {"source": "urlhaus", "type": "malware_download"}
    return {"url": result}


def _parse_threatfox(raw: str) -> dict:
    result = {"ip": {}, "domain": {}, "url": {}}
    reader = csv.reader(io.StringIO(raw))
    for row in reader:
        if len(row) < 5 or not row or row[0].startswith("#"):
            continue
        ioc_value = row[2].strip().strip('"') if len(row) > 2 else ""
        ioc_type_raw = row[3].strip().strip('"') if len(row) > 3 else ""
        threat_type = row[4].strip().strip('"') if len(row) > 4 else ""
        confidence = row[5].strip() if len(row) > 5 else ""
        if not ioc_value:
            continue
        detail = {"source": "threatfox", "threat_type": threat_type, "confidence": confidence}
        if ioc_type_raw in ("ip:port", "ip"):
            ip = ioc_value.split(":")[0]
            result["ip"][ip] = detail
        elif ioc_type_raw == "domain":
            result["domain"][ioc_value] = detail
        elif ioc_type_raw == "url":
            result["url"][ioc_value] = detail
    return result


def _parse_openphish(raw: str) -> dict:
    result = {}
    for line in raw.strip().splitlines():
        line = line.strip()
        if line and line.startswith("http"):
            result[line] = {"source": "openphish", "type": "phishing"}
    return {"url": result}


def _parse_blocklist(raw: str) -> dict:
    result = {}
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        ip = parts[0]
        try:
            ipaddress.ip_address(ip)
            result[ip] = {"source": "blocklist_de", "type": "brute_force"}
        except ValueError:
            continue
    return {"ip": result}


def _parse_vxvault(raw: str) -> dict:
    result = {}
    for line in raw.strip().splitlines():
        line = line.strip()
        if line and line.startswith("http") and not line.startswith("#"):
            result[line] = {"source": "vxvault", "type": "malware_c2"}
    return {"url": result}


def _parse_spamhaus_drop(raw: str) -> dict:
    result = {}
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        parts = line.split(";")
        cidr = parts[0].strip()
        desc = parts[1].strip() if len(parts) > 1 else ""
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            result[cidr] = {"source": "spamhaus_drop", "type": "drop_range", "network": str(network), "description": desc}
        except ValueError:
            continue
    return {"cidr": result}


def _parse_cisa_kev(raw: str) -> dict:
    result = {}
    try:
        data = json.loads(raw)
        for vuln in data.get("vulnerabilities", []):
            cve_id = vuln.get("cveID", "")
            if cve_id:
                result[cve_id] = {
                    "source": "cisa_kev",
                    "vendor": vuln.get("vendorProject", ""),
                    "product": vuln.get("product", ""),
                    "description": vuln.get("shortDescription", ""),
                    "date_added": vuln.get("dateAdded", ""),
                    "due_date": vuln.get("dueDate", ""),
                    "known_ransomware": vuln.get("knownRansomwareCampaignUse", "Unknown"),
                }
    except json.JSONDecodeError:
        pass
    return {"cve": result}


def _parse_mitre_attack(raw: str) -> dict:
    result = {}
    try:
        data = json.loads(raw)
        for obj in data.get("objects", []):
            obj_type = obj.get("type", "")
            if obj_type == "attack-pattern":
                name = obj.get("name", "")
                external_ids = obj.get("external_references", [])
                technique_id = ""
                for ref in external_ids:
                    if ref.get("source_name") == "mitre-attack":
                        technique_id = ref.get("external_id", "")
                        break
                if technique_id:
                    result[technique_id] = {
                        "source": "mitre_attack",
                        "name": name,
                        "description": (obj.get("description", "") or "")[:500],
                        "tactics": [t.get("phase_name", "") for t in obj.get("kill_chain_phases", []) if t.get("kill_chain_name") == "mitre-attack"],
                    }
    except json.JSONDecodeError:
        pass
    return {"technique": result}


# ---------- Feed 配置表 ----------

FEEDS = [
    # Abuse.ch 系列
    {"name": "sslbl_ip", "url": "https://sslbl.abuse.ch/blacklist/sslipblacklist.txt",
     "format": TEXT_ONE_PER_LINE, "ioc_types": ["ip"], "interval": 3600, "parse": _parse_sslbl_ip},
    {"name": "sslbl_cert", "url": "https://sslbl.abuse.ch/blacklist/sslblacklist.csv",
     "format": CSV_FORMAT, "ioc_types": ["hash"], "interval": 3600, "parse": _parse_sslbl_cert},
    {"name": "urlhaus", "url": "https://urlhaus.abuse.ch/downloads/text/",
     "format": TEXT_ONE_PER_LINE, "ioc_types": ["url"], "interval": 300, "parse": _parse_urlhaus},
    {"name": "threatfox", "url": "https://threatfox.abuse.ch/export/csv/recent/",
     "format": CSV_FORMAT, "ioc_types": ["ip", "domain", "url"], "interval": 600, "parse": _parse_threatfox},

    # 钓鱼 / 黑名单
    {"name": "openphish", "url": "https://openphish.com/feed.txt",
     "format": TEXT_ONE_PER_LINE, "ioc_types": ["url"], "interval": 43200, "parse": _parse_openphish},
    {"name": "blocklist_de", "url": "https://lists.blocklist.de/lists/all.txt",
     "format": TEXT_ONE_PER_LINE, "ioc_types": ["ip"], "interval": 3600, "parse": _parse_blocklist},
    {"name": "vxvault", "url": "https://vxvault.net/URL_List.php",
     "format": TEXT_ONE_PER_LINE, "ioc_types": ["url"], "interval": 3600, "parse": _parse_vxvault},
    {"name": "spamhaus_drop", "url": "https://www.spamhaus.org/drop/drop.txt",
     "format": TEXT_ONE_PER_LINE, "ioc_types": ["cidr"], "interval": 86400, "parse": _parse_spamhaus_drop},

    # 漏洞 / 威胁框架
    {"name": "cisa_kev", "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
     "format": JSON_FORMAT, "ioc_types": ["cve"], "interval": 86400, "parse": _parse_cisa_kev},
    {"name": "mitre_attack", "url": "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json",
     "format": JSON_FORMAT, "ioc_types": ["technique"], "interval": 604800, "parse": _parse_mitre_attack, "lazy": True},
]


# ---------- DB 操作 ----------

DB_PATH = os.environ.get("FEED_DB_PATH") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "feed_cache.db"
)


async def _get_db() -> aiosqlite.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA synchronous=NORMAL")
    return conn


async def _init_db():
    conn = await _get_db()
    try:
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS feed_rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_name TEXT NOT NULL,
                started_at REAL NOT NULL,
                completed_at REAL,
                ioc_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running'
            );
            CREATE INDEX IF NOT EXISTS idx_feed_rounds_feed
                ON feed_rounds(feed_name, started_at DESC);
            
            CREATE TABLE IF NOT EXISTS feed_cache (
                round_id INTEGER NOT NULL,
                feed_name TEXT NOT NULL,
                ioc_type TEXT NOT NULL,
                ioc_value TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (round_id) REFERENCES feed_rounds(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_feed_cache_lookup
                ON feed_cache(ioc_type, ioc_value, round_id);
            CREATE INDEX IF NOT EXISTS idx_feed_cache_feed_round
                ON feed_cache(feed_name, round_id);
            
            PRAGMA foreign_keys=ON;
        """)
        await conn.commit()
    finally:
        await conn.close()


# ---------- FeedManager ----------

class FeedManager:
    """全局单例：管理 Feed 拉取、DB 持久化、内存缓存"""

    def __init__(self):
        self._cache: dict[str, dict[str, dict]] = {}  # feed_name → {ioc_type → {value: detail}}
        self._last_fetch: dict[str, float] = {}
        self._started = False
        self.max_rounds: int = MAX_ROUNDS  # 可通过 API 调整

    async def start(self):
        """启动：初始化 DB + 从 DB 恢复最近一轮 + 后台拉取过期 Feed"""
        if self._started:
            return
        self._started = True
        await _init_db()
        await self._restore_from_db()
        # 后台启动拉取，不阻塞服务启动
        asyncio.create_task(self.refresh_stale(force=True))

    async def _restore_from_db(self):
        """从 DB 恢复最近一轮到内存缓存"""
        conn = await _get_db()
        try:
            # 对每个 feed，取最新完成的 round
            for feed in FEEDS:
                name = feed["name"]
                cursor = await conn.execute(
                    """SELECT id, completed_at, ioc_count FROM feed_rounds
                       WHERE feed_name=? AND status='completed'
                       ORDER BY completed_at DESC LIMIT 1""",
                    (name,)
                )
                row = await cursor.fetchone()
                if not row:
                    continue
                round_id = row["id"]
                self._last_fetch[name] = row["completed_at"]

                # 加载该轮所有 IOC
                cur2 = await conn.execute(
                    """SELECT ioc_type, ioc_value, detail FROM feed_cache
                       WHERE feed_name=? AND round_id=?""",
                    (name, round_id)
                )
                feed_cache = {}
                for r in await cur2.fetchall():
                    ioc_type = r["ioc_type"]
                    ioc_value = r["ioc_value"]
                    detail = json.loads(r["detail"])
                    if ioc_type not in feed_cache:
                        feed_cache[ioc_type] = {}
                    feed_cache[ioc_type][ioc_value] = detail
                if feed_cache:
                    self._cache[name] = feed_cache
        finally:
            await conn.close()

    async def refresh_all(self):
        """强制拉取所有 Feed"""
        await self.refresh_stale(force=True)

    async def refresh_stale(self, force=False):
        """拉取过期的 Feed（force=True 时全部拉取）"""
        now = time.time()
        proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or None
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False, proxy=proxy) as client:
            for feed in FEEDS:
                name = feed["name"]
                if feed.get("lazy"):
                    continue
                last = self._last_fetch.get(name, 0)
                if force or now - last > feed["interval"]:
                    await self._fetch_and_persist(client, feed)

    async def _fetch_and_persist(self, client: httpx.AsyncClient, feed: dict):
        """拉取 → 解析 → 写 DB → 更新内存缓存"""
        name = feed["name"]
        try:
            resp = await client.get(feed["url"], timeout=min(30, feed.get("timeout", 30)))
            if resp.status_code != 200:
                print(f"[FeedManager] {name}: HTTP {resp.status_code}")
                return
            raw = resp.text
            parsed = feed["parse"](raw)  # dict[ioc_type → dict[value → detail]]

            # 统计 IOC 数
            ioc_count = sum(len(v) for v in parsed.values())
            now = time.time()

            # 写入 DB
            conn = await _get_db()
            try:
                # 创建新 round
                cursor = await conn.execute(
                    "INSERT INTO feed_rounds (feed_name, started_at, completed_at, ioc_count, status) VALUES (?, ?, ?, ?, 'completed')",
                    (name, now, now, ioc_count)
                )
                round_id = cursor.lastrowid

                # 批量写 IOC
                rows = []
                for ioc_type, values in parsed.items():
                    for ioc_value, detail in values.items():
                        rows.append((round_id, name, ioc_type, ioc_value, json.dumps(detail, ensure_ascii=False), now))
                if rows:
                    await conn.executemany(
                        """INSERT INTO feed_cache (round_id, feed_name, ioc_type, ioc_value, detail, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        rows
                    )
                await conn.commit()

                # 清理旧轮
                await self._cleanup_old_rounds(conn, name)
            finally:
                await conn.close()

            # 更新内存缓存
            self._cache[name] = parsed
            self._last_fetch[name] = now

        except Exception as e:
            print(f"[FeedManager] {name}: fetch error: {e}")

    async def _cleanup_old_rounds(self, conn: aiosqlite.Connection, feed_name: str):
        """保留最近 max_rounds 轮，删除更旧的"""
        cursor = await conn.execute(
            """SELECT id FROM feed_rounds
               WHERE feed_name=? ORDER BY completed_at DESC LIMIT 1 OFFSET ?""",
            (feed_name, self.max_rounds)
        )
        row = await cursor.fetchone()
        if row:
            keep_from = row["id"]
            await conn.execute(
                "DELETE FROM feed_rounds WHERE feed_name=? AND id < ?",
                (feed_name, keep_from)
            )
            # CASCADE 会自动删除 feed_cache 对应行
            await conn.commit()

    def query(self, ioc_type: str, ioc_value: str) -> list[dict]:
        """从内存缓存查询"""
        # CVE 统一转大写
        if ioc_type == "cve":
            ioc_value = ioc_value.upper()
        matches = []
        for name, cache in self._cache.items():
            type_data = cache.get(ioc_type, {})
            if ioc_value in type_data:
                matches.append({"feed": name, **type_data[ioc_value]})
        # CIDR 范围匹配
        if ioc_type == "ip":
            try:
                ip_obj = ipaddress.ip_address(ioc_value)
                for name, cache in self._cache.items():
                    cidr_data = cache.get("cidr", {})
                    for cidr, detail in cidr_data.items():
                        try:
                            if ip_obj in ipaddress.ip_network(cidr, strict=False):
                                matches.append({"feed": name, **detail})
                        except ValueError:
                            continue
            except ValueError:
                pass
        return matches

    def stats(self) -> dict:
        """返回各 Feed 缓存统计"""
        result = {}
        total_ios = 0
        for feed in FEEDS:
            name = feed["name"]
            cache = self._cache.get(name, {})
            total = sum(len(v) for v in cache.values())
            total_ios += total
            result[name] = {
                "total_ios": total,
                "last_fetch": self._last_fetch.get(name),
                "interval": feed["interval"],
                "ioc_types": feed["ioc_types"],
            }
        result["_meta"] = {
            "total_feeds": len(FEEDS),
            "total_ios": total_ios,
            "max_rounds": self.max_rounds,
            "db_path": DB_PATH,
            "db_size_bytes": self.db_size(),
        }
        return result

    def db_size(self) -> int:
        """返回 feed_cache.db 文件大小（字节）"""
        try:
            return os.path.getsize(DB_PATH)
        except (OSError, TypeError):
            return 0

    def set_max_rounds(self, rounds: int) -> int:
        """设置保留轮次（立即触发清理），返回实际设置值"""
        self.max_rounds = max(1, min(rounds, 10))  # 限制 1~10
        return self.max_rounds

    async def query_history(self, ioc_type: str, ioc_value: str, rounds: int = 3) -> list[dict]:
        """查询历史多轮记录（按 round 分组，用于前端展示变化趋势）"""
        conn = await _get_db()
        try:
            cursor = await conn.execute(
                """SELECT r.feed_name, r.completed_at, c.detail
                   FROM feed_cache c
                   JOIN feed_rounds r ON c.round_id = r.id
                   WHERE c.ioc_type=? AND c.ioc_value=?
                   ORDER BY r.completed_at DESC
                   LIMIT ?""",
                (ioc_type, ioc_value, rounds * 20)
            )
            rows = await cursor.fetchall()
            result = {}
            for r in rows:
                feed_name = r["feed_name"]
                ts = r["completed_at"]
                if feed_name not in result:
                    result[feed_name] = []
                result[feed_name].append({
                    "time": ts,
                    "detail": json.loads(r["detail"]),
                })
            return result
        finally:
            await conn.close()


# 全局单例
feed_manager = FeedManager()