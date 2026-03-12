"""Generate per-invocation sandbox-runtime (srt) configuration files.

``srt`` is Anthropic's lightweight OS-level sandboxing tool.  It reads a JSON
settings file (``--settings <path>``) that declares filesystem and network
restrictions.  This module builds those settings dicts dynamically so each
sandbox invocation gets an appropriate, minimal policy.

Filesystem model (match existing sandbox_exec.py behaviour):
  - READ:  allowed globally (Python imports, dyld, claude runtime all need broad
           read access).  Only a small deny-list for secrets (.env, .ssh, etc.).
  - WRITE: denied globally except for explicitly allowed paths (topic workspace,
           IPC dir, claude / uv state dirs, OS temps).

Network model (disabled by default, can be enabled per invocation):
  - When ``allowed_domains`` is *None* (default): network restrictions are
    relaxed (``enableWeakerNetworkIsolation: true``) so agents can reach any
    API endpoint.
  - When ``allowed_domains`` is provided: strict domain allowlist is applied
    and ``enableWeakerNetworkIsolation`` is set to *false*.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_HOME = str(Path.home())


# ---------------------------------------------------------------------------
# Sensitive paths that should never be readable inside the sandbox
# ---------------------------------------------------------------------------

_DEFAULT_DENY_READ: list[str] = [
    "**/.env",
    "**/.env.*",
    os.path.join(_HOME, ".ssh"),
    os.path.join(_HOME, ".gnupg"),
    os.path.join(_HOME, ".aws"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_srt_settings(
    *,
    topic_workspace: str,
    ipc_dir: str,
    claude_config_dir: str | None = None,
    uv_cache_dir: str | None = None,
    allowed_domains: list[str] | None = None,
) -> dict:
    """Build a complete srt-settings dict for one sandbox invocation.

    Parameters
    ----------
    topic_workspace:
        Absolute path to the topic workspace directory.  The agent's primary
        read/write area.
    ipc_dir:
        Absolute path to the IPC temp directory used for input/output JSON
        exchange between the main process and the sandboxed runner.
    claude_config_dir:
        Absolute path to the ``~/.claude`` directory (or equivalent) that the
        claude CLI needs read/write access to for its own state.
    uv_cache_dir:
        Absolute path to the ``~/.cache/uv`` directory (or equivalent) that
        ``uv`` uses for package caching.
    allowed_domains:
        If *None* (default), network isolation is not applied — processes
        inside the sandbox have unrestricted network access.  If a list of
        domain strings is provided (e.g. ``["api.anthropic.com"]``), strict
        domain allowlisting is enabled and only listed domains are reachable.

    Returns
    -------
    dict
        A JSON-serialisable dict matching the srt-settings.json schema.
    """
    allow_write: list[str] = [
        topic_workspace,
        ipc_dir,
        "/tmp",
    ]

    # macOS private/tmp
    if os.path.exists("/private/tmp"):
        allow_write.append("/private/tmp")

    if claude_config_dir:
        allow_write.append(claude_config_dir)
    else:
        allow_write.append(os.path.join(_HOME, ".claude"))
        allow_write.append(os.path.join(_HOME, ".local"))

    if uv_cache_dir:
        allow_write.append(uv_cache_dir)
    else:
        allow_write.append(os.path.join(_HOME, ".cache", "uv"))

    settings: dict = {
        "filesystem": {
            "denyRead": list(_DEFAULT_DENY_READ),
            "allowWrite": allow_write,
            "denyWrite": [],
        },
    }

    if allowed_domains is not None:
        settings["network"] = {
            "allowedDomains": allowed_domains,
            "deniedDomains": [],
        }
        settings["enableWeakerNetworkIsolation"] = False
    else:
        # No network isolation — relax restrictions so agents can reach APIs.
        settings["enableWeakerNetworkIsolation"] = True

    return settings


def build_mcp_srt_settings(
    *,
    topic_workspace: str,
    allowed_domains: list[str] | None = None,
) -> dict:
    """Build srt-settings for an MCP server subprocess.

    MCP servers get a more restrictive policy than the main agent:
    - Write access limited to the topic workspace ``shared/`` sub-directory
      (MCP servers typically produce artefacts, not manage the whole workspace).
    - Same deny-read list as the main sandbox.

    Parameters
    ----------
    topic_workspace:
        Absolute path to the topic workspace.
    allowed_domains:
        Same semantics as :func:`build_srt_settings`.
    """
    shared_dir = os.path.join(topic_workspace, "shared")

    allow_write: list[str] = [
        shared_dir,
        "/tmp",
    ]
    if os.path.exists("/private/tmp"):
        allow_write.append("/private/tmp")

    settings: dict = {
        "filesystem": {
            "denyRead": list(_DEFAULT_DENY_READ),
            "allowWrite": allow_write,
            "denyWrite": [],
        },
    }

    if allowed_domains is not None:
        settings["network"] = {
            "allowedDomains": allowed_domains,
            "deniedDomains": [],
        }
        settings["enableWeakerNetworkIsolation"] = False
    else:
        settings["enableWeakerNetworkIsolation"] = True

    return settings


def write_srt_settings_file(
    settings: dict,
    *,
    target_dir: str | None = None,
) -> str:
    """Write *settings* to a temporary JSON file and return the path.

    The caller is responsible for cleaning up the file after use (typically in
    a ``finally`` block).

    Parameters
    ----------
    settings:
        Dict from :func:`build_srt_settings` or :func:`build_mcp_srt_settings`.
    target_dir:
        Directory to write the temp file in.  Defaults to the system temp dir.
    """
    fd, path = tempfile.mkstemp(
        prefix="srt_settings_",
        suffix=".json",
        dir=target_dir,
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        os.unlink(path)
        raise
    logger.debug("[SrtConfig] Wrote srt settings to %s", path)
    return path
