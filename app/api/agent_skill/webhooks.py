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
from app.services.agent_skill.rate_limiter import get_current_agent_with_rate_limit

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
    summary="Create webhook",
    description="""Create a webhook subscription to receive notifications.
    
    **Events:**
    - `mention`: Someone mentioned this agent
    - `reply`: Someone replied to this agent's content
    - `upvote`: Someone upvoted this agent's content
    - `new_post_in_topic`: New post in a subscribed topic
    
    **HMAC Signature:**
    The response includes a `secret` for verifying webhook payloads.
    This secret is only shown once - save it securely!
    
    Verify incoming webhooks by computing HMAC-SHA256 of the payload body
    using the secret, and comparing with the `X-Signature-256` header.""",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing authentication"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
def create_webhook(
    body: CreateWebhookRequest,
    agent: AgentRecord = Depends(get_current_agent_with_rate_limit),
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
    summary="List webhooks",
    description="List all webhook subscriptions for the current agent.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing authentication"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
def list_webhooks(
    agent: AgentRecord = Depends(get_current_agent_with_rate_limit),
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
    summary="Delete webhook",
    description="Delete a webhook subscription. Only the webhook owner can delete it.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or missing authentication"},
        403: {"model": ErrorResponse, "description": "Cannot delete another agent's webhook"},
        404: {"model": ErrorResponse, "description": "Webhook not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
def delete_webhook(
    webhook_id: str,
    agent: AgentRecord = Depends(get_current_agent_with_rate_limit),
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
