"""Skill 管理 API - 查看 / 安装 / 卸载 / ZIP上传安装 / 启用禁用 / 详情 / 编辑 / 统计 / 斜杠执行。"""

import json
from fastapi import HTTPException, Request, UploadFile, File
from pydantic import BaseModel
from app.skills import installed_skills, install_skill, uninstall_skill, get_skill, execute_skill, install_skill_from_zip, toggle_skill, get_skill_detail, update_skill
from app.models import database as db
from . import api_router

MAX_ZIP_SIZE = 10 * 1024 * 1024  # 10MB

class SkillSource(BaseModel):
    name: str
    description: str = ""
    parameters: dict = {}
    code: str = "async def run(params):\n    return {'result': 'ok'}\n"


@api_router.get("/skills")
async def list_skills():
    """列出已安装 skill。"""
    return {"items": installed_skills()}

@api_router.post("/skills/install")
async def install(req: SkillSource):
    """安装 skill：提交 name/description/parameters/code。"""
    try:
        skill = install_skill(req.name, {
            "name": req.name,
            "description": req.description,
            "parameters": req.parameters,
            "code": req.code,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "skill": skill}

@api_router.post("/skills/install-zip")
async def install_from_zip(file: UploadFile = File(...)):
    """通过 ZIP 文件安装 skill。ZIP 内须包含 SKILL.md + handler.py。"""
    if not file.filename or not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的文件")

    content = await file.read()
    if len(content) > MAX_ZIP_SIZE:
        raise HTTPException(status_code=400, detail=f"ZIP 文件超过 10MB 限制（当前 {len(content) // 1024}KB）")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")

    try:
        skill = install_skill_from_zip(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"安装失败: {e}")

    await db.log_operation("skill_install_zip", {"name": skill.get("name", "")})
    return {"status": "ok", "skill": skill}

@api_router.delete("/skills/{name}")
async def remove(name: str):
    """卸载 skill。"""
    if not uninstall_skill(name):
        raise HTTPException(status_code=404, detail=f"skill 不存在: {name}")
    return {"status": "ok"}

# ---- 管理端点 ----

class SkillToggle(BaseModel):
    enabled: bool

class SkillUpdate(BaseModel):
    description: str | None = None
    parameters: dict | None = None
    code: str | None = None
    skill_md: str | None = None

@api_router.put("/skills/{name}/toggle")
async def toggle(name: str, req: SkillToggle):
    """启用/禁用 skill。禁用后不注入 LLM 工具列表但保留安装。"""
    skill = toggle_skill(name, req.enabled)
    if not skill:
        raise HTTPException(status_code=404, detail=f"skill 不存在: {name}")
    await db.log_operation("skill_toggle", {"name": name, "enabled": req.enabled})
    return {"status": "ok", "skill": skill}

@api_router.get("/skills/{name}/detail")
async def detail(name: str):
    """获取 skill 完整详情：SKILL.md、handler.py 源码、skill.json 等。"""
    info = get_skill_detail(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"skill 不存在: {name}")
    return info

@api_router.put("/skills/{name}")
async def edit_skill(name: str, req: SkillUpdate):
    """编辑 skill 的 description / parameters / code / SKILL.md。"""
    changes = {}
    if req.description is not None:
        changes["description"] = req.description
    if req.parameters is not None:
        changes["parameters"] = req.parameters
    if req.code is not None:
        changes["code"] = req.code
    if req.skill_md is not None:
        changes["skill_md"] = req.skill_md
    if not changes:
        raise HTTPException(status_code=400, detail="未提供任何修改字段")

    try:
        skill = update_skill(name, changes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not skill:
        raise HTTPException(status_code=404, detail=f"skill 不存在: {name}")
    await db.log_operation("skill_update", {"name": name, "fields": list(changes.keys())})
    return {"status": "ok", "skill": skill}

@api_router.get("/skills/stats")
async def skill_stats():
    """返回所有 skill 的执行统计（按 skill 分组）。"""
    import aiosqlite
    from config import DB_PATH as db_path
    stats = {}
    try:
        conn = await aiosqlite.connect(str(db_path))
        try:
            cursor = await conn.execute(
                "SELECT detail, created_at FROM operation_logs WHERE action='skill_run' ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
            for row in rows:
                try:
                    detail = json.loads(row[0]) if row[0] else {}
                except (json.JSONDecodeError, TypeError):
                    continue
                sname = detail.get("name", "")
                if not sname:
                    continue
                if sname not in stats:
                    stats[sname] = {"total": 0, "success": 0, "fail": 0, "last_run": row[1]}
                stats[sname]["total"] += 1
                if detail.get("ok"):
                    stats[sname]["success"] += 1
                else:
                    stats[sname]["fail"] += 1
        finally:
            await conn.close()
    except Exception:
        pass
    return {"stats": stats}

@api_router.post("/skills/slash")
async def slash_skill(request: Request):
    """Slash 命令直接执行 skill（不经 LLM）。

    请求体为 JSON（Content-Type 可为 text/plain，避免 params 被框架预解析）:
      {"name": "report_summarizer", "params": "{\"ioc\":\"1.1.1.1\"}"}
    params 支持 dict / JSON 字符串 / 缺省三种形态。
    """
    raw = (await request.body()).decode("utf-8", errors="replace").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="请求体为空")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON")

    name = str(data.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="缺少 skill 名称")
    skill = get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"skill 不存在: {name}")

    params = _parse_params(data.get("params"))
    result = await execute_skill(name, params)

    if "error" in result:
        # 操作日志：skill 执行失败
        await db.log_operation("skill_run", {"name": name, "ok": False, "error": str(result["error"])[:120]})
        return {"name": name, "description": skill.get("description", ""),
                "ok": False, "error": str(result["error"]), "output": None}
    # 执行结果剔除内部字段；优先取 result 键，否则返回整个 dict
    output = {k: v for k, v in result.items() if k != "_skill"}
    if "result" in output:
        output = output["result"]
    # 操作日志：skill 执行成功
    await db.log_operation("skill_run", {"name": name, "ok": True})
    return {"name": name, "description": skill.get("description", ""),
            "ok": True, "error": None, "output": output}


def _parse_params(raw) -> dict:
    """params 支持 dict / JSON 字符串 / 缺省。"""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"value": raw}
    return {}
