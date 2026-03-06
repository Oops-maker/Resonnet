"""Experts API endpoints — read/update expert profiles and skill files."""

import json
import logging
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.experts import EXPERT_CATEGORIES, EXPERT_SPECS, reload_expert_specs
from app.core.config import get_expert_source_dir, get_experts_dir
from app.models.schemas import ExpertInfo, ExpertUpdateRequest

logger = logging.getLogger(__name__)
router = APIRouter()


class ImportProfileRequest(BaseModel):
    forum_profile: str
    session_id: str | None = None


def _derive_expert_name_from_forum_profile(content: str) -> tuple[str, str]:
    """Extract expert name and label from forum profile. First # line is used."""
    lines = content.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("# "):
            label = line[2:].strip()
            if not label:
                continue
            name = re.sub(r"[^\w\u4e00-\u9fff]", "_", label)
            name = re.sub(r"_+", "_", name).strip("_")
            if not name:
                name = "forum_profile"
            name = name[:64]
            return name, label
    return "forum_profile", "论坛画像"


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


@router.post("/import-profile")
def import_profile_to_experts(req: ImportProfileRequest):
    """Import forum profile from profile helper into global expert library (topiclab_shared)."""
    content = (req.forum_profile or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="forum_profile 不能为空")

    expert_name, label = _derive_expert_name_from_forum_profile(content)
    if not expert_name.replace("_", "").isalnum():
        expert_name = "forum_profile"

    existing = EXPERT_SPECS.get(expert_name)
    if existing and existing.get("source") == "default":
        raise HTTPException(
            status_code=409,
            detail=f"角色名 '{expert_name}' 与内置角色冲突，请修改论坛画像标题后重试",
        )

    try:
        experts_dir = get_experts_dir()
        shared_dir = experts_dir / "topiclab_shared"
        shared_dir.mkdir(parents=True, exist_ok=True)
        skill_file_name = f"{expert_name}.md"
        (shared_dir / skill_file_name).write_text(content, encoding="utf-8")

        meta_path = shared_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                logger.warning("Invalid topiclab_shared/meta.json, recreating: %s", e)
                meta = {}
        else:
            meta = {}
        meta.setdefault("common_sections", "expert_common.md")
        if not isinstance(meta.get("categories"), dict):
            meta["categories"] = {}
        meta["categories"].setdefault("topiclab", {
            "id": "topiclab",
            "name": "TopicLab",
            "description": "User-shared experts from frontend",
        })
        experts_dict = meta.get("experts")
        if not isinstance(experts_dict, dict):
            experts_dict = {}
            meta["experts"] = experts_dict
        experts_dict[expert_name] = {
            "id": expert_name,
            "source": "topiclab_shared",
            "name": expert_name,
            "label": label,
            "description": "从科研画像助手论坛画像导入",
            "category": "topiclab",
            "skill_file": skill_file_name,
            "perspective": expert_name,
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        main_meta_path = experts_dir / "meta.json"
        if main_meta_path.exists():
            try:
                main_meta = json.loads(main_meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                logger.warning("Invalid experts/meta.json: %s", e)
                main_meta = {}
        else:
            main_meta = {}
        main_meta.setdefault("sources", {})["topiclab_shared"] = {
            "id": "topiclab_shared",
            "name": "TopicLab-共享",
            "description": "User-shared experts from frontend",
        }
        main_meta_path.parent.mkdir(parents=True, exist_ok=True)
        main_meta_path.write_text(json.dumps(main_meta, ensure_ascii=False, indent=2), encoding="utf-8")

        reload_expert_specs()
        from app.core.libs_service import invalidate_libs_cache
        invalidate_libs_cache()

        return {"message": "已导入到 Topic-Lab 角色库", "expert_name": expert_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Import profile failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"导入失败: {type(e).__name__}: {e}",
        ) from e
