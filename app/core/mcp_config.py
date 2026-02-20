"""MCP config load/save and validation. Only npm, uvx, remote allowed; no local paths."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.core.config import get_workspace_base
from app.models.schemas import MCPServerConfig, MCPConfig

ALLOWED_COMMANDS = ("npx", "npm", "uvx")
REMOTE_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


def _is_local_path(s: str) -> bool:
    """Return True if s looks like a local path (reject)."""
    s = s.strip()
    if not s:
        return False
    # Absolute path
    if s.startswith("/") or (len(s) > 1 and s[1] == ":"):
        return True
    # Relative path
    if s.startswith("./") or s.startswith("../"):
        return True
    # Windows backslash
    if "\\" in s:
        return True
    return False


def validate_mcp_server(server_id: str, cfg: MCPServerConfig) -> None:
    """Validate a single MCP server config. Raises ValueError if local/invalid."""
    cmd = (cfg.command or "").strip().lower()
    if not cmd:
        raise ValueError(f"MCP server '{server_id}': command is required")

    # Reject command that is a local path
    if _is_local_path(cfg.command):
        raise ValueError(
            f"MCP server '{server_id}': local paths are not allowed. "
            "Use npm, uvx, or remote (mcp-remote) only."
        )

    # Accept: npx, npm, uvx
    if cmd in ALLOWED_COMMANDS:
        args = cfg.args or []
        # npx mcp-remote <url>: second arg must be https URL
        if cmd == "npx" and len(args) >= 2 and str(args[0]).strip().lower() == "mcp-remote":
            url = str(args[1]).strip()
            if not REMOTE_URL_PATTERN.match(url):
                raise ValueError(
                    f"MCP server '{server_id}': mcp-remote requires https:// URL as second arg"
                )
        # No local paths in args
        for i, a in enumerate(args):
            if _is_local_path(str(a)):
                raise ValueError(
                    f"MCP server '{server_id}': args[{i}] contains local path. "
                    "Only npm packages, uvx packages, or remote URLs allowed."
                )
        return

    # Reject unknown command (e.g. python, node, /usr/bin/foo)
    raise ValueError(
        f"MCP server '{server_id}': command '{cfg.command}' is not allowed. "
        "Only npx, npm, uvx, or npx mcp-remote <url> are accepted."
    )


def validate_mcp_config(config: MCPConfig) -> None:
    """Validate full MCP config. Raises ValueError on first invalid server."""
    for sid, srv in config.mcpServers.items():
        validate_mcp_server(sid, srv)


def get_mcp_config_path() -> Path:
    """Return path to workspace/config/mcp.json."""
    return get_workspace_base() / "config" / "mcp.json"


def load_mcp_config() -> MCPConfig:
    """Load MCP config from workspace/config/mcp.json. Returns empty config if missing."""
    path = get_mcp_config_path()
    if not path.exists():
        return MCPConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers") or {}
        return MCPConfig(
            mcpServers={
                k: MCPServerConfig(**v) if isinstance(v, dict) else v
                for k, v in servers.items()
                if isinstance(v, dict)
            }
        )
    except (json.JSONDecodeError, TypeError, ValidationError) as e:
        raise ValueError(f"Invalid mcp.json: {e}") from e


def save_mcp_config(config: MCPConfig) -> None:
    """Save MCP config to workspace/config/mcp.json. Validates before save."""
    validate_mcp_config(config)
    path = get_mcp_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "mcpServers": {
            k: {
                "command": v.command,
                "args": v.args,
                **({"env": v.env} if v.env else {}),
            }
            for k, v in config.mcpServers.items()
        }
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_mcp_config_from_path(path: Path) -> MCPConfig:
    """Load MCP config from a specific path. Returns empty config if missing."""
    if not path.exists():
        return MCPConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers") or {}
        return MCPConfig(
            mcpServers={
                k: MCPServerConfig(**v) if isinstance(v, dict) else v
                for k, v in servers.items()
                if isinstance(v, dict)
            }
        )
    except (json.JSONDecodeError, TypeError, ValidationError):
        return MCPConfig()
