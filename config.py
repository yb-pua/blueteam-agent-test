import os
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH: Path = BASE_DIR / "data" / "threat_intel.db"
CONFIG_FILE: Path = BASE_DIR / "data" / "config.json"

# 内存缓存: 避免每次属性访问都重新读取并解析 config.json
_runtime_cache: dict | None = None
_runtime_mtime: float | None = None


def _load_runtime(force: bool = False) -> dict:
    """读取运行时配置（带 mtime 缓存失效）。

    force=True 用于配置写入后强制刷新缓存。
    """
    global _runtime_cache, _runtime_mtime
    try:
        mtime = CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else None
    except OSError:
        mtime = None

    if not force and _runtime_cache is not None and mtime == _runtime_mtime:
        return _runtime_cache

    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
        else:
            data = {}
    except (json.JSONDecodeError, OSError):
        data = {}

    _runtime_cache = data
    _runtime_mtime = mtime
    return data


def refresh_runtime_cache():
    """配置写入后调用，强制下次读取刷新。"""
    _load_runtime(force=True)


def _get_env(key: str, default: str = "") -> str:
    val = os.getenv(key, "")
    if val:
        return val
    runtime = _load_runtime()
    return runtime.get(key, default)


class Settings:
    @property
    def VIRUSTOTAL_API_KEY(self): return _get_env("VT_API_KEY")
    @property
    def ABUSEIPDB_API_KEY(self): return _get_env("ABUSEIPDB_API_KEY")
    @property
    def SHODAN_API_KEY(self): return _get_env("SHODAN_API_KEY")
    @property
    def OTX_API_KEY(self): return _get_env("OTX_API_KEY")
    @property
    def URLSCAN_API_KEY(self): return _get_env("URLSCAN_API_KEY")
    @property
    def CENSYS_API_ID(self): return _get_env("CENSYS_API_ID")
    @property
    def CENSYS_API_SECRET(self): return _get_env("CENSYS_API_SECRET")
    @property
    def THREATBOOK_API_KEY(self): return _get_env("THREATBOOK_API_KEY")
    CACHE_TTL: int = 3600
    RATE_LIMIT: int = 10
    HOST: str = "0.0.0.0"
    PORT: int = 8020
    DEBUG: bool = False

settings = Settings()

class LLMSettings:
    @property
    def BASE_URL(self): return _get_env("LLM_BASE_URL", "https://api.openai.com/v1")
    @property
    def API_KEY(self): return _get_env("LLM_API_KEY")
    @property
    def MODEL(self): return _get_env("LLM_MODEL", "gpt-4o-mini")
    TEMPERATURE: float = 0.3
    MAX_TOKENS: int = 4096

llm_settings = LLMSettings()
