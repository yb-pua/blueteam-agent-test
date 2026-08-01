import json
import time
import aiosqlite
from pathlib import Path
from typing import Optional
from config import DB_PATH, settings

def _serialize(value: dict) -> str:
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return json.dumps({"error": "unserializable data", "raw": str(value)[:500]})

async def get_db() -> aiosqlite.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA synchronous=NORMAL")
    return conn

async def init_db():
    conn = await get_db()
    try:
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS ioc_cache (
                ioc_type TEXT NOT NULL,
                ioc_value TEXT NOT NULL,
                source TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (ioc_type, ioc_value, source)
            );
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT NOT NULL,
                attack_type TEXT,
                risk_level TEXT,
                mitre_id TEXT,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS intel_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT,
                source TEXT NOT NULL,
                summary TEXT,
                severity TEXT,
                published_at TEXT,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session
                ON chat_messages(session_id, id);
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated
                ON chat_sessions(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_ioc_cache_lookup
                ON ioc_cache(ioc_type, ioc_value);
            CREATE INDEX IF NOT EXISTS idx_intel_articles_created
                ON intel_articles(created_at DESC);
            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                detail TEXT,
                risk TEXT,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_oplog_created
                ON operation_logs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_oplog_action
                ON operation_logs(action);
        """)
        await conn.commit()
    finally:
        await conn.close()

async def save_ioc_result(ioc_type: str, ioc_value: str, source: str, result: dict):
    conn = await get_db()
    try:
        await conn.execute(
            """INSERT OR REPLACE INTO ioc_cache (ioc_type, ioc_value, source, result, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (ioc_type, ioc_value, source, _serialize(result), time.time())
        )
        await conn.commit()
    finally:
        await conn.close()

async def get_ioc_result(ioc_type: str, ioc_value: str, source: str, max_age: float = 3600) -> Optional[dict]:
    conn = await get_db()
    try:
        now = time.time()
        cursor = await conn.execute(
            """SELECT result, created_at FROM ioc_cache
               WHERE ioc_type=? AND ioc_value=? AND source=?
               AND ? - created_at < ?""",
            (ioc_type, ioc_value, source, now, max_age)
        )
        row = await cursor.fetchone()
        if row:
            return json.loads(row["result"])
        return None
    finally:
        await conn.close()


# ---- AI 会话持久化 (chat sessions & messages) ----

async def create_chat_session(title: str = "新会话") -> int:
    """创建会话，返回新会话 id。"""
    conn = await get_db()
    try:
        now = time.time()
        cursor = await conn.execute(
            "INSERT INTO chat_sessions (title, created_at, updated_at) VALUES (?, ?, ?)",
            (title, now, now)
        )
        await conn.commit()
        return cursor.lastrowid
    finally:
        await conn.close()

async def list_chat_sessions(limit: int = 50) -> list[dict]:
    """按最近更新倒序列出会话概要（含消息数）。"""
    conn = await get_db()
    try:
        cursor = await conn.execute(
            """SELECT s.id, s.title, s.created_at, s.updated_at,
                      (SELECT COUNT(*) FROM chat_messages m WHERE m.session_id = s.id) AS msg_count
               FROM chat_sessions s
               ORDER BY s.updated_at DESC
               LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def get_chat_session(session_id: int) -> Optional[dict]:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE id = ?",
            (session_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()

async def get_chat_messages(session_id: int) -> list[dict]:
    """按时间正序取会话全部消息。"""
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT id, role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY id",
            (session_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()

async def append_chat_message(session_id: int, role: str, content: str) -> int:
    """追加一条消息并刷新会话 updated_at。"""
    conn = await get_db()
    try:
        now = time.time()
        cursor = await conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now)
        )
        await conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )
        await conn.commit()
        return cursor.lastrowid
    finally:
        await conn.close()

async def rename_chat_session(session_id: int, title: str):
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, time.time(), session_id)
        )
        await conn.commit()
    finally:
        await conn.close()

async def delete_chat_session(session_id: int):
    conn = await get_db()
    try:
        await conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        await conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        await conn.commit()
    finally:
        await conn.close()

async def touch_chat_session(session_id: int):
    """更新会话时间戳（用于回到旧会话继续对话）。"""
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (time.time(), session_id)
        )
        await conn.commit()
    finally:
        await conn.close()


# ---- 操作日志 (operation logs for BI dashboard) ----

async def log_operation(action: str, detail: dict | None = None, risk: str | None = None):
    """记录一条平台操作日志。

    action: 动作类型（ioc_query / alert_parse / skill_run / chat_ask /
            config_update / session_create / session_delete / report_view）
    detail: 附加摘要信息（写为 JSON 字符串）
    risk:   可选风险标签（critical/high/medium/low/info）
    """
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO operation_logs (action, detail, risk, created_at) VALUES (?, ?, ?, ?)",
            (action, _serialize(detail or {}), risk, time.time())
        )
        await conn.commit()
    finally:
        await conn.close()

async def get_recent_operations(limit: int = 20) -> list[dict]:
    """按时间倒序取最近操作日志（detail 解析回 dict）。"""
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT id, action, detail, risk, created_at FROM operation_logs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            item = dict(r)
            try:
                item["detail"] = json.loads(item["detail"]) if item["detail"] else {}
            except (json.JSONDecodeError, TypeError):
                item["detail"] = {"raw": str(item["detail"])[:300]}
            result.append(item)
        return result
    finally:
        await conn.close()
