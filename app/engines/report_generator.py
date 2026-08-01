import time
import datetime
from app.models.database import get_db

# 动作类型 → 中文标签（BI 图表 + 日志展示共用）
ACTION_LABELS = {
    "ioc_query": "IoC 查询",
    "alert_parse": "告警解析",
    "skill_run": "Skill 执行",
    "chat_ask": "AI 对话",
    "config_update": "配置变更",
    "session_create": "新建会话",
    "session_delete": "删除会话",
    "report_view": "日报查看",
}

# 主要图表动作（其余归为「其他」）
CORE_ACTIONS = ["ioc_query", "alert_parse", "skill_run", "chat_ask"]


class ReportGenerator:
    """BI 聚合引擎：基于 operation_logs / ioc_cache / chat 表生成统计看板数据。"""

    async def generate_daily_brief(self) -> dict:
        conn = await get_db()
        try:
            now = time.time()
            today_start = self._day_start(now)
            day_key = datetime.date.today().isoformat()

            # ---- 1. 近 14 天操作趋势（按天 × action 分组）----
            daily_ops = await self._daily_ops(conn, now)

            # ---- 2. 操作类型分布 ----
            action_dist = await self._action_dist(conn)

            # ---- 3. 风险级别分布 ----
            risk_dist = await self._risk_dist(conn)

            # ---- 4. IoC 查询类型分布 ----
            ioc_types = await self._ioc_type_dist(conn)

            # ---- 5. Top IoC（按 ioc_cache 条数聚合）----
            top_iocs = await self._top_iocs(conn)

            # ---- 6. 最近操作日志 ----
            recent_logs = await self._recent_logs(conn)

            # ---- 7. 总量指标 ----
            totals = await self._totals(conn, now, today_start)

            return {
                "date": day_key,
                "daily_ops": daily_ops,        # {days: [...], series: [{name, data}]}
                "action_dist": action_dist,    # [{name, value}]
                "risk_dist": risk_dist,        # [{name, value}]
                "ioc_types": ioc_types,        # [{name, value}]
                "top_iocs": top_iocs,          # [{name, value}]
                "recent_logs": recent_logs,    # [{id, action, action_label, detail, risk, time_str}]
                "totals": totals,              # {total_ops, today_ops, sessions, messages, cache_items, skills}
            }
        finally:
            await conn.close()

    # ---- 各聚合块 ----

    async def _daily_ops(self, conn, now: float) -> dict:
        """近 14 天每天的各核心动作计数（含「其他」列）。"""
        days, day_keys = [], []
        for i in range(13, -1, -1):
            d = datetime.date.today() - datetime.timedelta(days=i)
            days.append(d.strftime("%m-%d"))
            day_keys.append(d.isoformat())

        start_ts = self._day_start(now) - 13 * 86400
        cursor = await conn.execute(
            """SELECT action, created_at FROM operation_logs WHERE created_at >= ?""",
            (start_ts,)
        )
        rows = await cursor.fetchall()

        buckets = {k: {a: 0 for a in CORE_ACTIONS} | {"other": 0} for k in day_keys}
        for r in rows:
            idx = datetime.datetime.fromtimestamp(r["created_at"]).date().isoformat()
            if idx not in buckets:
                continue
            a = r["action"]
            if a in CORE_ACTIONS:
                buckets[idx][a] += 1
            else:
                buckets[idx]["other"] += 1

        series_names = CORE_ACTIONS + ["other"]
        return {
            "days": days,
            "series": [
                {"name": ACTION_LABELS.get(a, a), "data": [buckets[k][a] for k in day_keys]}
                for a in series_names
            ],
        }

    async def _action_dist(self, conn) -> list[dict]:
        cursor = await conn.execute(
            "SELECT action, COUNT(*) AS cnt FROM operation_logs GROUP BY action ORDER BY cnt DESC"
        )
        rows = await cursor.fetchall()
        return [{"name": ACTION_LABELS.get(r["action"], r["action"]), "value": r["cnt"]} for r in rows]

    async def _risk_dist(self, conn) -> list[dict]:
        """只统计带风险标签的动作（告警解析等）。"""
        cursor = await conn.execute(
            "SELECT risk, COUNT(*) AS cnt FROM operation_logs WHERE risk IS NOT NULL AND risk != '' GROUP BY risk ORDER BY cnt DESC"
        )
        rows = await cursor.fetchall()
        label_map = {"critical": "严重", "high": "高危", "medium": "中危", "low": "低危", "info": "信息"}
        return [{"name": label_map.get(r["risk"], r["risk"]), "value": r["cnt"]} for r in rows]

    async def _ioc_type_dist(self, conn) -> list[dict]:
        cursor = await conn.execute(
            "SELECT ioc_type, COUNT(*) AS cnt FROM ioc_cache GROUP BY ioc_type ORDER BY cnt DESC"
        )
        rows = await cursor.fetchall()
        type_label = {"ip": "IP 地址", "domain": "域名", "url": "URL", "hash": "文件 Hash", "cve": "CVE 漏洞"}
        return [{"name": type_label.get(r["ioc_type"], r["ioc_type"]), "value": r["cnt"]} for r in rows]

    async def _top_iocs(self, conn) -> list[dict]:
        cursor = await conn.execute(
            """SELECT ioc_type, ioc_value, COUNT(*) AS cnt FROM ioc_cache
               GROUP BY ioc_type, ioc_value ORDER BY cnt DESC LIMIT 8"""
        )
        rows = await cursor.fetchall()
        return [{"name": f"{r['ioc_type']}:{r['ioc_value']}", "value": r["cnt"]} for r in rows]

    async def _recent_logs(self, conn) -> list[dict]:
        from app.models import database as db
        logs = await db.get_recent_operations(20)
        for log in logs:
            log["action_label"] = ACTION_LABELS.get(log["action"], log["action"])
            log["time_str"] = datetime.datetime.fromtimestamp(log["created_at"]).strftime("%m-%d %H:%M:%S")
        return logs

    async def _totals(self, conn, now: float, today_start: float) -> dict:
        def one(sql):
            return conn.execute(sql)

        cur = await one("SELECT COUNT(*) AS c FROM operation_logs")
        total_ops = (await cur.fetchone())["c"]
        cur = await one(f"SELECT COUNT(*) AS c FROM operation_logs WHERE created_at >= {today_start}")
        today_ops = (await cur.fetchone())["c"]
        cur = await one("SELECT COUNT(*) AS c FROM chat_sessions")
        sessions = (await cur.fetchone())["c"]
        cur = await one("SELECT COUNT(*) AS c FROM chat_messages")
        messages = (await cur.fetchone())["c"]
        cur = await one("SELECT COUNT(*) AS c FROM ioc_cache")
        cache_items = (await cur.fetchone())["c"]

        from app.skills import installed_skills
        skills = len(installed_skills())
        return {
            "total_ops": total_ops,
            "today_ops": today_ops,
            "sessions": sessions,
            "messages": messages,
            "cache_items": cache_items,
            "skills": skills,
        }

    @staticmethod
    def _day_start(ts: float) -> float:
        """当日 0 点时间戳（本地时区）。"""
        dt = datetime.datetime.fromtimestamp(ts).replace(hour=0, minute=0, second=0, microsecond=0)
        return dt.timestamp()
