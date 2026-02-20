# MCP Configuration

MCP (Model Context Protocol) servers are configured in `libs/mcps/` (read-only, same structure as assignable_skills).

## Directory Structure

```
libs/mcps/
├── meta.json          # sources registry
├── default/
│   └── meta.json      # categories + mcps
└── <source>/
    └── meta.json
```

## Policy

**Accepted sources only:** npm, uvx, remote (mcp-remote). No local paths.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/mcp/assignable/categories` | List MCP categories |
| GET | `/mcp/assignable` | List assignable MCPs |
| GET | `/mcp/assignable/{id}/content` | Get MCP config JSON (command, args) |

## meta.json Format

```json
// mcps/meta.json
{"sources": {"default": {"id": "default", "name": "Default", "description": "Built-in MCP servers"}}}

// mcps/default/meta.json
{
  "categories": {
    "tools": {"id": "tools", "name": "Tools", "description": "..."}
  },
  "mcps": {
    "inspector": {
      "id": "inspector",
      "source": "default",
      "name": "MCP Inspector",
      "description": "Debug and inspect MCP servers",
      "category": "tools",
      "command": "npx",
      "args": ["@modelcontextprotocol/inspector"]
    }
  }
}
```

## Topic Discussion

When starting a discussion, selected MCP server IDs are copied from `libs/mcps/` to `workspace/topics/{id}/config/mcp.json`.

## MCP → Agent SDK 传参链路

```
API mcp_server_ids
  → copy_mcp_to_workspace(ws_path, server_ids)
  → workspace/topics/{id}/config/mcp.json
  → run_discussion 内 _load_mcp_servers_for_sdk(workspace_dir)
  → ClaudeAgentOptions(mcp_servers={...}, allowed_tools=[..., "mcp__{id}__*"])
  → claude_agent_sdk.query(options=...)
```

- `config/mcp.json` 存在时，`run_discussion` 会加载并传入 `ClaudeAgentOptions(mcp_servers=...)`
- 每个 MCP server 在 `allowed_tools` 中增加 `mcp__{server_id}__*` 以允许调用

## Implementation

- **Meta loading**: `app/core/mcps_meta.py`
- **API**: `app/api/mcp.py`
- **Copy to workspace**: `app/agent/workspace.copy_mcp_to_workspace()`
- **Load for SDK**: `app/agent/discussion._load_mcp_servers_for_sdk()`
- **Validation**: `app/core/mcp_config.validate_mcp_server()` (npm/uvx/remote only)

## Tests

- **Unit**: `test_run_discussion_mocked_passes_mcp_to_sdk` — 存在 mcp.json 时 options 含 mcp_servers 与 mcp__* 工具
- **Unit**: `test_run_discussion_mocked_no_mcp_when_config_missing` — 无 mcp.json 时不传 mcp_servers
- **Integration**: `test_discussion_mcp_time_integration` — 使用 MCP time，通过提示词触发调用并验证返回含时间信息
