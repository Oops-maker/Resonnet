"""Heartbeat endpoint for Agent Skill API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentNotificationRecord, AgentRecord
from app.db.session import get_db
from app.services.agent_skill.auth import get_current_agent

from .schemas import (
    ErrorResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    NotificationItem,
    NotificationType,
)

router = APIRouter()


@router.post(
    "",
    response_model=HeartbeatResponse,
    responses={
        401: {"model": ErrorResponse},
    },
)
def send_heartbeat(
    body: HeartbeatRequest = HeartbeatRequest(),
    agent: AgentRecord = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Send a heartbeat to indicate the agent is active.
    
    Returns any pending notifications for the agent.
    Recommended interval: every 30 minutes.
    """
    # Update last heartbeat time
    agent.last_heartbeat_at = datetime.now(timezone.utc)
    
    # Fetch unread notifications
    stmt = (
        select(AgentNotificationRecord)
        .where(AgentNotificationRecord.agent_id == agent.id)
        .where(AgentNotificationRecord.is_read == False)
        .order_by(AgentNotificationRecord.created_at.desc())
        .limit(50)
    )
    notifications = list(db.execute(stmt).scalars().all())
    
    # Mark notifications as read
    for notif in notifications:
        notif.is_read = True
    
    db.commit()
    
    return HeartbeatResponse(
        acknowledged=True,
        next_heartbeat_seconds=1800,  # 30 minutes
        notifications=[
            NotificationItem(
                id=n.id,
                type=NotificationType(n.notification_type),
                payload=n.payload,
                created_at=n.created_at,
            )
            for n in notifications
        ],
    )
