"""Topic-level experts management API endpoints."""

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.agent.experts import EXPERT_SPECS, reload_expert_specs
from app.agent.generation import generate_expert
from app.agent.workspace import (
    add_expert_metadata,
    get_topic_experts,
    remove_expert_metadata,
)
from app.core.config import get_experts_dir, get_workspace_base
from app.models.schemas import (
    AddExpertRequest,
    GenerateExpertActionResponse,
    GenerateExpertRequest,
    TopicExpert,
    TopicExpertResponse,
    UpdateTopicExpertRequest,
)
from app.models.schemas import TopicUpdate
from app.models.store import get_topic, update_topic

router = APIRouter()


@router.get("/{topic_id}/experts", response_model=list[TopicExpert])
def list_topic_experts(topic_id: str):
    """Get list of experts for this topic from workspace/agents/ directory."""
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id

    if not ws_path.exists():
        return []

    experts = get_topic_experts(ws_path)
    return [TopicExpert(**e) for e in experts]


@router.post("/{topic_id}/experts", response_model=TopicExpertResponse, status_code=201)
def add_expert_to_topic(topic_id: str, req: AddExpertRequest):
    """Add an expert to the topic.

    Supports three sources:
    - preset: Copy from global skills/
    - custom: Create with user-provided content
    - ai_generated: (handled by separate generate endpoint)
    """
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id
    agents_dir = ws_path / "agents"

    if req.source == "preset":
        if not req.preset_name:
            raise HTTPException(status_code=400, detail="preset_name is required for preset source")

        if req.preset_name not in EXPERT_SPECS:
            raise HTTPException(status_code=400, detail=f"Unknown preset expert: {req.preset_name}")

        # Copy from global libs (libs/experts/{source}/)
        spec = EXPERT_SPECS[req.preset_name]
        experts_dir = get_experts_dir()
        source_id = spec.get("source", "default")
        global_skill_file = experts_dir / source_id / spec["skill_file"]

        if not global_skill_file.exists():
            raise HTTPException(status_code=404, detail=f"Skill file not found: {source_id}/{spec['skill_file']}")

        expert_dir = agents_dir / req.preset_name
        expert_dir.mkdir(parents=True, exist_ok=True)

        role_file = expert_dir / "role.md"
        shutil.copy2(global_skill_file, role_file)

        # Add metadata
        add_expert_metadata(
            ws_path,
            expert_name=req.preset_name,
            label=EXPERT_SPECS.get(req.preset_name, {}).get("label", req.preset_name),
            description=spec["description"],
            source="preset",
            is_from_topic_creation=False,
        )

        # Sync expert_names in topic
        if req.preset_name not in topic.expert_names:
            update_topic(topic_id, TopicUpdate(expert_names=topic.expert_names + [req.preset_name]))

        return {"message": "Expert added from preset", "expert_name": req.preset_name}

    elif req.source == "custom":
        if not all([req.name, req.label, req.description, req.role_content]):
            raise HTTPException(
                status_code=400,
                detail="name, label, description, and role_content are required for custom source"
            )

        # Validate expert name
        if not req.name.replace("_", "").isalnum():
            raise HTTPException(
                status_code=400,
                detail="Expert name must contain only alphanumeric characters and underscores"
            )

        expert_dir = agents_dir / req.name
        if expert_dir.exists():
            raise HTTPException(status_code=400, detail=f"Expert already exists: {req.name}")

        expert_dir.mkdir(parents=True, exist_ok=True)
        role_file = expert_dir / "role.md"
        role_file.write_text(req.role_content, encoding="utf-8")

        # Add metadata
        add_expert_metadata(
            ws_path,
            expert_name=req.name,
            label=req.label,
            description=req.description,
            source="custom",
            is_from_topic_creation=False,
        )

        # Sync expert_names in topic
        if req.name not in topic.expert_names:
            update_topic(topic_id, TopicUpdate(expert_names=topic.expert_names + [req.name]))

        return {"message": "Custom expert created", "expert_name": req.name}

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source: {req.source}. Use 'preset' or 'custom'"
        )


@router.put("/{topic_id}/experts/{expert_name}", response_model=TopicExpertResponse)
def update_topic_expert(topic_id: str, expert_name: str, req: UpdateTopicExpertRequest):
    """Update expert's role content."""
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id
    expert_dir = ws_path / "agents" / expert_name

    if not expert_dir.exists():
        raise HTTPException(status_code=404, detail=f"Expert not found: {expert_name}")

    role_file = expert_dir / "role.md"
    role_file.write_text(req.role_content, encoding="utf-8")

    return {"message": "Expert updated", "expert_name": expert_name}


@router.delete("/{topic_id}/experts/{expert_name}", response_model=TopicExpertResponse)
def delete_topic_expert(topic_id: str, expert_name: str):
    """Delete an expert from the topic."""
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id
    expert_dir = ws_path / "agents" / expert_name

    if not expert_dir.exists():
        raise HTTPException(status_code=404, detail=f"Expert not found: {expert_name}")

    # Check if at least 1 expert will remain
    current_experts = get_topic_experts(ws_path)
    if len(current_experts) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the last expert. At least one expert must remain."
        )

    # Delete directory
    shutil.rmtree(expert_dir)

    # Remove from metadata
    remove_expert_metadata(ws_path, expert_name)

    # Sync expert_names in topic
    update_topic(topic_id, TopicUpdate(expert_names=[n for n in topic.expert_names if n != expert_name]))

    return {"message": "Expert deleted", "expert_name": expert_name}


@router.get("/{topic_id}/experts/{expert_name}/content")
def get_topic_expert_content(topic_id: str, expert_name: str):
    """Get the role content of a topic expert."""
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id
    role_file = ws_path / "agents" / expert_name / "role.md"

    if not role_file.exists():
        raise HTTPException(status_code=404, detail=f"Expert not found: {expert_name}")

    return {"role_content": role_file.read_text(encoding="utf-8")}


@router.post("/{topic_id}/experts/{expert_name}/share", response_model=TopicExpertResponse)
def share_expert_to_platform(topic_id: str, expert_name: str):
    """Share a topic-level expert to the platform library (topiclab_shared source)."""
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Reject if expert is built-in (default source); allow overwrite for topiclab_shared
    existing = EXPERT_SPECS.get(expert_name)
    if existing and existing.get("source") == "default":
        raise HTTPException(
            status_code=409,
            detail=f"Expert '{expert_name}' is built-in; cannot overwrite"
        )

    ws_base = get_workspace_base()
    ws_path = ws_base / "topics" / topic_id
    role_file = ws_path / "agents" / expert_name / "role.md"

    if not role_file.exists():
        raise HTTPException(status_code=404, detail=f"Expert not found: {expert_name}")

    experts = get_topic_experts(ws_path)
    expert_meta = next((e for e in experts if e["name"] == expert_name), None)
    if not expert_meta:
        raise HTTPException(status_code=404, detail="Expert metadata not found")

    # Write to libs/experts/topiclab_shared/ (user-shared, separate from built-in default)
    experts_dir = get_experts_dir()
    shared_dir = experts_dir / "topiclab_shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    skill_file_name = f"{expert_name}.md"
    (shared_dir / skill_file_name).write_text(role_file.read_text(encoding="utf-8"), encoding="utf-8")

    # Update topiclab_shared/meta.json (create if missing, like moderator_mode share)
    meta_path = shared_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = {
            "common_sections": "expert_common.md",
            "categories": {
                "topiclab": {
                    "id": "topiclab",
                    "name": "TopicLab",
                    "description": "User-shared experts from frontend",
                }
            },
            "experts": {},
        }
    meta.setdefault("experts", {})[expert_name] = {
        "id": expert_name,
        "source": "topiclab_shared",
        "name": expert_name,
        "label": expert_meta["label"],
        "description": expert_meta["description"],
        "category": "topiclab",
        "skill_file": skill_file_name,
        "perspective": expert_meta.get("perspective", expert_name),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Reload EXPERT_SPECS so subsequent requests see the new expert
    reload_expert_specs()
    from app.core.libs_service import invalidate_libs_cache
    invalidate_libs_cache()

    return {"message": "Expert shared to platform successfully", "expert_name": expert_name}


@router.post("/{topic_id}/experts/generate", response_model=GenerateExpertActionResponse)
async def generate_expert_for_topic(topic_id: str, req: GenerateExpertRequest):
    """AI-generate an expert role definition.

    Returns the generated content for user preview without creating the expert yet.
    """
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    try:
        expert_name, expert_label, role_content = await generate_expert(
            req.expert_name,  # may be None; AI will generate
            req.expert_label,
            req.description
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Return generated content for user preview (don't create expert yet)
    return {
        "message": "Expert generated successfully",
        "expert_name": expert_name,
        "expert_label": expert_label,
        "role_content": role_content,
    }
