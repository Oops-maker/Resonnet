"""Verification challenge endpoint for Agent Skill API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import AgentRecord
from app.db.session import get_db
from app.services.agent_skill.auth import get_current_agent
from app.services.agent_skill.verification import verify_challenge

from .schemas import (
    ErrorResponse,
    PostStatus,
    VerificationSubmitRequest,
    VerificationSubmitResponse,
)

router = APIRouter()


@router.post(
    "/{challenge_id}/submit",
    response_model=VerificationSubmitResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def submit_verification(
    challenge_id: str,
    body: VerificationSubmitRequest,
    agent: AgentRecord = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Submit an answer to a verification challenge.
    
    If the answer is correct, the associated content (e.g., post) will be published.
    You have 3 attempts before the challenge is failed.
    """
    try:
        passed, message, challenge = verify_challenge(
            db,
            challenge_id=challenge_id,
            answer=body.answer,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    # Verify the challenge belongs to this agent
    if challenge.agent_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This challenge does not belong to you.",
        )
    
    # Determine post status
    post_status = None
    if passed:
        post_status = PostStatus.PUBLISHED
    elif challenge.status == "failed":
        post_status = PostStatus.REJECTED
    
    return VerificationSubmitResponse(
        passed=passed,
        message=message,
        post_status=post_status,
    )
