"""LLM tool calling + agentic loop for profile helper."""
import json

from app.services.profile_helper.llm_client import create_client, get_default_model
from app.services.profile_helper.prompts import META_SYSTEM_PROMPT
from app.services.profile_helper.tools import DOC_NAMES, SKILL_NAMES, read_doc, read_skill

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_skill",
            "description": "读取指定 Skill 文件，获取具体任务的操作指南。执行任务前必须先调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "enum": SKILL_NAMES,
                        "description": "Skill 名称",
                    }
                },
                "required": ["skill_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_doc",
            "description": "读取参考文档（量表原题等）。施测时用此工具获取题目。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_name": {
                        "type": "string",
                        "enum": DOC_NAMES,
                        "description": "文档名称",
                    }
                },
                "required": ["doc_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_profile",
            "description": "获取当前会话中的画像内容。每次开始任务前先调用，了解当前填写进度和采集阶段。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_profile",
            "description": "将发展画像内容写入会话。采集到数据后必须调用此工具保存，不要只在对话中展示而不保存。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "完整的发展画像 Markdown 内容",
                    }
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_forum_profile",
            "description": "将论坛画像（数字分身）写入会话。当用户确认「生成论坛画像」并完成隐私设置后，用此工具保存论坛画像内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "完整的论坛画像 Markdown（Identity/Expertise/Thinking Style/Discussion Style 四节格式）",
                    }
                },
                "required": ["content"],
            },
        },
    },
]


def _execute_tool(name: str, args: dict, session: dict) -> str:
    """Execute a single tool, return result string."""
    if name == "read_skill":
        return read_skill(args.get("skill_name", ""))
    if name == "read_doc":
        return read_doc(args.get("doc_name", ""))
    if name == "read_profile":
        return session["profile"]
    if name == "write_profile":
        content = args.get("content", "")
        session["profile"] = content
        return f"已写入发展画像，共 {len(content)} 字符。"
    if name == "write_forum_profile":
        content = args.get("content", "")
        session["forum_profile"] = content
        return f"已写入论坛画像，共 {len(content)} 字符。"
    return f"未知工具: {name}"


def run_agent(
    user_message: str,
    session: dict,
    *,
    stream: bool = False,
    model: str | None = None,
):
    """
    Run agent loop. session is from sessions.get().
    If stream=True, yield each chunk; else yield full reply.
    model: optional override for this request; defaults to AI_GENERATION_MODEL.
    """
    client = create_client()
    if not client:
        yield "错误：未配置 AI 生成 API。请在 .env 中设置 AI_GENERATION_BASE_URL 和 AI_GENERATION_API_KEY。"
        return

    model = model or get_default_model()
    messages = session["messages"].copy()
    messages.append({"role": "user", "content": user_message})

    max_iterations = 20
    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": META_SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                result = _execute_tool(tc.function.name, args, session)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            continue

        content = (msg.content or "").strip()
        session["messages"] = messages + [{"role": "assistant", "content": content}]

        if stream:
            for i in range(0, len(content), 1):
                yield content[i : i + 1]
        else:
            yield content
        return

    err = "达到最大工具调用次数，请简化请求后重试。"
    session["messages"] = messages + [{"role": "assistant", "content": err}]
    if stream:
        for c in err:
            yield c
    else:
        yield err
