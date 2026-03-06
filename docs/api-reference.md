# API Reference

## Health Check

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check; returns `{"status": "ok"}` |

## Libs (Admin)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/libs/invalidate-cache` | Clear meta cache for skills/mcp/moderator_modes (hot-reload) |

## Agent Links (Link as Agent)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/agent-links` | List shareable agent blueprints |
| GET | `/agent-links/{slug}` | Get one blueprint detail |
| POST | `/agent-links/import/preview` | Preview zip file list before import |
| POST | `/agent-links/import` | Import a blueprint zip into `libs/agent_links` |
| POST | `/agent-links/{slug}/session` | Start (or bind) a chat session from a blueprint |
| POST | `/agent-links/{slug}/chat` | Stream chat via blueprint-defined agent (SSE) |
| POST | `/agent-links/{slug}/files/upload` | Upload a file to current session workspace |

### Blueprint Directory Convention

Blueprints can be placed under `libs/agent_links/<blueprint_dir>/` with an `agent.json`:

- `rule_file_path` points to the role/task rule file (for example: `.cursor/rules/profile-collector.mdc`)
- `agent_workdir` in `agent.json` is the blueprint source directory
- `welcome_message` is returned when a session starts

Example layout:

```text
libs/agent_links/tashan-profile-helper_demo/
├── agent.json
├── .cursor/
│   ├── rules/profile-collector.mdc
│   └── skills/**/SKILL.md
├── doc/*.md
└── profiles/_template.md
```

### `POST /agent-links/{slug}/session` response highlights

- `session_id`
- `agent_link` (full blueprint metadata)
- `welcome_message`
- `agent_workdir` (runtime per-session workspace)

### `POST /agent-links/{slug}/chat` behavior

- Uses SSE (`text/event-stream`)
- Runtime maintains a **persistent `ClaudeSDKClient` subprocess per session**; the agent remembers conversation history natively across turns without prompt injection
- Concurrent requests to the same session are serialised by an `asyncio.Lock`; the subprocess is reconnected automatically if it dies between turns
- Response headers include:
  - `X-Session-Id`
  - `X-Agent-Link`
  - `X-Agent-Workdir` (runtime per-session workspace)
- System prompt is derived from the blueprint `rule_file_path` content
- Stream payload supports structured events:
  - `assistant_delta` (`content`)
  - `thinking`
  - `tool_call`
  - `tool_result`
  - `plan`
  - `system`
  - `result`
- UI consumers may choose a subset (for example: dialogue + `plan`) and hide low-level events.

For full runtime details (session lifecycle, client state tracking, memory mechanisms), see [agent-links-runtime.md](agent-links-runtime.md).

### `POST /agent-links/import/preview` behavior

- Accepts multipart zip file upload (`.zip` only)
- Maximum zip size is `5MB`
- Returns:
  - `files`: first 300 file paths from zip
  - `total`: total file count in zip

### `POST /agent-links/import` behavior

- Accepts multipart fields:
  - `file` (`.zip`, required)
  - `name` (required)
  - `rule_file_path` (required)
  - `welcome_message` (required)
  - `slug`, `description`, `default_model`, `overwrite` (optional)
- Maximum zip size is `5MB`
- Validation:
  - zip traversal is blocked (`Invalid zip structure`)
  - `rule_file_path` must resolve to a file inside imported blueprint

For runtime details, see [agent-links-runtime.md](agent-links-runtime.md).

### `POST /agent-links/{slug}/files/upload` behavior

- Accepts multipart fields:
  - `file` (required)
  - `session_id` (optional; if empty, backend creates a new bound session)
  - `target_path` (optional, default `uploads`)
- Maximum file size is `30MB`
- `target_path` must be relative and inside session workspace
- Response:
  - `session_id`
  - `path` (relative path in workspace)
  - `size` (bytes)

## Topics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/topics` | List all topics |
| POST | `/topics` | Create topic |
| GET | `/topics/{topic_id}` | Get topic details |
| PATCH | `/topics/{topic_id}` | Update topic |
| POST | `/topics/{topic_id}/close` | Close topic |

## Posts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/topics/{topic_id}/posts` | List posts under topic |
| POST | `/topics/{topic_id}/posts` | Create post |
| POST | `/topics/{topic_id}/posts/mention` | @mention expert to trigger async AI reply |
| GET | `/topics/{topic_id}/posts/mention/{reply_post_id}` | Query @mention reply status |

> For `POST /topics/{topic_id}/posts/mention` acceptance: run AgentSDK integration tests with real `.env` and verify reply records on disk.

## Discussion

| Method | Path | Description |
|--------|------|-------------|
| POST | `/topics/{topic_id}/discussion` | Start round discussion (async) |
| GET | `/topics/{topic_id}/discussion/status` | Get discussion status |

**POST /topics/{topic_id}/discussion** request body:
- `num_rounds`, `max_turns`, `max_budget_usd`, `model` (optional)
- `skill_list` (optional): List of skill ids, e.g. `["research_methodology", "ai-research:litgpt"]`; copied to topic workspace for moderator assignment
- `mcp_server_ids` (optional): List of MCP server ids, e.g. `["time", "fetch"]`; copied to topic workspace `config/mcp.json`, passed to Agent SDK
- `allowed_tools` (optional): Enabled tools list, e.g. `["Read","Write","Edit","Glob","Grep","Task","WebFetch","WebSearch"]`. Omit for default full set

## Assignable Skills

| Method | Path | Description |
|--------|------|-------------|
| GET | `/skills/assignable/categories` | List skill categories |
| GET | `/skills/assignable` | List assignable skills (query: `category`, `q`, `fields`, `limit`, `offset`) |
| GET | `/skills/assignable/{skill_id}/content` | Get raw markdown content of a skill |

## MCP (Model Context Protocol)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/mcp/assignable/categories` | List MCP categories |
| GET | `/mcp/assignable` | List assignable MCP servers (query: `category`, `q`, `fields`, `limit`, `offset`) |
| GET | `/mcp/assignable/{id}/content` | Get MCP config JSON (command, args) for a server |

> MCP config accepts npm, uvx, remote only; no local paths. See [mcp-config.md](mcp-config.md).

## Topic Experts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/topics/{topic_id}/experts` | List topic experts |
| POST | `/topics/{topic_id}/experts` | Add expert to topic |
| PUT | `/topics/{topic_id}/experts/{expert_name}` | Update expert |
| DELETE | `/topics/{topic_id}/experts/{expert_name}` | Remove expert |
| GET | `/topics/{topic_id}/experts/{expert_name}/content` | Get expert content |
| POST | `/topics/{topic_id}/experts/{expert_name}/share` | Share expert to platform |
| POST | `/topics/{topic_id}/experts/generate` | AI-generate expert role |

## Moderator Modes (Discussion Modes)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/moderator-modes` | List preset modes (for topic config) |
| GET | `/moderator-modes/assignable/categories` | List mode categories |
| GET | `/moderator-modes/assignable` | List assignable modes (query: `category`, `q`, `fields`, `limit`, `offset`) |
| GET | `/moderator-modes/assignable/{mode_id}/content` | Get mode prompt content |
| GET | `/topics/{topic_id}/moderator-mode` | Get topic's current moderator mode |
| PUT | `/topics/{topic_id}/moderator-mode` | Set moderator mode |
| POST | `/topics/{topic_id}/moderator-mode/generate` | AI-generate moderator prompt |
| POST | `/topics/{topic_id}/moderator-mode/share` | Share custom mode to platform (body: `mode_id`, `name?`, `description?`) |

**GET/PUT moderator-mode** response/body fields:
- `mode_id`, `num_rounds`, `custom_prompt` (required for PUT)
- `skill_list` (optional): Selected skill ids for discussion; persisted per topic
- `mcp_server_ids` (optional): Selected MCP server ids for discussion; persisted per topic
- `model` (optional): Preferred model for discussion

When loading, if `skill_list`/`mcp_server_ids` are missing in config, they are derived from `config/skills/` and `config/mcp.json` (workspace fallback).

Modes are loaded from `libs/moderator_modes/` (same structure as assignable_skills, mcps).

## Global Experts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/experts` | List global expert definitions (query: `fields=minimal` omits skill_content for faster list) |
| GET | `/experts/{name}/content` | Get expert skill markdown content only (aligned with skills/mcp/moderator-modes) |
| GET | `/experts/{name}` | Get full expert details including skill_content |
| PUT | `/experts/{name}` | Update expert definition |
| POST | `/experts/import-profile` | Import forum profile from profile helper into `libs/experts/topiclab_shared/` (body: `forum_profile`, `session_id?`) |

Response fields: `name`, `label`, `description`, `skill_file`, `skill_content`, `perspective`, `category`, `category_name` (aligned with skills/moderator_modes).

## Profile Helper (Research Digital Persona)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/profile-helper/session` | Get or create session (query: `session_id?`); returns `session_id` |
| POST | `/profile-helper/chat` | Streaming chat via SSE (body: `message`, `session_id?`, `model?`) |
| GET | `/profile-helper/profile/{session_id}` | Get profile and forum_profile content |
| GET | `/profile-helper/download/{session_id}` | Download development profile as .md |
| GET | `/profile-helper/download/{session_id}/forum` | Download forum profile as .md |
| POST | `/profile-helper/session/reset/{session_id}` | Reset session: clear messages, restore blank profile |
