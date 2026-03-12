"""Topics API endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.agent.experts import EXPERT_SPECS
from app.agent.moderator_modes import PRESET_MODES, load_moderator_mode_config, save_moderator_mode_config
from app.agent.workspace import (
    add_expert_metadata,
    copy_skills_to_workspace,
    ensure_topic_workspace,
    read_discussion_history,
)
from app.core.config import get_workspace_base
from app.core.topic_defaults import DEFAULT_TOPIC_EXPERT_NAMES, DEFAULT_TOPIC_SKILL_IDS
from app.models.schemas import (
    DiscussionResult,
    DiscussionStatus,
    Topic,
    TopicCreate,
    TopicUpdate,
)
from app.models.store import (
    close_topic,
    create_topic,
    get_topic,
    list_topics,
    update_topic,
)

router = APIRouter()


def _resolve_generated_image_path(topic_id: str, asset_path: str) -> Path:
    """Resolve a generated image path under shared/generated_images/ safely."""
    generated_dir = (get_workspace_base() / "topics" / topic_id / "shared" / "generated_images").resolve()
    target = (generated_dir / asset_path).resolve()
    if generated_dir != target and generated_dir not in target.parents:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return target


def _augment_topic_with_moderator_mode(topic: Topic) -> Topic:
    """Add moderator_mode_id and moderator_mode_name from workspace config."""
    try:
        ws_base = get_workspace_base()
        ws_path = ws_base / "topics" / topic.id
        cfg = load_moderator_mode_config(ws_path)
        mode_id = cfg.get("mode_id", "standard")
        topic.moderator_mode_id = mode_id
        if mode_id == "custom":
            topic.moderator_mode_name = "自定义模式"
        else:
            topic.moderator_mode_name = PRESET_MODES.get(mode_id, {}).get("name", mode_id)
    except Exception:
        topic.moderator_mode_id = "standard"
        topic.moderator_mode_name = PRESET_MODES.get("standard", {}).get("name", "Standard Round Table")
    return topic


@router.get("", response_model=list[Topic])
def get_topics():
    topics = list_topics()
    for t in topics:
        _augment_topic_with_moderator_mode(t)
    return topics


@router.post("", response_model=Topic, status_code=201)
def post_topic(data: TopicCreate):
    topic = create_topic(data)
    # Create full workspace layout immediately (shared/ + agents/)
    ws_base = get_workspace_base()
    ws_path = ensure_topic_workspace(ws_base, topic.id)

    copied_skills = copy_skills_to_workspace(ws_path, DEFAULT_TOPIC_SKILL_IDS)
    save_moderator_mode_config(ws_path, {
        "mode_id": "standard",
        "num_rounds": topic.num_rounds,
        "custom_prompt": None,
        "skill_list": copied_skills,
        "mcp_server_ids": [],
        "model": None,
    })

    for expert_name in DEFAULT_TOPIC_EXPERT_NAMES:
        spec = EXPERT_SPECS.get(expert_name)
        if not spec:
            continue
        add_expert_metadata(
            ws_path,
            expert_name=expert_name,
            label=spec.get("label", expert_name),
            description=spec.get("description", ""),
            source="preset",
            is_from_topic_creation=True,
        )
    return topic


@router.get("/{topic_id}", response_model=Topic)
def get_topic_detail(topic_id: str):
    topic = get_topic(topic_id)
    if topic:
        _augment_topic_with_moderator_mode(topic)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # When running, read live discussion history from workspace
    if topic.discussion_status == DiscussionStatus.RUNNING:
        try:
            ws_base = get_workspace_base()
            ws_path = ws_base / "topics" / topic_id
            history = read_discussion_history(ws_path)
            if history:
                if not topic.discussion_result:
                    topic.discussion_result = DiscussionResult(
                        discussion_history=history,
                        discussion_summary="",
                        turns_count=0,
                        cost_usd=None,
                        completed_at="",
                    )
                else:
                    topic.discussion_result.discussion_history = history
        except Exception:
            pass

    return topic


@router.get("/{topic_id}/assets/generated_images/{asset_path:path}")
def get_topic_generated_image(topic_id: str, asset_path: str):
    """Serve generated discussion images from shared/generated_images/."""
    return FileResponse(_resolve_generated_image_path(topic_id, asset_path))


@router.patch("/{topic_id}", response_model=Topic)
def patch_topic(topic_id: str, data: TopicUpdate):
    topic = update_topic(topic_id, data)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.post("/{topic_id}/close", response_model=Topic)
def close_topic_endpoint(topic_id: str):
    topic = close_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic
