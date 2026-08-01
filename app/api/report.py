from app.engines.report_generator import ReportGenerator
from app.models import database as db
from . import api_router

report_gen = ReportGenerator()

@api_router.get("/report/daily")
async def daily_report():
    result = await report_gen.generate_daily_brief()
    # 操作日志
    await db.log_operation("report_view", {"date": result.get("date", "")})
    return result
