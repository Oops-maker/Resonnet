"""App configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (./.env) when backend is submodule; fallback to backend/.env
_project_root = Path(__file__).resolve().parent.parent.parent.parent
_env_root = _project_root / ".env"
_env_backend = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_root.exists():
    load_dotenv(_env_root, override=True)
elif _env_backend.exists():
    load_dotenv(_env_backend, override=True)


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


def _libs_root() -> Path:
    """Return libs/ root (experts, moderator_modes, mcps, assignable_skills, prompts)."""
    return Path(__file__).resolve().parent.parent.parent / "libs"


def get_assignable_skills_dir() -> Path:
    """Return libs/assignable_skills/."""
    return _libs_root() / "assignable_skills"


def get_mcps_dir() -> Path:
    """Return libs/mcps/ (assignable MCP servers, read-only config)."""
    return _libs_root() / "mcps"


def get_moderator_modes_dir() -> Path:
    """Return libs/moderator_modes/."""
    return _libs_root() / "moderator_modes"


def get_experts_dir() -> Path:
    """Return libs/experts/."""
    return _libs_root() / "experts"


def get_prompts_dir() -> Path:
    """Return prompts directory: libs/prompts/ if exists, else app/prompts/."""
    libs_prompts = _libs_root() / "prompts"
    if libs_prompts.exists() and libs_prompts.is_dir():
        return libs_prompts
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
