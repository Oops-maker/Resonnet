# Agent Links Runtime

This document describes how `agent link` sessions run in the backend.

## Scope

- This runtime applies to `/agent-links/*` endpoints only.
- It does not change `/profile-helper/*` behavior.

## Runtime Model

`agent link` chat uses a **persistent `ClaudeSDKClient` subprocess per session**.  
Each session gets one long-lived Claude Code CLI process that is reused across all turns,
so the agent retains full conversation history natively — no prompt-injection required.

### Turn Flow

```
POST /agent-links/{slug}/chat
  → ensure session workspace exists (copy blueprint on first use)
  → acquire per-session asyncio.Lock  (serialises concurrent turns)
  → _get_or_create_client(session_id, options)
       ├─ existing client alive & clean → reuse subprocess
       └─ dead / dirty → disconnect, reconnect
  → client.query(user_message)          → writes to subprocess stdin
  → async for msg in client.receive_response()   → reads until ResultMessage
  → yield SSE events
  → mark turn complete, release lock
```

### Conversation Memory

Memory is maintained by two complementary mechanisms:

| Mechanism | How | Scope |
|-----------|-----|-------|
| **Subprocess conversation history** | `ClaudeSDKClient` keeps the Claude Code process alive between turns; the CLI process natively remembers prior messages | Within one uninterrupted subprocess lifetime |
| **Workspace file state** | Agent reads/writes files in `WORKSPACE_BASE/agent_links_sessions/<session_id>/`; subsequent turns (even fresh subprocesses) read those files | Persistent for the session lifetime |

### Session Lifecycle

```
Session starts
  → ClaudeSDKClient.connect()           (subprocess spawned)
  → subprocess idle, stdin open

Turn N
  → _turn_complete[session_id] = False  (dirty)
  → client.query(msg)
  → client.receive_response() → ... → ResultMessage
  → _turn_complete[session_id] = True   (clean)

Turn N+1 … (same subprocess, full history retained)

Subprocess dies (idle timeout / crash)
  → _get_or_create_client detects _query._closed == True or _turn_complete == False
  → disconnect old, connect new subprocess
  → conversation continues via workspace file state

Session expires (TTL / max-count eviction)
  → _cleanup_orphans() disconnects client, removes workspace directory
```

### Client State Tracking

| Variable | Type | Purpose |
|----------|------|---------|
| `_sdk_clients` | `dict[session_id, ClaudeSDKClient]` | Persistent subprocess per session |
| `_sdk_locks` | `dict[session_id, asyncio.Lock]` | Prevents concurrent turns on same session |
| `_turn_complete` | `dict[session_id, bool]` | True after ResultMessage; False means subprocess may be in dirty state |

Implementation files:

- `app/api/agent_links.py`
- `app/services/agent_links.py`
- `app/services/agent_links_runtime.py`
- `app/services/profile_helper/sessions.py`

## Session Workspace

- Blueprint root in metadata (`agent_workdir`) is a source template path.
- Actual runtime execution path is session-specific:
  - `agent_session_workdir` stored in session data.
- API returns runtime path in:
  - `POST /agent-links/{slug}/session` response `agent_workdir`
  - `POST /agent-links/{slug}/chat` header `X-Agent-Workdir`

## Cleanup Behavior

- Session cleanup is still controlled by in-memory session TTL and max-count:
  - `PROFILE_HELPER_SESSION_TTL_SECONDS`
  - `PROFILE_HELPER_SESSION_MAX_COUNT`
- `agent_links_runtime.ensure_session_workspace(...)` performs best-effort orphan cleanup:
  - any directory under `WORKSPACE_BASE/agent_links_sessions/` whose name is not in active session IDs is removed.
  - the corresponding `ClaudeSDKClient` subprocess is disconnected.

## Prompt and Model

- Prompt source:
  - runtime prefers loading rule content from the copied session workspace path.
  - fallback reads blueprint `rule_file_path` when session path cannot be resolved.
  - if missing/unreadable, runtime falls back to `META_SYSTEM_PROMPT`.
- Runtime always appends a workspace boundary system suffix:
  - only paths inside current session workspace are allowed
  - prefer relative paths from workspace root
  - reject absolute/outside paths and `..` traversal
- Model priority:
  1. request body `model`
  2. blueprint `default_model`
  3. agent config default (`ANTHROPIC_MODEL`/configured model)

## Tools and Permissions

- Allowed tools are set from `DEFAULT_ALLOWED_TOOLS`.
- Permission mode is `bypassPermissions` for agent link runtime.
- Runtime passes `cwd` and `add_dirs` as the session workspace.

## Blueprint Import Limits

`POST /agent-links/import` and `/agent-links/import/preview`:

- only `.zip` uploads are accepted
- max upload size is `5MB`
- zip path traversal is blocked (`Invalid zip structure`)
- preview returns up to 300 file paths plus total file count

## Session Workspace File Upload

`POST /agent-links/{slug}/files/upload`:

- uploads a file into current session workspace
- supports `target_path` (relative subdirectory; default `uploads`)
- blocks path escape outside workspace
- max file size is `30MB`
- uploaded files appear in the workspace; the agent reads them automatically on the next turn

## SSE Format

`POST /agent-links/{slug}/chat` returns `text/event-stream`.

- structured events:
  - `data: {"type":"assistant_delta","content":"..."}`
  - `data: {"type":"thinking","content":"..."}`
  - `data: {"type":"tool_call", ...}`
  - `data: {"type":"tool_result", ...}`
  - `data: {"type":"plan", ...}`
  - `data: {"type":"system", ...}`
  - `data: {"type":"result", ...}`
- error event:
  - `data: {"error":"..."}`
- end marker:
  - `data: [DONE]`

Nginx (frontend reverse proxy) must have `proxy_buffering off` on the `/topic-lab/api/` location block for SSE to stream through without buffering delay.

## Agent Link Chat UI Defaults

Current `agent link` chat page is intentionally simplified for end users:

- auto-sends a hidden first user message `"你好"` after session init, so the first assistant reply acts as welcome text
- by default only renders normal dialogue and `plan` blocks
- hides low-level runtime events (`thinking`, `tool_call`, `tool_result`, `system`) in this page
- Enter sends message, but IME composing Enter (Chinese input method candidate selection) does not send
- input box remains enabled during agent output (only the send button is disabled while loading)
- uploaded files are stored in the workspace `uploads/` subdirectory; file chips are read-only (paths are not injected into the chat input)
