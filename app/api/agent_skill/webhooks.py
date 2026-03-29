"""Webhook endpoints for Agent Skill API."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentRecord, WebhookRecord
from app.db.session import get_db
from app.services.agent_skill.auth import get_current_agent

from .schemas import (
    CreateWebhookRequest,
    CreateWebhookResponse,
    ErrorResponse,
    Webhook,
    WebhookListResponse,
)

router = APIRouter()


def _webhook_to_schema(webhook: WebhookRecord) -> Webhook:
    """Convert WebhookRecord to Webhook schema."""
    return Webhook(
        id=webhook.id,
        url=webhook.url,
        events=webhook.events,
        is_active=webhook.is_active,
        created_at=webhook.created_at,
    )


@router.post(
    "",
    response_model=CreateWebhookResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse},
    },
)
def create_webhook(
    body: CreateWebhookRequest,
    agent: AgentRecord = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Create a webhook subscription.
    
    Returns the webhook secret for HMAC signature verification.
    The secret is only shown once - save it!
    """
    webhook_secret = secrets.token_hex(32)
    
    webhook = WebhookRecord(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        url=body.url,
        events=[e.value for e in body.events],
        secret=webhook_secret,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    
    return CreateWebhookResponse(
        webhook=_webhook_to_schema(webhook),
        secret=webhook_secret,
    )


@router.get(
    "",
    response_model=WebhookListResponse,
    responses={
        401: {"model": ErrorResponse},
    },
)
def list_webhooks(
    agent: AgentRecord = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """List all webhook subscriptions for the current agent."""
    stmt = (
        select(WebhookRecord)
        .where(WebhookRecord.agent_id == agent.id)
        .order_by(WebhookRecord.created_at.desc())
    )
    webhooks = list(db.execute(stmt).scalars().all())
    
    return WebhookListResponse(
        webhooks=[_webhook_to_schema(w) for w in webhooks],
    )


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def delete_webhook(
    webhook_id: str,
    agent: AgentRecord = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Delete a webhook subscription."""
    webhook = db.get(WebhookRecord, webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found.",
        )
    
    if webhook.agent_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own webhooks.",
        )
    
    db.delete(webhook)
    db.commit()
