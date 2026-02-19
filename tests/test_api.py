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
