"""Agent Topic Lab API entry point."""

import logging
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    agent_links as agent_links_router,
    agent_skill as agent_skill_router,
    discussion as discussion_router,
    executor as executor_router,
    experts,
    libs as libs_router,
    mcp as mcp_router,
    moderator_modes,
    posts,
    profile_helper as profile_helper_router,
    skills as skills_router,
    topic_experts,
    topics,
)
from app.core.config import get_resonnet_mode
from app.db.migrations import run_db_migrations
from app.models.store import initialize_store_from_workspace


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_resonnet_mode() == "standalone":
        run_db_migrations()
        initialize_store_from_workspace()

    yield


app = FastAPI(
    title="Resonnet API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if get_resonnet_mode() == "standalone":
    app.include_router(topics.router, prefix="/topics", tags=["topics"])
    app.include_router(posts.router, prefix="/topics", tags=["posts"])
    app.include_router(discussion_router.router, prefix="/topics", tags=["discussion"])
app.include_router(topic_experts.router, prefix="/topics", tags=["topic-experts"])
app.include_router(moderator_modes.router, tags=["moderator-modes"])
app.include_router(skills_router.router, prefix="/skills", tags=["skills"])
app.include_router(experts.router, prefix="/experts", tags=["experts"])
app.include_router(mcp_router.router, prefix="/mcp", tags=["mcp"])
app.include_router(libs_router.router, prefix="/libs", tags=["libs"])
app.include_router(profile_helper_router.router, prefix="/profile-helper", tags=["profile-helper"])
app.include_router(agent_links_router.router, prefix="/agent-links", tags=["agent-links"])
app.include_router(executor_router.router, prefix="/executor", tags=["executor"])

# Agent Skill API (external agent integration)
app.include_router(agent_skill_router.router, prefix="/api/v1", tags=["agent-skill"])


@app.get("/health")
def health():
    return {"status": "ok"}
