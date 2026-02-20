# API Reference

## Health Check

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check; returns `{"status": "ok"}` |

## Libs (Admin)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/libs/invalidate-cache` | Clear meta cache for skills/mcp/moderator_modes (hot-reload) |

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

Modes are loaded from `libs/moderator_modes/` (same structure as assignable_skills, mcps).

## Global Experts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/experts` | List global expert definitions (query: `fields=minimal` omits skill_content for faster list) |
| GET | `/experts/{name}/content` | Get expert skill markdown content only (aligned with skills/mcp/moderator-modes) |
| GET | `/experts/{name}` | Get full expert details including skill_content |
| PUT | `/experts/{name}` | Update expert definition |

Response fields: `name`, `label`, `description`, `skill_file`, `skill_content`, `perspective`, `category`, `category_name` (aligned with skills/moderator_modes).
