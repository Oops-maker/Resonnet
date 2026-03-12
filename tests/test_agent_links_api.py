"""Tests for agent-links APIs."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient


_DEMO_LINK = {
    "slug": "demo-agent",
    "name": "Demo Agent",
    "description": "Demo",
    "module": "profile_helper",
    "entry_skill": "collect-basic-info",
    "blueprint_root": "/tmp/demo",
    "agent_workdir": "/tmp/demo",
    "rule_file_path": "/tmp/demo/.cursor/rules/profile-collector.mdc",
    "skills_path": "/tmp/demo/.cursor/skills",
    "docs_path": "/tmp/demo/doc",
    "template_path": "/tmp/demo/profiles/_template.md",
    "welcome_message": "Welcome",
    "default_model": "",
}


def test_agent_links_list_and_get(client: TestClient, monkeypatch):
    monkeypatch.setattr("app.api.agent_links.links_service.list_agent_links", lambda: [_DEMO_LINK])
    monkeypatch.setattr("app.api.agent_links.links_service.get_agent_link", lambda slug: _DEMO_LINK if slug == "demo-agent" else None)

    slug = "demo-agent"
    list_resp = client.get("/agent-links")
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["slug"] == slug

    detail_resp = client.get(f"/agent-links/{slug}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["module"] == "profile_helper"
    assert detail["slug"] == slug
    assert detail["agent_workdir"]
    assert detail["rule_file_path"]


def test_agent_link_start_session_and_chat_stream(client: TestClient, monkeypatch):
    from app.services.profile_helper import sessions as profile_sessions

    async def _fake_stream_chat(
        *,
        session_id: str,
        user_message: str,
        workdir: str,
        system_prompt: str,
        model: str | None = None,
    ):
        assert session_id
        assert system_prompt is not None
        assert "profile-collector.mdc" in system_prompt
        assert workdir == "/tmp/session-ws"
        assert user_message == "hello"
        yield {"type": "assistant_delta", "content": "O"}
        yield {"type": "assistant_delta", "content": "K"}
        yield {"type": "tool_call", "tool_name": "Read", "tool_use_id": "t1", "input": {"file_path": "x.md"}}

    monkeypatch.setattr("app.api.agent_links.agent_links_runtime.stream_chat", _fake_stream_chat)
    monkeypatch.setattr(
        "app.api.agent_links.agent_links_runtime.ensure_session_workspace",
        lambda *args, **kwargs: "/tmp/session-ws",
    )
    monkeypatch.setattr("app.api.agent_links.links_service.get_agent_link", lambda slug: _DEMO_LINK if slug == "demo-agent" else None)
    monkeypatch.setattr("app.api.agent_links.links_service.load_rule_prompt_for_link", lambda link: (link["rule_file_path"], "# rule content"))
    monkeypatch.setattr("app.api.agent_links.profile_sessions.list_ids", lambda: ["x"])

    slug = "demo-agent"
    start_resp = client.post(f"/agent-links/{slug}/session", json={})
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]
    assert session_id
    assert start_resp.json()["agent_workdir"]
    assert start_resp.json()["welcome_message"]

    # Session is bound to this agent link.
    s = profile_sessions.get(session_id)
    assert s is not None
    assert s.get("agent_link_slug") == slug
    assert s.get("agent_workdir")

    chat_resp = client.post(
        f"/agent-links/{slug}/chat",
        json={"session_id": session_id, "message": "hello"},
    )
    assert chat_resp.status_code == 200
    assert chat_resp.headers.get("x-session-id") == session_id
    assert chat_resp.headers.get("x-agent-link") == slug
    assert chat_resp.headers.get("x-agent-workdir")
    assert '"type": "assistant_delta"' in chat_resp.text
    assert '"type": "tool_call"' in chat_resp.text
    assert "data: [DONE]" in chat_resp.text

    s2 = profile_sessions.get(session_id)
    assert s2 is not None


def test_agent_link_chat_rejects_cross_link_session(client: TestClient, monkeypatch):
    from app.services.profile_helper import sessions as profile_sessions

    def _fake_get_agent_link(slug: str):
        if slug == "persona-agent":
            return {
                "slug": "persona-agent",
                "name": "A",
                "description": "",
                "module": "profile_helper",
                "entry_skill": "",
                "blueprint_root": "/tmp/a",
                "agent_workdir": "/tmp/a",
                "rule_file_path": "/tmp/a/.cursor/rules/profile-collector.mdc",
                "skills_path": "",
                "docs_path": "",
                "template_path": "",
                "welcome_message": "",
                "default_model": "",
            }
        if slug == "survey-agent":
            return {
                "slug": "survey-agent",
                "name": "B",
                "description": "",
                "module": "profile_helper",
                "entry_skill": "",
                "blueprint_root": "/tmp/b",
                "agent_workdir": "/tmp/b",
                "rule_file_path": "/tmp/b/.cursor/rules/profile-collector.mdc",
                "skills_path": "",
                "docs_path": "",
                "template_path": "",
                "welcome_message": "",
                "default_model": "",
            }
        return None

    monkeypatch.setattr("app.api.agent_links.links_service.get_agent_link", _fake_get_agent_link)
    monkeypatch.setattr(
        "app.api.agent_links.agent_links_runtime.ensure_session_workspace",
        lambda *args, **kwargs: "/tmp/session-ws",
    )
    monkeypatch.setattr("app.api.agent_links.profile_sessions.list_ids", lambda: ["x"])

    sid, session = profile_sessions.get_or_create(None)
    session["agent_link_slug"] = "persona-agent"

    resp = client.post(
        "/agent-links/survey-agent/chat",
        json={"session_id": sid, "message": "hi"},
    )
    assert resp.status_code == 409


def _make_blueprint_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("demo/.cursor/rules/profile-collector.mdc", "# role definition")
        zf.writestr("demo/profiles/_template.md", "# template")
        zf.writestr("demo/doc/README.md", "demo docs")
    return buf.getvalue()


def test_agent_link_import_zip_success(client: TestClient, monkeypatch, tmp_path: Path):
    target_root = tmp_path / "agent_links"
    monkeypatch.setattr("app.services.agent_links.get_agent_links_dir", lambda: target_root)

    files = {
        "file": ("demo.zip", _make_blueprint_zip(), "application/zip"),
    }
    data = {
        "slug": "imported-demo",
        "name": "Imported Demo",
        "description": "Imported from zip",
        "rule_file_path": ".cursor/rules/profile-collector.mdc",
        "welcome_message": "Hello from imported demo",
        "default_model": "qwen3.5-plus",
        "overwrite": "false",
    }
    resp = client.post("/agent-links/import", files=files, data=data)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["slug"] == "imported-demo"
    assert payload["name"] == "Imported Demo"
    assert payload["welcome_message"] == "Hello from imported demo"
    assert payload["default_model"] == "qwen3.5-plus"

    cfg_path = target_root / "imported-demo" / "agent.json"
    assert cfg_path.exists()


def test_agent_link_import_zip_requires_zip(client: TestClient):
    files = {
        "file": ("demo.txt", b"not a zip", "text/plain"),
    }
    data = {
        "name": "Bad Import",
        "rule_file_path": ".cursor/rules/profile-collector.mdc",
        "welcome_message": "welcome",
    }
    resp = client.post("/agent-links/import", files=files, data=data)
    assert resp.status_code == 400


def test_agent_link_workspace_file_upload_success(client: TestClient, monkeypatch, tmp_path: Path):
    from app.services.profile_helper import sessions as profile_sessions

    session_ws = tmp_path / "session-ws"
    session_ws.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("app.api.agent_links.links_service.get_agent_link", lambda slug: _DEMO_LINK if slug == "demo-agent" else None)
    monkeypatch.setattr(
        "app.api.agent_links.agent_links_runtime.ensure_session_workspace",
        lambda *args, **kwargs: str(session_ws),
    )
    monkeypatch.setattr("app.api.agent_links.profile_sessions.list_ids", lambda: ["x"])

    sid, _ = profile_sessions.get_or_create(None)
    files = {"file": ("notes.md", b"# hello", "text/markdown")}
    data = {"session_id": sid, "target_path": "uploads/research"}
    resp = client.post("/agent-links/demo-agent/files/upload", files=files, data=data)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["session_id"] == sid
    assert payload["path"] == "uploads/research/notes.md"
    assert payload["size"] == 7
    assert (session_ws / "uploads" / "research" / "notes.md").exists()


def test_agent_link_workspace_file_upload_rejects_outside_path(client: TestClient, monkeypatch, tmp_path: Path):
    session_ws = tmp_path / "session-ws"
    session_ws.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("app.api.agent_links.links_service.get_agent_link", lambda slug: _DEMO_LINK if slug == "demo-agent" else None)
    monkeypatch.setattr(
        "app.api.agent_links.agent_links_runtime.ensure_session_workspace",
        lambda *args, **kwargs: str(session_ws),
    )
    monkeypatch.setattr("app.api.agent_links.profile_sessions.list_ids", lambda: ["x"])

    files = {"file": ("notes.md", b"abc", "text/markdown")}
    data = {"target_path": "../outside"}
    resp = client.post("/agent-links/demo-agent/files/upload", files=files, data=data)
    assert resp.status_code == 400
