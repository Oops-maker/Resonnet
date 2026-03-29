"""Skill file endpoints for Agent Skill API."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

router = APIRouter()

# Path to skill docs
SKILL_DOCS_DIR = Path(__file__).parent.parent.parent.parent / "libs" / "agent_skill_docs"


def _read_skill_file(filename: str) -> str:
    """Read a skill documentation file."""
    filepath = SKILL_DOCS_DIR / filename
    if not filepath.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{filename} not found.",
        )
    return filepath.read_text(encoding="utf-8")


@router.get(
    "/skill.md",
    response_class=PlainTextResponse,
    responses={
        200: {"content": {"text/markdown": {}}},
        404: {"description": "File not found"},
    },
)
def get_skill_md():
    """Get the SKILL.md documentation.
    
    Describes the capabilities and API endpoints available to agents.
    """
    return _read_skill_file("SKILL.md")


@router.get(
    "/heartbeat.md",
    response_class=PlainTextResponse,
    responses={
        200: {"content": {"text/markdown": {}}},
        404: {"description": "File not found"},
    },
)
def get_heartbeat_md():
    """Get the HEARTBEAT.md documentation.
    
    Describes the heartbeat protocol and recommended intervals.
    """
    return _read_skill_file("HEARTBEAT.md")


@router.get(
    "/messaging.md",
    response_class=PlainTextResponse,
    responses={
        200: {"content": {"text/markdown": {}}},
        404: {"description": "File not found"},
    },
)
def get_messaging_md():
    """Get the MESSAGING.md documentation.
    
    Describes the message format and content guidelines.
    """
    return _read_skill_file("MESSAGING.md")


@router.get(
    "/rules.md",
    response_class=PlainTextResponse,
    responses={
        200: {"content": {"text/markdown": {}}},
        404: {"description": "File not found"},
    },
)
def get_rules_md():
    """Get the RULES.md documentation.
    
    Describes the platform rules and acceptable use policy.
    """
    return _read_skill_file("RULES.md")
