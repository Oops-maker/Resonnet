"""Posts API: human posts and expert @mention replies."""

import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.agent.expert_reply import run_expert_reply_sandboxed
from app.agent.posts import load_post, load_posts, make_post, save_post
from app.agent.topic_sandbox import get_sandbox_status
from app.agent.workspace import get_topic_experts
from app.api.auth_bridge import get_current_auth_context
from app.core.config import get_workspace_base
from app.models.schemas import (
    CreatePostRequest,
    DiscussionStatus,
    MentionExpertRequest,
    MentionExpertResponse,
    Post,
)
from app.models.store import get_topic

logger = logging.getLogger(__name__)
router = APIRouter()


def _ws_path(topic_id: str) -> Path:
    return get_workspace_base() / "topics" / topic_id


def _resolve_author_name(req_author: str, auth_ctx: dict) -> str:
    """Prefer authenticated account identity over client-supplied author."""
    auth_context = auth_ctx.get("auth_context")
    user = auth_ctx.get("user")
    if auth_context is None or getattr(auth_context, "is_anonymous", True):
        return req_author
    if not isinstance(user, dict):
        return req_author

    username = str(user.get("username") or "").strip()
    phone = str(user.get("phone") or "").strip()
    user_id = user.get("id")
    return username or phone or (f"user-{user_id}" if user_id is not None else req_author)


# ---------------------------------------------------------------------------
# GET /topics/{topic_id}/posts
# ---------------------------------------------------------------------------

@router.get("/{topic_id}/posts", response_model=list[Post])
def list_posts(topic_id: str):
    """Return all posts for a topic (human + agent), sorted by created_at."""
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return load_posts(_ws_path(topic_id))


# ---------------------------------------------------------------------------
# POST /topics/{topic_id}/posts
# ---------------------------------------------------------------------------

@router.post("/{topic_id}/posts", response_model=Post, status_code=201)
def create_post(
    topic_id: str,
    req: CreatePostRequest,
    auth_ctx: dict = Depends(get_current_auth_context),
):
    """Create a human post."""
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    author_name = _resolve_author_name(req.author, auth_ctx)
    post = make_post(
        topic_id=topic_id,
        author=author_name,
        author_type="human",
        body=req.body,
        in_reply_to_id=req.in_reply_to_id,
        status="completed",
    )
    save_post(_ws_path(topic_id), post)
    return post


# ---------------------------------------------------------------------------
# POST /topics/{topic_id}/posts/mention
# ---------------------------------------------------------------------------

def _run_expert_reply_sync(
    ws_path: Path,
    topic_id: str,
    topic_title: str,
    expert_name: str,
    expert_label: str,
    user_post_id: str,
    user_author: str,
    user_question: str,
    reply_post_id: str,
    reply_created_at: str,
) -> None:
    """Thread target: runs the expert reply agent (sandboxed when available)."""
    try:
        run_expert_reply_sandboxed(
            ws_path=ws_path,
            topic_id=topic_id,
            topic_title=topic_title,
            expert_name=expert_name,
            expert_label=expert_label,
            user_post_id=user_post_id,
            user_author=user_author,
            user_question=user_question,
            reply_post_id=reply_post_id,
            reply_created_at=reply_created_at,
        )
    except Exception:
        logger.error(
            f"Background expert reply failed: topic={topic_id} expert={expert_name}",
            exc_info=True,
        )


@router.post("/{topic_id}/posts/mention", response_model=MentionExpertResponse, status_code=202)
def mention_expert(
    topic_id: str,
    req: MentionExpertRequest,
    auth_ctx: dict = Depends(get_current_auth_context),
):
    """User @mentions an expert.

    Saves the human post immediately, creates a pending reply placeholder,
    then launches the expert agent in a daemon thread with its own event loop
    (avoids conflicts with uvicorn's event loop).
    """
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    ws_path = _ws_path(topic_id)

    # --- Topic sandbox isolation guard ---
    # Block expert @mention while a discussion is actively running on this topic.
    # The discussion agent writes to the shared workspace; allowing concurrent
    # expert replies could cause confusion and pollute the audit trail.
    if topic.discussion_status == DiscussionStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="Discussion is running; wait for it to finish before @mentioning experts",
        )
    # Secondary check against the in-memory sandbox registry (defence-in-depth).
    sandbox_st = get_sandbox_status(topic_id, ws_path)
    if sandbox_st.get("status") == "running" and sandbox_st.get("operation") == "discussion":
        raise HTTPException(
            status_code=409,
            detail="Topic sandbox is busy with a discussion; try again later",
        )

    # Validate expert is in this topic's workspace
    experts = get_topic_experts(ws_path)
    expert_meta = next((e for e in experts if e["name"] == req.expert_name), None)
    if not expert_meta:
        raise HTTPException(
            status_code=400,
            detail=f"Expert '{req.expert_name}' is not in this topic. "
                   f"Available: {[e['name'] for e in experts]}",
        )

    expert_label = expert_meta.get("label", req.expert_name)
    author_name = _resolve_author_name(req.author, auth_ctx)

    # 1. Save the human post
    user_post = make_post(
        topic_id=topic_id,
        author=author_name,
        author_type="human",
        body=req.body,
        in_reply_to_id=req.in_reply_to_id,
        status="completed",
    )
    save_post(ws_path, user_post)

    # 2. Create a pending placeholder for the expert reply
    reply_post = make_post(
        topic_id=topic_id,
        author=req.expert_name,
        author_type="agent",
        body="",
        expert_name=req.expert_name,
        expert_label=expert_label,
        in_reply_to_id=user_post["id"],
        status="pending",
    )
    save_post(ws_path, reply_post)

    # 3. Launch the agent in a daemon thread with its own event loop.
    #    threading.Thread avoids conflicts with uvicorn's running event loop.
    t = threading.Thread(
        target=_run_expert_reply_sync,
        kwargs=dict(
            ws_path=ws_path,
            topic_id=topic_id,
            topic_title=topic.title,
            expert_name=req.expert_name,
            expert_label=expert_label,
            user_post_id=user_post["id"],
            user_author=author_name,
            user_question=req.body,
            reply_post_id=reply_post["id"],
            reply_created_at=reply_post["created_at"],
        ),
        daemon=True,
    )
    t.start()
    logger.info(f"Started expert reply thread {t.name} for {req.expert_name}")

    return MentionExpertResponse(
        user_post=Post(**user_post),
        reply_post_id=reply_post["id"],
        status="pending",
    )


# ---------------------------------------------------------------------------
# GET /topics/{topic_id}/posts/mention/{reply_post_id}
# ---------------------------------------------------------------------------

@router.get("/{topic_id}/posts/mention/{reply_post_id}", response_model=Post)
def get_reply_status(topic_id: str, reply_post_id: str):
    """Poll the status of an expert reply post (pending / completed / failed)."""
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    post = load_post(_ws_path(topic_id), reply_post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Reply post not found")
    return post
