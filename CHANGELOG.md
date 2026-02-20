# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
