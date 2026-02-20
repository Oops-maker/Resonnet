# Resonnet Technical Documentation

This directory contains technical implementation details and design docs for Resonnet.

## Document Index

| Doc | Description |
|-----|-------------|
| [architecture.md](architecture.md) | Overall architecture: API layer, agent layer, workspace layout, data flow |
| [assignable-skills-flow.md](assignable-skills-flow.md) | Assignable skills API, copy logic, meta aggregation |
| [config.md](config.md) | Environment variables; .env loading (project root first); ANTHROPIC_* vs AI_GENERATION_* |
| [mcp-config.md](mcp-config.md) | MCP config API, validation (npm/uvx/remote only, no local) |
| [testing.md](testing.md) | Test layers (unit/integration), .env setup, CI notes |
| [api-reference.md](api-reference.md) | API endpoint list and brief descriptions |
| [skills-generalization.md](skills-generalization.md) | Library design; experts in `libs/experts/`; discussion modes in `libs/moderator_modes/` |
| [skills-submodule-guide.md](skills-submodule-guide.md) | Add/update skill libraries via submodule; points to Cursor skill |
| [import-skill-repo.md](import-skill-repo.md) | One-click import script for external skill repos |
| [../app/prompts/README.md](../app/prompts/README.md) | AI prompt management (expert/moderator generation, round discussion, expert reply) |
| [../libs/README.md](../libs/README.md) | Libs directory structure; experts, moderator_modes, mcps, prompts |

## Quick Navigation

- **Getting started**: Read [config.md](config.md) for env setup, then [testing.md](testing.md) to run tests
- **Architecture**: [architecture.md](architecture.md)
- **API development**: [api-reference.md](api-reference.md)

## Important Notes

- AgentSDK availability must be validated with a real `.env`; `ANTHROPIC_API_KEY=test` is not acceptable for acceptance.
