"""Discussion orchestration: run_discussion and run_discussion_for_topic."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from app.core.config import get_prompts_dir, get_skills_dir
from app.models.schemas import DEFAULT_ALLOWED_TOOLS
from app.core.model_pricing import calculate_cost_from_usage
from .config import get_agent_config
from .experts import EXPERT_SPECS, build_experts, build_experts_from_workspace, build_workspace_boundary
from .moderator_modes import get_moderator_prompt, prepare_moderator_skill
from .topic_sandbox import exclusive_topic_sandbox
from .workspace import (
    ensure_topic_workspace,
    init_discussion_history,
    read_discussion_history,
    read_discussion_summary,
)

logger = logging.getLogger(__name__)

_PROMPTS_DIR = get_prompts_dir()

# Default expert order when topic has none configured
EXPERT_ORDER = list(EXPERT_SPECS.keys())


def _load_system_prompt(ws_abs: str) -> str:
    """Load moderator system prompt from prompts/moderator_system.md."""
    template = (_PROMPTS_DIR / "moderator_system.md").read_text(encoding="utf-8")
    return template.replace("{ws_abs}", ws_abs)


def _expert_tools_from_moderator_tools(moderator_tools: list[str]) -> list[str]:
    """专家不使用 Task（仅主持人用于调用子 agent），其余工具与主持人一致"""
    return [t for t in moderator_tools if t != "Task"]


async def run_discussion(
    workspace_dir: Path,
    config: dict[str, str],
    topic: str,
    num_rounds: int = 5,
    expert_names: list[str] | None = None,
    max_turns: int = 60,
    max_budget_usd: float = 5.0,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """Run discussion and return num_turns, total_cost_usd."""
    logger.info(f"Starting run_discussion for topic, model={config.get('model')}, experts={expert_names}")

    skills_dir = get_skills_dir()

    env = {"ANTHROPIC_API_KEY": config["api_key"]}
    if config.get("base_url"):
        env["ANTHROPIC_BASE_URL"] = config["base_url"]
    model = config.get("model") or None
    if model:
        env["ANTHROPIC_MODEL"] = model

    ws_abs = str(workspace_dir.resolve())

    # Build AgentDefinitions from workspace role files (fallback to global skills)
    # Pass ws_abs so each expert's prompt includes the topic sandbox boundary.
    tools = allowed_tools if allowed_tools else DEFAULT_ALLOWED_TOOLS
    expert_tools = _expert_tools_from_moderator_tools(tools)

    if expert_names:
        experts = build_experts_from_workspace(
            workspace_dir, skills_dir, expert_names, model=model, ws_abs=ws_abs, tools=expert_tools
        )
    else:
        logger.warning("No expert_names specified, using all default experts")
        experts = build_experts(skills_dir, model=model, tools=expert_tools)

    logger.info(f"Built {len(experts)} experts: {list(experts.keys())}")

    # Allow claude_agent_sdk to spawn a subprocess even when the server itself
    # was started inside a Claude Code session (which sets CLAUDECODE=1).
    os.environ.pop("CLAUDECODE", None)

    # Append topic sandbox boundary to the moderator system prompt as well.
    system_prompt = _load_system_prompt(ws_abs) + build_workspace_boundary(ws_abs)

    # Write formatted skill to config/moderator_skill.md, then pass a short
    # "read your skill file" instruction as the user prompt.
    prepare_moderator_skill(workspace_dir, topic, expert_names or EXPERT_ORDER, num_rounds=num_rounds)
    prompt = get_moderator_prompt(workspace_dir)

    options = ClaudeAgentOptions(
        allowed_tools=tools,
        permission_mode="bypassPermissions",
        system_prompt=system_prompt,
        cwd=ws_abs,
        add_dirs=[ws_abs],
        agents=experts,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        env=env,
        model=model,
    )

    result_info: dict[str, Any] = {"num_turns": 0, "total_cost_usd": None}
    logger.info("Starting query...")
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                logger.info(f"Finished: turns={message.num_turns}, cost={message.total_cost_usd}, usage={message.usage}")
                result_info["num_turns"] = message.num_turns
                # Use custom per-model pricing if configured, otherwise fall back to SDK value
                custom_cost = calculate_cost_from_usage(model or "", message.usage) if model else None
                result_info["total_cost_usd"] = custom_cost if custom_cost is not None else message.total_cost_usd
    except Exception as e:
        logger.error(f"Error in query loop: {e}", exc_info=True)
        raise

    return result_info


async def run_discussion_for_topic(
    topic_id: str,
    topic_title: str,
    topic_body: str,
    workspace_base: Path | str | None = None,
    num_rounds: int = 5,
    expert_names: list[str] | None = None,
    max_turns: int = 60,
    max_budget_usd: float = 5.0,
    model: str | None = None,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """Run discussion for a topic; return discussion_history, summary, cost, etc."""
    from app.core.config import get_workspace_base

    base = Path(workspace_base) if workspace_base else get_workspace_base()
    ws_path = ensure_topic_workspace(base, topic_id)
    init_discussion_history(ws_path, topic_title, topic_body)

    config = get_agent_config()
    if model:
        config = {**config, "model": model}
    topic_text = f"{topic_title}\n\n{topic_body}"

    # Acquire exclusive topic sandbox lock for the duration of the discussion.
    # This prevents concurrent discussion runs and blocks new expert @mentions
    # from starting while the topic workspace is being written to.
    with exclusive_topic_sandbox(topic_id, ws_path, "discussion"):
        result_info = await run_discussion(
            workspace_dir=ws_path,
            config=config,
            topic=topic_text,
            num_rounds=num_rounds,
            expert_names=expert_names,
            max_turns=max_turns,
            max_budget_usd=max_budget_usd,
            allowed_tools=allowed_tools,
        )

    return {
        "discussion_history": read_discussion_history(ws_path),
        "discussion_summary": read_discussion_summary(ws_path),
        "turns_count": result_info.get("num_turns", 0),
        "cost_usd": result_info.get("total_cost_usd"),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
