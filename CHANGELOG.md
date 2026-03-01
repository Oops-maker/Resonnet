# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-03-01

### Added

- **Expert share to platform**: `POST /topics/{id}/experts/{name}/share` — share topic-level expert to `libs/experts/topiclab_shared/`; rejects built-in experts (source=default); reloads EXPERT_SPECS and invalidates libs cache
- **Moderator mode share to platform**: `POST /topics/{id}/moderator-mode/share` — share custom moderator mode to `libs/moderator_modes/topiclab_shared/`; body: `mode_id`, `name?`, `description?`; creates meta.json if missing
- **Topic-level moderator config**: `GET/PUT /topics/{id}/moderator-mode` supports `skill_list`, `mcp_server_ids`, `model`; persisted per topic; fallback from `config/skills/` and `config/mcp.json` when missing
- **Discussion params**: `POST /topics/{id}/discussion` accepts `skill_list`, `mcp_server_ids`, `allowed_tools`; copied to topic workspace for moderator/agent use

### Fixed

- **Expert share 500**: `POST /topics/{id}/experts/{name}/share` no longer returns 500 when `libs/experts/topiclab_shared/meta.json` does not exist (first share). Creates default meta structure like moderator-mode share.

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
