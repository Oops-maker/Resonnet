"""Preset moderator modes for multi-agent discussions."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import get_moderator_mode_source_dir
from app.core.topic_defaults import normalize_skill_id, normalize_skill_ids
from app.core.moderator_modes_meta import get_modes_and_common

from .experts import get_discussion_image_guidance
from .workspace import build_output_language_instruction

logger = logging.getLogger(__name__)

_MODES, _SOURCE_COMMON_SECTIONS = get_modes_and_common()


def _load_preset_modes() -> dict:
    """Load preset moderator modes from libs/moderator_modes/ (unified meta)."""
    valid_modes = {}
    for mode_id, mode_data in _MODES.items():
        if all(key in mode_data for key in ["id", "name", "description", "num_rounds", "convergence_strategy"]):
            valid_modes[mode_id] = {
                "id": mode_data["id"],
                "name": mode_data["name"],
                "description": mode_data["description"],
                "num_rounds": mode_data["num_rounds"],
                "convergence_strategy": mode_data["convergence_strategy"],
                "prompt_file": mode_data.get("prompt_file", f"{mode_id}.md"),
                "summary_scope": mode_data.get("summary_scope", "key findings, consensus, disagreements"),
                "source": mode_data.get("source", "default"),
            }
        else:
            logger.warning(f"Skipping invalid mode '{mode_id}': missing required fields")
    return valid_modes


def _load_common_content(source_id: str = "default") -> str:
    """Load common moderator sections (Workspace, Rules, Language) for given source."""
    common_file = _SOURCE_COMMON_SECTIONS.get(source_id, "moderator_common.md")
    modes_dir = get_moderator_mode_source_dir(source_id)
    common_path = modes_dir / source_id / common_file
    if common_path.exists():
        return common_path.read_text(encoding="utf-8")
    return ""


def _load_mode_prompt(mode_id: str) -> str:
    """Load moderator mode prompt (role-specific part only)."""
    spec = PRESET_MODES.get(mode_id, {})
    source_id = spec.get("source", "default")
    prompt_file = spec.get("prompt_file", f"{mode_id}.md")
    modes_dir = get_moderator_mode_source_dir(source_id)
    skill_file = modes_dir / source_id / prompt_file
    if not skill_file.exists():
        raise FileNotFoundError(f"Moderator skill file not found: {skill_file}")
    return skill_file.read_text(encoding="utf-8")


def _build_moderator_prompt_from_preset(mode_id: str, params: dict) -> str:
    """Build full moderator prompt from mode (role) + common sections."""
    mode_content = _load_mode_prompt(mode_id)
    spec = PRESET_MODES.get(mode_id, {})
    source_id = spec.get("source", "default")
    common_content = _load_common_content(source_id)
    params = dict(params, summary_scope=spec.get("summary_scope", "key findings, consensus, disagreements"))
    combined = f"{mode_content}\n\n{common_content}" if common_content else mode_content
    return _fill_skill_template(combined, **params)


# Preset moderator modes (loaded from libs/moderator_modes/)
PRESET_MODES = _load_preset_modes()


def reload_moderator_modes() -> None:
    """Reload PRESET_MODES from disk (e.g. after share to topiclab_shared).

    Updates dict in-place so importers (e.g. moderator_modes API) see the new data.
    """
    global _MODES, _SOURCE_COMMON_SECTIONS
    _MODES, _SOURCE_COMMON_SECTIONS = get_modes_and_common()
    new_modes = _load_preset_modes()
    PRESET_MODES.clear()
    PRESET_MODES.update(new_modes)


def load_moderator_mode_config(ws_path: Path) -> dict:
    """Load moderator mode configuration from config/moderator_mode.json.

    Returns:
        dict with structure: {"mode_id": "standard", "num_rounds": 5, "custom_prompt": null,
        "skill_list": [], "mcp_server_ids": [], "model": null}
        If file doesn't exist, returns default standard mode config.
        Falls back to workspace config/skills/ and config/mcp.json when those fields are missing.
    """
    config_file = ws_path / "config" / "moderator_mode.json"
    default = {
        "mode_id": "standard",
        "num_rounds": 5,
        "custom_prompt": None,
        "skill_list": [],
        "mcp_server_ids": [],
        "model": None,
    }

    if not config_file.exists():
        return _enrich_config_from_workspace(default, ws_path)

    try:
        content = config_file.read_text(encoding="utf-8")
        data = json.loads(content)
        # Ensure extended fields exist
        for key in ("skill_list", "mcp_server_ids", "model"):
            if key not in data:
                data[key] = default[key]
        data["skill_list"] = normalize_skill_ids(data.get("skill_list", []))
        return _enrich_config_from_workspace(data, ws_path)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load moderator mode config: {e}")
        return _enrich_config_from_workspace(default, ws_path)


def _enrich_config_from_workspace(config: dict, ws_path: Path) -> dict:
    """Fill skill_list and mcp_server_ids from workspace when missing in config."""
    result = dict(config)
    skills_dir = ws_path / "config" / "skills"
    mcp_file = ws_path / "config" / "mcp.json"

    if not result.get("skill_list") and skills_dir.exists():
        result["skill_list"] = _skill_ids_from_workspace(skills_dir)

    if not result.get("mcp_server_ids") and mcp_file.exists():
        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
            servers = data.get("mcpServers") or {}
            result["mcp_server_ids"] = list(servers.keys())
        except (json.JSONDecodeError, OSError):
            pass

    return result


def _skill_ids_from_workspace(skills_dir: Path) -> list[str]:
    """Derive skill ids from config/skills/ filenames (reverse of _skill_dest_filename).

    Filename is either slug.md or source_slug.md (colon replaced with underscore).
    Resolve against assignable skills meta to pick the correct id when ambiguous.
    """
    ids: list[str] = []
    try:
        from app.core.config import get_assignable_skills_dir
        from app.core.skills_meta import load_aggregated_meta

        base_dir = get_assignable_skills_dir()
        _, skills_meta = load_aggregated_meta(base_dir)
    except Exception:
        skills_meta = {}

    for p in skills_dir.glob("*.md"):
        stem = normalize_skill_id(p.stem)
        if stem in (skills_meta or {}):
            ids.append(stem)
        elif "_" in stem:
            candidate = stem.replace("_", ":", 1)
            if candidate in (skills_meta or {}):
                ids.append(candidate)
            else:
                ids.append(stem)
        else:
            ids.append(stem)
    return ids


def save_moderator_mode_config(ws_path: Path, config: dict):
    """Save moderator mode configuration to config/moderator_mode.json."""
    config_file = ws_path / "config" / "moderator_mode.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Only persist known fields
    to_save = {
        "mode_id": config.get("mode_id", "standard"),
        "num_rounds": config.get("num_rounds", 5),
        "custom_prompt": config.get("custom_prompt"),
        "skill_list": normalize_skill_ids(config.get("skill_list", [])),
        "mcp_server_ids": config.get("mcp_server_ids", []),
        "model": config.get("model"),
    }

    try:
        content = json.dumps(to_save, indent=2, ensure_ascii=False)
        config_file.write_text(content, encoding="utf-8")
        logger.info(f"Saved moderator mode config to {config_file}")
    except OSError as e:
        logger.error(f"Failed to save moderator mode config: {e}")
        raise


def _fill_skill_template(template: str, **kwargs) -> str:
    """Replace only known {key} placeholders, leaving unknown ones (e.g. {round}) intact."""
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", str(value))
    return template


def _topic_explicitly_requests_image(topic: str) -> bool:
    """Return True when the topic clearly asks for a visual deliverable."""
    lowered = topic.lower()
    keywords = (
        "生成一张", "画一张", "绘制", "出图", "配图", "图示", "架构图",
        "generate an image", "generate a diagram", "draw", "figure", "diagram",
        "schematic", "visualize", "visualise",
    )
    return any(keyword in lowered for keyword in keywords)


def prepare_moderator_skill(ws_path: Path, topic: str, expert_names: list[str], num_rounds: int | None = None) -> Path:
    """Format the moderator skill and save it to config/moderator_skill.md in the workspace.

    This ensures the agent reads its skill from the topic workspace, consistent
    with how expert skills are stored per-topic.

    Returns:
        Path to the saved skill file.
    """
    config = load_moderator_mode_config(ws_path)
    mode_id = config.get("mode_id", "standard")
    # num_rounds: explicit override wins over workspace config
    num_rounds = num_rounds if num_rounds is not None else config.get("num_rounds", 5)
    custom_prompt = config.get("custom_prompt")

    output_lang = build_output_language_instruction(ws_path)
    params = dict(
        topic=topic,
        ws_abs=str(ws_path.resolve()),
        expert_names_str="、".join(expert_names),
        num_experts=len(expert_names),
        num_rounds=num_rounds,
        output_language_instruction=output_lang,
    )

    if mode_id == "custom" and custom_prompt:
        # Custom: role-only content + common sections (with default summary_scope)
        common_content = _load_common_content("default")
        params_with_scope = dict(params, summary_scope="key findings, consensus, disagreements, and recommendations")
        combined = f"{custom_prompt}\n\n{common_content}" if common_content else custom_prompt
        skill_content = _fill_skill_template(combined, **params_with_scope)
    else:
        if mode_id not in PRESET_MODES:
            logger.warning(f"Unknown mode_id: {mode_id}, falling back to standard")
            mode_id = "standard"
        skill_content = _build_moderator_prompt_from_preset(mode_id, params)

    # Append skill assignment section when config/skills/ has assignable skills
    skills_dir = ws_path / "config" / "skills"
    if skills_dir.exists():
        skill_files = sorted(skills_dir.glob("*.md"))
        if skill_files:
            skill_names = [f.stem for f in skill_files]
            assignment_section = _build_skill_assignment_section(skill_names, ws_path.name, topic)
            skill_content = skill_content.rstrip() + "\n\n" + assignment_section
            logger.info(f"Added skill assignment section for {skill_names}")

    skill_file = ws_path / "config" / "moderator_skill.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(skill_content, encoding="utf-8")
    logger.info(f"Saved moderator skill to {skill_file} (mode={mode_id}, rounds={num_rounds})")
    return skill_file


def _build_skill_assignment_section(skill_names: list[str], topic_id: str, topic: str) -> str:
    """Build moderator instructions for assigning skills to experts."""
    paths_str = "\n".join(f"- config/skills/{s}.md" for s in skill_names)
    image_guidance = ""
    image_skill_name = next((name for name in skill_names if normalize_skill_id(name) == "image_generation"), None)
    if image_skill_name:
        required_delivery = ""
        if _topic_explicitly_requests_image(topic):
            required_delivery = """

## Required Visual Deliverable

- If the topic explicitly asks for an image, diagram, figure, architecture chart, or other visual output, treat at least one image as a required deliverable rather than an optional enhancement.
- If the topic explicitly asks for an image, diagram, figure, architecture chart, or other visual output, actively use the image generation skill to produce the figure instead of stopping at text-only analysis.
- In that case, assign the image generation skill to a suitable expert at an appropriate stage and coordinate other experts to refine scope, labels, and comparison dimensions.
- Do not end the discussion with text-only output when the original task explicitly asked for a visual artifact unless image generation fails; if it fails, explain the failure clearly and provide a Markdown-ready fallback description.
"""
        image_guidance = f"""

## Image Generation Guidance

When assigning `config/skills/{image_skill_name}.md`, explicitly tell the expert that image generation is available in this discussion and that they should follow these rules:

{get_discussion_image_guidance(topic_id).strip()}{required_delivery}
"""
    return f"""## Skill Assignment (config/skills/)

以下技能已拷贝到工作区，供你按需分配给专家：

{paths_str}

**使用方式**：
1. 每轮开始前，用 Read 工具阅读上述技能文件，根据当前讨论阶段与话题选择最相关的技能
2. 调用专家 Task 时，在指令中附加技能内容，例如：「除你的角色外，请额外遵循以下指导：[粘贴技能内容]。然后阅读 shared/topic.md 并参与讨论。」
3. 同一专家可分配多个技能，或不同专家分配不同技能；根据话题与专家专长灵活选择

## Source Citation Guardrails

- Only cite verifiable external sources using full `https://` URLs with a real domain.
- Never use placeholder or internal pseudo-source paths such as `/api/2026-*` as evidence citations.
- If a claim cannot be supported by a verifiable source, state uncertainty directly instead of inventing a source.{image_guidance}"""


def get_moderator_prompt(ws_path: Path) -> str:
    """Return the short prompt that instructs the moderator to read its skill file.

    Must be called after prepare_moderator_skill() has written config/moderator_skill.md.
    """
    return "请阅读 config/moderator_skill.md 获取你的主持技能指南，然后严格按照其中的要求主持本次讨论。"
