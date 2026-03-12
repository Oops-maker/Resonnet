"""Topics API endpoints."""

from hashlib import sha256
from pathlib import Path
import re
import tempfile

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError

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
    TopicListItem,
    TopicUpdate,
)
from app.models.store import (
    close_topic,
    create_topic,
    get_topic,
    list_topics,
    set_topic_moderator_mode_fields,
    update_topic,
)

router = APIRouter()
_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*]\(([^)\s]+(?:\s+\"[^\"]*\")?)\)")
_PREVIEW_CACHE_DIRNAME = ".generated_image_previews"
_PREVIEW_DEFAULT_QUALITY = 72
_PREVIEW_MAX_DIMENSION = 2048
_PREVIEW_DEFAULT_FORMAT = "webp"


def _resolve_generated_image_path(topic_id: str, asset_path: str) -> Path:
    """Resolve a generated image path under shared/generated_images/ safely."""
    generated_dir = (get_workspace_base() / "topics" / topic_id / "shared" / "generated_images").resolve()
    target = (generated_dir / asset_path).resolve()
    if generated_dir != target and generated_dir not in target.parents:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return target


def _preview_cache_dir(topic_id: str) -> Path:
    cache_dir = get_workspace_base() / "topics" / topic_id / "shared" / _PREVIEW_CACHE_DIRNAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _build_preview_cache_path(
    topic_id: str,
    asset_key: str,
    source_path: Path,
    *,
    width: int | None,
    height: int | None,
    quality: int,
    output_format: str,
) -> Path:
    stat = source_path.stat()
    cache_key = sha256(
        f"{asset_key}|{stat.st_mtime_ns}|{stat.st_size}|{width}|{height}|{quality}|{output_format}".encode("utf-8")
    ).hexdigest()[:20]
    width_part = width if width is not None else "auto"
    height_part = height if height is not None else "auto"
    filename = f"{source_path.stem}.{cache_key}.{width_part}x{height_part}.q{quality}.{output_format}"
    return _preview_cache_dir(topic_id) / filename


def _create_generated_image_preview(
    topic_id: str,
    asset_path: str,
    *,
    width: int | None,
    height: int | None,
    quality: int,
    output_format: str,
) -> Path:
    source_path = _resolve_generated_image_path(topic_id, asset_path)
    cache_path = _build_preview_cache_path(
        topic_id,
        asset_path,
        source_path,
        width=width,
        height=height,
        quality=quality,
        output_format=output_format,
    )
    if cache_path.exists():
        return cache_path

    max_size = (
        width if width is not None else _PREVIEW_MAX_DIMENSION,
        height if height is not None else _PREVIEW_MAX_DIMENSION,
    )

    try:
        with Image.open(source_path) as image:
            preview = ImageOps.exif_transpose(image)
            preview.load()
            preview = preview.copy()
            preview.thumbnail(max_size, Image.Resampling.LANCZOS)
            if preview.mode not in {"RGB", "RGBA"}:
                preview = preview.convert("RGBA" if "A" in preview.getbands() else "RGB")

            with tempfile.NamedTemporaryFile(
                dir=cache_path.parent,
                prefix=f"{cache_path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
            try:
                preview.save(
                    tmp_path,
                    format=output_format.upper(),
                    quality=quality,
                    method=6,
                )
                tmp_path.replace(cache_path)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=415, detail="Unsupported image format") from exc

    return cache_path


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


def _extract_first_markdown_image(markdown: str | None) -> str:
    if not markdown:
        return ""
    match = _MARKDOWN_IMAGE_PATTERN.search(markdown)
    if not match:
        return ""
    raw = match.group(1).strip()
    path_only = raw.split('"')[0].strip() if '"' in raw else raw
    if path_only.startswith("<") and path_only.endswith(">"):
        return path_only[1:-1].strip()
    return path_only


def _build_topic_list_item(topic: Topic) -> TopicListItem:
    preview_image = _extract_first_markdown_image(topic.body)
    if not preview_image and topic.discussion_result:
        preview_image = _extract_first_markdown_image(topic.discussion_result.discussion_summary)
    if not preview_image and topic.discussion_result:
        preview_image = _extract_first_markdown_image(topic.discussion_result.discussion_history)

    return TopicListItem(
        id=topic.id,
        session_id=topic.session_id,
        title=topic.title,
        body=topic.body,
        status=topic.status,
        discussion_status=topic.discussion_status,
        created_at=topic.created_at,
        updated_at=topic.updated_at,
        moderator_mode_id=topic.moderator_mode_id,
        moderator_mode_name=topic.moderator_mode_name,
        preview_image=preview_image or None,
    )


@router.get("", response_model=list[TopicListItem])
def get_topics():
    return [_build_topic_list_item(topic) for topic in list_topics()]


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
    set_topic_moderator_mode_fields(
        topic.id,
        mode_id="standard",
        mode_name=PRESET_MODES.get("standard", {}).get("name", "Standard Round Table"),
    )

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
def get_topic_generated_image(
    topic_id: str,
    asset_path: str,
    w: int | None = Query(default=None, ge=1, le=_PREVIEW_MAX_DIMENSION),
    h: int | None = Query(default=None, ge=1, le=_PREVIEW_MAX_DIMENSION),
    q: int = Query(default=_PREVIEW_DEFAULT_QUALITY, ge=30, le=95),
    fm: str | None = Query(default=None, pattern="^webp$"),
):
    """Serve generated discussion images from shared/generated_images/."""
    if w is None and h is None and fm is None:
        return FileResponse(
            _resolve_generated_image_path(topic_id, asset_path),
            headers={"Cache-Control": "public, max-age=300"},
        )

    output_format = fm or _PREVIEW_DEFAULT_FORMAT
    return FileResponse(
        _create_generated_image_preview(
            topic_id,
            asset_path,
            width=w,
            height=h,
            quality=q,
            output_format=output_format,
        ),
        media_type=f"image/{output_format}",
        headers={"Cache-Control": "public, max-age=300"},
    )


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
