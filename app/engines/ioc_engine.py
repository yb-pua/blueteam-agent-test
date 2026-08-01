from app.models.schemas import IoCQueryResponse, IoCSourceResult
from app.sources import get_configured_sources

class IoCEngine:
    def __init__(self):
        self.sources = get_configured_sources()

    async def analyze(self, ioc_type: str, ioc_value: str) -> IoCQueryResponse:
        ioc_value = ioc_value.strip().lower()
        source_results = []

        for source in self.sources:
            if not source.can_handle(ioc_type):
                source_results.append(IoCSourceResult(
                    source=source.name,
                    data={},
                    error=f"不支持查询 {ioc_type} 类型"
                ))
                continue
            if not source.is_configured and source.requires_key:
                source_results.append(IoCSourceResult(
                    source=source.name,
                    data={},
                    error="API Key 未配置"
                ))
                continue
            try:
                raw = await source.query(ioc_type, ioc_value)
                if raw and "error" not in raw:
                    source_results.append(IoCSourceResult(source=source.name, data=raw))
                else:
                    source_results.append(IoCSourceResult(
                        source=source.name,
                        data={},
                        error=raw.get("error", "查询失败")
                    ))
            except Exception as e:
                source_results.append(IoCSourceResult(
                    source=source.name, data={}, error=str(e)
                ))

        return IoCQueryResponse(
            ioc_type=ioc_type,
            ioc_value=ioc_value,
            score=0,
            risk_level="unknown",
            summary=f"已查询 {len(source_results)} 个情报源，详细结果见各源数据。",
            sources=source_results,
            recommendation="建议使用自然语言查询获取AI分析结果：POST /api/v1/ask",
        )
