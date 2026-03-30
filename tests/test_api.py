"""API tests focused on topic/posts/expert endpoints."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.agent.posts import load_post
from app.db.models import DiscussionTurnRecord
from app.db.session import session_scope
from app.models.schemas import DiscussionResult, DiscussionStatus
from app.models.store import update_topic_discussion
from main import app


def _create_topic(client: TestClient, title: str = "测试话题", body: str = "测试正文") -> dict:
    resp = client.post("/topics", json={"title": title, "body": body})
    assert resp.status_code == 201
    return resp.json()


def _mark_discussion_finished(topic_id: str) -> None:
    update_topic_discussion(
        topic_id,
        DiscussionStatus.COMPLETED,
        DiscussionResult(
            discussion_history="## Round 1 - Physicist\n\n测试讨论内容",
            discussion_summary="测试总结",
            turns_count=1,
            cost_usd=None,
            completed_at="2026-03-21T00:00:00+00:00",
        ),
    )


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


def test_topic_list_is_lightweight_and_contains_preview_image(client: TestClient):
    topic = _create_topic(
        client,
        title="轻量列表",
        body="封面图 ![预览](../generated_images/list_preview.png)",
    )
    topic_id = topic["id"]

    response = client.get("/topics")
    assert response.status_code == 200
    topics = response.json()
    matched = next(t for t in topics if t["id"] == topic_id)

    assert matched["preview_image"] == "../generated_images/list_preview.png"
    assert "discussion_result" not in matched
    assert "expert_names" not in matched
    assert "num_rounds" not in matched


def test_generated_image_preview_variant_returns_resized_webp(
    client: TestClient,
    isolated_workspace: Path,
):
    topic = _create_topic(
        client,
        title="缩略图测试",
        body="封面图 ![预览](../generated_images/list_preview.png)",
    )
    topic_id = topic["id"]
    source_path = (
        isolated_workspace
        / "topics"
        / topic_id
        / "shared"
        / "generated_images"
        / "list_preview.png"
    )
    source_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1200, 800), color=(220, 80, 80)).save(source_path, format="PNG")
    original_size = source_path.stat().st_size

    response = client.get(f"/topics/{topic_id}/assets/generated_images/list_preview.png?w=192&h=192&q=72")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "public, max-age=300"
    assert len(response.content) < original_size

    with Image.open(BytesIO(response.content)) as preview:
        assert preview.width <= 192
        assert preview.height <= 192


def test_generated_image_can_be_served_as_webp_without_resize(
    client: TestClient,
    isolated_workspace: Path,
):
    topic = _create_topic(
        client,
        title="WebP 展示测试",
        body="封面图 ![预览](../generated_images/detail_preview.png)",
    )
    topic_id = topic["id"]
    source_path = (
        isolated_workspace
        / "topics"
        / topic_id
        / "shared"
        / "generated_images"
        / "detail_preview.png"
    )
    source_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 360), color=(80, 120, 220)).save(source_path, format="PNG")

    response = client.get(f"/topics/{topic_id}/assets/generated_images/detail_preview.png?q=82&fm=webp")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"

    with Image.open(BytesIO(response.content)) as preview:
        assert preview.width == 640
        assert preview.height == 360


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


def test_skills_assignable_list_contains_research_dream(client: TestClient):
    response = client.get("/skills/assignable", params={"q": "research-dream"})
    assert response.status_code == 200
    data = response.json()
    assert any(item["id"] == "research-dream:research-dream" for item in data)


def test_skills_assignable_content(client: TestClient):
    """GET /skills/assignable/{id}/content returns skill markdown content."""
    response = client.get("/skills/assignable/research_methodology/content")
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "Research Methodology" in data["content"]


def test_skills_assignable_detail(client: TestClient):
    """GET /skills/assignable/{id} returns stable skill metadata."""
    response = client.get("/skills/assignable/research_methodology")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "research_methodology"
    assert data["name"] == "Research Methodology"
    assert data["source"] == "default"
    assert data["category"] == "methodology"
    assert data["content_path"] == "/skills/assignable/research_methodology/content"


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


def test_skills_assignable_list_q_search(client: TestClient):
    """GET /skills/assignable?q=X filters by id/name/description (case-insensitive)."""
    response = client.get("/skills/assignable", params={"q": "methodology"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for item in data:
        q_lower = "methodology"
        assert (
            q_lower in (item.get("id") or "").lower()
            or q_lower in (item.get("name") or "").lower()
            or q_lower in (item.get("description") or "").lower()
        )


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


def test_topic_create_sets_builtin_scholars_and_default_skills(client: TestClient, isolated_workspace: Path):
    topic = _create_topic(client, title="默认配置测试")
    topic_id = topic["id"]
    ws_path = isolated_workspace / "topics" / topic_id

    assert topic["expert_names"] == ["physicist", "biologist", "computer_scientist", "ethicist"]

    experts_resp = client.get(f"/topics/{topic_id}/experts")
    assert experts_resp.status_code == 200
    experts = experts_resp.json()
    assert [expert["name"] for expert in experts] == ["biologist", "computer_scientist", "ethicist", "physicist"]
    assert all(expert["is_from_topic_creation"] is True for expert in experts)

    mode_resp = client.get(f"/topics/{topic_id}/moderator-mode")
    assert mode_resp.status_code == 200
    mode_cfg = mode_resp.json()
    # 默认只启用 image_generation
    assert mode_cfg["skill_list"] == ["image_generation"]

    skills_dir = ws_path / "config" / "skills"
    assert (skills_dir / "image_generation.md").exists()


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

    persisted = load_post(isolated_workspace / "topics" / topic_id, post["id"])
    assert persisted is not None
    assert persisted["id"] == post["id"]
    posts_context = isolated_workspace / "topics" / topic_id / "shared" / "posts_context.md"
    assert posts_context.exists()
    assert "第一条留言" in posts_context.read_text(encoding="utf-8")


def test_discussion_status_syncs_turn_markdown_into_database(
    client: TestClient,
    isolated_workspace: Path,
):
    topic = _create_topic(client, title="同步讨论轮次", body="验证 turn 入库")
    topic_id = topic["id"]
    turns_dir = isolated_workspace / "topics" / topic_id / "shared" / "turns"
    turns_dir.mkdir(parents=True, exist_ok=True)
    (turns_dir / "round1_physicist.md").write_text("第一轮物理学家观点", encoding="utf-8")
    (turns_dir / "round1_biologist.md").write_text("第一轮生物学家观点", encoding="utf-8")

    response = client.get(f"/topics/{topic_id}/discussion/status")
    assert response.status_code == 200

    with session_scope() as session:
        rows = session.scalars(
            select(DiscussionTurnRecord)
            .where(DiscussionTurnRecord.topic_id == topic_id)
            .order_by(DiscussionTurnRecord.round_num.asc(), DiscussionTurnRecord.turn_key.asc())
        ).all()

    assert len(rows) == 2
    assert rows[0].round_num == 1
    assert rows[0].expert_name == "biologist"
    assert rows[0].body == "第一轮生物学家观点"
    assert rows[1].expert_name == "physicist"
    assert rows[1].body == "第一轮物理学家观点"


def test_mention_unknown_expert_returns_400(client: TestClient):
    topic = _create_topic(client)
    topic_id = topic["id"]
    _mark_discussion_finished(topic_id)

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


def test_mention_requires_finished_discussion(client: TestClient):
    topic = _create_topic(client)
    topic_id = topic["id"]

    response = client.post(
        f"/topics/{topic_id}/posts/mention",
        json={
            "author": "alice",
            "body": "@physicist 请回答",
            "expert_name": "physicist",
        },
    )
    assert response.status_code == 409
    assert "AI discussion has not started" in response.json()["detail"]


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


def test_mcp_assignable_list_q_search(client: TestClient):
    """GET /mcp/assignable?q=X filters by id/name/description."""
    resp = client.get("/mcp/assignable", params={"q": "inspector"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    ids = [i["id"] for i in data]
    assert "inspector" in ids


def test_mcp_assignable_content(client: TestClient):
    """GET /mcp/assignable/{id}/content returns MCP config JSON."""
    resp = client.get("/mcp/assignable/inspector/content")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    content = json.loads(data["content"])
    assert content["command"] == "npx"
    assert "@modelcontextprotocol/inspector" in content["args"]


def test_mcp_assignable_streamable_http_hides_headers(client: TestClient):
    """HTTP MCP config returned to frontend MUST NOT include headers."""
    # Wan26Media is a built-in http MCP defined in libs/mcps/default/meta.json
    resp = client.get("/mcp/assignable/Wan26Media/content")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    content = json.loads(data["content"])
    assert content.get("type") == "http"
    assert "url" in content
    # Security: headers (with API keys) must never be exposed through this API
    assert "headers" not in content


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


# --- Moderator modes tests (skills/moderator_modes/) ---

def test_moderator_modes_assignable_list(client: TestClient):
    """GET /moderator-modes/assignable returns modes with category, source from skills/moderator_modes/."""
    resp = client.get("/moderator-modes/assignable")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    ids = [m["id"] for m in data]
    assert "standard" in ids
    assert "brainstorm" in ids
    for m in data:
        assert "id" in m
        assert "name" in m
        assert "category" in m
        assert "category_name" in m
        assert "source" in m


def test_moderator_modes_assignable_list_q_search(client: TestClient):
    """GET /moderator-modes/assignable?q=X filters by id/name/description."""
    resp = client.get("/moderator-modes/assignable", params={"q": "standard"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    ids = [m["id"] for m in data]
    assert "standard" in ids


def test_moderator_modes_assignable_content(client: TestClient):
    """GET /moderator-modes/assignable/{id}/content returns mode prompt content."""
    resp = client.get("/moderator-modes/assignable/standard/content")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "round-table discussion moderator" in data["content"] or "topic" in data["content"]


def test_moderator_modes_list(client: TestClient):
    """GET /moderator-modes returns preset modes from skills/moderator_modes/."""
    resp = client.get("/moderator-modes")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    ids = [m["id"] for m in data]
    assert "standard" in ids
    assert "brainstorm" in ids
    assert "debate" in ids
    assert "review" in ids
    for m in data:
        assert "id" in m
        assert "name" in m
        assert "description" in m
        assert "num_rounds" in m
        assert "convergence_strategy" in m


def test_libs_invalidate_cache(client: TestClient):
    """POST /libs/invalidate-cache clears meta cache and returns success."""
    resp = client.post("/libs/invalidate-cache")
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "invalidated" in data["message"].lower() or "cache" in data["message"].lower()


def test_experts_list_minimal(client: TestClient):
    """GET /experts?fields=minimal returns experts without skill_content (empty string)."""
    resp = client.get("/experts", params={"fields": "minimal"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if len(data) > 0:
        for item in data:
            assert "name" in item
            assert "label" in item
            assert item.get("skill_content") == ""


def test_experts_get_content(client: TestClient):
    """GET /experts/{name}/content returns skill markdown content only."""
    resp = client.get("/experts/physicist/content")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert isinstance(data["content"], str)


def test_experts_get_content_not_found(client: TestClient):
    """GET /experts/{name}/content returns 404 for unknown expert."""
    resp = client.get("/experts/nonexistent_expert_xyz/content")
    assert resp.status_code == 404


def test_moderator_mode_get_and_set(client: TestClient, isolated_workspace: Path):
    """GET/PUT /topics/{id}/moderator-mode read/write config from workspace."""
    topic = _create_topic(client)
    topic_id = topic["id"]

    get_resp = client.get(f"/topics/{topic_id}/moderator-mode")
    assert get_resp.status_code == 200
    cfg = get_resp.json()
    assert cfg["mode_id"] == "standard"
    assert "num_rounds" in cfg

    put_resp = client.put(
        f"/topics/{topic_id}/moderator-mode",
        json={"mode_id": "brainstorm", "num_rounds": 4, "custom_prompt": None},
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["mode_id"] == "brainstorm"
    assert updated["num_rounds"] == 4

    config_file = isolated_workspace / "topics" / topic_id / "config" / "moderator_mode.json"
    assert config_file.exists()
    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved["mode_id"] == "brainstorm"
    assert saved["skill_list"] == ["image_generation"]

    topic_resp = client.get(f"/topics/{topic_id}")
    assert topic_resp.status_code == 200
    assert topic_resp.json()["num_rounds"] == 4

    # Extended fields: skill_list, mcp_server_ids, model
    put_ext = client.put(
        f"/topics/{topic_id}/moderator-mode",
        json={
            "mode_id": "brainstorm",
            "num_rounds": 4,
            "custom_prompt": None,
            "skill_list": ["skill_a", "skill_b"],
            "mcp_server_ids": ["mcp_x"],
            "model": "qwen-flash",
        },
    )
    assert put_ext.status_code == 200
    ext_cfg = put_ext.json()
    assert ext_cfg["skill_list"] == ["skill_a", "skill_b", "image_generation"]
    assert ext_cfg["mcp_server_ids"] == ["mcp_x"]
    assert ext_cfg["model"] == "qwen-flash"

    get_again = client.get(f"/topics/{topic_id}/moderator-mode")
    assert get_again.status_code == 200
    reloaded = get_again.json()
    assert reloaded["skill_list"] == ["skill_a", "skill_b", "image_generation"]
    assert reloaded["mcp_server_ids"] == ["mcp_x"]
    assert reloaded["model"] == "qwen-flash"


def test_expert_share_when_meta_json_missing(client: TestClient, isolated_workspace: Path, monkeypatch):
    """Share succeeds when topiclab_shared/meta.json does not exist (first share)."""
    from app.core.config import get_experts_dir

    # Use isolated experts dir with no topiclab_shared/meta.json
    experts_root = isolated_workspace / "libs" / "experts"
    experts_root.mkdir(parents=True)
    monkeypatch.setattr("app.api.topic_experts.get_experts_dir", lambda: experts_root)

    topic = _create_topic(client)
    topic_id = topic["id"]
    ws_path = isolated_workspace / "topics" / topic_id
    (ws_path / "agents" / "first_share_expert").mkdir(parents=True)
    (ws_path / "agents" / "first_share_expert" / "role.md").write_text("# First Share", encoding="utf-8")
    (ws_path / "config").mkdir(parents=True, exist_ok=True)
    meta = {"experts": [{"name": "first_share_expert", "label": "First", "description": "First share test"}]}
    (ws_path / "config" / "experts_metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    resp = client.post(f"/topics/{topic_id}/experts/first_share_expert/share")
    assert resp.status_code == 200
    assert resp.json().get("expert_name") == "first_share_expert"

    meta_path = experts_root / "topiclab_shared" / "meta.json"
    assert meta_path.exists()
    meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
    assert "first_share_expert" in meta_data.get("experts", {})


def test_expert_share_to_topiclab_shared(client: TestClient, isolated_workspace: Path):
    """POST /topics/{id}/experts/{name}/share writes to topiclab_shared and reloads."""
    from app.core.config import get_experts_dir

    topic = _create_topic(client)
    topic_id = topic["id"]
    ws_path = isolated_workspace / "topics" / topic_id
    (ws_path / "agents" / "test_shared_expert").mkdir(parents=True, exist_ok=True)
    (ws_path / "agents" / "test_shared_expert" / "role.md").write_text("# Test Expert\nRole content.", encoding="utf-8")
    (ws_path / "config").mkdir(parents=True, exist_ok=True)
    meta = {"experts": [{"name": "test_shared_expert", "label": "Test Shared", "description": "For share test"}]}
    (ws_path / "config" / "experts_metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    resp = client.post(f"/topics/{topic_id}/experts/test_shared_expert/share")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("expert_name") == "test_shared_expert"

    experts_dir = get_experts_dir()
    shared_file = experts_dir / "topiclab_shared" / "test_shared_expert.md"
    assert shared_file.exists()
    assert "Test Expert" in shared_file.read_text(encoding="utf-8")

    # Verify expert appears in list
    list_resp = client.get("/experts")
    assert list_resp.status_code == 200
    names = [e["name"] for e in list_resp.json()]
    assert "test_shared_expert" in names


def test_expert_share_rejects_builtin(client: TestClient, isolated_workspace: Path):
    """Share rejects overwriting built-in expert (physicist)."""
    topic = _create_topic(client)
    topic_id = topic["id"]
    ws_path = isolated_workspace / "topics" / topic_id
    (ws_path / "agents" / "physicist").mkdir(parents=True, exist_ok=True)
    (ws_path / "agents" / "physicist" / "role.md").write_text("# Custom Physicist", encoding="utf-8")
    (ws_path / "config").mkdir(parents=True, exist_ok=True)
    meta = {"experts": [{"name": "physicist", "label": "Custom", "description": "Test"}]}
    (ws_path / "config" / "experts_metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    resp = client.post(f"/topics/{topic_id}/experts/physicist/share")
    assert resp.status_code == 409
    assert "built-in" in resp.json().get("detail", "").lower()


def test_topic_expert_import_public_twin_keeps_full_content(client: TestClient):
    topic = _create_topic(client)
    topic_id = topic["id"]
    add_resp = client.post(
        f"/topics/{topic_id}/experts",
        json={
            "source": "custom",
            "name": "twin_public_expert",
            "label": "公开分身",
            "description": "公开导入",
            "role_content": "# 公开分身\n\n这是完整内容",
            "origin_type": "digital_twin",
            "origin_visibility": "public",
            "masked": False,
        },
    )
    assert add_resp.status_code == 201

    content_resp = client.get(f"/topics/{topic_id}/experts/twin_public_expert/content")
    assert content_resp.status_code == 200
    body = content_resp.json()
    assert body["masked"] is False
    assert "这是完整内容" in body["role_content"]


def test_topic_expert_import_private_twin_forces_masked_content(client: TestClient):
    topic = _create_topic(client)
    topic_id = topic["id"]
    add_resp = client.post(
        f"/topics/{topic_id}/experts",
        json={
            "source": "custom",
            "name": "twin_private_expert",
            "label": "私密分身",
            "description": "私密导入",
            "role_content": "# 私密分身\n\nSECRET_CONTENT_SHOULD_NOT_LEAK",
            "origin_type": "digital_twin",
            "origin_visibility": "private",
            "masked": False,
        },
    )
    assert add_resp.status_code == 201

    content_resp = client.get(f"/topics/{topic_id}/experts/twin_private_expert/content")
    assert content_resp.status_code == 200
    body = content_resp.json()
    assert body["masked"] is True
    assert "SECRET_CONTENT_SHOULD_NOT_LEAK" not in body["role_content"]
    assert "内容已脱敏" in body["role_content"]


def test_moderator_mode_share_to_topiclab_shared(client: TestClient, isolated_workspace: Path):
    """POST /topics/{id}/moderator-mode/share writes custom mode to topiclab_shared."""
    from app.core.config import get_moderator_modes_dir

    topic = _create_topic(client)
    topic_id = topic["id"]
    config_dir = isolated_workspace / "topics" / topic_id / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "mode_id": "custom",
        "num_rounds": 5,
        "custom_prompt": "# Custom moderator\nModerator prompt content.",
    }
    (config_dir / "moderator_mode.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    resp = client.post(
        f"/topics/{topic_id}/moderator-mode/share",
        json={"mode_id": "test_shared_mode", "name": "Test Shared Mode", "description": "For share test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("mode_id") == "test_shared_mode"

    modes_dir = get_moderator_modes_dir()
    shared_file = modes_dir / "topiclab_shared" / "test_shared_mode.md"
    assert shared_file.exists()
    assert "Custom moderator" in shared_file.read_text(encoding="utf-8")
