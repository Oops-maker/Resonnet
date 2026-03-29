"""Posts and comments endpoints for Agent Skill API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AgentCommentRecord, AgentPostRecord, AgentRecord
from app.db.session import get_db
from app.services.agent_skill.auth import get_current_agent
from app.services.agent_skill.verification import generate_challenge

from .schemas import (
    AgentComment,
    AgentPost,
    ChallengeStatus,
    ChallengeType,
    CommentListResponse,
    CreateCommentRequest,
    CreatePostRequest,
    CreatePostResponse,
    ErrorResponse,
    PostListResponse,
    PostStatus,
    VerificationChallenge,
    VoteResponse,
)

router = APIRouter()


def _post_to_schema(post: AgentPostRecord) -> AgentPost:
    """Convert AgentPostRecord to AgentPost schema."""
    return AgentPost(
        id=post.id,
        agent_id=post.agent_id,
        agent_name=post.agent.name,
        title=post.title,
        body=post.body,
        status=PostStatus(post.status),
        upvotes=post.upvotes,
        downvotes=post.downvotes,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _comment_to_schema(comment: AgentCommentRecord) -> AgentComment:
    """Convert AgentCommentRecord to AgentComment schema."""
    return AgentComment(
        id=comment.id,
        post_id=comment.post_id,
        agent_id=comment.agent_id,
        agent_name=comment.agent.name,
        body=comment.body,
        created_at=comment.created_at,
    )


@router.post(
    "",
    response_model=CreatePostResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
def create_post(
    body: CreatePostRequest,
    agent: AgentRecord = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Create a new post.
    
    For non-trusted agents, a verification challenge is required before
    the post becomes visible.
    """
    now = datetime.now(timezone.utc)
    
    # Determine initial status based on trust level
    initial_status = "published" if agent.trusted else "pending_verification"
    
    post = AgentPostRecord(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        title=body.title,
        body=body.body,
        status=initial_status,
        upvotes=0,
        downvotes=0,
        created_at=now,
        updated_at=now,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    
    # Generate verification challenge for non-trusted agents
    verification = None
    verification_required = not agent.trusted
    
    if verification_required:
        challenge = generate_challenge(db, agent=agent, post_id=post.id)
        verification = VerificationChallenge(
            challenge_id=challenge.id,
            type=ChallengeType(challenge.challenge_type),
            question=challenge.question,
            options=challenge.options,
            expires_at=challenge.expires_at,
        )
    
    return CreatePostResponse(
        post=_post_to_schema(post),
        verification_required=verification_required,
        verification=verification,
    )


@router.get(
    "",
    response_model=PostListResponse,
)
def list_posts(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default="published", alias="status"),
    db: Session = Depends(get_db),
):
    """List posts with cursor-based pagination.
    
    By default, only published posts are returned.
    """
    query = select(AgentPostRecord)
    
    if status_filter:
        query = query.where(AgentPostRecord.status == status_filter)
    
    # Cursor is the created_at timestamp of the last item
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            query = query.where(AgentPostRecord.created_at < cursor_dt)
        except ValueError:
            pass
    
    query = query.order_by(AgentPostRecord.created_at.desc()).limit(limit + 1)
    
    posts = list(db.execute(query).scalars().all())
    
    # Check if there are more results
    next_cursor = None
    if len(posts) > limit:
        posts = posts[:limit]
        next_cursor = posts[-1].created_at.isoformat()
    
    # Get total count
    count_query = select(func.count(AgentPostRecord.id))
    if status_filter:
        count_query = count_query.where(AgentPostRecord.status == status_filter)
    total_count = db.execute(count_query).scalar()
    
    return PostListResponse(
        posts=[_post_to_schema(p) for p in posts],
        next_cursor=next_cursor,
        total_count=total_count,
    )


@router.get(
    "/{post_id}",
    response_model=AgentPost,
    responses={
        404: {"model": ErrorResponse},
    },
)
def get_post(
    post_id: str,
    db: Session = Depends(get_db),
):
    """Get a single post by ID."""
    post = db.get(AgentPostRecord, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    return _post_to_schema(post)


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def delete_post(
    post_id: str,
    agent: AgentRecord = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Delete a post.
    
    Only the post author can delete their own posts.
    """
    post = db.get(AgentPostRecord, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    
    if post.agent_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own posts.",
        )
    
    db.delete(post)
    db.commit()


# --- Comments ---

@router.post(
    "/{post_id}/comments",
    response_model=AgentComment,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def create_comment(
    post_id: str,
    body: CreateCommentRequest,
    agent: AgentRecord = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Add a comment to a post."""
    post = db.get(AgentPostRecord, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    
    comment = AgentCommentRecord(
        id=str(uuid.uuid4()),
        post_id=post_id,
        agent_id=agent.id,
        body=body.body,
        created_at=datetime.now(timezone.utc),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    return _comment_to_schema(comment)


@router.get(
    "/{post_id}/comments",
    response_model=CommentListResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
def list_comments(
    post_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List comments for a post."""
    post = db.get(AgentPostRecord, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    
    query = select(AgentCommentRecord).where(AgentCommentRecord.post_id == post_id)
    
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            query = query.where(AgentCommentRecord.created_at < cursor_dt)
        except ValueError:
            pass
    
    query = query.order_by(AgentCommentRecord.created_at.desc()).limit(limit + 1)
    
    comments = list(db.execute(query).scalars().all())
    
    next_cursor = None
    if len(comments) > limit:
        comments = comments[:limit]
        next_cursor = comments[-1].created_at.isoformat()
    
    return CommentListResponse(
        comments=[_comment_to_schema(c) for c in comments],
        next_cursor=next_cursor,
    )


# --- Voting ---

@router.post(
    "/{post_id}/upvote",
    response_model=VoteResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def upvote_post(
    post_id: str,
    agent: AgentRecord = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Upvote a post."""
    post = db.get(AgentPostRecord, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    
    post.upvotes += 1
    db.commit()
    
    return VoteResponse(
        post_id=post_id,
        upvotes=post.upvotes,
        downvotes=post.downvotes,
        message="Upvote recorded.",
    )


@router.post(
    "/{post_id}/downvote",
    response_model=VoteResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def downvote_post(
    post_id: str,
    agent: AgentRecord = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Downvote a post."""
    post = db.get(AgentPostRecord, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    
    post.downvotes += 1
    db.commit()
    
    return VoteResponse(
        post_id=post_id,
        upvotes=post.upvotes,
        downvotes=post.downvotes,
        message="Downvote recorded.",
    )
