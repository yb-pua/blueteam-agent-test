import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.models.database import init_db
from app.engines.intel_collector import IntelCollector
from app.api import api_router

logger = logging.getLogger("uvicorn.error")
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    
    # 启动 FeedManager（预加载所有威胁情报 Feed）
    from app.feeds import feed_manager
    await feed_manager.start()
    
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    collector = IntelCollector()
    scheduler.add_job(collector.run_once, "interval", hours=6)
    # 每 30 分钟刷新过期的 Feed
    scheduler.add_job(feed_manager.refresh_stale, "interval", minutes=30)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="Blue Team Threat Intel Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


# ---- 全局异常处理器：统一错误响应格式 ----

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # 不向客户端泄露内部堆栈/敏感信息，仅记录到服务端日志
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "内部服务器错误，请查看服务端日志。"})


@app.get("/health")
async def health():
    from app.sources import get_configured_sources
    return {"status": "ok", "sources_configured": len(get_configured_sources())}

# Serve frontend static assets
if os.path.isdir(os.path.join(FRONTEND_DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

# SPA catch-all: serve index.html for any unmatched route (except /api/)
if os.path.isfile(os.path.join(FRONTEND_DIST, "index.html")):
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        index_path = os.path.join(FRONTEND_DIST, "index.html")
        return FileResponse(index_path)
