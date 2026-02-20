"""API tests focused on topic/posts/expert endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app


def _create_topic(client: TestClient, title: str = "测试话题", body: str = "测试正文") -> dict:
    resp = client.post("/topics", json={"title": title, "body": body})
    assert resp.status_code == 201
    return resp.json()


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_topic_create_and_get(client: TestClient):
    topic = _create_topic(client, title="API 话题", body="用于 API 测试")
    topic_id = topic["id"]

    get_resp = client.get(f"/topics/{topic_id}")
    assert get_resp.status_code == 200
    got = get_resp.json()
    assert got["id"] == topic_id
    assert got["title"] == "API 话题"
    assert got["body"] == "用于 API 测试"
    assert got["discussion_status"] == "pending"


def test_topic_list_contains_created_topics(client: TestClient):
    _create_topic(client, title="列表A")
    _create_topic(client, title="列表B")

    response = client.get("/topics")
    assert response.status_code == 200
    topics = response.json()
    assert isinstance(topics, list)
    titles = [t["title"] for t in topics]
    assert "列表A" in titles
    assert "列表B" in titles


def test_topic_update_and_close(client: TestClient):
    topic = _create_topic(client, title="待更新", body="old")
    topic_id = topic["id"]

    patch_resp = client.patch(f"/topics/{topic_id}", json={"title": "已更新", "body": "new"})
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["title"] == "已更新"
    assert patched["body"] == "new"

    close_resp = client.post(f"/topics/{topic_id}/close")
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "closed"


def test_topic_create_invalid_empty_title(client: TestClient):
    response = client.post("/topics", json={"title": "", "body": "body"})
    assert response.status_code == 422


def test_get_topic_not_found(client: TestClient):
    response = client.get("/topics/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_skills_assignable_list(client: TestClient):
    """GET /skills/assignable returns list of assignable skills from meta.json."""
    response = client.get("/skills/assignable")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        for item in data:
            assert "id" in item
            assert "name" in item
            assert "description" in item
            assert "category" in item
            assert "category_name" in item
            assert "source" in item


def test_skills_assignable_content(client: TestClient):
    """GET /skills/assignable/{id}/content returns skill markdown content."""
    response = client.get("/skills/assignable/research_methodology/content")
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "Research Methodology" in data["content"]


def test_skills_assignable_list_category_filter(client: TestClient):
    """GET /skills/assignable?category=X returns only skills in that category."""
    response = client.get("/skills/assignable", params={"category": "methodology"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        assert item.get("category") == "methodology"


def test_skills_assignable_list_minimal_fields(client: TestClient):
    """GET /skills/assignable?fields=minimal returns id, name, category, category_name only."""
    response = client.get("/skills/assignable", params={"fields": "minimal"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        item = data[0]
        assert "id" in item and "name" in item and "category" in item and "category_name" in item
        assert "description" not in item
        assert "source" not in item


def test_skills_assignable_list_pagination(client: TestClient):
    """GET /skills/assignable?limit=2&offset=0 returns at most 2 items."""
    response = client.get("/skills/assignable", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 2


def test_skills_assignable_categories(client: TestClient):
    """GET /skills/assignable/categories returns list of skill categories."""
    response = client.get("/skills/assignable/categories")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        for item in data:
            assert "id" in item
            assert "name" in item


def test_workspace_is_created_with_default_agents(client: TestClient, isolated_workspace: Path):
    topic = _create_topic(client)
    ws_path = isolated_workspace / "topics" / topic["id"]

    assert ws_path.exists()
    assert (ws_path / "shared" / "turns").exists()
    assert (ws_path / "config" / "sandbox_meta.json").exists()
    assert (ws_path / "agents").exists()

    experts_resp = client.get(f"/topics/{topic['id']}/experts")
    assert experts_resp.status_code == 200
    experts = experts_resp.json()
    assert isinstance(experts, list)
    assert len(experts) > 0


def test_posts_create_list_and_persistence(client: TestClient, isolated_workspace: Path):
    topic = _create_topic(client)
    topic_id = topic["id"]

    post_resp = client.post(
        f"/topics/{topic_id}/posts",
        json={"author": "alice", "body": "第一条留言"},
    )
    assert post_resp.status_code == 201
    post = post_resp.json()
    assert post["author"] == "alice"
    assert post["status"] == "completed"

    list_resp = client.get(f"/topics/{topic_id}/posts")
    assert list_resp.status_code == 200
    posts = list_resp.json()
    assert len(posts) == 1
    assert posts[0]["id"] == post["id"]
    assert posts[0]["body"] == "第一条留言"

    posts_dir = isolated_workspace / "topics" / topic_id / "posts"
    files = list(posts_dir.glob("*.json"))
    assert len(files) == 1
    persisted = json.loads(files[0].read_text(encoding="utf-8"))
    assert persisted["id"] == post["id"]


def test_mention_unknown_expert_returns_400(client: TestClient):
    topic = _create_topic(client)
    topic_id = topic["id"]

    response = client.post(
        f"/topics/{topic_id}/posts/mention",
        json={
            "author": "bob",
            "body": "@ghost 你怎么看？",
            "expert_name": "ghost",
        },
    )
    assert response.status_code == 400
    assert "not in this topic" in response.json()["detail"]


def test_copy_skills_to_workspace(isolated_workspace: Path):
    """copy_skills_to_workspace copies selected skills from assignable_skills to config/skills/."""
    from app.agent.workspace import copy_skills_to_workspace, ensure_topic_workspace

    topic_id = "test-skill-copy"
    ws_path = ensure_topic_workspace(isolated_workspace, topic_id)

    copied = copy_skills_to_workspace(ws_path, ["research_methodology", "critical_thinking"])
    assert len(copied) == 2
    assert "research_methodology" in copied
    assert "critical_thinking" in copied

    skills_dir = ws_path / "config" / "skills"
    assert skills_dir.exists()
    assert (skills_dir / "research_methodology.md").exists()
    assert (skills_dir / "critical_thinking.md").exists()
    assert "Research Methodology" in (skills_dir / "research_methodology.md").read_text(encoding="utf-8")

    # Invalid skill id is skipped
    copied2 = copy_skills_to_workspace(ws_path, ["nonexistent_skill"])
    assert len(copied2) == 0

    # Empty list returns empty
    assert copy_skills_to_workspace(ws_path, []) == []


def test_copy_skills_uses_default_source_path(isolated_workspace: Path):
    """Verify skills are resolved from default/{category}/{slug}.md structure."""
    from app.agent.workspace import copy_skills_to_workspace, ensure_topic_workspace

    ws_path = ensure_topic_workspace(isolated_workspace, "test-default-path")
    copied = copy_skills_to_workspace(ws_path, ["evidence_based"])
    assert "evidence_based" in copied
    content = (ws_path / "config" / "skills" / "evidence_based.md").read_text(encoding="utf-8")
    assert "Evidence-Based" in content


# --- MCP assignable tests ---

def test_mcp_assignable_list(client: TestClient):
    """GET /mcp/assignable returns list of assignable MCPs from skills/mcps/."""
    resp = client.get("/mcp/assignable")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if len(data) > 0:
        for item in data:
            assert "id" in item
            assert "name" in item
            assert "description" in item
            assert "category" in item
            assert "category_name" in item
            assert "source" in item


def test_mcp_assignable_content(client: TestClient):
    """GET /mcp/assignable/{id}/content returns MCP config JSON."""
    resp = client.get("/mcp/assignable/inspector/content")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    content = json.loads(data["content"])
    assert content["command"] == "npx"
    assert "@modelcontextprotocol/inspector" in content["args"]


def test_copy_mcp_to_workspace(isolated_workspace: Path):
    """copy_mcp_to_workspace copies selected MCPs from skills/mcps/ to topic config/mcp.json."""
    from app.agent.workspace import copy_mcp_to_workspace, ensure_topic_workspace

    topic_id = "test-mcp-copy"
    ws_path = ensure_topic_workspace(isolated_workspace, topic_id)

    copied = copy_mcp_to_workspace(ws_path, ["inspector"])
    assert len(copied) == 1
    assert "inspector" in copied

    mcp_path = ws_path / "config" / "mcp.json"
    assert mcp_path.exists()
    data = json.loads(mcp_path.read_text(encoding="utf-8"))
    assert "inspector" in data["mcpServers"]
    assert data["mcpServers"]["inspector"]["command"] == "npx"
