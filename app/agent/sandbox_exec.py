"""OS-level sandbox execution for agent operations.

Wraps agent subprocess execution under Anthropic's sandbox-runtime (srt),
or falls back to macOS sandbox-exec (Apple Seatbelt) / Linux bubblewrap
(bwrap), physically restricting filesystem access to the topic workspace
directory.

Backend selection priority (highest first):
  1. **srt** (sandbox-runtime) — preferred; Anthropic-maintained, supports
     filesystem *and* network isolation via JSON config.  Requires Node.js
     and ``npm install -g @anthropic-ai/sandbox-runtime``.
  2. **sandbox-exec** — macOS legacy; custom Seatbelt profile.
  3. **bwrap** — Linux legacy; custom bubblewrap command.

Set ``SANDBOX_USE_SRT=false`` to skip srt and use the legacy backend.

Design doc: docs/sandbox-isolation.md

## Why subprocess?

claude_agent_sdk.query() spawns a `claude` CLI subprocess internally. The only
way to apply OS-level filesystem restrictions to the `claude` process is to run
its parent (sandbox_runner.py) inside the OS sandbox — all child processes
inherit the sandbox restrictions automatically.

## macOS Seatbelt profile (legacy fallback)

The Seatbelt profile uses `(deny default)` then allowlists:
- macOS system paths (/usr, /System, /Library) — read-only
- Homebrew prefix (/opt/homebrew) — read-only (Python runtime + packages)
- UV package cache (~/.cache/uv) — read-write (pip imports may update cache)
- Claude binary and config (~/.local, ~/.claude) — read/write for claude state
- Backend source (for Python imports) — read-only
- Topic workspace (WS_PATH) — read AND write (agent's work area)
- IPC directory (IPC_DIR) — read AND write (for task config + result JSON)

## Fallback

If no OS sandbox is available, callers should fall back to the original
asyncio.run(run_expert_reply(...)) behavior. This is handled in expert_reply.py.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to the sandbox runner script (runs inside the OS sandbox)
_SANDBOX_RUNNER = Path(__file__).parent / "sandbox_runner.py"

# Backend root directory (needed for Python import paths in sandbox)
_BACKEND_ROOT = Path(__file__).parent.parent.parent

# User home directory
_HOME = Path.home()

# ---------------------------------------------------------------------------
# macOS Seatbelt profile template
# ---------------------------------------------------------------------------
#
# Placeholders substituted at runtime by build_macos_profile():
#   {homebrew}  — homebrew prefix (e.g., /opt/homebrew)
#   {home}      — user home directory
#   {backend}   — absolute path to backend/ directory
#   {ws}        — absolute path to topic workspace (WS_PATH)
#   {ipc}       — absolute path to IPC temp directory
#
# Rules: (deny default) + allowlist. More specific rules override general ones.
# Order: later rules override earlier rules of equal specificity.
# "literal" is more specific than "subpath", so the .env deny at the bottom
# overrides the broader backend subpath allow above it.

_MACOS_PROFILE_TEMPLATE = """\
(version 1)
(deny default)

; ==========================================================================
; Network: allow all (agents need LLM API access for Claude/DashScope)
; ==========================================================================
(allow network*)
(allow network-outbound)
(allow network-bind)
(allow network-inbound)
(allow system-socket)

; ==========================================================================
; Process operations (needed to spawn claude CLI subprocess)
; ==========================================================================
(allow process-fork)
(allow process-exec*)
(allow signal (target self))
(allow signal (target children))
(allow sysctl-read)
(allow mach-lookup)
(allow mach-priv-host-port)
(allow ipc-posix*)
(allow file-ioctl)

; ==========================================================================
; File READS: allow globally
; Python startup (dyld, realpath, site-packages discovery) requires reading
; many paths that are difficult to enumerate. We allow all reads and rely on
; EXPERT_SECURITY_SUFFIX prompt constraints for read-boundary enforcement.
; The primary hard guarantee is WRITE isolation (see below).
; ==========================================================================
(allow file-read*)

; ==========================================================================
; File WRITES: selective allowlist (everything else is denied by default)
;
; Security guarantee: agents can ONLY WRITE to:
;   1. Their topic workspace (WS_PATH)
;   2. IPC temp directory (for subprocess communication)
;   3. Claude/UV state directories (required for agent runtime)
;   4. OS temp directories (required for Python, dyld)
;   5. /dev/null (required by many standard programs)
;
; Agents CANNOT write to:
;   - Other topic workspaces (cross-topic write isolation)
;   - Backend source files (including .env)
;   - User home files (SSH keys, shell configs, etc.)
;   - System paths (/usr, /etc, /System, /Library)
; ==========================================================================

; Topic workspace (the agent's isolated read-write work area)
(allow file-write* (subpath "{ws}"))

; IPC directory (sandbox_runner.py writes results here)
(allow file-write* (subpath "{ipc}"))

; OS temp directories (needed by Python, dyld shared cache, and OS internals)
(allow file-write* (subpath "/private/tmp"))
(allow file-write* (subpath "/private/var/folders"))

; /dev/null and dtracehelper (needed by many standard programs)
(allow file-write* (literal "/dev/null"))
(allow file-write* (literal "/dev/dtracehelper"))

; Claude runtime data (~/.claude and ~/.local/share/claude)
; Claude writes session state, cache, and config to these directories
(allow file-write* (subpath "{home}/.claude"))
(allow file-write* (subpath "{home}/.local/share/claude"))
(allow file-write* (subpath "{home}/.local/share/anthropic"))

; UV package cache (Python imports may update cache during execution)
(allow file-write* (subpath "{home}/.cache/uv"))
"""


# ---------------------------------------------------------------------------
# Sandbox availability detection
# ---------------------------------------------------------------------------

def is_macos_sandbox_available() -> bool:
    """Check if macOS sandbox-exec is available and functional."""
    try:
        result = subprocess.run(
            ["sandbox-exec", "-p", "(version 1)(allow default)", "echo", "sandbox_ok"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and "sandbox_ok" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def is_linux_bwrap_available() -> bool:
    """Check if Linux bubblewrap (bwrap) is available."""
    try:
        result = subprocess.run(
            ["bwrap", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def is_srt_available() -> bool:
    """Check if Anthropic sandbox-runtime (srt) CLI is installed."""
    return shutil.which("srt") is not None


# Check at import time (cached for performance)
SRT_AVAILABLE: bool = is_srt_available()
MACOS_SANDBOX: bool = is_macos_sandbox_available()
LINUX_BWRAP: bool = is_linux_bwrap_available()
SANDBOX_AVAILABLE: bool = SRT_AVAILABLE or MACOS_SANDBOX or LINUX_BWRAP

if SRT_AVAILABLE:
    logger.info("[SandboxExec] sandbox-runtime (srt) available — preferred sandbox backend")
elif MACOS_SANDBOX:
    logger.info("[SandboxExec] OS sandbox available: macos-sandbox-exec (legacy)")
elif LINUX_BWRAP:
    logger.info("[SandboxExec] OS sandbox available: linux-bwrap (legacy)")
else:
    logger.warning(
        "[SandboxExec] No OS sandbox available (srt/sandbox-exec/bwrap not found). "
        "Agent isolation will use soft prompt constraints only."
    )


# ---------------------------------------------------------------------------
# macOS profile builder
# ---------------------------------------------------------------------------


def build_macos_profile(ws_abs: str, ipc_dir: str) -> str:
    """Build a macOS Seatbelt profile that enforces write isolation for ws_abs.

    Security model:
    - READ: allowed globally (Python startup, dyld, and imports require broad access)
    - WRITE: restricted to ws_abs, ipc_dir, claude/uv state dirs, and OS temps

    Args:
        ws_abs: Absolute path to the topic workspace (the agent's work area).
        ipc_dir: Absolute path to the IPC temp directory for input/output JSON.

    Returns:
        SBPL profile string suitable for ``sandbox-exec -p <profile>``.
    """
    return _MACOS_PROFILE_TEMPLATE.format(
        home=str(_HOME),
        ws=ws_abs,
        ipc=ipc_dir,
    )


# ---------------------------------------------------------------------------
# Linux bwrap command builder
# ---------------------------------------------------------------------------

def _build_linux_bwrap_cmd(
    ws_abs: str,
    ipc_dir: str,
    python_exec: str,
    runner_path: str,
    input_json: str,
    output_json: str,
) -> list[str]:
    """Build a bubblewrap command for Linux filesystem isolation.

    Note: ``--unshare-net`` is commented out because agents need network access
    for LLM API calls. Add it back if you want to test without API access.
    """
    home = str(_HOME)
    cmd = [
        "bwrap",
        # System paths (read-only)
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/sbin", "/sbin",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/etc", "/etc",
        # Backend source (read-only for imports)
        "--ro-bind", str(_BACKEND_ROOT), str(_BACKEND_ROOT),
        # Agent workspace (read-write)
        "--bind", ws_abs, ws_abs,
        # IPC directory (read-write)
        "--bind", ipc_dir, ipc_dir,
        # Claude config (read-write)
        "--bind", f"{home}/.claude", f"{home}/.claude",
        "--ro-bind", f"{home}/.local/bin/claude", f"{home}/.local/bin/claude",
        # UV cache
        "--bind", f"{home}/.cache/uv", f"{home}/.cache/uv",
        # Pseudo-filesystems
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        # Note: network NOT isolated (agents need API access)
        # "--unshare-net",
        "--",
        python_exec, runner_path, input_json, output_json,
    ]

    # Only bind-mount optional directories if they exist
    for optional in ["/lib64", f"{home}/.nvm"]:
        if Path(optional).exists():
            cmd = cmd[:cmd.index("--")] + ["--ro-bind", optional, optional] + cmd[cmd.index("--"):]

    return cmd


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_in_os_sandbox(task_config: dict[str, Any]) -> dict[str, Any]:
    """Run an agent task inside an OS-level filesystem sandbox.

    Creates a temporary IPC directory, serializes ``task_config`` to
    ``input.json``, spawns ``sandbox_runner.py`` under ``sandbox-exec``
    (macOS) or ``bwrap`` (Linux), waits for completion, and reads back
    ``output.json``.

    The subprocess (``sandbox_runner.py``) runs inside the OS sandbox, so
    the ``claude`` CLI subprocess it spawns also inherits the restrictions.

    Args:
        task_config: Task configuration dict.  Must contain at minimum:
            - ``task_type``: "expert_reply" or "discussion"
            - ``ws_path``: Absolute path to topic workspace
            - ``api_key``: Anthropic API key (or DashScope key)
            Other keys depend on task_type (see sandbox_runner.py).

    Returns:
        Result dict with at least ``{"success": bool}``. On success includes
        ``"result_info"`` dict. On failure includes ``"error"`` string.

    Raises:
        RuntimeError: If no OS sandbox is available. Callers should check
            ``SANDBOX_AVAILABLE`` first and fall back gracefully.
        subprocess.TimeoutExpired: If subprocess exceeds the timeout.
    """
    if not SANDBOX_AVAILABLE:
        raise RuntimeError(
            "No OS sandbox available. "
            "Check SANDBOX_AVAILABLE before calling run_in_os_sandbox()."
        )

    ws_abs = task_config["ws_path"]
    python_exec = sys.executable
    runner_path = str(_SANDBOX_RUNNER)

    # Generous timeout: max_budget * 10 minutes, minimum 10 minutes
    max_budget = task_config.get("max_budget_usd", 10.0)
    timeout_seconds = max(600, int(max_budget * 600))

    # Create isolated IPC directory in /private/tmp (macOS) or /tmp (Linux)
    tmp_base = Path("/private/tmp") if Path("/private/tmp").exists() else Path("/tmp")
    ipc_dir = str(tmp_base / f"agent-topic-lab-{uuid.uuid4().hex[:8]}")
    Path(ipc_dir).mkdir(parents=True, exist_ok=True)

    input_path = f"{ipc_dir}/input.json"
    output_path = f"{ipc_dir}/output.json"

    try:
        # Write task config to IPC input file
        Path(input_path).write_text(
            json.dumps(task_config, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        # Build the sandboxed command
        from app.core.config import get_sandbox_use_srt

        use_srt = SRT_AVAILABLE and get_sandbox_use_srt()
        srt_settings_path: str | None = None

        if use_srt:
            from app.agent.srt_config import build_srt_settings, write_srt_settings_file

            srt_settings = build_srt_settings(
                topic_workspace=ws_abs,
                ipc_dir=ipc_dir,
            )
            srt_settings_path = write_srt_settings_file(
                srt_settings, target_dir=ipc_dir,
            )
            cmd = [
                "srt", "--settings", srt_settings_path,
                python_exec, runner_path, input_path, output_path,
            ]
            logger.info("[SandboxExec] Using sandbox-runtime (srt) backend")
        elif MACOS_SANDBOX:
            profile = build_macos_profile(ws_abs, ipc_dir)
            cmd = [
                "sandbox-exec", "-p", profile,
                python_exec, runner_path, input_path, output_path,
            ]
            logger.info("[SandboxExec] Using legacy macOS sandbox-exec backend")
        else:
            cmd = _build_linux_bwrap_cmd(
                ws_abs, ipc_dir, python_exec, runner_path, input_path, output_path
            )
            logger.info("[SandboxExec] Using legacy Linux bwrap backend")

        logger.info(
            "[SandboxExec] Launching sandboxed subprocess: task_type=%s ws=%s",
            task_config.get("task_type"), ws_abs,
        )

        # Run subprocess (blocking — called from a daemon thread)
        proc = subprocess.run(
            cmd,
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            env=_build_subprocess_env(),
        )

        # Log subprocess output for debugging
        if proc.stdout:
            logger.debug("[SandboxExec] stdout: %s", proc.stdout[:2000])
        if proc.stderr:
            level = logging.WARNING if proc.returncode != 0 else logging.DEBUG
            logger.log(level, "[SandboxExec] stderr: %s", proc.stderr[:2000])

        if proc.returncode != 0:
            logger.error(
                "[SandboxExec] Subprocess exited with non-zero code %d",
                proc.returncode,
            )

        # Read output file
        output_file = Path(output_path)
        if output_file.exists():
            result = json.loads(output_file.read_text(encoding="utf-8"))
            logger.info(
                "[SandboxExec] Subprocess complete: success=%s task_type=%s",
                result.get("success"), task_config.get("task_type"),
            )
            return result
        else:
            error_msg = (
                f"Subprocess exited (code={proc.returncode}) without writing output. "
                f"stderr={proc.stderr[:500]!r}"
            )
            logger.error("[SandboxExec] %s", error_msg)
            return {"success": False, "error": error_msg}

    finally:
        # Always clean up IPC directory
        try:
            shutil.rmtree(ipc_dir, ignore_errors=True)
        except Exception:
            pass


def _build_subprocess_env() -> dict[str, str]:
    """Build a minimal environment for the sandbox subprocess.

    Inherits the current process environment but removes variables that
    could interfere with the subprocess or that should be provided via
    the task config (api keys are passed via IPC, not env vars directly).

    We keep most env vars because the subprocess needs PATH, HOME, etc.
    The ANTHROPIC_API_KEY will be set by sandbox_runner.py from task config.
    """
    env = dict(os.environ)
    # Remove Claude Code marker so claude CLI can run as standalone
    env.pop("CLAUDECODE", None)
    return env
