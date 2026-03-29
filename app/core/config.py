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


def get_database_url() -> str:
    url = os.getenv("TOPICDATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()
    if not url and get_resonnet_mode() == "standalone":
        sqlite_path = Path(__file__).resolve().parent.parent.parent / "workspace" / "resonnet.sqlite3"
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{sqlite_path}"
    if not url:
        raise ValueError("DATABASE_URL is not required in executor mode; standalone mode can use local SQLite automatically")
    return url


def get_resonnet_mode() -> str:
    mode = os.getenv("RESONNET_MODE", "executor").strip().lower()
    if mode in {"executor", "standalone"}:
        return mode
    return "executor"


def get_auth_service_base_url() -> str:
    """Auth service base URL for token introspection via topiclab-backend."""
    return os.getenv("AUTH_SERVICE_BASE_URL", "http://topiclab-backend:8000")


def get_auth_mode() -> str:
    """Auth mode selector: none | jwt | proxy."""
    mode = os.getenv("AUTH_MODE", "none").strip().lower()
    if mode in {"none", "jwt", "proxy"}:
        return mode
    return "none"


def is_auth_required() -> bool:
    """Whether missing/invalid auth should be rejected."""
    return os.getenv("AUTH_REQUIRED", "false").strip().lower() == "true"


def is_account_sync_enabled() -> bool:
    """Whether to sync published twins into external account system."""
    return os.getenv("ACCOUNT_SYNC_ENABLED", "false").strip().lower() == "true"


def get_libs_cache_ttl_seconds() -> int:
    """Libs meta cache TTL. 0 = no cache (always fresh, hot-reload). Default 60."""
    raw = os.getenv("LIBS_CACHE_TTL_SECONDS", "60")
    try:
        return max(0, int(raw))
    except ValueError:
        return 60


def get_sandbox_use_srt() -> bool:
    """Whether to prefer sandbox-runtime (srt) for OS-level sandboxing.

    When True (default), the system uses ``srt`` if it is installed on the
    host.  Set to ``false`` to fall back to the legacy bwrap / sandbox-exec
    code path.
    """
    return os.getenv("SANDBOX_USE_SRT", "true").lower() in ("true", "1", "yes")


def get_enable_semantic_search() -> bool:
    """Whether to enable semantic search by default.

    Controlled by the ENABLE_SEMANTIC_SEARCH env var. Defaults to true (enabled).
    """
    return os.getenv("ENABLE_SEMANTIC_SEARCH", "true").lower() in ("true", "1", "yes")


def _libs_root() -> Path:
    """Return primary libs/ root (mount point in Docker; where we write topiclab_shared)."""
    return Path(__file__).resolve().parent.parent.parent / "libs"


def get_libs_builtin_root() -> Path | None:
    """Return built-in libs root if exists (Docker: /app/libs_builtin). None when not in Docker."""
    builtin = Path("/app/libs_builtin").resolve()
    if builtin.exists():
        return builtin
    return None


def get_expert_source_dir(source_id: str) -> Path:
    """Return experts base dir. default→builtin (canonical); topiclab_shared→primary (mount, user supplement)."""
    primary = _libs_root() / "experts"
    builtin = get_libs_builtin_root()
    if source_id == "topiclab_shared":
        return primary
    if builtin:
        builtin_experts = builtin / "experts"
        if (builtin_experts / source_id).exists():
            return builtin_experts
    return primary


def get_moderator_mode_source_dir(source_id: str) -> Path:
    """Return moderator_modes dir. default→builtin; topiclab_shared→primary (mount, user supplement)."""
    primary = _libs_root() / "moderator_modes"
    builtin = get_libs_builtin_root()
    if source_id == "topiclab_shared":
        return primary
    if builtin:
        builtin_modes = builtin / "moderator_modes"
        if (builtin_modes / source_id).exists():
            return builtin_modes
    return primary


def get_assignable_skills_dir() -> Path:
    """Return primary libs/assignable_skills/ (for writing). Reading merges builtin + primary."""
    return _libs_root() / "assignable_skills"


def get_mcps_dir() -> Path:
    """Return primary libs/mcps/ (for writing). Reading merges builtin + primary."""
    return _libs_root() / "mcps"


def get_moderator_modes_dir() -> Path:
    """Return libs/moderator_modes/."""
    return _libs_root() / "moderator_modes"


def get_experts_dir() -> Path:
    """Return libs/experts/."""
    return _libs_root() / "experts"


def get_agent_links_dir() -> Path:
    """Return libs/agent_links/."""
    return _libs_root() / "agent_links"


def get_profile_helper_root() -> Path:
    """Return libs/profile_helper/ (skills, docs, template for profile helper module)."""
    return _libs_root() / "profile_helper"


def get_profile_helper_profiles_dir() -> Path:
    """Return workspace-backed profile helper profiles directory."""
    return get_workspace_base() / "profile_helper" / "profiles"


def get_user_workspace(user_id: int | str) -> Path:
    """Return workspace directory for a specific user: workspace/users/{user_id}/."""
    return get_workspace_base() / "users" / str(user_id)


def get_user_profile_dir(user_id: int | str) -> Path:
    """Return profile directory for a user: workspace/users/{user_id}/profile/."""
    return get_user_workspace(user_id) / "profile"


def get_user_agents_dir(user_id: int | str) -> Path:
    """Return agents directory for a user: workspace/users/{user_id}/agents/."""
    return get_user_workspace(user_id) / "agents"


def get_public_agents_dir() -> Path:
    """Return public agents plaza directory: workspace/public_agents/."""
    return get_workspace_base() / "public_agents"


def get_prompts_dir() -> Path:
    """Return prompts directory: builtin libs/prompts/ > primary (mount) > app/prompts/. Mount only supplement."""
    builtin = get_libs_builtin_root()
    if builtin:
        builtin_prompts = builtin / "prompts"
        if builtin_prompts.exists() and builtin_prompts.is_dir():
            return builtin_prompts
    libs_prompts = _libs_root() / "prompts"
    if libs_prompts.exists() and libs_prompts.is_dir():
        return libs_prompts
    return Path(__file__).resolve().parent.parent / "prompts"


# Module-level constants for easy import
WORKSPACE_BASE = get_workspace_base()
ENABLE_SEMANTIC_SEARCH = get_enable_semantic_search()

# Claude Agent SDK configuration (for discussion orchestration)
ANTHROPIC_API_KEY = get_anthropic_api_key()
ANTHROPIC_BASE_URL = get_anthropic_base_url()
ANTHROPIC_MODEL = get_anthropic_model()

# AI Generation configuration (for expert/moderator generation via HTTP API)
# WARNING: These are completely separate from ANTHROPIC_* settings
AI_GENERATION_BASE_URL = get_ai_generation_base_url()
AI_GENERATION_API_KEY = get_ai_generation_api_key()
AI_GENERATION_MODEL = get_ai_generation_model()
