from fastapi import Query
from app.models.schemas import IoCQueryResponse
from app.engines.ioc_engine import IoCEngine
from app.models import database as db
from . import api_router

engine = IoCEngine()

@api_router.get("/analyze/{ioc_type}/{ioc_value}", response_model=IoCQueryResponse)
async def analyze_ioc(ioc_type: str, ioc_value: str):
    ioc_type = ioc_type.lower()
    valid_types = ("ip", "domain", "url", "hash", "cve")
    if ioc_type not in valid_types:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unsupported type. Use: {', '.join(valid_types)}")
    result = await engine.analyze(ioc_type, ioc_value)
    # 操作日志：记录查询类型与值
    await db.log_operation("ioc_query", {"type": ioc_type, "value": ioc_value})
    return result
