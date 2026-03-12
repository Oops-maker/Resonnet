"""Topic workspace: workspace/topics/{topic_id}/shared/ structure."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# --- Workspace config (config/workspace.json) ---

WORKSPACE_CONFIG_FILE = "config/workspace.json"
DEFAULT_OUTPUT_LANGUAGE = "auto"
LANGUAGE_NAMES = {"zh": "中文", "en": "English", "auto": "auto"}


def _detect_language_from_text(text: str) -> str:
    """Detect output language from text. Returns 'zh' if Chinese chars dominate, else 'en'."""
    if not text or not text.strip():
        return "en"
    # Count CJK-ish characters (Chinese, Japanese, Korean)
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff" or "\u3000" <= c <= "\u303f")
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return "en"
    if cjk / total_alpha >= 0.3:
        return "zh"
    return "en"


def load_workspace_config(ws_path: Path) -> dict:
    """Load workspace config from config/workspace.json.

    Returns:
        dict with output_language, output_language_name, etc.
    """
    config_file = ws_path / WORKSPACE_CONFIG_FILE
    if not config_file.exists():
        return {"output_language": DEFAULT_OUTPUT_LANGUAGE, "output_language_name": LANGUAGE_NAMES[DEFAULT_OUTPUT_LANGUAGE]}

    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
        lang = data.get("output_language", DEFAULT_OUTPUT_LANGUAGE)
        return {
            "output_language": lang,
            "output_language_name": data.get("output_language_name") or LANGUAGE_NAMES.get(lang, "auto"),
        }
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load workspace config: {e}")
        return {"output_language": DEFAULT_OUTPUT_LANGUAGE, "output_language_name": LANGUAGE_NAMES[DEFAULT_OUTPUT_LANGUAGE]}


def save_workspace_config(ws_path: Path, config: dict) -> None:
    """Save workspace config to config/workspace.json."""
    config_file = ws_path / WORKSPACE_CONFIG_FILE
    config_file.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(config, indent=2, ensure_ascii=False)
    config_file.write_text(content, encoding="utf-8")
    logger.info(f"Saved workspace config to {config_file}")


def init_workspace_language_from_topic(ws_path: Path, topic_title: str, topic_body: str) -> None:
    """Initialize or update output_language in workspace config from topic content.

    If config already has explicit output_language (zh/en), do not overwrite.
    If output_language is 'auto' or missing, detect from topic_title + topic_body.
    """
    config = load_workspace_config(ws_path)
    if config.get("output_language") in ("zh", "en"):
        return  # Already explicitly set
    combined = f"{topic_title}\n{topic_body}"
    detected = _detect_language_from_text(combined)
    config["output_language"] = detected
    config["output_language_name"] = LANGUAGE_NAMES[detected]
    save_workspace_config(ws_path, config)
    logger.info(f"Initialized workspace output_language from topic: {detected}")


FALLBACK_LANGUAGE_INSTRUCTION = (
    "If no other language is specified, prefer the language of the topic and user context "
    "for all output and communication."
)


def build_output_language_instruction(ws_path: Path) -> str:
    """Build the Output Language skill section for prompts.

    Returns a strict instruction when output_language is zh/en; otherwise
    a fallback 'prefer request context' instruction.
    """
    config = load_workspace_config(ws_path)
    lang = config.get("output_language", DEFAULT_OUTPUT_LANGUAGE)
    name = config.get("output_language_name") or LANGUAGE_NAMES.get(lang, "auto")

    if lang in ("zh", "en"):
        return (
            f"**MUST** use {name} for all output: discussion turns, summaries, replies, and any text you produce. "
            f"Do not switch to another language unless the user explicitly requests it."
        )
    return FALLBACK_LANGUAGE_INSTRUCTION


def validate_topic_id(topic_id: str) -> str:
    """Validate topic_id to prevent path traversal attacks.

    Only allows alphanumeric characters, hyphens, and underscores.
    Rejects '..' sequences, '/' or '\\' separators, and any other
    characters that could be used for directory traversal.
    """
    if not topic_id or not re.match(r'^[a-zA-Z0-9_-]+$', topic_id):
        raise ValueError(
            f"Invalid topic_id: '{topic_id}'. "
            "Only alphanumeric characters, hyphens, and underscores are allowed."
        )
    return topic_id


def ensure_topic_workspace(workspace_base: Path | str, topic_id: str) -> Path:
    """Ensure workspace/topics/{topic_id}/shared/turns/ exists. Return topic workspace path.

    Validates topic_id and verifies the resolved path stays inside workspace_base.
    Also creates agents/<name>/ directories with default role.md for each expert.
    Creates config/ directory for metadata storage.
    """
    validate_topic_id(topic_id)

    base = Path(workspace_base).resolve()
    ws = base / "topics" / topic_id

    # Double-check: resolved path must be under workspace_base/topics/
    if not str(ws.resolve()).startswith(str(base / "topics")):
        raise ValueError(f"Path traversal detected for topic_id: '{topic_id}'")

    (ws / "shared" / "turns").mkdir(parents=True, exist_ok=True)
    (ws / "config").mkdir(exist_ok=True)  # Create config directory

    # Create agents/ structure with default roles
    _ensure_agents_structure(ws)

    # Initialize topic sandbox metadata (idempotent)
    from .topic_sandbox import init_sandbox_meta
    init_sandbox_meta(ws)

    return ws


def init_discussion_history(ws_path: Path, topic_title: str, topic_body: str) -> Path:
    """Ensure shared/turns/ exists and write shared/topic.md so experts can read the full topic (title + body).

    shared/topic.md is the canonical source for experts to understand the discussion topic,
    including any URLs or links in the body. The moderator also gets topic via config/moderator_skill.md.

    Also initializes config/workspace.json output_language from topic content when set to 'auto'.
    """
    shared_dir = ws_path / "shared"
    turns_dir = shared_dir / "turns"
    turns_dir.mkdir(parents=True, exist_ok=True)

    topic_content = f"# {topic_title}\n\n{topic_body}".strip()
    topic_file = shared_dir / "topic.md"
    topic_file.write_text(topic_content, encoding="utf-8")
    logger.info("Wrote shared/topic.md for experts to read")

    init_workspace_language_from_topic(ws_path, topic_title, topic_body)

    return turns_dir


def _parse_skill_id(skill_id: str) -> tuple[str, str]:
    """Parse skill_id into (source, slug). Supports source-prefixed format: source:slug."""
    raw = skill_id.removesuffix(".md") if skill_id.endswith(".md") else skill_id
    if ":" in raw:
        parts = raw.split(":", 1)
        return parts[0], parts[1]
    return "", raw


def _resolve_skill_path(base_dir: Path, skill_id: str, skill_info: dict) -> Path | None:
    """Resolve source file path for a skill. Returns None if not found.

    - default: assignable_skills/default/{category}/{slug}.md
    - imported (submodule): assignable_skills/_submodules/{source}/{skills_dir}/{category}/{slug}/SKILL.md
      or {skills_dir}/{slug}/SKILL.md when category is 'general'
    Uses _base_dir from skill_info when skill was loaded from builtin.
    """
    base_dir = skill_info.get("_base_dir", base_dir) or base_dir
    _, slug = _parse_skill_id(skill_id)
    source = skill_info.get("source", "default") or "default"
    category = skill_info.get("category", "")

    submodules = base_dir / "_submodules" / source
    if source != "default" and submodules.exists():
        skills_dir = skill_info.get("_skills_dir", ".") or "."
        if category and category != "general":
            path = base_dir / "_submodules" / source / skills_dir / category / slug / "SKILL.md"
        else:
            path = base_dir / "_submodules" / source / skills_dir / slug / "SKILL.md"
        return path if path.exists() else None

    if not category:
        return base_dir / source / f"{slug}.md"
    return base_dir / source / category / f"{slug}.md"


def _skill_dest_filename(skill_id: str) -> str:
    """Destination filename in config/skills/. Replaces : with _ to avoid collisions."""
    _, slug = _parse_skill_id(skill_id)
    if ":" in (skill_id.removesuffix(".md") if skill_id.endswith(".md") else skill_id):
        return f"{skill_id.replace(':', '_')}.md"
    return f"{slug}.md"


def copy_skills_to_workspace(ws_path: Path, skill_list: list[str]) -> list[str]:
    """Copy selected skills from global assignable_skills to topic workspace config/skills/.

    Supports source-prefixed IDs (e.g. awesome:critical_thinking) to avoid collisions
    when importing from multiple skill libraries.

    Path rule: assignable_skills/{source}/{category}/{slug}.md (all sources)

    Args:
        ws_path: Topic workspace path (workspace/topics/{topic_id})
        skill_list: List of skill ids (e.g. ["research_methodology", "awesome:critical_thinking"])

    Returns:
        List of skill ids that were successfully copied.
    """
    if not skill_list:
        return []

    from app.core.config import get_assignable_skills_dir
    from app.core.skills_meta import load_aggregated_meta

    base_dir = get_assignable_skills_dir()
    _, skills_meta = load_aggregated_meta(base_dir)
    if not skills_meta:
        logger.warning("Assignable skills meta not found")
        return []

    # Allow alphanumeric, underscore, hyphen, colon (for source:slug)
    id_pattern = re.compile(r"^[a-zA-Z0-9_.-]+(:[a-zA-Z0-9_.-]+)*$")

    dest_dir = ws_path / "config" / "skills"
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for skill_id in skill_list:
        raw = skill_id.removesuffix(".md") if skill_id.endswith(".md") else skill_id
        if not id_pattern.match(raw):
            logger.warning(f"Invalid skill id (skipped): {skill_id}")
            continue

        skill_info = skills_meta.get(raw, {}) if isinstance(skills_meta.get(raw), dict) else {}
        if not skill_info:
            logger.warning(f"Skill not found in meta (skipped): {raw}")
            continue

        src = _resolve_skill_path(base_dir, raw, skill_info)
        if not src or not src.exists():
            logger.warning(f"Skill file not found (skipped): {src}")
            continue

        dest_name = _skill_dest_filename(raw)
        dest = dest_dir / dest_name
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(raw)
        logger.info(f"Copied skill {raw} to {dest}")

    return copied


def _replace_env_variables(env_dict: dict | None) -> dict | None:
    """Replace ${VAR_NAME} patterns in env values with actual environment variables.
    
    Args:
        env_dict: Dictionary of environment variables that may contain ${VAR} patterns
        
    Returns:
        Dictionary with ${VAR} patterns replaced with actual env values, or None if input is None/empty
    """
    if not env_dict:
        return None
    
    result = {}
    pattern = re.compile(r'\$\{([^}]+)\}')
    
    for key, value in env_dict.items():
        if isinstance(value, str):
            # Replace all ${VAR} patterns with actual env values
            def replacer(match):
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))  # Keep original if not found
            result[key] = pattern.sub(replacer, value)
        else:
            result[key] = value
    
    return result


def copy_mcp_to_workspace(ws_path: Path, server_ids: list[str]) -> list[str]:
    """Copy selected MCP servers from libs/mcps/ to topic workspace config/mcp.json.

    Args:
        ws_path: Topic workspace path (workspace/topics/{topic_id})
        server_ids: List of MCP server IDs to copy (e.g. ["inspector"])

    Returns:
        List of server IDs that were successfully copied.
    """
    if not server_ids:
        return []

    from app.core.config import get_mcps_dir
    from app.core.mcps_meta import load_aggregated_mcps_meta

    base_dir = get_mcps_dir()
    _, mcps_meta = load_aggregated_mcps_meta(base_dir)
    if not mcps_meta:
        logger.warning("Assignable MCPs meta not found")
        return []

    dest_dir = ws_path / "config"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "mcp.json"

    from app.models.schemas import MCPServerConfig

    mcp_servers: dict = {}
    for sid in server_ids:
        info = mcps_meta.get(sid, {}) if isinstance(mcps_meta.get(sid), dict) else {}
        if not info:
            logger.warning(f"MCP not found in meta (skipped): {sid}")
            continue
        
        # Check if this is a streamableHttp type or stdio type
        is_http = info.get("type") == "streamableHttp"

        if is_http:
            headers = _replace_env_variables(info.get("headers")) or {}
            if not info.get("baseUrl"):
                logger.warning(f"MCP {sid}: baseUrl is required for streamableHttp type")
                continue
            mcp_servers[sid] = {
                "type": "streamableHttp",
                "baseUrl": info.get("baseUrl"),
                **({"headers": headers} if headers else {}),
                **({"description": info.get("description")} if info.get("description") else {}),
                "isActive": bool(info.get("isActive", True)),
            }
            continue

        # Stdio type: require command
        if not info.get("command"):
            logger.warning(f"MCP {sid}: command is required for stdio type")
            continue

        try:
            # Replace environment variables in env dict
            resolved_env = _replace_env_variables(info.get("env"))
            cfg = MCPServerConfig(
                command=info.get("command", ""),
                args=info.get("args", []),
                env=resolved_env,
            )

            from app.core.mcp_config import validate_mcp_server
            validate_mcp_server(sid, cfg)
        except ValueError as e:
            logger.warning(f"MCP {sid} validation failed (skipped): {e}")
            continue

        # Build the server config dict
        mcp_servers[sid] = {
            "command": info.get("command", ""),
            "args": info.get("args", []),
            **({"env": resolved_env} if resolved_env else {}),
        }

    if not mcp_servers:
        return []

    data = {"mcpServers": mcp_servers}
    dest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    copied = list(mcp_servers.keys())
    logger.info(f"Copied MCP servers {copied} to {dest_path}")
    return copied


def _get_expert_label(expert_key: str, ws_path: Path) -> str:
    """Map expert key to display label.

    Priority:
    1. Workspace config/experts_metadata.json  (topic-level override)
    2. Global libs/experts/ via EXPERT_SPECS  (single source of truth)
    3. expert_key itself as fallback
    """
    from .experts import EXPERT_SPECS

    # 1. Topic-level override
    meta_file = ws_path / "config" / "experts_metadata.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if expert_key in meta:
                return meta[expert_key].get("label", expert_key)
        except Exception:
            pass

    # 2. Global meta.json (maintained alongside expert skills)
    if expert_key in EXPERT_SPECS:
        return EXPERT_SPECS[expert_key].get("label", expert_key)

    return expert_key


def read_discussion_history(ws_path: Path) -> str:
    """Build discussion history dynamically from shared/turns/*.md files.

    Each turn is formatted as '## Round N - ExpertLabel' so the frontend can parse
    individual posts. discussion_history.md is no longer generated or read.
    """
    turns_dir = ws_path / "shared" / "turns"
    if not turns_dir.exists():
        return ""

    turn_files = sorted(turns_dir.glob("*.md"))
    if not turn_files:
        return ""

    parts = []
    for turn_file in turn_files:
        stem = turn_file.stem  # e.g. round1_physicist
        m = re.match(r"round(\d+)_(.+)", stem)
        if m:
            round_num = m.group(1)
            expert_key = m.group(2)
            label = _get_expert_label(expert_key, ws_path)
            heading = f"## Round {round_num} - {label}"
        else:
            heading = f"## {stem}"
        content = turn_file.read_text(encoding="utf-8").strip()
        parts.append(f"{heading}\n\n{content}\n\n---")

    return "\n\n".join(parts)


def read_discussion_summary(ws_path: Path) -> str:
    """Read shared/discussion_summary.md content."""
    f = ws_path / "shared" / "discussion_summary.md"
    if not f.exists():
        return ""
    return f.read_text(encoding="utf-8")


def _ensure_agents_structure(ws_path: Path):
    """Create agents/<name>/ directories and copy default role.md if not exists.

    For each system-supported expert, creates an agents/<name>/ directory.
    If role.md doesn't exist, copies from global libs/experts/ as default content.
    Existing role.md files are never overwritten (preserves user customization).
    """
    from .experts import EXPERT_SPECS
    from app.core.config import get_expert_source_dir

    agents_dir = ws_path / "agents"
    agents_dir.mkdir(exist_ok=True)

    for expert_name, spec in EXPERT_SPECS.items():
        expert_dir = agents_dir / expert_name
        expert_dir.mkdir(exist_ok=True)

        role_file = expert_dir / "role.md"

        # Only copy if role.md doesn't exist (idempotent, preserves customization)
        if not role_file.exists():
            source_id = spec.get("source", "default")
            experts_dir = get_expert_source_dir(source_id)
            global_skill_file = experts_dir / source_id / spec["skill_file"]
            if global_skill_file.exists():
                logger.info(
                    f"Creating default role for {expert_name} from {global_skill_file.name}"
                )
                role_file.write_text(
                    global_skill_file.read_text(encoding="utf-8"),
                    encoding="utf-8"
                )
            else:
                logger.warning(
                    f"Global skill file not found for {expert_name}: {global_skill_file}"
                )
                # Create a minimal placeholder
                role_file.write_text(
                    f"# {expert_name}\n\n{spec['description']}\n",
                    encoding="utf-8"
                )


# --- Expert Metadata Management ---

def load_experts_metadata(ws_path: Path) -> dict:
    """Load experts metadata from config/experts_metadata.json.

    Returns:
        dict with structure: {"experts": [{"name": "physicist", "label": "...", ...}, ...]}
        If file doesn't exist, returns empty structure.
    """
    metadata_file = ws_path / "config" / "experts_metadata.json"

    if not metadata_file.exists():
        return {"experts": []}

    try:
        content = metadata_file.read_text(encoding="utf-8")
        return json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load experts metadata: {e}")
        return {"experts": []}


def save_experts_metadata(ws_path: Path, metadata: dict):
    """Save experts metadata to config/experts_metadata.json.

    Args:
        ws_path: Topic workspace path
        metadata: dict with structure: {"experts": [...]}
    """
    metadata_file = ws_path / "config" / "experts_metadata.json"
    metadata_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        content = json.dumps(metadata, indent=2, ensure_ascii=False)
        metadata_file.write_text(content, encoding="utf-8")
        logger.info(f"Saved experts metadata to {metadata_file}")
    except OSError as e:
        logger.error(f"Failed to save experts metadata: {e}")
        raise


def get_topic_experts(ws_path: Path) -> list[dict]:
    """Get list of experts for this topic by reading workspace/agents/ directory.

    Returns list of expert dicts with metadata merged from experts_metadata.json.
    """
    agents_dir = ws_path / "agents"
    if not agents_dir.exists():
        return []

    # Load metadata
    metadata = load_experts_metadata(ws_path)
    metadata_map = {e["name"]: e for e in metadata.get("experts", [])}

    experts = []
    for expert_dir in sorted(agents_dir.iterdir()):
        if not expert_dir.is_dir():
            continue

        role_file = expert_dir / "role.md"
        if not role_file.exists():
            continue

        expert_name = expert_dir.name
        meta = metadata_map.get(expert_name, {})

        experts.append({
            "name": expert_name,
            "label": meta.get("label", expert_name),
            "description": meta.get("description", ""),
            "source": meta.get("source", "unknown"),
            "role_file": f"agents/{expert_name}/role.md",
            "added_at": meta.get("added_at", ""),
            "is_from_topic_creation": meta.get("is_from_topic_creation", False),
            "origin_type": meta.get("origin_type"),
            "origin_visibility": meta.get("origin_visibility"),
            "masked": bool(meta.get("masked", False)),
        })

    return experts


def add_expert_metadata(
    ws_path: Path,
    expert_name: str,
    label: str,
    description: str,
    source: str,
    is_from_topic_creation: bool = False,
    *,
    origin_type: str | None = None,
    origin_visibility: str | None = None,
    masked: bool | None = None,
):
    """Add or update expert metadata entry."""
    metadata = load_experts_metadata(ws_path)
    experts = metadata.get("experts", [])

    # Remove existing entry if present
    experts = [e for e in experts if e["name"] != expert_name]

    # Add new entry
    experts.append({
        "name": expert_name,
        "label": label,
        "description": description,
        "source": source,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "is_from_topic_creation": is_from_topic_creation,
        "origin_type": origin_type,
        "origin_visibility": origin_visibility,
        "masked": bool(masked) if masked is not None else False,
    })

    metadata["experts"] = experts
    save_experts_metadata(ws_path, metadata)


def remove_expert_metadata(ws_path: Path, expert_name: str):
    """Remove expert from metadata."""
    metadata = load_experts_metadata(ws_path)
    experts = metadata.get("experts", [])

    experts = [e for e in experts if e["name"] != expert_name]

    metadata["experts"] = experts
    save_experts_metadata(ws_path, metadata)
