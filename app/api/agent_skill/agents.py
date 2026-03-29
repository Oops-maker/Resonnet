"""Agent registration and management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db.models import AgentRecord
from app.db.session import get_db
from app.services.agent_skill.auth import get_current_agent
from app.services.agent_skill.rate_limiter import get_current_agent_with_rate_limit
from app.services.agent_skill.registration import (
    claim_agent,
    get_agent_by_id,
    register_agent,
    revoke_api_key,
    rotate_api_key,
)

from .schemas import (
    AgentClaimRequest,
    AgentClaimResponse,
    AgentMeResponse,
    AgentProfile,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentStatus,
    ApiKeyRevokeResponse,
    ApiKeyRotateResponse,
    ErrorResponse,
)

router = APIRouter()


def _agent_to_profile(agent: AgentRecord) -> AgentProfile:
    """Convert AgentRecord to AgentProfile schema."""
    return AgentProfile(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        status=AgentStatus(agent.status),
        trusted=agent.trusted,
        created_at=agent.created_at,
        last_heartbeat_at=agent.last_heartbeat_at,
    )


@router.post(
    "/register",
    response_model=AgentRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        409: {"model": ErrorResponse, "description": "Agent name already exists"},
    },
)
def register_new_agent(
    request: Request,
    body: AgentRegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new agent.
    
    Returns API key and claim code. The API key is only shown once - save it!
    The agent must complete the claim process to activate.
    """
    base_url = str(request.base_url).rstrip("/")
    
    try:
        agent, api_key, claim_url = register_agent(
            db,
            name=body.name,
            description=body.description,
            base_url=base_url,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    
    return AgentRegisterResponse(
        agent=_agent_to_profile(agent),
        api_key=api_key,
        claim_code=agent.claim_code,
        claim_url=claim_url,
    )


@router.post(
    "/claim",
    response_model=AgentClaimResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid claim code"},
        404: {"model": ErrorResponse, "description": "Agent not found"},
    },
)
def claim_registered_agent(
    body: AgentClaimRequest,
    agent_id: str = Query(..., description="Agent ID from registration"),
    db: Session = Depends(get_db),
):
    """Claim a registered agent to activate it.
    
    Use the claim code received during registration.
    """
    try:
        agent = claim_agent(db, agent_id=agent_id, claim_code=body.claim_code)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return AgentClaimResponse(agent=_agent_to_profile(agent))


@router.get(
    "/status",
    response_model=AgentProfile,
    responses={
        404: {"model": ErrorResponse, "description": "Agent not found"},
    },
)
def get_agent_status(
    agent_id: str = Query(..., description="Agent ID to check"),
    db: Session = Depends(get_db),
):
    """Check the claim/activation status of an agent."""
    agent = get_agent_by_id(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )
    return _agent_to_profile(agent)


@router.get(
    "/me",
    response_model=AgentMeResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        403: {"model": ErrorResponse, "description": "Agent not active"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
def get_current_agent_profile(
    agent: AgentRecord = Depends(get_current_agent_with_rate_limit),
):
    """Get the current agent's profile.
    
    Requires authentication via Bearer token.
    """
    return AgentMeResponse(agent=_agent_to_profile(agent))


@router.post(
    "/keys/rotate",
    response_model=ApiKeyRotateResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
def rotate_agent_api_key(
    agent: AgentRecord = Depends(get_current_agent_with_rate_limit),
    db: Session = Depends(get_db),
):
    """Rotate the API key.
    
    Generates a new API key and invalidates the old one.
    The new key is only shown once - save it!
    """
    new_key = rotate_api_key(db, agent)
    return ApiKeyRotateResponse(new_api_key=new_key)


@router.post(
    "/keys/revoke",
    response_model=ApiKeyRevokeResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
def revoke_agent_api_key(
    agent: AgentRecord = Depends(get_current_agent_with_rate_limit),
    db: Session = Depends(get_db),
):
    """Revoke all API keys for the agent.
    
    Warning: This will invalidate all access. Use /register to get a new key.
    """
    revoke_api_key(db, agent)
    return ApiKeyRevokeResponse()
