# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Assignable skills pointers**: track `libs/assignable_skills/_submodules/ai-research` and `libs/assignable_skills/_submodules/anthropics` as gitlinks for shared skill source integration.

### Changed

- **Docs alignment**: refresh `docs/README.md` to match recent profile-helper/auth integration updates.
- **Shared catalog metadata**: update experts and moderator mode `meta.json` snapshots under `topiclab_shared`.
- **Dependency snapshot**: sync `pyproject.toml` and `uv.lock` with the current backend environment.

## [0.4.0] - 2026-03-07

### Added

- **Agent Links**: `GET /agent-links`, `GET /agent-links/{slug}`, `POST /agent-links/import/preview`, `POST /agent-links/import`, `POST /agent-links/{slug}/session`, `POST /agent-links/{slug}/chat` (SSE), `POST /agent-links/{slug}/files/upload`; blueprint dir convention `libs/agent_links/<blueprint_dir>/agent.json`
- **Profile Helper**: `GET /profile-helper/session`, `POST /profile-helper/chat` (SSE), `GET /profile-helper/profile/{session_id}`, `GET /profile-helper/download/{session_id}`, `GET /profile-helper/download/{session_id}/forum`, `POST /profile-helper/session/reset/{session_id}`
- **Experts import**: `POST /experts/import-profile` — import forum profile into `libs/experts/topiclab_shared/` as expert

### Changed

- api-reference.md: add Profile Helper, Experts import-profile docs

## [0.3.0] - 2026-03-01

### Added

- **Expert share to platform**: `POST /topics/{id}/experts/{name}/share` — share topic-level expert to `libs/experts/topiclab_shared/`; rejects built-in experts (source=default); reloads EXPERT_SPECS and invalidates libs cache
- **Moderator mode share to platform**: `POST /topics/{id}/moderator-mode/share` — share custom moderator mode to `libs/moderator_modes/topiclab_shared/`; body: `mode_id`, `name?`, `description?`; creates meta.json if missing
- **Topic-level moderator config**: `GET/PUT /topics/{id}/moderator-mode` supports `skill_list`, `mcp_server_ids`, `model`; persisted per topic; fallback from `config/skills/` and `config/mcp.json` when missing
- **Discussion params**: `POST /topics/{id}/discussion` accepts `skill_list`, `mcp_server_ids`, `allowed_tools`; copied to topic workspace for moderator/agent use

### Fixed

- **Expert share 500**: `POST /topics/{id}/experts/{name}/share` no longer returns 500 when `libs/experts/topiclab_shared/meta.json` does not exist (first share). Creates default meta structure like moderator-mode share.
- **Expert share (deploy)**: Ensures `topiclab_shared` is registered in `libs/experts/meta.json` so reload picks up shared experts when LIBS_PATH mount is empty; handles malformed JSON and missing fields; returns descriptive error on failure.

### Changed

- Topic moderator mode config: skill_list, mcp_server_ids, model persisted in workspace; discussion uses topic config when present
- Expert share: creates `topiclab_shared/meta.json` with default categories when missing (aligned with moderator-mode share)

## [0.2.0] - 2026-02-21

### Added

- **Libs meta cache**: TTL cache for skills/mcp/moderator_modes meta; `LIBS_CACHE_TTL_SECONDS` env (0=hot-reload)
- **Cache stampede protection**: Lock on cache miss so only one request loads; others wait and reuse
- **Libs admin API**: `POST /libs/invalidate-cache` for manual cache invalidation
- **Search param `q`**: List endpoints support `q` for id/name/description filtering (skills, mcp, moderator-modes)
- **Experts content endpoint**: `GET /experts/{name}/content` returns skill markdown only (aligned with other libs)
- **Experts list optimization**: `fields=minimal` omits skill_content for faster list
- **Unified libs service**: `app/core/libs_service.py` — shared list logic, cached loaders, search filter

### Changed

- Skills, MCP, moderator_modes list APIs now use cached meta and support `q` param
- Experts list: `fields=minimal` returns empty skill_content (content fetched on demand via `/content`)

## [0.1.0] - 2026-02-19

### Added

- Multi-agent discussion orchestration (Claude Agent SDK)
- Topic workspace isolation with concurrency lock
- Expert & moderator mode AI generation
- @mention expert reply (async)
- REST API: topics, posts, discussion, experts, moderator modes
- Preset expert roles (physics, biology, computer science, ethics)
- Preset moderator modes (standard, brainstorm, debate, review)
- Docker support
- Unit & integration test suite
- Bilingual README (Chinese default, English via README.en.md)
- API test guide for coding agents
