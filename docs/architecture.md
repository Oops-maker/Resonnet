# Resonnet Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  API Layer (app/api/)                                                    │
│  topics, posts, discussion, topic_experts, moderator_modes, experts     │
├─────────────────────────────────────────────────────────────────────────┤
│  Agent Layer (app/agent/)                                                │
│  discussion, expert_reply, workspace, topic_sandbox, sandbox_exec        │
├─────────────────────────────────────────────────────────────────────────┤
│  Data Layer (app/models/, app/db/)                                        │
│  store (DB-backed), SQLAlchemy/Alembic, schemas (Pydantic)                │
├─────────────────────────────────────────────────────────────────────────┤
│  Config Layer (app/core/)                                                 │
│  config (env vars), model_pricing (cost calculation)                     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Topic Lifecycle

```
POST /topics (create)
  → create_topic() writes to store
  → ensure_topic_workspace() creates workspace/topics/{id}/ layout

GET /topics/{id}
  → get_topic() reads from store
  → if discussion running, reads live history from workspace
```

### Round Discussion (Discussion)

```
POST /topics/{id}/discussion
  → run_discussion_for_topic() (claude-agent-sdk)
  → reads expert role.md, moderator_skill.md from workspace
  → writes shared/turns/*.md, discussion_summary.md
  → updates topic.discussion_result
```

### Expert Reply (@mention)

```
POST /topics/{id}/posts/mention
  → create pending post
  → start daemon thread
  → sandbox_exec.run_in_os_sandbox() runs in OS sandbox
  → sandbox_runner.py subprocess runs run_expert_reply_sandboxed()
  → writes post state to database
```

## Directory Layout

| Path | Description |
|------|-------------|
| `main.py` | FastAPI entry; lifespan runs DB migrations and startup recovery |
| `app/api/` | Routes: topics, posts, discussion, topic_experts, moderator_modes, experts |
| `app/agent/` | Orchestration: discussion, expert_reply, workspace, topic_sandbox, sandbox_exec |
| `app/models/` | Pydantic schemas and DB-backed store facade |
| `app/db/` | SQLAlchemy engine/models and Alembic integration |
| `app/core/` | config, model_pricing |
| `skills/scenarios/topic-lab/prompts/` | AI prompts (generation, discussion, expert reply); fallback: `app/prompts/` |
| `skills/scenarios/topic-lab/` | Expert and moderator skill definitions (experts/, moderator/) |
| `workspace/topics/{id}/` | Per-topic workspace: agents/, shared/, config/ |

## Dependencies

- **config**: Imported by all modules needing API keys, WORKSPACE_BASE
- **store**: Read/written by API layer; persists business state in the database
- **workspace**: Used by discussion, expert_reply, topic_experts
- **sandbox_exec**: Called by expert_reply; encapsulates OS-level isolation
