"""Main router for Agent Skill API."""

from fastapi import APIRouter

from . import agents, heartbeat, posts, search, skill_files, verification, webhooks

router = APIRouter()

# Agent registration and management
router.include_router(
    agents.router,
    prefix="/agents",
    tags=["agent-skill-agents"],
)

# Heartbeat
router.include_router(
    heartbeat.router,
    prefix="/heartbeat",
    tags=["agent-skill-heartbeat"],
)

# Posts and comments
router.include_router(
    posts.router,
    prefix="/posts",
    tags=["agent-skill-posts"],
)

# Search
router.include_router(
    search.router,
    prefix="/search",
    tags=["agent-skill-search"],
)

# Verification challenges
router.include_router(
    verification.router,
    prefix="/verification",
    tags=["agent-skill-verification"],
)

# Webhooks
router.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["agent-skill-webhooks"],
)

# Skill documentation files
router.include_router(
    skill_files.router,
    tags=["agent-skill-docs"],
)
