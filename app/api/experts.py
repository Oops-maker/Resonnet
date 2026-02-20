"""Experts API endpoints — read/update expert profiles and skill files."""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agent.experts import EXPERT_CATEGORIES, EXPERT_SPECS
from app.core.config import get_experts_dir
from app.models.schemas import ExpertInfo, ExpertUpdateRequest

router = APIRouter()

EXPERTS_DIR = get_experts_dir()


def _build_expert_info(name: str) -> ExpertInfo:
    spec = EXPERT_SPECS.get(name)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Expert '{name}' not found")
    source_id = spec.get("source", "default")
    skill_file = spec["skill_file"]
    skill_path = EXPERTS_DIR / source_id / skill_file
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
    )


@router.get("", response_model=list[ExpertInfo])
def list_experts():
    return [_build_expert_info(name) for name in EXPERT_SPECS]


@router.get("/{name}", response_model=ExpertInfo)
def get_expert(name: str):
    return _build_expert_info(name)


@router.put("/{name}", response_model=ExpertInfo)
def update_expert(name: str, req: ExpertUpdateRequest):
    spec = EXPERT_SPECS.get(name)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Expert '{name}' not found")
    source_id = spec.get("source", "default")
    skill_path = EXPERTS_DIR / source_id / spec["skill_file"]
    skill_path.write_text(req.skill_content, encoding="utf-8")
    return _build_expert_info(name)
