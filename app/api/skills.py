"""Skills API: list assignable skills from global skill library."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agent.workspace import _resolve_skill_path
from app.core.config import get_assignable_skills_dir
from app.core.libs_service import get_cached_skills_meta, list_assignable_items

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/assignable/categories")
def list_assignable_categories():
    """List skill categories from assignable_skills (main meta + per-source meta)."""
    base_dir = get_assignable_skills_dir()
    categories, _ = get_cached_skills_meta(base_dir)
    return [
        {
            "id": c.get("id", k),
            "name": c.get("name", k),
            "description": c.get("description", ""),
        }
        for k, c in categories.items()
        if isinstance(c, dict)
    ]


@router.get("/assignable", response_model=list)
def list_assignable_skills(
    category: str | None = None,
    q: str | None = None,
    fields: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    """List available assignable skills from libs/assignable_skills/.

    Query params (all optional):
    - category: filter by category id (e.g. methodology, thinking)
    - q: search in id, name, description (case-insensitive)
    - fields: "minimal" = id, name, category, category_name only (smaller payload)
    - limit, offset: pagination (default: no limit)

    Returns list of {id, name, description?, category, category_name} for each skill.
    """
    base_dir = get_assignable_skills_dir()
    categories, skills = get_cached_skills_meta(base_dir)
    try:
        minimal = (fields or "").strip().lower() == "minimal"
        return list_assignable_items(
            categories,
            skills,
            category=category,
            q=q,
            minimal=minimal,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"Failed to load assignable skills: {e}")
        raise HTTPException(status_code=500, detail="Failed to load assignable skills")


@router.get("/assignable/{skill_id}/content")
def get_skill_content(skill_id: str):
    """Return the raw markdown content of a skill file."""
    base_dir = get_assignable_skills_dir()
    _, skills_meta = get_cached_skills_meta(base_dir)

    raw = skill_id.removesuffix(".md") if skill_id.endswith(".md") else skill_id
    skill_info = skills_meta.get(raw, {}) if isinstance(skills_meta.get(raw), dict) else {}
    if not skill_info:
        raise HTTPException(status_code=404, detail="Skill not found")

    src = _resolve_skill_path(base_dir, raw, skill_info)
    if not src or not src.exists():
        raise HTTPException(status_code=404, detail="Skill file not found")

    return {"content": src.read_text(encoding="utf-8")}
