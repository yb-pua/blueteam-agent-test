"""Tool definitions for LLM function calling.

- 每个 OSINT 源对应一个 function tool：query_<source_name>
- build_tools(sources=None) 支持按用户选择的来源过滤（None=全部已配置源）
- execute_tool 通过 get_source() 动态查找，保证运行时配置刷新后无需重启即可生效
"""

from app.sources import ALL_SOURCES

def get_available_sources() -> list:
    """返回可用的源（未配置 Key 的需 Key 源会被过滤）。"""
    return [s for s in ALL_SOURCES if s.is_configured or not s.requires_key]

def build_tools(sources: list | None = None) -> list[dict]:
    """Build OpenAI-compatible tool definitions from OSINT sources.

    sources: 用户勾选保留的来源（名称列表），None 表示全部可用源。
    """
    if sources is None:
        src_list = get_available_sources()
    else:
        src_set = set(sources)
        src_list = [s for s in get_available_sources() if s.name in src_set]

    tools = []
    for source in src_list:
        types_str = ", ".join(source.supported_types)
        tools.append({
            "type": "function",
            "function": {
                "name": f"query_{source.name}",
                "description": f"从{source.name}查询威胁情报。支持类型: {types_str}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ioc_type": {
                            "type": "string",
                            "enum": source.supported_types,
                            "description": f"IoC类型: {types_str}",
                        },
                        "ioc_value": {
                            "type": "string",
                            "description": "要查询的值（IP地址/域名/URL/文件Hash/CVE编号）",
                        },
                    },
                    "required": ["ioc_type", "ioc_value"],
                },
            },
        })
    return tools

def get_source(name: str):
    """按工具名动态查找源（运行时配置变更后无需重建 TOOL_MAP）。"""
    for source in ALL_SOURCES:
        if f"query_{source.name}" == name and (source.is_configured or not source.requires_key):
            return source
    return None

async def execute_tool(name: str, arguments: dict) -> dict:
    """Execute a tool call and return the result."""
    source = get_source(name)
    if not source:
        return {"error": f"未知工具: {name}"}
    try:
        result = await source.query(arguments["ioc_type"], arguments["ioc_value"])
        result["_source"] = source.name
        result["_ioc_type"] = arguments["ioc_type"]
        result["_ioc_value"] = arguments["ioc_value"]
        return result
    except Exception as e:
        return {"error": str(e), "_source": source.name}
