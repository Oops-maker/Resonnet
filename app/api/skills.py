"""Skills API: list assignable skills from global skill library."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agent.workspace import _resolve_skill_path
from app.core.config import get_assignable_skills_dir
from app.core.skills_meta import load_aggregated_meta

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/assignable/categories")
def list_assignable_categories():
    """List skill categories from assignable_skills (main meta + per-source meta)."""
    base_dir = get_assignable_skills_dir()
    categories, _ = load_aggregated_meta(base_dir)
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
    fields: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    """List available assignable skills from skills/assignable_skills/.

    Query params (all optional):
    - category: filter by category id (e.g. methodology, thinking)
    - fields: "minimal" = id, name, category, category_name only (smaller payload)
    - limit, offset: pagination (default: no limit)

    Returns list of {id, name, description?, category, category_name} for each skill.
    """
    base_dir = get_assignable_skills_dir()
    categories, skills = load_aggregated_meta(base_dir)

    try:
        minimal = (fields or "").strip().lower() == "minimal"

        result = []
        for skill_id, skill_data in skills.items():
            if isinstance(skill_data, dict) and "id" in skill_data:
                cat_id = skill_data.get("category", "")
                if category is not None and category != "" and cat_id != category:
                    continue
                cat_info = categories.get(cat_id, {}) if isinstance(categories.get(cat_id), dict) else {}
                item = {
                    "id": skill_data["id"],
                    "name": skill_data.get("name", skill_id),
                    "category": cat_id,
                    "category_name": cat_info.get("name", cat_id),
                }
                if not minimal:
                    item["source"] = skill_data.get("source", "default")
                    item["description"] = skill_data.get("description", "")
                result.append(item)
            else:
                if category is not None and category != "":
                    continue
                item = {"id": skill_id, "name": skill_id, "category": "", "category_name": ""}
                if not minimal:
                    item["source"] = ""
                    item["description"] = ""
                result.append(item)

        if offset > 0:
            result = result[offset:]
        if limit is not None and limit > 0:
            result = result[:limit]

        return result
    except Exception as e:
        logger.error(f"Failed to load assignable skills: {e}")
        raise HTTPException(status_code=500, detail="Failed to load assignable skills")


@router.get("/assignable/{skill_id}/content")
def get_skill_content(skill_id: str):
    """Return the raw markdown content of a skill file."""
    base_dir = get_assignable_skills_dir()
    _, skills_meta = load_aggregated_meta(base_dir)

    raw = skill_id.removesuffix(".md") if skill_id.endswith(".md") else skill_id
    skill_info = skills_meta.get(raw, {}) if isinstance(skills_meta.get(raw), dict) else {}
    if not skill_info:
        raise HTTPException(status_code=404, detail="Skill not found")

    src = _resolve_skill_path(base_dir, raw, skill_info)
    if not src or not src.exists():
        raise HTTPException(status_code=404, detail="Skill file not found")

    return {"content": src.read_text(encoding="utf-8")}
