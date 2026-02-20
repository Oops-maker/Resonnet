"""App configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


def get_anthropic_api_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY is not set; configure it in .env")
    return key


def get_anthropic_base_url() -> str:
    return os.getenv("ANTHROPIC_BASE_URL", "")


def get_anthropic_model() -> str:
    return os.getenv("ANTHROPIC_MODEL", "")


def get_ai_generation_base_url() -> str:
    """Get base URL specifically for AI generation (expert/moderator mode generation).

    WARNING: Do NOT mix with ANTHROPIC_BASE_URL. These are separate systems.
    """
    url = os.getenv("AI_GENERATION_BASE_URL", "")
    if not url:
        raise ValueError("AI_GENERATION_BASE_URL is not set; configure it in .env")
    return url


def get_ai_generation_api_key() -> str:
    """Get API key for AI generation.

    WARNING: Do NOT fallback to ANTHROPIC_API_KEY. Must be explicitly set.
    """
    key = os.getenv("AI_GENERATION_API_KEY", "")
    if not key:
        raise ValueError("AI_GENERATION_API_KEY is not set; configure it in .env")
    return key


def get_ai_generation_model() -> str:
    """Get model name for AI generation.

    WARNING: Do NOT fallback to ANTHROPIC_MODEL. Must be explicitly set.
    """
    model = os.getenv("AI_GENERATION_MODEL", "")
    if not model:
        raise ValueError("AI_GENERATION_MODEL is not set; configure it in .env")
    return model


def get_workspace_base() -> Path:
    raw = os.getenv("WORKSPACE_BASE", "")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent.parent / "workspace"


def get_skills_dir() -> Path:
    """Return the skills root directory for the current scenario.

    - SKILLS_BASE: If set (absolute or relative to project root), use it.
    - SCENARIO_PRESET: topic-lab (default) | default | <custom_scenario_name>
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    skills_root = project_root / "skills"

    base_override = os.getenv("SKILLS_BASE", "")
    if base_override:
        p = Path(base_override)
        if not p.is_absolute():
            p = project_root / base_override
        return p.resolve()

    preset = os.getenv("SCENARIO_PRESET", "topic-lab")
    if preset == "topic-lab":
        return skills_root / "scenarios" / "topic-lab"
    if preset == "default":
        return skills_root / "default"
    return skills_root / "scenarios" / preset


def get_assignable_skills_dir() -> Path:
    """Return skills/assignable_skills/ (场景无关，与 scenarios 同级)."""
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "skills" / "assignable_skills"


def get_mcps_dir() -> Path:
    """Return skills/mcps/ (assignable MCP servers, read-only config)."""
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "skills" / "mcps"


def get_prompts_dir() -> Path:
    """Return the prompts directory for the current scenario.

    - If scenario has prompts/ subdir (e.g. skills/scenarios/topic-lab/prompts/), use it.
    - Otherwise fallback to app/prompts/ for backward compatibility.
    """
    scenario_prompts = get_skills_dir() / "prompts"
    if scenario_prompts.exists() and scenario_prompts.is_dir():
        return scenario_prompts
    return Path(__file__).resolve().parent.parent / "prompts"


# Module-level constants for easy import
WORKSPACE_BASE = get_workspace_base()

# Claude Agent SDK configuration (for discussion orchestration)
ANTHROPIC_API_KEY = get_anthropic_api_key()
ANTHROPIC_BASE_URL = get_anthropic_base_url()
ANTHROPIC_MODEL = get_anthropic_model()

# AI Generation configuration (for expert/moderator generation via HTTP API)
# WARNING: These are completely separate from ANTHROPIC_* settings
AI_GENERATION_BASE_URL = get_ai_generation_base_url()
AI_GENERATION_API_KEY = get_ai_generation_api_key()
AI_GENERATION_MODEL = get_ai_generation_model()
