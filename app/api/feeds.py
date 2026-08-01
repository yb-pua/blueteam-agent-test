"""Feed 情报源统计与管理 API"""

from fastapi import APIRouter, Query
from app.feeds import feed_manager

feed_router = APIRouter()


@feed_router.get("/feeds/stats")
async def feed_stats():
    """返回各 Feed 的缓存统计（IoC 数量、最后更新时间、DB 大小）"""
    return feed_manager.stats()


@feed_router.post("/feeds/refresh")
async def feed_refresh():
    """手动刷新所有 Feed"""
    await feed_manager.refresh_all()
    return {"status": "ok", "message": "所有 Feed 已刷新"}


@feed_router.get("/feeds/settings")
async def feed_settings():
    """获取当前 Feed 设置（max_rounds）"""
    return {"max_rounds": feed_manager.max_rounds, "db_size_bytes": feed_manager.db_size()}


@feed_router.post("/feeds/settings")
async def update_feed_settings(max_rounds: int = Query(..., ge=1, le=10, description="保留轮次（1-10）")):
    """更新 Feed 设置"""
    new_value = feed_manager.set_max_rounds(max_rounds)
    return {"status": "ok", "max_rounds": new_value, "message": f"已设置保留 {new_value} 轮数据"}