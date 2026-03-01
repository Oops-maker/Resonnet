"""Experts API endpoints — read/update expert profiles and skill files."""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agent.experts import EXPERT_CATEGORIES, EXPERT_SPECS
from app.core.config import get_expert_source_dir
from app.models.schemas import ExpertInfo, ExpertUpdateRequest

router = APIRouter()


def _build_expert_info(name: str, include_content: bool = True) -> ExpertInfo:
    """Build ExpertInfo. When include_content=False, skip disk read for skill_content."""
    spec = EXPERT_SPECS.get(name)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Expert '{name}' not found")
    source_id = spec.get("source", "default")
    skill_file = spec["skill_file"]
    skill_content = ""
    if include_content:
        experts_dir = get_expert_source_dir(source_id)
        skill_path = experts_dir / source_id / skill_file
        skill_content = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""
    cat_id = spec.get("category", "")
    cat_info = EXPERT_CATEGORIES.get(cat_id, {}) if cat_id else {}
    return ExpertInfo(
        name=name,
        label=EXPERT_SPECS[name].get("label", name),
        description=spec["description"],
        skill_file=skill_file,
        skill_content=skill_content,
        perspective=spec.get("perspective", name),
        category=cat_id or None,
        category_name=cat_info.get("name", cat_id) if cat_id else None,
        source=source_id,
    )


@router.get("", response_model=list[ExpertInfo])
def list_experts(fields: str | None = None):
    """List global expert definitions. fields=minimal omits skill_content (faster)."""
    include_content = (fields or "").strip().lower() != "minimal"
    return [_build_expert_info(name, include_content=include_content) for name in EXPERT_SPECS]


@router.get("/{name}/content")
def get_expert_content(name: str):
    """Return only the skill markdown content (aligned with skills/mcp/moderator-modes)."""
    info = _build_expert_info(name, include_content=True)
    return {"content": info.skill_content}


@router.get("/{name}", response_model=ExpertInfo)
def get_expert(name: str):
    """Get full expert details including skill_content."""
    return _build_expert_info(name, include_content=True)


@router.put("/{name}", response_model=ExpertInfo)
def update_expert(name: str, req: ExpertUpdateRequest):
    spec = EXPERT_SPECS.get(name)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Expert '{name}' not found")
    source_id = spec.get("source", "default")
    experts_dir = get_expert_source_dir(source_id)
    skill_path = experts_dir / source_id / spec["skill_file"]
    skill_path.write_text(req.skill_content, encoding="utf-8")
    return _build_expert_info(name)
