"""Skill 扩展引擎。

Skill 是预定义的函数工具：每个 skill 由 manifest (SKILL.md + skill.json) 描述，
安装后注册为一个 function tool `skill_<name>`，LLM 可按需调用，为 Agent 增加
可扩展能力（如报告生成、情报聚合、格式化输出等）。

存储位置: app/skills/store/<skill_name>/
- skill.json  : 工具元数据（name/description/parameters）
- handler.py  : 异步执行函数 run(params) -> dict
- SKILL.md    : 文档说明（可选）
"""

import importlib.util
import json
import shutil
import tempfile
import zipfile
import re
import yaml
from pathlib import Path
from typing import Any

STORE_DIR = Path(__file__).parent / "store"
MANIFEST_FILE = STORE_DIR / "skills.json"

# ---- 已安装 skill 注册表 ----

def _ensure_store():
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    if not MANIFEST_FILE.exists():
        MANIFEST_FILE.write_text(json.dumps({"skills": []}, indent=2, ensure_ascii=False))


def _read_manifest() -> dict:
    _ensure_store()
    try:
        return json.loads(MANIFEST_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"skills": []}


def _write_manifest(data: dict):
    _ensure_store()
    MANIFEST_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def installed_skills() -> list[dict]:
    """返回已安装 skill 元数据列表。"""
    return _read_manifest().get("skills", [])


def get_skill(name: str) -> dict | None:
    for s in installed_skills():
        if s["name"] == name:
            return s
    return None


# ---- 管理：启用/禁用 / 详情 / 编辑 ----

def toggle_skill(name: str, enabled: bool) -> dict | None:
    """切换 skill 启用/禁用状态。"""
    manifest = _read_manifest()
    for s in manifest["skills"]:
        if s["name"] == name:
            s["enabled"] = enabled
            _write_manifest(manifest)
            return s
    return None


def get_skill_detail(name: str) -> dict | None:
    """获取 skill 完整详情：manifest + skill.json + SKILL.md + handler.py 源码。"""
    skill = get_skill(name)
    if not skill:
        return None

    skill_dir = STORE_DIR / name
    result = dict(skill)

    # 读 skill.json（parameters 等）
    skill_json_path = skill_dir / "skill.json"
    if skill_json_path.exists():
        try:
            result["skill_json"] = json.loads(skill_json_path.read_text())
        except (json.JSONDecodeError, OSError):
            result["skill_json"] = {}

    # 读 SKILL.md
    skill_md_path = skill_dir / "SKILL.md"
    if skill_md_path.exists():
        result["skill_md"] = skill_md_path.read_text(errors="replace")
    else:
        result["skill_md"] = None

    # 读 handler.py 源码
    handler_path = skill_dir / "handler.py"
    if handler_path.exists():
        result["handler_code"] = handler_path.read_text(errors="replace")
    else:
        result["handler_code"] = None

    # 列出额外文件
    extras = []
    if skill_dir.exists():
        for p in skill_dir.iterdir():
            if p.name in ("skill.json", "handler.py", "SKILL.md", "__pycache__"):
                continue
            if p.is_file():
                extras.append(p.name)
            elif p.is_dir() and p.name != "__pycache__":
                extras.append(f"{p.name}/")
    result["extra_files"] = extras

    return result


def update_skill(name: str, changes: dict) -> dict | None:
    """编辑 skill 的 description / parameters / code。失败则回滚。"""
    skill = get_skill(name)
    if not skill:
        return None

    skill_dir = STORE_DIR / name

    # 备份当前状态
    backup = {}
    for fname in ("skill.json", "handler.py", "SKILL.md"):
        fp = skill_dir / fname
        if fp.exists():
            backup[fname] = fp.read_bytes()

    try:
        # 更新 description（manifest + skill.json）
        if "description" in changes:
            new_desc = changes["description"]
            manifest = _read_manifest()
            for s in manifest["skills"]:
                if s["name"] == name:
                    s["description"] = new_desc
                    break
            _write_manifest(manifest)
            # 同步 skill.json
            sj_path = skill_dir / "skill.json"
            if sj_path.exists():
                sj = json.loads(sj_path.read_text())
                sj["description"] = new_desc
                sj_path.write_text(json.dumps(sj, indent=2, ensure_ascii=False))

        # 更新 parameters（skill.json）
        if "parameters" in changes:
            sj_path = skill_dir / "skill.json"
            if sj_path.exists():
                sj = json.loads(sj_path.read_text())
            else:
                sj = {"name": name, "description": skill.get("description", ""), "parameters": {}}
            sj["parameters"] = changes["parameters"]
            sj_path.write_text(json.dumps(sj, indent=2, ensure_ascii=False))

        # 更新 handler.py 代码
        if "code" in changes:
            (skill_dir / "handler.py").write_text(changes["code"])

        # 更新 SKILL.md
        if "skill_md" in changes:
            (skill_dir / "SKILL.md").write_text(changes["skill_md"])

        # 预编译检查 handler
        _load_handler(name)

        return get_skill(name)

    except Exception as e:
        # 回滚
        for fname, content in backup.items():
            (skill_dir / fname).write_bytes(content)
        # 回滚 manifest
        manifest = _read_manifest()
        for s in manifest["skills"]:
            if s["name"] == name:
                s["description"] = skill.get("description", "")
                break
        _write_manifest(manifest)
        raise ValueError(f"编辑失败，已回滚: {e}")


# ---- 安装 / 卸载 ----

def install_skill(skill_id: str, source: dict) -> dict:
    """安装一个 skill。

    source 结构（来自客户端或内置市场）:
    {
      "name": "report_summarizer",        # 工具名（skill_ 前缀）
      "description": "...",
      "parameters": {...},                 # OpenAI 函数参数 schema
      "code": "async def run(params): ..." # 处理器源码
    }
    """
    name = source.get("name", "").strip()
    if not name:
        raise ValueError("skill name 不能为空")
    if get_skill(name):
        raise ValueError(f"skill 已存在: {name}")

    skill_dir = STORE_DIR / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    # 保存工具定义
    (skill_dir / "skill.json").write_text(
        json.dumps({
            "name": name,
            "description": source.get("description", ""),
            "parameters": source.get("parameters", {}),
        }, indent=2, ensure_ascii=False)
    )
    # 保存处理器源码
    (skill_dir / "handler.py").write_text(source.get("code", "async def run(params):\n    return {'result': 'ok'}\n"))

    # 注册到 manifest
    manifest = _read_manifest()
    manifest["skills"].append({
        "name": name,
        "description": source.get("description", ""),
        "enabled": True,
        "installed_at": __import__("time").time(),
    })
    _write_manifest(manifest)

    # 预编译检查
    try:
        _load_handler(name)
    except Exception as e:
        uninstall_skill(name)
        raise ValueError(f"skill 处理器加载失败，已回滚: {e}")

    return get_skill(name)


def _parse_skill_md_yaml(text: str) -> dict:
    """从 SKILL.md 中提取 YAML frontmatter，返回解析后的字典。"""
    # 标准 YAML frontmatter: ---\n...\n---
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        raise ValueError("SKILL.md 缺少 YAML frontmatter（--- 包裹的元数据块）")
    frontmatter = yaml.safe_load(m.group(1))
    if not isinstance(frontmatter, dict):
        raise ValueError("YAML frontmatter 解析结果不是字典")
    return frontmatter


def install_skill_from_zip(zip_bytes: bytes) -> dict:
    """从 ZIP 文件字节流安装 skill。

    ZIP 内必须包含:
      - SKILL.md    : 标准 skill 定义（含 YAML frontmatter，name/description 必填）
      - handler.py  : 异步执行函数 async def run(params) -> dict

    可包含额外文件（如 references/、scripts/ 等），安装时保留在 skill 目录。

    返回安装后的 skill 元数据。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "upload.zip"
        zip_path.write_bytes(zip_bytes)

        # 校验 ZIP 并提取
        skill_name = None
        skill_desc = ""
        handler_code = None
        extra_files = {}
        md_text = ""

        with zipfile.ZipFile(zip_path, 'r') as zf:
            # 安全检查：拒绝路径穿越
            for name in zf.namelist():
                if '..' in name or name.startswith('/') or name.startswith('\\'):
                    raise ValueError(f"ZIP 包含非法路径: {name}")

            # 查找 SKILL.md
            skill_md_names = [n for n in zf.namelist() if n.endswith('SKILL.md')]
            if not skill_md_names:
                raise ValueError("ZIP 中未找到 SKILL.md 文件")
            root_md = [n for n in skill_md_names if '/' not in n and '\\' not in n]
            md_name = root_md[0] if root_md else skill_md_names[0]

            md_text = zf.read(md_name).decode('utf-8', errors='replace')
            parsed = _parse_skill_md_yaml(md_text)
            skill_name = parsed.get("name", "").strip()
            if not skill_name:
                raise ValueError("SKILL.md 中未定义 name")
            skill_desc = str(parsed.get("description", "")).strip()

            # 查找 handler.py
            handler_names = [n for n in zf.namelist() if n.endswith('handler.py')]
            if not handler_names:
                raise ValueError("ZIP 中未找到 handler.py 文件")
            root_handler = [n for n in handler_names if '/' not in n and '\\' not in n]
            handler_name = root_handler[0] if root_handler else handler_names[0]
            handler_code = zf.read(handler_name).decode('utf-8', errors='replace')

            # 收集其他文件
            for name in zf.namelist():
                if name == md_name or name == handler_name:
                    continue
                if zf.getinfo(name).is_dir():
                    continue
                extra_files[name] = zf.read(name)

        if not handler_code:
            raise ValueError("handler.py 内容为空")

        # 安装 skill
        result = install_skill(skill_name, {
            "name": skill_name,
            "description": skill_desc,
            "parameters": parsed.get("parameters", {}),
            "code": handler_code,
        })

        # 保存额外文件（references/、scripts/ 等）
        skill_dir = STORE_DIR / skill_name
        for fname, content in extra_files.items():
            target = skill_dir / fname
            # 防止路径穿越
            try:
                target.relative_to(skill_dir)
            except ValueError:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        # 保存原始 SKILL.md
        (skill_dir / "SKILL.md").write_text(md_text)

        return result


def uninstall_skill(name: str) -> bool:
    """卸载 skill：从 manifest 移除并删除目录。"""
    manifest = _read_manifest()
    before = len(manifest["skills"])
    manifest["skills"] = [s for s in manifest["skills"] if s["name"] != name]
    if len(manifest["skills"]) == before:
        return False
    _write_manifest(manifest)
    shutil.rmtree(STORE_DIR / name, ignore_errors=True)
    return True


# ---- 工具定义 & 执行 ----

def build_skill_tools() -> list[dict]:
    """将已安装且启用的 skill 转为 OpenAI function tool 定义。"""
    tools = []
    for skill in installed_skills():
        if not skill.get("enabled", True):
            continue
        tools.append({
            "type": "function",
            "function": {
                "name": f"skill_{skill['name']}",
                "description": skill.get("description", ""),
                "parameters": skill.get("parameters", {"type": "object", "properties": {}}),
            },
        })
    return tools


def _load_handler(name: str):
    """动态加载 skill 的 handler 模块。"""
    skill_dir = STORE_DIR / name
    handler_file = skill_dir / "handler.py"
    if not handler_file.exists():
        raise FileNotFoundError(f"handler 缺失: {name}")
    spec = importlib.util.spec_from_file_location(f"app_skill_{name}", handler_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise AttributeError(f"handler 缺少 run 函数: {name}")
    return module


async def execute_skill(name: str, arguments: dict) -> dict:
    """执行已安装 skill。name 为去掉 skill_ 前缀后的技能名。"""
    if not get_skill(name):
        return {"error": f"未知 skill: {name}"}
    try:
        module = _load_handler(name)
        result = await module.run(arguments or {})
        if not isinstance(result, dict):
            result = {"result": result}
        result["_skill"] = name
        return result
    except Exception as e:
        return {"error": str(e), "_skill": name}
