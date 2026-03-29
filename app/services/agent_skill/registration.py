"""Agent registration and claim service."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentApiKeyRecord, AgentRecord

from .auth import generate_api_key


def generate_claim_code() -> str:
    """Generate a claim code like 'CLAIM-XXXX-XXXX'."""
    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    return f"CLAIM-{part1}-{part2}"


def register_agent(
    db: Session,
    *,
    name: str,
    description: str | None = None,
    base_url: str,
) -> tuple[AgentRecord, str, str]:
    """Register a new agent.
    
    Args:
        db: Database session
        name: Unique agent name
        description: Optional description
        base_url: Base URL for generating claim URL
    
    Returns:
        Tuple of (agent_record, api_key, claim_url)
    
    Raises:
        ValueError: If agent name already exists
    """
    # Check if name already exists
    existing = db.execute(
        select(AgentRecord).where(AgentRecord.name == name)
    ).scalar_one_or_none()
    
    if existing:
        raise ValueError(f"Agent name '{name}' is already registered.")
    
    # Generate IDs and secrets
    agent_id = str(uuid.uuid4())
    claim_code = generate_claim_code()
    api_key, key_hash, key_prefix = generate_api_key()
    
    # Create agent record
    now = datetime.now(timezone.utc)
    agent = AgentRecord(
        id=agent_id,
        name=name,
        description=description,
        status="pending_claim",
        claim_code=claim_code,
        trusted=False,
        created_at=now,
        last_heartbeat_at=None,
    )
    db.add(agent)
    
    # Create API key record
    api_key_record = AgentApiKeyRecord(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        key_hash=key_hash,
        prefix=key_prefix,
        is_active=True,
        created_at=now,
        last_used_at=None,
    )
    db.add(api_key_record)
    
    db.commit()
    db.refresh(agent)
    
    claim_url = f"{base_url}/api/v1/agents/claim?agent_id={agent_id}"
    
    return agent, api_key, claim_url


def claim_agent(db: Session, *, agent_id: str, claim_code: str) -> AgentRecord:
    """Claim an agent to activate it.
    
    Args:
        db: Database session
        agent_id: Agent ID
        claim_code: The claim code provided at registration
    
    Returns:
        Updated agent record
    
    Raises:
        ValueError: If claim code is invalid or agent not found
    """
    agent = db.get(AgentRecord, agent_id)
    
    if not agent:
        raise ValueError("Agent not found.")
    
    if agent.status != "pending_claim":
        raise ValueError("Agent is already claimed or suspended.")
    
    if agent.claim_code != claim_code:
        raise ValueError("Invalid claim code.")
    
    # Activate the agent
    agent.status = "active"
    agent.claim_code = None  # Clear claim code after use
    db.commit()
    db.refresh(agent)
    
    return agent


def get_agent_by_name(db: Session, name: str) -> AgentRecord | None:
    """Get an agent by name."""
    return db.execute(
        select(AgentRecord).where(AgentRecord.name == name)
    ).scalar_one_or_none()


def get_agent_by_id(db: Session, agent_id: str) -> AgentRecord | None:
    """Get an agent by ID."""
    return db.get(AgentRecord, agent_id)


def rotate_api_key(db: Session, agent: AgentRecord) -> str:
    """Rotate API key for an agent.
    
    Deactivates all existing keys and creates a new one.
    
    Returns:
        New API key (full key)
    """
    # Deactivate existing keys
    for key_record in agent.api_keys:
        key_record.is_active = False
    
    # Generate new key
    api_key, key_hash, key_prefix = generate_api_key()
    
    new_key_record = AgentApiKeyRecord(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        key_hash=key_hash,
        prefix=key_prefix,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        last_used_at=None,
    )
    db.add(new_key_record)
    db.commit()
    
    return api_key


def revoke_api_key(db: Session, agent: AgentRecord) -> None:
    """Revoke all API keys for an agent."""
    for key_record in agent.api_keys:
        key_record.is_active = False
    db.commit()
