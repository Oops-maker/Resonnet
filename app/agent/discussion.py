"""Discussion orchestration: run_discussion and run_discussion_for_topic."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from app.core.config import get_prompts_dir
from app.models.schemas import DEFAULT_ALLOWED_TOOLS
from app.core.model_pricing import calculate_cost_from_usage
from .config import get_agent_config
from .experts import EXPERT_SPECS, build_experts, build_experts_from_workspace, build_workspace_boundary
from .moderator_modes import get_moderator_prompt, prepare_moderator_skill
from .topic_sandbox import exclusive_topic_sandbox
from .workspace import (
    copy_mcp_to_workspace,
    copy_skills_to_workspace,
    ensure_topic_workspace,
    init_discussion_history,
    read_discussion_history,
    read_discussion_summary,
    sanitize_discussion_turn_sources,
    sync_claude_skill_discovery_files,
    validate_discussion_outputs,
)
from app.core.topic_defaults import normalize_skill_ids
from app.core.mcp_config import load_mcp_config_from_path

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


def _load_mcp_servers_for_sdk(workspace_dir: Path) -> dict[str, dict]:
    """Load MCP config from workspace config/mcp.json and convert to SDK format.

    Returns dict suitable for ClaudeAgentOptions(mcp_servers=...).
    Supports both:
    - stdio: {"command": str, "args": list, "env": dict | None}
    - http: {"type": "http", "url": str, "headers": dict | None}
    """
    path = workspace_dir / "config" / "mcp.json"
    cfg = load_mcp_config_from_path(path)
    if not cfg.mcpServers:
        return {}
    result: dict[str, dict] = {}
    for sid, srv in cfg.mcpServers.items():
        if srv.is_http():
            # Emit Claude Code style HTTP MCP config
            url = srv.url
            if not url:
                logger.warning("MCP %s is marked as HTTP type but has no url; skipping", sid)
                continue
            entry: dict[str, Any] = {
                "type": "http",
                "url": url,
            }
            if srv.headers:
                entry["headers"] = srv.headers
            result[sid] = entry
            continue

        if srv.command:
            entry = {"command": srv.command, "args": srv.args or []}
            if srv.env:
                entry["env"] = srv.env
            result[sid] = entry
    return result


async def run_discussion(
    workspace_dir: Path,
    config: dict[str, str],
    topic: str,
    num_rounds: int = 5,
    expert_names: list[str] | None = None,
    max_turns: int = 50000,
    max_budget_usd: float = 500.0,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """Run discussion and return num_turns, total_cost_usd."""
    logger.info(f"Starting run_discussion for topic, model={config.get('model')}, experts={expert_names}")

    env = {"ANTHROPIC_API_KEY": config["api_key"]}
    if config.get("base_url"):
        env["ANTHROPIC_BASE_URL"] = config["base_url"]
    model = config.get("model") or None
    if model:
        env["ANTHROPIC_MODEL"] = model

    ws_abs = str(workspace_dir.resolve())

    # Build AgentDefinitions from workspace role files (fallback to global skills)
    # Pass ws_abs so each expert's prompt includes the topic sandbox boundary.
    tools = list(allowed_tools) if allowed_tools else list(DEFAULT_ALLOWED_TOOLS)
    mcp_servers = _load_mcp_servers_for_sdk(workspace_dir)
    if mcp_servers:
        for sid in mcp_servers:
            tools.append(f"mcp__{sid}__*")
        logger.info(f"MCP servers loaded for discussion: {list(mcp_servers.keys())}")
    expert_tools = _expert_tools_from_moderator_tools(tools)

    if expert_names:
        experts = build_experts_from_workspace(
            workspace_dir, expert_names, model=model, ws_abs=ws_abs, tools=expert_tools
        )
    else:
        logger.warning("No expert_names specified, using all default experts")
        experts = build_experts(model=model, tools=expert_tools)

    logger.info(f"Built {len(experts)} experts: {list(experts.keys())}")

    # Allow claude_agent_sdk to spawn a subprocess even when the server itself
    # was started inside a Claude Code session (which sets CLAUDECODE=1).
    os.environ.pop("CLAUDECODE", None)

    # Append topic sandbox boundary to the moderator system prompt as well.
    system_prompt = _load_system_prompt(ws_abs) + build_workspace_boundary(ws_abs)

    # Write formatted skill to config/moderator_skill.md, then pass a short
    # "read your skill file" instruction as the user prompt.
    prepare_moderator_skill(workspace_dir, topic, expert_names or EXPERT_ORDER, num_rounds=num_rounds)
    discovered_skills = sync_claude_skill_discovery_files(workspace_dir)
    if discovered_skills:
        logger.info(
            "Synced %d auto-discoverable skills to .claude/skills: %s",
            len(discovered_skills),
            discovered_skills,
        )
    prompt = get_moderator_prompt(workspace_dir)

    options_kw: dict[str, Any] = {
        "allowed_tools": tools,
        "permission_mode": "bypassPermissions",
        "system_prompt": system_prompt,
        "cwd": ws_abs,
        "add_dirs": [ws_abs],
        "agents": experts,
        "max_turns": max_turns,
        "max_budget_usd": max_budget_usd,
        "env": env,
        "model": model,
        # Load project/local settings so Claude Code can auto-discover
        # skills under workspace/.claude/skills.
        "setting_sources": ["project", "local"],
    }
    if mcp_servers:
        options_kw["mcp_servers"] = mcp_servers
    options = ClaudeAgentOptions(**options_kw)

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
    max_turns: int = 50000,
    max_budget_usd: float = 500.0,
    model: str | None = None,
    allowed_tools: list[str] | None = None,
    skill_list: list[str] | None = None,
    mcp_server_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Run discussion for a topic; return discussion_history, summary, cost, etc."""
    from app.core.config import get_workspace_base

    base = Path(workspace_base) if workspace_base else get_workspace_base()
    ws_path = ensure_topic_workspace(base, topic_id)
    init_discussion_history(ws_path, topic_title, topic_body)

    # Copy user-selected skills from global assignable_skills to config/skills/
    skills_to_copy = normalize_skill_ids(skill_list or [])
    if "image_generation" not in skills_to_copy:
        skills_to_copy.append("image_generation")
    if skills_to_copy:
        copied = copy_skills_to_workspace(ws_path, skills_to_copy)
        if copied:
            logger.info(f"Copied {len(copied)} skills to workspace: {copied}")

    # Copy user-selected MCP servers from global mcp.json to config/mcp.json
    if mcp_server_ids:
        copied_mcp = copy_mcp_to_workspace(ws_path, mcp_server_ids)
        if copied_mcp:
            logger.info(f"Copied {len(copied_mcp)} MCP servers to workspace: {copied_mcp}")

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
        filtered_sources = sanitize_discussion_turn_sources(ws_path)
        if filtered_sources:
            logger.warning(
                "Filtered %d non-verifiable source links for topic %s",
                filtered_sources,
                topic_id,
            )
        validate_discussion_outputs(
            ws_path,
            expert_names=expert_names or EXPERT_ORDER,
            num_rounds=num_rounds,
            require_image=True,
        )

    return {
        "discussion_history": read_discussion_history(ws_path),
        "discussion_summary": read_discussion_summary(ws_path),
        "turns_count": result_info.get("num_turns", 0),
        "cost_usd": result_info.get("total_cost_usd"),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
