# API Reference

## Health Check

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check; returns `{"status": "ok"}` |

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
- `allowed_tools` (optional): Enabled tools list, e.g. `["Read","Write","Edit","Glob","Grep","Task","WebFetch","WebSearch"]`. Omit for default full set

## Assignable Skills

| Method | Path | Description |
|--------|------|-------------|
| GET | `/skills/assignable/categories` | List skill categories |
| GET | `/skills/assignable` | List assignable skills (query: `category`, `fields`, `limit`, `offset`) |
| GET | `/skills/assignable/{skill_id}/content` | Get raw markdown content of a skill |

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

## Moderator Modes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/moderator-modes` | List available moderator modes |
| GET | `/topics/{topic_id}/moderator-mode` | Get topic's current moderator mode |
| PUT | `/topics/{topic_id}/moderator-mode` | Set moderator mode |
| POST | `/topics/{topic_id}/moderator-mode/generate` | AI-generate moderator prompt |

## Global Experts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/experts` | List global expert definitions |
| GET | `/experts/{name}` | Get expert details |
| PUT | `/experts/{name}` | Update expert definition |
