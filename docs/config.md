# Configuration Guide

## Environment Variables

### Env File Location

The backend loads `.env` in this order:
1. **Project root** `./.env` (when backend is a submodule, e.g. `agent-topic-lab/.env`)
2. **Backend root** `backend/.env` (fallback)

Copy from `backend/.env.example` or project root `.env.example`, then edit with your API keys.

All libraries (experts, moderator_modes, mcps, assignable_skills, prompts) are loaded from `libs/`. No scenario preset.

---

Resonnet uses **two separate API configurations**; do not mix them:

### 1. Claude Agent SDK (Round Discussion Orchestration)

```bash
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
ANTHROPIC_MODEL=glm-4.7-flashx
```

**Use for:**
- Round discussion orchestration (`app/agent/discussion.py`)
- Multi-agent coordination via Claude Agent SDK

**Warning:** Do not use OpenAI/ZhipuAI coding-style APIs here.

---

### 2. AI Generation (Expert/Moderator Generation)

```bash
AI_GENERATION_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4
AI_GENERATION_API_KEY=your_key_here
AI_GENERATION_MODEL=glm-4-flash
```

**Use for:**
- Expert role generation (`app/agent/generation.py`)
- Moderator mode generation
- Direct HTTP API calls (not Anthropic SDK)

**Warning:** Do not use Claude Agent SDK–compatible APIs here.

---

### 3. Libs Cache (Hot-Reload)

```bash
LIBS_CACHE_TTL_SECONDS=60
```

- **Default**: 60 seconds. Meta for skills, mcps, moderator_modes is cached for this duration.
- **0**: Disable cache — always read from disk (full hot-reload, slower list endpoints).
- **>0**: Cache for N seconds; changes in `libs/` appear after TTL expires.

Manual invalidation: `POST /libs/invalidate-cache` clears cache immediately.

---

### 4. Sandbox Runtime (srt)

Resonnet prefers Anthropic sandbox-runtime (`srt`) for OS-level sandboxing.

```bash
SANDBOX_USE_SRT=true
```

- **Default**: `true`
- **Behavior**:
  - `true`: use `srt` when available (`PATH` contains `srt`)
  - `false`: skip srt and fall back to legacy backend (`sandbox-exec` on macOS / `bwrap` on Linux)
- **Scope**: expert reply, discussion, MCP subprocesses, and agent-links runtime.

Install and verify (Linux example):

```bash
# 1) Install Node.js + npm
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 2) Install srt CLI
sudo npm install -g @anthropic-ai/sandbox-runtime

# 3) Verify
which srt
srt --version
```

Notes:
- `srt` is not a Python dependency; `uv`/`pyproject.toml` do not install it.
- Docker image already installs `srt` and required Linux dependencies (see `Dockerfile`).
- `scripts/ci_local.sh` checks srt availability and tries npm installation when possible.

---

### 5. Semantic Search Default

```bash
ENABLE_SEMANTIC_SEARCH=true
```

- **Default**: `true`
- **Behavior**: controls default semantic search enablement.

---

### 6. MCP (Model Context Protocol)

MCP servers are configured in `libs/mcps/` (read-only, same structure as assignable_skills). **Accepted sources only**: npm, uvx, remote (mcp-remote). No local paths.

- Discussion API accepts `mcp_server_ids`; selected servers are copied to `workspace/topics/{id}/config/mcp.json` and passed to Claude Agent SDK.
- See [mcp-config.md](mcp-config.md) for API, validation, and pass-through flow.

---

### 7. Workspace and Libs (Docker)

```bash
WORKSPACE_BASE=/path/to/workspace
```

- TopicLab 集成模式下，topic 主业务数据库由 `topiclab-backend` 使用 `DATABASE_URL` 持有。
- Resonnet 仅保留 workspace，供 Agent SDK 运行上下文和非结构化产物（turn markdown、summary、generated images）使用。

For Docker deployments, both workspace and libs can be mounted for persistence:

| Volume | Env / Default | Purpose |
|--------|---------------|---------|
| `WORKSPACE_PATH` | `./backend/workspace` | Topic workspaces, posts, discussion artifacts |
| `LIBS_PATH` | `./backend/libs` | Experts, moderator modes, skills, MCP config; **user-shared** content in `topiclab_shared/` |

User-shared experts and moderator modes (from frontend "共享到角色库" / "共享到讨论方式库") are stored in `libs/experts/topiclab_shared/` and `libs/moderator_modes/topiclab_shared/` respectively. Mount `libs` to persist them across container restarts.

**When `LIBS_PATH` points to an empty directory** (e.g. `/data/libs` for persistence): the backend merges from both built-in (`/app/libs_builtin` in Docker) and the mount. Built-in `default` sources (experts, moderator modes, skills, MCP) are read from built-in; `topiclab_shared` and user writes go to the mount.

Default: `backend/workspace/`. For Docker, see volume mounts above.

---

### 5.1 TopicLab Executor Sync (per-round push)

When `topiclab_sync_url` is set in the executor request, Resonnet pushes discussion snapshot to TopicLab during discussion:

```bash
DISCUSSION_SYNC_INTERVAL_SECONDS=10.0
```

- **Default**: 10 seconds. How often to check workspace for new turns.
- **Push policy**: Only push when `turns_count` increases (new round completed), not every interval — reduces TopicLab DB load.
- **Range**: Minimum 1.0 second.

---

### 6. Profile Helper Auth Modes

Profile Helper supports pluggable auth modes:

```bash
# none | jwt | proxy
AUTH_MODE=none
AUTH_REQUIRED=false
AUTH_SERVICE_BASE_URL=http://topiclab-backend:8000
ACCOUNT_SYNC_ENABLED=false
```

- `AUTH_MODE=none`: default open-source mode; no account dependency.
- `AUTH_MODE=jwt`: validate bearer token via `topiclab-backend /auth/me`.
- `AUTH_MODE=proxy`: trust upstream gateway headers (`X-User-Id`, optional `X-Tenant-Id`, `X-User-Scopes`).
- `AUTH_REQUIRED`: in `jwt` mode, reject missing token when set to `true`.
- `ACCOUNT_SYNC_ENABLED`: whether `/profile-helper/publish-to-library` should sync records to external `digital_twins`.

---

## Rules

1. **Do not mix the two configs**
   - ANTHROPIC_* for Claude Agent SDK
   - AI_GENERATION_* for direct HTTP API calls

2. **No fallback**
   - Missing AI_GENERATION_API_KEY does not fall back to ANTHROPIC_API_KEY
   - Each config must be set explicitly

3. **Different API formats**
   - ANTHROPIC_BASE_URL expects Anthropic-compatible API
   - AI_GENERATION_BASE_URL expects OpenAI-compatible API (e.g. ZhipuAI)

## Validation

The app will not start if these are unset:
- AI_GENERATION_BASE_URL
- AI_GENERATION_API_KEY
- AI_GENERATION_MODEL
- ANTHROPIC_API_KEY

This is intentional to avoid misconfiguration.

## Unit Tests

Unit tests use conftest placeholders; no real API keys needed. See [testing.md](testing.md).

## AgentSDK Real-Env Testing

- Integration tests require a real `.env`; `ANTHROPIC_API_KEY` must not be empty or `test`
- Recommended:

```bash
pytest tests/test_agent_sdk.py -m integration -v -s
```

- Acceptance criteria:
  - API returns success
  - Topic/post/discussion 状态成功写入数据库
  - Discussion turn / summary artifacts written under `workspace/topics/{topic_id}/shared/`
