"""LLM agent orchestration - manages the LLM + tool calling loop."""

from app.llm.client import chat_completion, build_messages, parse_tool_calls, get_content
from app.agent.tools import build_tools, execute_tool
from app.skills import build_skill_tools, execute_skill
from app.models import database as db

MAX_TOOL_ROUNDS = 5
MAX_HISTORY_MESSAGES = 20  # 保留最近 N 条历史消息作为上下文

def _build_tool_set(sources: list[str] | None) -> list[dict]:
    """构建工具集 = 用户所选 OSINT 工具 + 已安装 skill 工具。"""
    osint_tools = build_tools(sources) if (sources is None or sources) else []
    return osint_tools + build_skill_tools()

async def _dispatch_tool(name: str, arguments: dict) -> dict:
    """统一分派：优先 OSINT 源工具，其次 skill 工具。"""
    if name.startswith("skill_"):
        return await execute_skill(name[len("skill_"):], arguments)
    return await execute_tool(name, arguments)

async def ask(user_input: str, session_id: int | None = None,
              sources: list[str] | None = None,
              thinking: str | None = None) -> tuple[str, int]:
    """Process a natural language query through the LLM agent loop.

    返回 (回答文本, 会话id)：
    - session_id 为 None 时创建新会话并自动生成标题
    - sources 为用户勾选的情报来源名称列表（None=全部可用源）
    - thinking 为思考强度 "low"/"medium"/"high"（None=不指定）
    - 非空时加载该会话历史，实现多轮上下文
    - 用户消息与 AI 回答均持久化到数据库
    """
    # 1. 确定会话：新建或复用
    if session_id is None or not await db.get_chat_session(session_id):
        session_id = await db.create_chat_session("新会话")
    else:
        await db.touch_chat_session(session_id)

    # 2. 加载历史上下文（跳过 system 提示，只保留 user/assistant 轮次）
    history = await db.get_chat_messages(session_id)
    history_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history if m["role"] in ("user", "assistant")
    ][-MAX_HISTORY_MESSAGES:]

    # 3. 持久化本次用户消息
    await db.append_chat_message(session_id, "user", user_input)

    # 4. 拼接消息：system 提示 + 历史 + 本轮用户输入
    messages = build_messages(user_input)
    messages = [messages[0]] + history_messages + [messages[-1]]

    # 按用户选择构建工具集（OSINT 工具 + skill 工具）
    tools = _build_tool_set(sources)

    answer = ""
    for _ in range(MAX_TOOL_ROUNDS):
        response = await chat_completion(messages, tools=tools, thinking=thinking)
        tool_calls = parse_tool_calls(response)

        if not tool_calls:
            answer = get_content(response)
            break

        choice = response.get("choices", [{}])[0]
        msg = choice.get("message", {})
        messages.append(msg)

        for tc in tool_calls:
            result = await _dispatch_tool(tc["name"], tc["arguments"])
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result),
            })
    else:
        final = await chat_completion(messages, thinking=thinking)
        answer = get_content(final)

    # 5. 持久化 AI 回答，并自动生成会话标题
    await db.append_chat_message(session_id, "assistant", answer)
    session = await db.get_chat_session(session_id)
    if session and session["title"] == "新会话":
        title = user_input.strip().replace("\n", " ")[:30] or "新会话"
        await db.rename_chat_session(session_id, title)

    return answer, session_id
