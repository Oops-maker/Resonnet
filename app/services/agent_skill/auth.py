"""API Key authentication for Agent Skill API."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentApiKeyRecord, AgentRecord
from app.db.session import get_db


# API key format: rsk_live_<32 random hex chars>
API_KEY_PREFIX = "rsk_live_"
API_KEY_RANDOM_LENGTH = 32


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.
    
    Returns:
        Tuple of (full_key, key_hash, prefix)
    """
    random_part = secrets.token_hex(API_KEY_RANDOM_LENGTH // 2)
    full_key = f"{API_KEY_PREFIX}{random_part}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    prefix = full_key[:12]  # rsk_live_xxx
    return full_key, key_hash, prefix


def hash_api_key(key: str) -> str:
    """Hash an API key for storage/comparison."""
    return hashlib.sha256(key.encode()).hexdigest()


class AgentApiKeyAuth(HTTPBearer):
    """FastAPI dependency for API key authentication."""
    
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
    
    async def __call__(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=True)),
        db: Session = Depends(get_db),
    ) -> AgentRecord:
        """Validate API key and return the associated agent."""
        if credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Use 'Bearer <api_key>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        api_key = credentials.credentials
        if not api_key.startswith(API_KEY_PREFIX):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key format.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        key_hash = hash_api_key(api_key)
        
        # Find the API key record
        stmt = (
            select(AgentApiKeyRecord)
            .where(AgentApiKeyRecord.key_hash == key_hash)
            .where(AgentApiKeyRecord.is_active == True)
        )
        key_record = db.execute(stmt).scalar_one_or_none()
        
        if not key_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get the agent
        agent = db.get(AgentRecord, key_record.agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Agent not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if agent.status == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent is suspended.",
            )
        
        if agent.status == "pending_claim":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent is not yet claimed. Complete the claim process first.",
            )
        
        # Update last_used_at
        key_record.last_used_at = datetime.now(timezone.utc)
        db.commit()
        
        return agent


# Dependency instance
get_current_agent = AgentApiKeyAuth()


def get_optional_agent(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[AgentRecord]:
    """Optional agent authentication - returns None if no valid auth provided."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    api_key = auth_header[7:]  # Remove "Bearer "
    if not api_key.startswith(API_KEY_PREFIX):
        return None
    
    key_hash = hash_api_key(api_key)
    
    stmt = (
        select(AgentApiKeyRecord)
        .where(AgentApiKeyRecord.key_hash == key_hash)
        .where(AgentApiKeyRecord.is_active == True)
    )
    key_record = db.execute(stmt).scalar_one_or_none()
    
    if not key_record:
        return None
    
    agent = db.get(AgentRecord, key_record.agent_id)
    if not agent or agent.status != "active":
        return None
    
    # Update last_used_at
    key_record.last_used_at = datetime.now(timezone.utc)
    db.commit()
    
    return agent
