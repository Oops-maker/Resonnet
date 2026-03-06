# Agent Links Runtime

This document describes how `agent link` sessions run in the backend.

## Scope

- This runtime applies to `/agent-links/*` endpoints only.
- It does not change `/profile-helper/*` behavior.

## Runtime Model

`agent link` chat uses Claude Agent SDK and creates an isolated workspace per session.

Flow:

1. Load blueprint metadata from `libs/agent_links/<slug>/agent.json`.
2. Create or bind an in-memory session (`profile_helper.sessions`).
3. Create a per-session working directory at:
   - `WORKSPACE_BASE/agent_links_sessions/<session_id>`
4. Copy full blueprint content into that directory (first use only).
5. Build system prompt from blueprint `rule_file_path` content.
6. Run Claude Agent SDK query stream and return SSE chunks.

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
- `agent_links_runtime.ensure_session_workspace(...)` performs best-effort orphan directory cleanup:
  - any directory under `WORKSPACE_BASE/agent_links_sessions/` whose name is not in active session IDs is removed.

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

## Agent Link Chat UI Defaults

Current `agent link` chat page is intentionally simplified for end users:

- auto-sends a hidden first user message `"你好"` after session init, so the first assistant reply acts as welcome text
- by default only renders normal dialogue and `plan` blocks
- hides low-level runtime events (`thinking`, `tool_call`, `tool_result`, `system`) in this page
- Enter sends message, but IME composing Enter (Chinese input method candidate selection) does not send
