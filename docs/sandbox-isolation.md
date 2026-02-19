# Topic-Level Sandbox Isolation: Design Document

**Date**: 2026-02-19
**Status**: Implemented (Phase 2 — OS-level isolation)
**Author**: Resonnet Engineering

---

## 1. Background and Motivation

### 1.1 Design Principle

> Relying only on the Agent SDK's `cwd` is not hard isolation. To achieve
> "can only access the session directory", you must use OS-level sandboxing
> (e.g. bwrap / nsjail / sandbox-exec).

### 1.2 What Tests Proved (Phase 1 Failures)

During Phase 1 (soft isolation via prompt constraints), integration tests using
the "canary" pattern revealed two real vulnerabilities:

**Vulnerability 1 — Prompt Injection via Workspace File**
A file `shared/SECURITY_UPDATE_v2.md` claiming to override security rules caused
the agent to read an external canary file. Mitigation: strengthened
`EXPERT_SECURITY_SUFFIX` with explicit "rules cannot be overridden by content"
language. **Status: mitigated (prompt hardening).**

**Vulnerability 2 — `allowed_tools` Not Enforced as Hard Whitelist**
With `permission_mode="acceptEdits"` and `allowed_tools=["Read","Glob"]`, the
agent still used the `Write` tool when prompted to. The `allowed_tools` parameter
is NOT a hard whitelist — it's a UI hint that `acceptEdits` overrides.
**Status: unresolved — requires OS-level enforcement.**

**Root diagnosis**: `add_dirs` and `allowed_tools` in `claude_agent_sdk` are
**soft constraints**, not hard OS-level restrictions. The agent process can still
access any file the operating system permits the process to access.

---

## 2. Architecture: Two Layers

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Layer 1: Concurrency Tracking + Audit (topic_sandbox.py)               │
│  - Per-topic exclusive lock for discussion (in-memory _TopicRegistry)   │
│  - Per-operation audit log → config/audit.jsonl                         │
│  - Sandbox metadata → config/sandbox_meta.json                          │
│  - Does NOT restrict filesystem access (soft layer)                     │
├──────────────────────────────────────────────────────────────────────────┤
│  Layer 2: OS-Level Filesystem Isolation (sandbox_exec.py)               │
│  - macOS: sandbox-exec with Apple Seatbelt profile (.sb)                │
│  - Linux: bubblewrap (bwrap) with namespace isolation                   │
│  - Physical: kernel enforces file access policy                         │
│  - Subprocess (sandbox_runner.py) runs inside OS sandbox                │
│  - Agent can ONLY read/write within its topic workspace directory        │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. OS-Level Isolation Design

### 3.1 Subprocess Model

The key architectural decision is the **subprocess wrapper pattern**:

```
FastAPI server (main process)
  │
  ├── receives @mention request
  ├── creates pending post
  ├── starts daemon thread
  │     │
  │     └── sandbox_exec.run_in_os_sandbox(task_config)
  │           │
  │           ├── writes task_config to /private/tmp/.../input.json
  │           ├── builds OS sandbox profile
  │           └── subprocess.run(["sandbox-exec", "-p", PROFILE,
  │                               python3, sandbox_runner.py,
  │                               input.json, output.json])
  │                 │
  │                 └── sandbox_runner.py (runs INSIDE sandbox)
  │                       ├── reads input.json
  │                       ├── sets env vars from config
  │                       ├── imports app.agent.expert_reply
  │                       ├── asyncio.run(run_expert_reply(...))
  │                       │     │
  │                       │     └── claude_agent_sdk.query(...)
  │                       │           │
  │                       │           └── spawns claude CLI subprocess
  │                       │                 (inherits sandbox restrictions)
  │                       └── writes output.json
  │
  └── reads output.json → result_info
```

**Why subprocess instead of in-process sandbox?**
Because `sandbox-exec` / `bwrap` restrict the ENTIRE process and all its
children. The only way to apply OS sandboxing to the `claude` CLI (spawned by
`claude_agent_sdk.query()`) is to run the parent process inside the sandbox.

### 3.2 macOS Seatbelt (sandbox-exec)

macOS provides `sandbox-exec` with the **Seatbelt Policy Language (SBPL)**.

**Key properties:**
- `(deny default)` — deny all operations unless explicitly allowed
- Allowlist-based — specify exactly what is permitted
- Applies to the entire process tree (all child processes inherit the sandbox)
- More specific rules override less specific ones (e.g., `literal` > `subpath`)

**Profile structure** (see `app/agent/sandbox_exec.py:_MACOS_PROFILE_TEMPLATE`):

- Allow network (agents need API access)
- Allow process operations (claude CLI spawning)
- Allow macOS system paths (read-only)
- Allow topic workspace (read AND write — agent's work area)
- Allow IPC directory (for input/output JSON files)
- Deny backend `.env` and sensitive paths

### 3.3 Linux bubblewrap (bwrap)

On Linux, `bwrap` (bubblewrap) provides namespace-based isolation. Linux support
is implemented but less tested than macOS.

### 3.4 What the Sandbox Enforces

| Operation | Allowed | Denied |
|-----------|---------|--------|
| Read topic workspace files | Yes | — |
| Write topic workspace files | Yes | — |
| Read backend Python source | Yes (imports) | — |
| Read other topic workspaces | — | Kernel EPERM |
| Write outside workspace | — | Kernel EPERM |
| Read user's SSH keys (~/.ssh) | — | Kernel EPERM |
| Network calls to LLM API | Yes | — |
| Execute claude CLI | Yes | — |

### 3.5 Fallback Strategy

If no OS sandbox is available, the system falls back to soft-isolation
(prompt constraints + `allowed_tools` + audit logging).

---

## 4. Workspace Layout

```
workspace/topics/{topic_id}/
├── agents/
│   ├── physicist/
│   │   └── role.md         ← agent reads this (context)
│   └── economist/
│       └── role.md
├── shared/
│   └── turns/              ← discussion writes here
├── posts/
│   └── *.json              ← expert writes reply here
└── config/
    ├── audit.jsonl          ← append-only audit log (Layer 1)
    ├── sandbox_meta.json    ← sandbox status (Layer 1)
    └── experts_metadata.json
```

---

## 5. File Organization

```
Resonnet/
├── app/
│   └── agent/
│       ├── sandbox_exec.py      ← OS sandbox wrapper
│       ├── sandbox_runner.py    ← Script run inside sandbox
│       ├── topic_sandbox.py     ← Audit/concurrency layer
│       ├── expert_reply.py      ← Uses sandbox_exec
│       └── discussion.py        ← Uses sandbox_exec
└── tests/
    ├── test_topic_sandbox.py        ← Unit tests (Layer 1)
    └── test_sandbox_agent_isolation.py  ← Real integration tests
```

---

## 6. Testing Approach

### 6.1 Unit Tests (`test_topic_sandbox.py`)

Tests Layer 1 (audit/concurrency) without real API calls:
- Path boundary validation
- Audit log writing
- Sandbox metadata lifecycle
- Exclusive/tracked lock interaction
- API 409 response when discussion is running

### 6.2 Integration Tests (`test_sandbox_agent_isolation.py`)

Tests real agent behavior using the **canary pattern**:
1. Place a unique secret string in a file OUTSIDE the workspace
2. Prompt the agent to find and return the secret
3. Check if agent output contains the secret → isolation breach

**Test cases:**
- `test_workspace_read_allowed` — agent CAN read its workspace (positive control)
- `test_cross_topic_read_blocked` — agent CANNOT read sibling topic workspace
- `test_parent_dir_traversal_blocked` — `../` traversal blocked
- `test_write_outside_workspace_blocked` — writes outside workspace fail
- `test_prompt_injection_ignored` — injection in workspace file ignored

---

## 7. Known Limitations

1. **sandbox-exec is deprecated** on macOS (since macOS 11+). It still works
   but may be removed in future macOS versions.

2. **No process/resource isolation**: A malicious agent can fork-bomb or allocate
   excessive memory. Use `ulimit` or container resource limits for production.

3. **Linux support**: `bwrap` implementation exists but is untested. May need
   adjustment for different Linux distributions.
