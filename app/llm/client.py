"""OpenAI-compatible async LLM client."""

import json
import httpx
from typing import Any
from config import llm_settings

SYSTEM_PROMPT = """你是一名蓝队威胁情报分析师。你的任务是：

1. 用户会提出安全问题或提供IoC（IP/域名/URL/Hash/告警等）
2. 使用可用的情报查询工具获取数据
3. 综合分析各来源数据，给出专业研判
4. 输出格式：用中文给出分析结论，包含：
   - 风险评级（低/中/高/严重）
   - 证据摘要（各来源的关键发现）
   - 综合研判（攻击类型、置信度、关联信息）
   - 处置建议（具体可操作的步骤）

注意：
- 所有工具返回的是原始JSON，你需要解读这些数据
- 如果数据表明无害（如1.1.1.1是Cloudflare DNS），如实报告
- 如果工具返回错误（如不支持该类型），忽略该工具
- 保持客观，不要过度解读无害数据"""

async def chat_completion(messages: list[dict], tools: list[dict] | None = None,
                          thinking: str | None = None) -> dict:
    """Call OpenAI-compatible chat completion API.

    thinking: 思考强度 "low" / "medium" / "high"，映射为 OpenAI reasoning_effort；
              None 时不附加该参数（向后兼容）。
    """
    if not llm_settings.API_KEY:
        raise ValueError(
            "LLM API Key 未配置。请在页面「设置」中配置 LLM API Key，"
            "或通过环境变量 LLM_API_KEY 设置。"
        )
    headers = {
        "Authorization": f"Bearer {llm_settings.API_KEY}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": llm_settings.MODEL,
        "messages": messages,
        "temperature": llm_settings.TEMPERATURE,
        "max_tokens": llm_settings.MAX_TOKENS,
    }
    if thinking in ("low", "medium", "high"):
        body["reasoning_effort"] = thinking
    if tools:
        body["tools"] = tools

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{llm_settings.BASE_URL.rstrip('/')}/chat/completions",
            headers=headers,
            json=body,
        )
        if resp.status_code != 200:
            raise Exception(f"LLM API error: {resp.status_code} {resp.text[:500]}")
        return resp.json()

def build_messages(user_input: str, tool_results: list[dict] | None = None) -> list[dict]:
    """Build messages array for chat completion."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({"role": "user", "content": user_input})
    if tool_results:
        for tr in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": tr["tool_call_id"],
                "content": json.dumps(tr["content"], ensure_ascii=False, default=str),
            })
    return messages

def parse_tool_calls(response: dict) -> list[dict]:
    """Extract tool calls from LLM response."""
    choice = response.get("choices", [{}])[0]
    msg = choice.get("message", {})
    tool_calls = msg.get("tool_calls", [])
    if not tool_calls:
        return []
    result = []
    for tc in tool_calls:
        func = tc.get("function", {})
        try:
            args = json.loads(func.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}
        result.append({
            "id": tc["id"],
            "name": func.get("name", ""),
            "arguments": args,
        })
    return result

def get_content(response: dict) -> str:
    """Extract text content from LLM response."""
    choice = response.get("choices", [{}])[0]
    return choice.get("message", {}).get("content", "")
