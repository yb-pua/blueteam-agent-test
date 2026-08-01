"""Runtime configuration API - allows configuring API keys from the UI."""

import json
import os
from pathlib import Path
from pydantic import BaseModel
from fastapi import HTTPException
from app.sources import refresh_all
from app.models import database as db
from . import api_router

CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"

def load_runtime_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def save_runtime_config(data: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    # Update env so running sources pick up new keys
    for k, v in data.items():
        if v:
            os.environ[k] = v

CONFIG_SCHEMA = {
    "VT_API_KEY": {"label": "VirusTotal API Key", "type": "password", "source": "virustotal", "doc": "https://www.virustotal.com/gui/my-apikey"},
    "ABUSEIPDB_API_KEY": {"label": "AbuseIPDB API Key", "type": "password", "source": "abuseipdb", "doc": "https://www.abuseipdb.com/register"},
    "SHODAN_API_KEY": {"label": "Shodan API Key", "type": "password", "source": "shodan", "doc": "https://account.shodan.io/register"},
    "OTX_API_KEY": {"label": "AlienVault OTX API Key", "type": "password", "source": "otx", "doc": "https://otx.alienvault.com/"},
    "URLSCAN_API_KEY": {"label": "URLScan.io API Key (可选)", "type": "password", "source": "urlscan", "doc": "https://urlscan.io/user/apikey/"},
    "CENSYS_API_ID": {"label": "Censys API ID", "type": "text", "source": "censys", "doc": "https://search.censys.io/account/api"},
    "CENSYS_API_SECRET": {"label": "Censys API Secret", "type": "password", "source": "censys", "doc": "https://search.censys.io/account/api"},
    "THREATBOOK_API_KEY": {"label": "微步在线 ThreatBook API Key", "type": "password", "source": "threatbook", "doc": "https://x.threatbook.com/v5/myService"},
    "LLM_BASE_URL": {"label": "LLM API 地址", "type": "text", "source": "llm", "doc": "OpenAI兼容接口地址"},
    "LLM_API_KEY": {"label": "LLM API Key (sk-...) ", "type": "password", "source": "llm", "doc": ""},
    "LLM_MODEL": {"label": "LLM 模型名", "type": "text", "source": "llm", "doc": "如: gpt-4o-mini, deepseek-chat, qwen-turbo"},
}

class ConfigUpdate(BaseModel):
    key: str
    value: str

@api_router.get("/config")
async def get_config():
    runtime = load_runtime_config()
    result = []
    for key, schema in CONFIG_SCHEMA.items():
        env_val = os.getenv(key, "")
        runtime_val = runtime.get(key, "")
        is_set = bool(env_val or runtime_val)
        result.append({
            "key": key,
            "label": schema["label"],
            "type": schema["type"],
            "source": schema["source"],
            "doc": schema["doc"],
            "is_set": is_set,
            "value": "******" if is_set and schema["type"] == "password" else (env_val or runtime_val or ""),
        })
    return {"items": result}

@api_router.post("/config")
async def update_config(req: ConfigUpdate):
    if req.key not in CONFIG_SCHEMA:
        raise HTTPException(status_code=400, detail=f"未知配置项: {req.key}")
    runtime = load_runtime_config()
    if req.value:
        runtime[req.key] = req.value
    else:
        runtime.pop(req.key, None)
    save_runtime_config(runtime)
    from config import refresh_runtime_cache
    refresh_runtime_cache()
    changed = refresh_all()
    # 操作日志：记录配置变更（不记录 Key 明文）
    await db.log_operation("config_update", {"key": req.key, "set": bool(req.value)})
    return {"status": "ok", "key": req.key, "set": bool(req.value), "sources_refreshed": changed}
