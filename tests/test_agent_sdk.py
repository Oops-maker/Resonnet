"""Agent SDK tests: unit (mock, CI) + integration (real API, requires ANTHROPIC_API_KEY).

One file for all Agent SDK coverage. Contributors: add unit tests here for CI;
add integration tests for real API validation (run manually or via cron).

- Unit: pytest -m "not integration" — no API key, runs in CI
- Integration: pytest -m integration — needs .env ANTHROPIC_API_KEY, skip if missing
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.agent.expert_reply import _extract_reply_body, run_expert_reply


# =============================================================================
# Unit tests (no integration marker — run in CI, no API key)
# =============================================================================


# --- _extract_reply_body ---


def test_extract_reply_body_plain_text():
    """Plain text passes through with strip."""
    assert _extract_reply_body("  Hello world  ") == "Hello world"
    assert _extract_reply_body("Simple reply") == "Simple reply"


def test_extract_reply_body_bare_json():
    """Bare JSON object extracts body field."""
    assert _extract_reply_body('{"body": "Extracted content"}') == "Extracted content"
    assert _extract_reply_body('{"body": ""}') == '{"body": ""}'


def test_extract_reply_body_code_fenced_json():
    """Code-fenced JSON block extracts body."""
    text = '```json\n{"body": "From code block"}\n```'
    assert _extract_reply_body(text) == "From code block"


def test_extract_reply_body_code_fenced_plain_text():
    """Code-fenced plain text strips fences."""
    text = "```\nPlain text inside fences\n```"
    assert _extract_reply_body(text) == "Plain text inside fences"


def test_extract_reply_body_empty():
    """Empty string returns as-is."""
    assert _extract_reply_body("") == ""
    assert _extract_reply_body("   ") == "   "


# --- run_expert_reply (mocked) ---


@pytest.fixture
def expert_reply_workspace(tmp_path):
    """Minimal workspace with physicist role for expert_reply."""
    ws = tmp_path / "workspace" / "topics" / "t1"
    (ws / "agents" / "physicist").mkdir(parents=True)
    (ws / "agents" / "physicist" / "role.md").write_text(
        "# Physicist\n\nYou are a physicist.",
        encoding="utf-8",
    )
    return ws


async def _mock_query_expert_reply(assistant_text: str = "Mocked expert reply.", **kwargs):
    """Async generator yielding AssistantMessage then ResultMessage."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

    yield AssistantMessage(
        content=[TextBlock(text=assistant_text)],
        model="claude-test",
    )
    yield ResultMessage(
        subtype="success",
        duration_ms=100,
        duration_api_ms=80,
        is_error=False,
        num_turns=1,
        session_id="test-session",
        total_cost_usd=0.001,
        usage=None,
        result=assistant_text,
    )


@pytest.mark.asyncio
async def test_run_expert_reply_mocked_saves_completed_post(expert_reply_workspace: Path):
    """run_expert_reply with mocked query writes completed post to disk."""
    with patch("app.agent.expert_reply.query", side_effect=_mock_query_expert_reply):
        result_info = await run_expert_reply(
            ws_path=expert_reply_workspace,
            topic_id="t1",
            topic_title="Test Topic",
            expert_name="physicist",
            expert_label="Physicist",
            user_post_id="user-1",
            user_author="alice",
            user_question="What is 2+2?",
            reply_post_id="reply-1",
            reply_created_at="2025-01-01T00:00:00Z",
        )

    assert result_info["num_turns"] == 1
    assert result_info["total_cost_usd"] == 0.001

    posts_dir = expert_reply_workspace / "posts"
    assert posts_dir.exists()
    reply_post = _find_post_by_id(posts_dir, "reply-1")
    assert reply_post is not None
    assert reply_post["status"] == "completed"
    assert "Mocked expert reply" in reply_post["body"]
    assert reply_post["author"] == "physicist"


@pytest.mark.asyncio
async def test_run_expert_reply_mocked_extracts_json_body(expert_reply_workspace: Path):
    """run_expert_reply extracts body from JSON when agent returns JSON."""
    json_body = '{"body": "Extracted from JSON response"}'

    async def mock_query_json(**kwargs):
        from claude_agent_sdk import ResultMessage

        yield ResultMessage(
            subtype="success",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            total_cost_usd=0.001,
            usage=None,
            result=json_body,
        )

    with patch("app.agent.expert_reply.query", side_effect=mock_query_json):
        await run_expert_reply(
            ws_path=expert_reply_workspace,
            topic_id="t1",
            topic_title="Test",
            expert_name="physicist",
            expert_label="Physicist",
            user_post_id="u1",
            user_author="alice",
            user_question="Q",
            reply_post_id="r1",
            reply_created_at="2025-01-01T00:00:00Z",
        )

    reply_post = _find_post_by_id(expert_reply_workspace / "posts", "r1")
    assert reply_post is not None
    assert reply_post["body"] == "Extracted from JSON response"


# --- run_discussion (mocked) ---


@pytest.fixture
def discussion_workspace(tmp_path):
    """Workspace for discussion run."""
    ws = tmp_path / "topic_ws"
    (ws / "shared" / "turns").mkdir(parents=True)
    (ws / "config").mkdir(exist_ok=True)
    (ws / "agents" / "physicist").mkdir(parents=True)
    (ws / "agents" / "physicist" / "role.md").write_text("# Physicist", encoding="utf-8")
    return ws


@pytest.mark.asyncio
async def test_run_discussion_mocked_populates_result_info(discussion_workspace: Path):
    """run_discussion with mocked query returns num_turns and total_cost_usd."""
    from app.agent.discussion import run_discussion
    from claude_agent_sdk import ResultMessage

    async def mock_query(**kwargs):
        yield ResultMessage(
            subtype="success",
            duration_ms=500,
            duration_api_ms=400,
            is_error=False,
            num_turns=3,
            session_id="test-session",
            total_cost_usd=0.05,
            usage={"input_tokens": 100, "output_tokens": 200},
            result=None,
        )

    with (
        patch("app.agent.discussion.query", side_effect=mock_query),
        patch("app.agent.discussion.build_experts_from_workspace") as mock_build,
    ):
        mock_build.return_value = {}
        result = await run_discussion(
            workspace_dir=discussion_workspace,
            config={"api_key": "test", "model": None},
            topic="Test topic",
            num_rounds=1,
            expert_names=["physicist"],
            max_turns=10,
            max_budget_usd=1.0,
        )

    assert result["num_turns"] == 3
    assert result["total_cost_usd"] == 0.05


@pytest.mark.asyncio
async def test_run_discussion_mocked_passes_mcp_to_sdk(discussion_workspace: Path):
    """When config/mcp.json exists, run_discussion passes mcp_servers and mcp__* to ClaudeAgentOptions."""
    from app.agent.discussion import run_discussion
    from claude_agent_sdk import ResultMessage

    captured_options: list[Any] = []

    async def mock_query(prompt: str = "", options=None, **kwargs):
        captured_options.append(options)
        yield ResultMessage(
            subtype="success",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            total_cost_usd=0.001,
            usage=None,
            result=None,
        )

    mcp_json = discussion_workspace / "config" / "mcp.json"
    mcp_json.write_text(
        json.dumps({
            "mcpServers": {
                "time": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-time"]},
            }
        }, indent=2),
        encoding="utf-8",
    )

    with (
        patch("app.agent.discussion.query", side_effect=mock_query),
        patch("app.agent.discussion.build_experts_from_workspace") as mock_build,
    ):
        mock_build.return_value = {}
        await run_discussion(
            workspace_dir=discussion_workspace,
            config={"api_key": "test", "model": None},
            topic="Test",
            num_rounds=1,
            expert_names=["physicist"],
            max_turns=10,
            max_budget_usd=1.0,
        )

    assert len(captured_options) == 1
    opts = captured_options[0]
    assert opts is not None
    assert hasattr(opts, "mcp_servers")
    assert opts.mcp_servers == {
        "time": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-time"]},
    }
    assert "mcp__time__*" in opts.allowed_tools


@pytest.mark.asyncio
async def test_run_discussion_mocked_no_mcp_when_config_missing(discussion_workspace: Path):
    """When config/mcp.json does not exist, run_discussion does not pass mcp_servers."""
    from app.agent.discussion import run_discussion
    from claude_agent_sdk import ResultMessage

    captured_options: list[Any] = []

    async def mock_query(prompt: str = "", options=None, **kwargs):
        captured_options.append(options)
        yield ResultMessage(
            subtype="success",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            total_cost_usd=0.001,
            usage=None,
            result=None,
        )

    # No mcp.json - do not create it
    with (
        patch("app.agent.discussion.query", side_effect=mock_query),
        patch("app.agent.discussion.build_experts_from_workspace") as mock_build,
    ):
        mock_build.return_value = {}
        await run_discussion(
            workspace_dir=discussion_workspace,
            config={"api_key": "test", "model": None},
            topic="Test",
            num_rounds=1,
            expert_names=["physicist"],
            max_turns=10,
            max_budget_usd=1.0,
        )

    assert len(captured_options) == 1
    opts = captured_options[0]
    mcp = getattr(opts, "mcp_servers", None)
    assert mcp is None or mcp == {}
    mcp_tools = [t for t in opts.allowed_tools if t.startswith("mcp__")]
    assert not mcp_tools


# --- API mention flow (mocked) ---


def test_mention_api_mocked_returns_202_and_completes(client: TestClient, isolated_workspace: Path):
    """POST mention returns 202; mocked agent completes; poll returns completed post."""
    with (
        patch("app.agent.sandbox_exec.SANDBOX_AVAILABLE", False),
        patch("app.agent.expert_reply.query", side_effect=_mock_query_expert_reply),
    ):
        create = client.post("/topics", json={"title": "AgentSDK Unit", "body": "Test"})
        assert create.status_code == 201
        topic_id = create.json()["id"]

        mention = client.post(
            f"/topics/{topic_id}/posts/mention",
            json={"author": "tester", "body": "@physicist What is light?", "expert_name": "physicist"},
        )
        assert mention.status_code == 202, mention.text
        data = mention.json()
        reply_post_id = data["reply_post_id"]
        assert data["status"] == "pending"

        post = _poll_mention_until_done(client, topic_id, reply_post_id, timeout_sec=6)
        assert post["status"] == "completed"
        assert "Mocked expert reply" in post["body"]
        assert post["author"] == "physicist"

        persisted = _find_post_by_id(isolated_workspace / "topics" / topic_id / "posts", reply_post_id)
        assert persisted is not None
        assert persisted["status"] == "completed"


# =============================================================================
# Integration tests (real API — require ANTHROPIC_API_KEY, skip if missing)
# =============================================================================


def _has_real_api_key() -> bool:
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    return bool(key and key != "test")


def _print_section(title: str):
    print(f"\n[AGENTSDK] {title}")


def _preview_one_line(text: str, limit: int = 400) -> str:
    compact = " ".join((text or "").strip().split())
    return compact[:limit] + "..." if len(compact) > limit else compact


def _assert_evidence(scenario: str, evidence: dict[str, Any], required_keys: list[str]):
    missing = [k for k in required_keys if not evidence.get(k)]
    if missing:
        raise AssertionError(
            f"{scenario} 缺少 AgentSDK 输出证据: {missing}\n"
            f"evidence={json.dumps(evidence, ensure_ascii=False, indent=2)}"
        )
    print("[AGENTSDK_EVIDENCE]", json.dumps(evidence, ensure_ascii=False))


def _find_post_by_id(posts_dir: Path, post_id: str) -> dict | None:
    """Find a post by id in posts directory."""
    if not posts_dir.exists():
        return None
    for f in posts_dir.glob("*.json"):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
            if p.get("id") == post_id:
                return p
        except Exception:
            pass
    return None


def _poll_mention_until_done(
    client: TestClient, topic_id: str, reply_post_id: str, timeout_sec: int = 6
) -> dict:
    """Poll mention status until completed or failed."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        resp = client.get(f"/topics/{topic_id}/posts/mention/{reply_post_id}")
        assert resp.status_code == 200
        post = resp.json()
        if post["status"] in ("completed", "failed"):
            return post
        time.sleep(0.2)
    pytest.fail(f"Mention did not complete within {timeout_sec}s")


def _poll_discussion_until_done(client: TestClient, topic_id: str, timeout_sec: int = 240) -> dict:
    """Poll discussion status until completed or failed."""
    deadline = time.time() + timeout_sec
    latest = None
    while time.time() < deadline:
        resp = client.get(f"/topics/{topic_id}/discussion/status")
        assert resp.status_code == 200
        latest = resp.json()
        print(f"[AGENTSDK] discussion status={latest.get('status')}")
        if latest["status"] in {"completed", "failed"}:
            return latest
        time.sleep(2)
    raise AssertionError(f"Discussion polling timeout, last status={latest}")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    not _has_real_api_key(),
    reason="需要 .env 中提供真实 ANTHROPIC_API_KEY 才能执行 Agent SDK 集成测试",
)
def test_mention_expert_real_agentsdk_generates_reply(
    client: TestClient,
    isolated_workspace: Path,
):
    """Integration: real Agent SDK generates reply and records dialog."""
    _print_section(f"mention integration workspace={isolated_workspace}")

    create = client.post("/topics", json={"title": "AgentSDK集成测试", "body": "验证真实对话链路"})
    assert create.status_code == 201
    topic_id = create.json()["id"]

    mention_resp = client.post(
        f"/topics/{topic_id}/posts/mention",
        json={
            "author": "integration_tester",
            "body": "@physicist 请用两句话解释光电效应，并给一个生活化例子。",
            "expert_name": "physicist",
        },
    )
    assert mention_resp.status_code == 202, mention_resp.text
    mention_data = mention_resp.json()
    reply_post_id = mention_data["reply_post_id"]
    user_post_id = mention_data["user_post"]["id"]
    assert mention_data["status"] == "pending"

    deadline = time.time() + 120
    latest = None
    while time.time() < deadline:
        poll = client.get(f"/topics/{topic_id}/posts/mention/{reply_post_id}")
        assert poll.status_code == 200
        latest = poll.json()
        if latest["status"] in {"completed", "failed"}:
            break
        time.sleep(2)

    assert latest is not None
    assert latest["status"] == "completed", f"专家回复未成功: {latest}"
    assert latest["body"].strip()
    assert latest["in_reply_to_id"] == user_post_id

    persisted_reply = _find_post_by_id(isolated_workspace / "topics" / topic_id / "posts", reply_post_id)
    assert persisted_reply is not None
    assert persisted_reply["status"] == "completed"
    assert persisted_reply["body"].strip()

    evidence = {
        "scenario": "mention",
        "reply_status_completed": latest["status"] == "completed",
        "reply_body_non_empty": bool(latest["body"].strip()),
        "persisted_reply_found": persisted_reply is not None,
    }
    _assert_evidence("mention", evidence, list(evidence.keys()))


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    not _has_real_api_key(),
    reason="需要 .env 中提供真实 ANTHROPIC_API_KEY 才能执行 Agent SDK 集成测试",
)
def test_discussion_real_agentsdk_generates_history(
    client: TestClient,
    isolated_workspace: Path,
):
    """Integration: real Agent SDK generates discussion history and turn files."""
    _print_section(f"discussion integration workspace={isolated_workspace}")

    create = client.post("/topics", json={"title": "Discussion AgentSDK集成测试", "body": "验证真实讨论链路"})
    assert create.status_code == 201
    topic_id = create.json()["id"]

    client.patch(f"/topics/{topic_id}", json={"expert_names": ["physicist"]})
    start_resp = client.post(
        f"/topics/{topic_id}/discussion",
        json={"num_rounds": 1, "max_turns": 20, "max_budget_usd": 1.0},
    )
    assert start_resp.status_code == 202
    assert start_resp.json()["status"] == "running"

    final = _poll_discussion_until_done(client, topic_id, timeout_sec=240)
    assert final["status"] == "completed", f"讨论运行失败: {final}"
    result = final.get("result")
    assert result is not None
    assert result["turns_count"] > 0
    assert result.get("discussion_history", "").strip()

    ws_topic = isolated_workspace / "topics" / topic_id
    turn_files = sorted((ws_topic / "shared" / "turns").glob("*.md"))
    assert len(turn_files) >= 1
    assert turn_files[0].read_text(encoding="utf-8").strip()

    evidence = {
        "scenario": "discussion",
        "status_completed": final["status"] == "completed",
        "turns_count_gt_0": result["turns_count"] > 0,
        "history_non_empty": bool(result.get("discussion_history", "").strip()),
        "turn_files_exist": len(turn_files) >= 1,
    }
    _assert_evidence("discussion", evidence, list(evidence.keys()))


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    not _has_real_api_key(),
    reason="需要 .env 中提供真实 ANTHROPIC_API_KEY 才能执行 Agent SDK 集成测试",
)
def test_discussion_mcp_time_integration(
    client: TestClient,
    isolated_workspace: Path,
):
    """Integration: MCP time server passed to Agent SDK; prompt triggers MCP tool call.

    验证 MCP 传参链路：API mcp_server_ids -> copy_mcp_to_workspace -> run_discussion
    -> ClaudeAgentOptions(mcp_servers) -> 模型调用 MCP 时间工具并返回时间信息。
    """
    _print_section("MCP time integration: 通过提示词触发 MCP 调用")

    create = client.post(
        "/topics",
        json={
            "title": "MCP 时间工具测试",
            "body": "请使用 MCP 时间工具获取当前时间，并简要回答当前是几点几分（或对应时区）。",
        },
    )
    assert create.status_code == 201
    topic_id = create.json()["id"]

    client.patch(f"/topics/{topic_id}", json={"expert_names": ["physicist"]})
    start_resp = client.post(
        f"/topics/{topic_id}/discussion",
        json={
            "num_rounds": 1,
            "max_turns": 30,
            "max_budget_usd": 1.0,
            "mcp_server_ids": ["time"],
        },
    )
    assert start_resp.status_code == 202, start_resp.text
    assert start_resp.json()["status"] == "running"

    final = _poll_discussion_until_done(client, topic_id, timeout_sec=180)
    assert final["status"] == "completed", f"MCP 讨论运行失败: {final}"
    result = final.get("result")
    assert result is not None

    # 1. 验证 MCP 传参链路：config/mcp.json 应已写入且包含 time server
    ws_topic = isolated_workspace / "topics" / topic_id
    mcp_path = ws_topic / "config" / "mcp.json"
    assert mcp_path.exists(), "copy_mcp_to_workspace 应已写入 config/mcp.json"
    mcp_data = json.loads(mcp_path.read_text(encoding="utf-8"))
    assert "time" in (mcp_data.get("mcpServers") or {}), "mcp.json 应包含 time server"

    # 2. 讨论历史（可能为空，取决于 agent 是否写出 turn 文件）
    history = (result.get("discussion_history") or "").strip()
    if not history:
        turns_dir = ws_topic / "shared" / "turns"
        if turns_dir.exists():
            turn_files = sorted(turns_dir.glob("*.md"))
            history = "\n\n".join(
                f.read_text(encoding="utf-8") for f in turn_files
            ).strip()

    # 3. 若历史非空，验证包含时间相关表述（MCP 时间工具被调用）
    time_pattern = re.compile(
        r"\d{1,2}:\d{2}|"
        r"\d{1,2}\s*点\s*\d{1,2}\s*分|"
        r"\d{4}-\d{2}-\d{2}|"
        r"UTC|GMT|timezone|时区|时间"
    )
    history_contains_time = bool(history and time_pattern.search(history))

    evidence = {
        "scenario": "mcp_time",
        "status_completed": final["status"] == "completed",
        "mcp_json_written": mcp_path.exists(),
        "mcp_time_in_config": "time" in (mcp_data.get("mcpServers") or {}),
        "history_contains_time": history_contains_time,
    }
    # 必选：MCP 传参链路（copy + config）；可选：历史含时间（取决于 agent 是否写出 turn）
    _assert_evidence("mcp_time", evidence, ["scenario", "status_completed", "mcp_json_written", "mcp_time_in_config"])
