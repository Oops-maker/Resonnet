#!/usr/bin/env python3
"""Standalone script executed inside the OS sandbox.

This script is the entry point that runs INSIDE sandbox-exec (macOS) or
bwrap (Linux). It:

1. Reads task configuration from input JSON file (via IPC)
2. Sets environment variables from config BEFORE any app.* imports
3. Dispatches to the appropriate agent task function
4. Writes result JSON to output file (via IPC)
5. Exits

The OS sandbox restricts this process (and all its children, including
the claude CLI spawned by claude_agent_sdk.query()) to the topic workspace.

## IMPORTANT: Environment setup order

``app.core.config`` calls ``get_anthropic_api_key()`` and other functions at
MODULE LEVEL. These raise ValueError if the env vars are not set. Therefore,
``_setup_env()`` MUST be called before any ``from app.*`` import statements.

This is enforced by the structure of ``main()``:
    task = read input JSON
    _setup_env(task)        ← sets os.environ BEFORE any app imports
    from app.agent.expert_reply import run_expert_reply   ← AFTER setup
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: add backend to sys.path BEFORE any app imports
# ---------------------------------------------------------------------------
# This file lives at: backend/app/agent/sandbox_runner.py
# So parent.parent.parent = backend/
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SANDBOX] %(name)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Environment setup (MUST run before any app.* imports)
# ---------------------------------------------------------------------------

def _setup_env(task: dict) -> None:
    """Set os.environ from task config before importing app modules.

    ``app.core.config`` evaluates module-level code that reads env vars
    (and raises ValueError if they are missing). By setting env vars here,
    before any app imports, we ensure the module loads successfully.

    Sensitive vars (api_key, base_url, model) come from the task config
    (passed via the IPC input.json) rather than the sandbox's .env file.

    Args:
        task: Task configuration dict loaded from input.json.
    """
    # Core Anthropic/Claude credentials (from task config, not .env)
    if task.get("api_key"):
        os.environ["ANTHROPIC_API_KEY"] = task["api_key"]
    os.environ.setdefault("ANTHROPIC_BASE_URL", task.get("base_url") or "")
    os.environ.setdefault("ANTHROPIC_MODEL", task.get("model") or "")

    # Derive workspace base from ws_path for app.core.config.get_workspace_base()
    ws_path = Path(task["ws_path"])
    workspace_base = ws_path.parent.parent  # .../workspace/topics/ID → .../workspace/
    os.environ.setdefault("WORKSPACE_BASE", str(workspace_base))

    # AI Generation vars: used by app.core.config module-level code but NOT
    # needed for agent sandbox tasks. Set placeholders to avoid ValueError.
    os.environ.setdefault("AI_GENERATION_BASE_URL", "placeholder_not_used_in_sandbox")
    os.environ.setdefault("AI_GENERATION_API_KEY", "placeholder_not_used_in_sandbox")
    os.environ.setdefault("AI_GENERATION_MODEL", "placeholder_not_used_in_sandbox")

    # Prevent claude CLI from thinking it's running inside Claude Code
    os.environ.pop("CLAUDECODE", None)


# ---------------------------------------------------------------------------
# Task dispatchers (imported AFTER _setup_env() is called in main())
# ---------------------------------------------------------------------------

def _run_expert_reply_task(task: dict) -> dict:
    """Run expert reply agent and return result_info dict.

    The agent reads workspace context and writes the reply post to disk.
    This function blocks until the agent completes.
    """
    # Import here (after env setup) to avoid module-level config errors
    from app.agent.expert_reply import run_expert_reply  # noqa: PLC0415

    ws_path = Path(task["ws_path"])
    result_info = asyncio.run(
        run_expert_reply(
            ws_path=ws_path,
            topic_id=task["topic_id"],
            topic_title=task["topic_title"],
            expert_name=task["expert_name"],
            expert_label=task["expert_label"],
            user_post_id=task["user_post_id"],
            user_author=task["user_author"],
            user_question=task["user_question"],
            reply_post_id=task["reply_post_id"],
            reply_created_at=task["reply_created_at"],
            max_turns=task.get("max_turns", 100),
            max_budget_usd=task.get("max_budget_usd", 10.0),
        )
    )
    return {"result_info": result_info}


def _run_discussion_task(task: dict) -> dict:
    """Run discussion and return result dict.

    The moderator agent orchestrates expert sub-agents. All writes go to
    the topic workspace (shared/turns/, shared/discussion_summary.md, etc.).
    This function blocks until the discussion completes.
    """
    # Import here (after env setup)
    from app.agent.discussion import run_discussion  # noqa: PLC0415
    from app.agent.workspace import (  # noqa: PLC0415
        read_discussion_history,
        read_discussion_summary,
    )

    ws_path = Path(task["ws_path"])
    config = {
        "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "base_url": os.environ.get("ANTHROPIC_BASE_URL", ""),
        "model": os.environ.get("ANTHROPIC_MODEL", ""),
    }

    result_info = asyncio.run(
        run_discussion(
            workspace_dir=ws_path,
            config=config,
            topic=task["topic_text"],
            num_rounds=task.get("num_rounds", 5),
            expert_names=task.get("expert_names"),
            max_turns=task.get("max_turns", 10000),
            max_budget_usd=task.get("max_budget_usd", 5.0),
        )
    )

    return {
        "result_info": result_info,
        "discussion_history": read_discussion_history(ws_path),
        "discussion_summary": read_discussion_summary(ws_path),
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point: read input.json, dispatch task, write output.json."""
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <input.json> <output.json>",
            file=sys.stderr,
        )
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    # Step 1: Load task config (BEFORE env setup and app imports)
    try:
        task = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception as exc:
        # Can't write output yet — just exit with error
        print(f"Failed to read input JSON: {exc}", file=sys.stderr)
        sys.exit(2)

    # Step 2: Set environment variables BEFORE any app.* imports
    _setup_env(task)

    # Step 3: Dispatch to task handler (imports happen inside each function)
    task_type = task.get("task_type", "unknown")
    logger.info("Sandbox runner starting: task_type=%s", task_type)

    try:
        if task_type == "expert_reply":
            result = _run_expert_reply_task(task)
        elif task_type == "discussion":
            result = _run_discussion_task(task)
        else:
            raise ValueError(f"Unknown task_type: {task_type!r}")

        output = {"success": True, **result}
        logger.info("Sandbox runner completed: task_type=%s", task_type)

    except Exception as exc:
        logger.error("Sandbox runner failed: %s", exc, exc_info=True)
        output = {"success": False, "error": str(exc)}

    # Step 4: Write result to output file
    try:
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"Failed to write output JSON: {exc}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
