"""Moderator modes API endpoints."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agent.generation import generate_moderator_mode
from app.agent.moderator_modes import (
    _ensure_required_discussion_skills,
    PRESET_MODES,
    load_moderator_mode_config,
    reload_moderator_modes,
    save_moderator_mode_config,
)
from app.core.config import get_moderator_modes_dir, get_resonnet_mode, get_workspace_base
from app.core.libs_service import get_cached_modes_meta, invalidate_libs_cache, list_assignable_items
from app.models.schemas import (
    GenerateModeratorModeRequest,
    GenerateModeratorModeResponse,
    ModeratorModeConfig,
    ModeratorModeInfo,
    SetModeratorModeRequest,
    ShareModeratorModeRequest,
)
from app.models.store import get_topic, set_topic_moderator_mode_fields

logger = logging.getLogger(__name__)
router = APIRouter()


def _topic_workspace_exists(topic_id: str) -> bool:
    return (get_workspace_base() / "topics" / topic_id).exists()


def _require_topic(topic_id: str):
    if get_resonnet_mode() == "standalone":
        topic = get_topic(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        return topic
    if not _topic_workspace_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return None


@router.get("/moderator-modes/assignable/categories")
def list_assignable_moderator_mode_categories():
    """List moderator mode categories from libs/moderator_modes/."""
    base_dir = get_moderator_modes_dir()
    categories, _, _ = get_cached_modes_meta(base_dir)
    return [
        {"id": c.get("id", k), "name": c.get("name", k), "description": c.get("description", "")}
        for k, c in categories.items()
        if isinstance(c, dict)
    ]


def _modes_extra_fields(m: dict, _cat: dict) -> dict:
    return {
        "num_rounds": m.get("num_rounds", 5),
        "convergence_strategy": m.get("convergence_strategy", ""),
    }


@router.get("/moderator-modes/assignable")
def list_assignable_moderator_modes(
    category: str | None = None,
    q: str | None = None,
    fields: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    """List assignable moderator modes from libs/moderator_modes/ (category, source).

    Query params (all optional):
    - category: filter by category id
    - q: search in id, name, description (case-insensitive)
    - fields: "minimal" = id, name, category, category_name only
    - limit, offset: pagination
    """
    base_dir = get_moderator_modes_dir()
    categories, modes, _ = get_cached_modes_meta(base_dir)
    minimal = (fields or "").strip().lower() == "minimal"
    return list_assignable_items(
        categories,
        modes,
        category=category,
        q=q,
        minimal=minimal,
        limit=limit,
        offset=offset,
        extra_item_fields=None if minimal else _modes_extra_fields,
    )


@router.get("/moderator-modes/assignable/{mode_id}/content")
def get_moderator_mode_content(mode_id: str):
    """Return the mode prompt content (role-specific .md)."""
    base_dir = get_moderator_modes_dir()
    _, modes, _ = get_cached_modes_meta(base_dir)
    raw = mode_id.removesuffix(".md") if mode_id.endswith(".md") else mode_id
    mode_info = modes.get(raw, {}) if isinstance(modes.get(raw), dict) else {}
    if not mode_info:
        raise HTTPException(status_code=404, detail="Moderator mode not found")
    source_id = mode_info.get("source", "default")
    prompt_file = mode_info.get("prompt_file", f"{raw}.md")
    path = base_dir / source_id / prompt_file
    if not path.exists():
        raise HTTPException(status_code=404, detail="Moderator mode prompt file not found")
    return {"content": path.read_text(encoding="utf-8")}


@router.get("/moderator-modes", response_model=list[ModeratorModeInfo])
def list_moderator_modes():
    """Get list of preset moderator modes."""
    modes = []
    for mode_id, mode_data in PRESET_MODES.items():
        modes.append(
            ModeratorModeInfo(
                id=mode_data["id"],
                name=mode_data["name"],
                description=mode_data["description"],
                num_rounds=mode_data["num_rounds"],
                convergence_strategy=mode_data["convergence_strategy"],
            )
        )
    return modes


@router.get("/topics/{topic_id}/moderator-mode", response_model=ModeratorModeConfig)
def get_topic_moderator_mode(topic_id: str):
    """Get moderator mode configuration for this topic."""
    _require_topic(topic_id)

    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id

    config = load_moderator_mode_config(ws_path)
    return ModeratorModeConfig(**config)


@router.put("/topics/{topic_id}/moderator-mode", response_model=ModeratorModeConfig)
def set_topic_moderator_mode(topic_id: str, req: SetModeratorModeRequest):
    """Set moderator mode for this topic."""
    _require_topic(topic_id)

    # Validate mode_id
    if req.mode_id not in PRESET_MODES and req.mode_id != "custom":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode_id. Must be one of: {', '.join(PRESET_MODES.keys())}, custom"
        )

    # If custom mode, require custom_prompt
    if req.mode_id == "custom" and not req.custom_prompt:
        raise HTTPException(
            status_code=400,
            detail="custom_prompt is required when mode_id is 'custom'"
        )

    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id

    existing = load_moderator_mode_config(ws_path)
    config = {
        "mode_id": req.mode_id,
        "num_rounds": req.num_rounds,
        "custom_prompt": req.custom_prompt,
        "skill_list": _ensure_required_discussion_skills(
            req.skill_list if req.skill_list is not None else existing.get("skill_list", [])
        ),
        "mcp_server_ids": req.mcp_server_ids if req.mcp_server_ids is not None else existing.get("mcp_server_ids", []),
        "model": req.model if req.model is not None else existing.get("model"),
    }

    save_moderator_mode_config(ws_path, config)
    mode_name = "自定义模式" if req.mode_id == "custom" else PRESET_MODES.get(req.mode_id, {}).get("name", req.mode_id)
    if get_resonnet_mode() == "standalone":
        set_topic_moderator_mode_fields(topic_id, mode_id=req.mode_id, mode_name=mode_name, num_rounds=req.num_rounds)

    return ModeratorModeConfig(**config)


@router.post("/topics/{topic_id}/moderator-mode/generate", response_model=GenerateModeratorModeResponse)
async def generate_moderator_mode_endpoint(topic_id: str, req: GenerateModeratorModeRequest):
    """AI-generate a moderator mode based on user's description."""
    _require_topic(topic_id)

    try:
        custom_prompt = await generate_moderator_mode(req.prompt)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Automatically save as custom mode, preserve skill_list/mcp_server_ids/model
    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id
    existing = load_moderator_mode_config(ws_path)

    config = {
        "mode_id": "custom",
        "num_rounds": 5,  # Default, user can adjust
        "custom_prompt": custom_prompt,
        "skill_list": _ensure_required_discussion_skills(existing.get("skill_list", [])),
        "mcp_server_ids": existing.get("mcp_server_ids", []),
        "model": existing.get("model"),
    }

    save_moderator_mode_config(ws_path, config)
    if get_resonnet_mode() == "standalone":
        set_topic_moderator_mode_fields(topic_id, mode_id="custom", mode_name="自定义模式", num_rounds=5)

    return {
        "message": "Moderator mode generated successfully",
        "custom_prompt": custom_prompt,
        "config": config,
    }


@router.post("/topics/{topic_id}/moderator-mode/share", response_model=dict)
def share_moderator_mode_to_platform(topic_id: str, req: ShareModeratorModeRequest):
    """Share topic's custom moderator mode to platform library (topiclab_shared source)."""
    _require_topic(topic_id)

    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id
    config = load_moderator_mode_config(ws_path)

    if config.get("mode_id") != "custom" or not config.get("custom_prompt"):
        raise HTTPException(
            status_code=400,
            detail="Topic must use a custom moderator mode with custom_prompt to share"
        )

    # Reject if mode_id is built-in (default source)
    existing = PRESET_MODES.get(req.mode_id)
    if existing and existing.get("source") == "default":
        raise HTTPException(
            status_code=409,
            detail=f"Mode '{req.mode_id}' conflicts with built-in mode; choose a different id"
        )

    modes_dir = get_moderator_modes_dir()
    shared_dir = modes_dir / "topiclab_shared"
    shared_dir.mkdir(parents=True, exist_ok=True)

    prompt_file_name = f"{req.mode_id}.md"
    (shared_dir / prompt_file_name).write_text(config["custom_prompt"], encoding="utf-8")

    name = req.name or req.mode_id.replace("_", " ").title()
    description = req.description or f"User-shared moderator mode: {name}"

    meta_path = shared_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = {
            "common_sections": "moderator_common.md",
            "categories": {
                "topiclab": {
                    "id": "topiclab",
                    "name": "TopicLab",
                    "description": "User-shared moderator modes from frontend",
                }
            },
            "modes": {},
        }
    # Ensure topiclab_shared is registered in main meta.json
    main_meta_path = modes_dir / "meta.json"
    main_meta = json.loads(main_meta_path.read_text(encoding="utf-8"))
    main_meta.setdefault("sources", {})["topiclab_shared"] = {
        "id": "topiclab_shared",
        "name": "TopicLab-共享",
        "description": "User-shared moderator modes from frontend",
    }
    main_meta_path.write_text(json.dumps(main_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    meta.setdefault("modes", {})[req.mode_id] = {
        "id": req.mode_id,
        "source": "topiclab_shared",
        "name": name,
        "description": description,
        "category": "topiclab",
        "num_rounds": config.get("num_rounds", 5),
        "convergence_strategy": "User-defined flow",
        "prompt_file": prompt_file_name,
        "summary_scope": "key findings, consensus, disagreements",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    reload_moderator_modes()
    invalidate_libs_cache()

    return {"message": "Moderator mode shared to platform successfully", "mode_id": req.mode_id}
