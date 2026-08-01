from fastapi import UploadFile, File, Form
from app.models.schemas import AlertParseRequest, AlertParseResponse
from app.engines.alert_engine import AlertEngine
from app.models import database as db
from . import api_router

alert_engine = AlertEngine()


@api_router.post("/alert/parse", response_model=AlertParseResponse)
async def parse_alert(req: AlertParseRequest):
    result = alert_engine.parse(req.raw_text, req.source)
    await db.log_operation(
        "alert_parse",
        {"attack_type": result.attack_type, "confidence": result.confidence},
        risk=result.risk_level if result.risk_level != "low" else None,
    )
    return result


@api_router.post("/alert/upload", response_model=AlertParseResponse)
async def upload_alert(file: UploadFile = File(...)):
    raw_bytes = await file.read()
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    line_count = raw_text.count("\n") + 1

    result = alert_engine.parse(raw_text, source="upload")
    result.file_info = {
        "filename": file.filename,
        "size": len(raw_bytes),
        "line_count": line_count,
    }
    result.line_count = line_count

    await db.log_operation(
        "alert_upload",
        {
            "filename": file.filename,
            "size": len(raw_bytes),
            "attack_type": result.attack_type,
        },
        risk=result.risk_level if result.risk_level != "low" else None,
    )
    return result
