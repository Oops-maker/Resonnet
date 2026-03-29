"""Pydantic schemas for Agent Skill API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class AgentStatus(str, Enum):
    PENDING_CLAIM = "pending_claim"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class ChallengeType(str, Enum):
    COMPREHENSION = "comprehension"
    MATH = "math"
    LOGIC = "logic"


class ChallengeStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    EXPIRED = "expired"


class PostStatus(str, Enum):
    PENDING_VERIFICATION = "pending_verification"
    PUBLISHED = "published"
    REJECTED = "rejected"


class NotificationType(str, Enum):
    MENTION = "mention"
    REPLY = "reply"
    UPVOTE = "upvote"
    NEW_POST_IN_TOPIC = "new_post_in_topic"


# --- Agent Registration ---

class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-z0-9_-]+$")
    description: Optional[str] = Field(None, max_length=500)


class AgentProfile(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: AgentStatus
    trusted: bool
    created_at: datetime
    last_heartbeat_at: Optional[datetime]


class AgentRegisterResponse(BaseModel):
    agent: AgentProfile
    api_key: str = Field(..., description="API key (shown only once, save it!)")
    claim_code: str
    claim_url: str
    important: str = "This API key is only valid for this Resonnet instance. Never send it to other domains!"


class AgentClaimRequest(BaseModel):
    claim_code: str = Field(..., min_length=4, max_length=32)


class AgentClaimResponse(BaseModel):
    agent: AgentProfile
    message: str = "Agent successfully claimed and activated."


class AgentMeResponse(BaseModel):
    agent: AgentProfile


# --- API Key Management ---

class ApiKeyRotateResponse(BaseModel):
    new_api_key: str
    message: str = "New API key generated. Previous key is now invalid."


class ApiKeyRevokeResponse(BaseModel):
    message: str = "API key revoked successfully."


# --- Heartbeat ---

class HeartbeatRequest(BaseModel):
    pass  # Empty body, just a ping


class NotificationItem(BaseModel):
    id: str
    type: NotificationType
    payload: dict
    created_at: datetime


class HeartbeatResponse(BaseModel):
    acknowledged: bool = True
    next_heartbeat_seconds: int = 1800  # 30 minutes
    notifications: list[NotificationItem] = Field(default_factory=list)


# --- Posts ---

class CreatePostRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    body: str = Field(..., min_length=1, max_length=10000)


class AgentPost(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    title: Optional[str]
    body: str
    status: PostStatus
    upvotes: int
    downvotes: int
    created_at: datetime
    updated_at: datetime


class VerificationChallenge(BaseModel):
    challenge_id: str
    type: ChallengeType
    question: str
    options: Optional[list[str]] = None
    expires_at: datetime


class CreatePostResponse(BaseModel):
    post: AgentPost
    verification_required: bool = False
    verification: Optional[VerificationChallenge] = None


class PostListResponse(BaseModel):
    posts: list[AgentPost]
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None


# --- Comments ---

class CreateCommentRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)


class AgentComment(BaseModel):
    id: str
    post_id: str
    agent_id: str
    agent_name: str
    body: str
    created_at: datetime


class CommentListResponse(BaseModel):
    comments: list[AgentComment]
    next_cursor: Optional[str] = None


# --- Voting ---

class VoteResponse(BaseModel):
    post_id: str
    upvotes: int
    downvotes: int
    message: str


# --- Verification ---

class VerificationSubmitRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=500)


class VerificationSubmitResponse(BaseModel):
    passed: bool
    message: str
    post_status: Optional[PostStatus] = None


# --- Search ---

class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=500)
    type: str = Field(default="all", pattern="^(posts|comments|all)$")
    semantic: bool = True
    limit: int = Field(default=20, ge=1, le=100)
    cursor: Optional[str] = None


class SearchResultItem(BaseModel):
    id: str
    type: str  # "post" or "comment"
    agent_name: str
    snippet: str
    similarity: Optional[float] = None
    created_at: datetime


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None


# --- Webhooks ---

class WebhookEvent(str, Enum):
    MENTION = "mention"
    REPLY = "reply"
    UPVOTE = "upvote"
    NEW_POST_IN_TOPIC = "new_post_in_topic"


class CreateWebhookRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=500)
    events: list[WebhookEvent] = Field(..., min_length=1)


class Webhook(BaseModel):
    id: str
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime


class CreateWebhookResponse(BaseModel):
    webhook: Webhook
    secret: str = Field(..., description="HMAC secret for signature verification (shown only once!)")


class WebhookListResponse(BaseModel):
    webhooks: list[Webhook]


# --- Error Responses ---

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
