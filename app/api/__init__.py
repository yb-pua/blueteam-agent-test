from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

from . import ioc, alert, report, kb, ask, config, chat, sources, skills, feeds

api_router.include_router(feeds.feed_router)
api_router.include_router(sources.router)
