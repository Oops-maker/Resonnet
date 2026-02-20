"""Moderator modes API endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agent.generation import generate_moderator_mode
from app.agent.moderator_modes import (
    PRESET_MODES,
    load_moderator_mode_config,
    save_moderator_mode_config,
)
from app.core.config import get_moderator_modes_dir, get_workspace_base
from app.core.moderator_modes_meta import load_aggregated_modes_meta
from app.models.schemas import (
    GenerateModeratorModeRequest,
    GenerateModeratorModeResponse,
    ModeratorModeConfig,
    ModeratorModeInfo,
    SetModeratorModeRequest,
)
from app.models.store import get_topic

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/moderator-modes/assignable/categories")
def list_assignable_moderator_mode_categories():
    """List moderator mode categories from libs/moderator_modes/."""
    base_dir = get_moderator_modes_dir()
    categories, _, _ = load_aggregated_modes_meta(base_dir)
    return [
        {"id": c.get("id", k), "name": c.get("name", k), "description": c.get("description", "")}
        for k, c in categories.items()
        if isinstance(c, dict)
    ]


@router.get("/moderator-modes/assignable")
def list_assignable_moderator_modes(
    category: str | None = None,
    fields: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    """List assignable moderator modes from libs/moderator_modes/ (category, source)."""
    base_dir = get_moderator_modes_dir()
    categories, modes, _ = load_aggregated_modes_meta(base_dir)
    minimal = (fields or "").strip().lower() == "minimal"
    result = []
    for mode_id, m in modes.items():
        if not isinstance(m, dict) or "id" not in m:
            continue
        cat_id = m.get("category", "")
        if category is not None and category != "" and cat_id != category:
            continue
        cat_info = categories.get(cat_id, {}) if isinstance(categories.get(cat_id), dict) else {}
        item = {
            "id": m["id"],
            "name": m.get("name", mode_id),
            "category": cat_id,
            "category_name": cat_info.get("name", cat_id),
        }
        if not minimal:
            item["source"] = m.get("source", "default")
            item["description"] = m.get("description", "")
            item["num_rounds"] = m.get("num_rounds", 5)
            item["convergence_strategy"] = m.get("convergence_strategy", "")
        result.append(item)
    if offset > 0:
        result = result[offset:]
    if limit is not None and limit > 0:
        result = result[:limit]
    return result


@router.get("/moderator-modes/assignable/{mode_id}/content")
def get_moderator_mode_content(mode_id: str):
    """Return the mode prompt content (role-specific .md)."""
    base_dir = get_moderator_modes_dir()
    _, modes, _ = load_aggregated_modes_meta(base_dir)
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
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id

    config = load_moderator_mode_config(ws_path)
    return ModeratorModeConfig(**config)


@router.put("/topics/{topic_id}/moderator-mode", response_model=ModeratorModeConfig)
def set_topic_moderator_mode(topic_id: str, req: SetModeratorModeRequest):
    """Set moderator mode for this topic."""
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

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

    config = {
        "mode_id": req.mode_id,
        "num_rounds": req.num_rounds,
        "custom_prompt": req.custom_prompt,
    }

    save_moderator_mode_config(ws_path, config)

    return ModeratorModeConfig(**config)


@router.post("/topics/{topic_id}/moderator-mode/generate", response_model=GenerateModeratorModeResponse)
async def generate_moderator_mode_endpoint(topic_id: str, req: GenerateModeratorModeRequest):
    """AI-generate a moderator mode based on user's description."""
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    try:
        custom_prompt = await generate_moderator_mode(req.prompt)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Automatically save as custom mode
    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id

    config = {
        "mode_id": "custom",
        "num_rounds": 5,  # Default, user can adjust
        "custom_prompt": custom_prompt,
    }

    save_moderator_mode_config(ws_path, config)

    return {
        "message": "Moderator mode generated successfully",
        "custom_prompt": custom_prompt,
        "config": config,
    }
