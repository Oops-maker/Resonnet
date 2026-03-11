"""Pydantic schemas for data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TopicStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class TopicMode(str, Enum):
    HUMAN_AGENT = "human_agent"
    DISCUSSION = "discussion"
    BOTH = "both"


class DiscussionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AuthorType(str, Enum):
    HUMAN = "human"
    AGENT = "agent"


# --- Topic models ---

class TopicCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(default="", min_length=0)  # optional; default empty
    category: Optional[str] = None
    # mode, num_rounds, expert_names are configured after creation inside the topic


class TopicUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    body: Optional[str] = Field(None, min_length=0)
    category: Optional[str] = None
    expert_names: Optional[list[str]] = None


class DiscussionResult(BaseModel):
    discussion_history: str
    discussion_summary: str
    turns_count: int
    cost_usd: Optional[float] = None
    completed_at: str


class Topic(BaseModel):
    id: str
    session_id: str = ""  # same as id; maps to workspace/topics/{session_id}/
    title: str
    body: str
    category: Optional[str]
    status: TopicStatus
    mode: TopicMode
    num_rounds: int = 5
    expert_names: list[str] = Field(default_factory=list)
    discussion_result: Optional[DiscussionResult] = None
    discussion_status: DiscussionStatus = DiscussionStatus.PENDING
    created_at: str
    updated_at: str
    # Populated by API from config/moderator_mode.json (not in topic.json)
    moderator_mode_id: Optional[str] = None
    moderator_mode_name: Optional[str] = None


# --- Comment models ---

class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1)
    author_type: AuthorType = AuthorType.HUMAN


class Comment(BaseModel):
    id: str
    topic_id: str
    author: str
    author_type: AuthorType
    body: str
    mentions: list[str] = Field(default_factory=list)
    created_at: str


# --- Discussion API models ---

# 默认启用的全量工具（Bash 因安全未包含）。API 可通过 allowed_tools 覆盖
DEFAULT_ALLOWED_TOOLS = [
    "Read", "Write", "Edit", "Glob", "Grep", "Task", "WebFetch", "WebSearch",
]


class StartDiscussionRequest(BaseModel):
    num_rounds: int = Field(default=5, ge=1, le=20)
    max_turns: int = Field(default=10000, ge=10, le=10000)
    max_budget_usd: float = Field(default=5.0, ge=0.1)  # no upper limit
    model: str | None = None
    allowed_tools: list[str] | None = Field(
        default=None,
        description="启用的工具列表，如 Read, Write, Edit, Glob, Grep, Task, WebFetch, WebSearch。不传则使用默认全量",
    )
    skill_list: list[str] = Field(
        default_factory=list,
        description="可选的 skill 列表（id），从全局 assignable_skills 拷贝到工作区 config/skills/，供主持人分配给专家",
    )
    mcp_server_ids: list[str] | None = Field(
        default=None,
        description="MCP 服务器 ID 列表，不传则默认使用所有可用的 MCP 服务器",
    )


class DiscussionProgress(BaseModel):
    completed_turns: int = 0
    total_turns: int = 0          # num_rounds × num_experts; 0 = unknown
    current_round: int = 0        # highest round seen so far
    latest_speaker: str = ""      # label of most recently written turn


class DiscussionStatusResponse(BaseModel):
    status: DiscussionStatus
    result: Optional[DiscussionResult] = None
    progress: Optional[DiscussionProgress] = None


# --- Expert models ---

class ExpertInfo(BaseModel):
    name: str
    label: str
    description: str
    skill_file: str
    skill_content: str
    perspective: str = ""  # 学科视角，如 physics, biology
    category: Optional[str] = None  # 分类 id，用于分组（与 skills/mcps 一致）
    category_name: Optional[str] = None  # 分类显示名
    source: Optional[str] = None  # default=内置, topiclab_shared=共享


class ExpertUpdateRequest(BaseModel):
    skill_content: str = Field(..., min_length=1)


# --- Topic-level expert models ---

class TopicExpert(BaseModel):
    """Topic-level expert info (read from workspace)."""
    name: str                           # physicist | economist_custom
    label: str                          # Physics Researcher | Economist
    description: str                    # Expert bio
    source: str                         # "preset" | "custom" | "ai_generated"
    role_file: str                      # agents/physicist/role.md
    added_at: str                       # When added
    is_from_topic_creation: bool = False  # From topic creation selection


class AddExpertRequest(BaseModel):
    """Add expert request."""
    source: str = Field(..., pattern="^(preset|custom|ai_generated)$")
    # From preset
    preset_name: Optional[str] = None
    # Manual
    name: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    role_content: Optional[str] = None
    # AI-generated
    user_prompt: Optional[str] = None


class GenerateExpertRequest(BaseModel):
    """AI generate expert request."""
    expert_name: Optional[str] = Field(None, min_length=2, max_length=50, pattern=r"^[a-z_]+$")
    expert_label: str = Field(..., min_length=2, max_length=50)
    description: str = Field(..., min_length=1, max_length=1000)


class GenerateModeratorModeRequest(BaseModel):
    """AI generate moderator mode request."""
    prompt: str = Field(..., min_length=1, max_length=1000)


# --- Moderator mode models ---

class ModeratorModeInfo(BaseModel):
    """Moderator mode info."""
    id: str
    name: str
    description: str
    num_rounds: int
    convergence_strategy: str


class ModeratorModeConfig(BaseModel):
    """Topic moderator mode config."""
    mode_id: str
    num_rounds: int = Field(default=5, ge=1, le=20)
    custom_prompt: Optional[str] = None
    skill_list: list[str] = Field(default_factory=list, description="Selected skill ids for discussion")
    mcp_server_ids: list[str] = Field(default_factory=list, description="Selected MCP server ids for discussion")
    model: Optional[str] = Field(default=None, description="Preferred model for discussion")


class SetModeratorModeRequest(BaseModel):
    """Set moderator mode request."""
    mode_id: str
    num_rounds: int = Field(default=5, ge=1, le=20)
    custom_prompt: Optional[str] = None
    skill_list: Optional[list[str]] = None
    mcp_server_ids: Optional[list[str]] = None
    model: Optional[str] = None


class ShareModeratorModeRequest(BaseModel):
    """Share topic's custom moderator mode to platform library."""
    mode_id: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z0-9_]+$")
    name: Optional[str] = Field(None, min_length=2, max_length=80)
    description: Optional[str] = Field(None, min_length=1, max_length=500)


# --- Post models ---

class Post(BaseModel):
    id: str
    topic_id: str
    author: str
    author_type: AuthorType
    expert_name: Optional[str] = None
    expert_label: Optional[str] = None
    body: str
    mentions: list[str] = Field(default_factory=list)
    in_reply_to_id: Optional[str] = None
    status: str = "completed"   # "pending" | "completed" | "failed"
    created_at: str


class CreatePostRequest(BaseModel):
    author: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    in_reply_to_id: Optional[str] = None


class MentionExpertRequest(BaseModel):
    author: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    expert_name: str = Field(..., min_length=1)
    in_reply_to_id: Optional[str] = None


class MentionExpertResponse(BaseModel):
    user_post: Post
    reply_post_id: str          # id of the pending agent reply post
    status: str = "pending"


# --- Topic expert mutation response models ---

class UpdateTopicExpertRequest(BaseModel):
    role_content: str = Field(..., min_length=1)


class TopicExpertResponse(BaseModel):
    message: str
    expert_name: str


class GenerateExpertActionResponse(BaseModel):
    message: str
    expert_name: str
    expert_label: str
    role_content: str


class GenerateModeratorModeResponse(BaseModel):
    message: str
    custom_prompt: str
    config: ModeratorModeConfig


# --- MCP models ---

class MCPServerConfig(BaseModel):
    """Single MCP server config. Supports stdio (npm, uvx) and streamableHttp types."""
    # Stdio type (npm, uvx, npx)
    command: str | None = Field(None, min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None
    
    # Remote HTTP type (streamableHttp)
    type: str | None = Field(None, description="Connection type: 'stdio' or 'streamableHttp'")
    baseUrl: str | None = Field(None, description="Base URL for streamableHttp type")
    headers: dict[str, str] | None = Field(None, description="HTTP headers for streamableHttp type")
    description: str | None = Field(None, description="Server description")
    isActive: bool | None = Field(None, description="Whether the server is active")
    name: str | None = Field(None, description="Display name")
    
    def is_stdio(self) -> bool:
        """Check if this is a stdio type server."""
        return self.type is None or self.type == "stdio" or self.command is not None
    
    def is_http(self) -> bool:
        """Check if this is a streamableHttp type server."""
        return self.type == "streamableHttp" and self.baseUrl is not None


class MCPConfig(BaseModel):
    """MCP config (Cursor-compatible mcpServers format)."""
    mcpServers: dict[str, MCPServerConfig] = Field(default_factory=dict)
