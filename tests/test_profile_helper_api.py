"""Tests for profile helper and profile import APIs."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_profile_helper_session_expired_cleanup(monkeypatch):
    from app.services.profile_helper import sessions as profile_sessions

    profile_sessions._sessions.clear()
    monkeypatch.setattr(profile_sessions, "SESSION_TTL_SECONDS", 60)

    sid, session = profile_sessions.get_or_create("expired_session")
    assert sid == "expired_session"
    session["updated_at"] = profile_sessions._now() - 120

    assert profile_sessions.get(sid) is None
    assert sid not in profile_sessions._sessions


def test_profile_helper_session_max_count_cleanup(monkeypatch):
    from app.services.profile_helper import sessions as profile_sessions

    profile_sessions._sessions.clear()
    monkeypatch.setattr(profile_sessions, "SESSION_TTL_SECONDS", 3600)
    monkeypatch.setattr(profile_sessions, "SESSION_MAX_COUNT", 2)

    s1, _ = profile_sessions.get_or_create("s1")
    profile_sessions._sessions[s1]["updated_at"] = profile_sessions._now() - 10
    s2, _ = profile_sessions.get_or_create("s2")
    profile_sessions._sessions[s2]["updated_at"] = profile_sessions._now() - 5
    s3, _ = profile_sessions.get_or_create("s3")

    assert s3 in profile_sessions._sessions
    assert len(profile_sessions._sessions) == 2
    assert "s1" not in profile_sessions._sessions
    assert "s2" in profile_sessions._sessions


def test_profile_helper_session_lifecycle_and_download(client: TestClient):
    create_resp = client.get("/profile-helper/session")
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]
    assert session_id

    profile_resp = client.get(f"/profile-helper/profile/{session_id}")
    assert profile_resp.status_code == 200
    data = profile_resp.json()
    assert "profile" in data
    assert data["forum_profile"] == ""

    # forum profile should not be downloadable before generation
    forum_download_404 = client.get(f"/profile-helper/download/{session_id}/forum")
    assert forum_download_404.status_code == 404

    download_resp = client.get(f"/profile-helper/download/{session_id}")
    assert download_resp.status_code == 200
    assert "attachment; filename=\"profile.md\"" in download_resp.headers.get("content-disposition", "")
    assert "markdown" in download_resp.headers.get("content-type", "")

    reset_resp = client.post(f"/profile-helper/session/reset/{session_id}")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["ok"] is True


def test_profile_helper_chat_stream_updates_profile(client: TestClient, monkeypatch):
    from app.services.profile_helper import sessions as profile_sessions

    def _fake_run_agent(user_message: str, session: dict, *, stream: bool = False, model: str | None = None):
        # Simulate the real tool side-effects, including auto-save.
        profile_sessions.save_profile(session, f"# 科研人员画像 — Test User\n\nprofile updated: {user_message}")
        profile_sessions.save_forum_profile(session, "# Test Forum Profile\n\nGenerated forum profile")
        text = "OK"
        if stream:
            for ch in text:
                yield ch
        else:
            yield text

    monkeypatch.setattr("app.api.profile_helper.profile_agent.run_agent", _fake_run_agent)

    session_id, _ = profile_sessions.get_or_create(None)

    resp = client.post(
        "/profile-helper/chat",
        json={"session_id": session_id, "message": "hello", "model": "qwen-flash"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("x-session-id") == session_id
    body = resp.text
    assert 'data: {"content": "O"}' in body
    assert 'data: {"content": "K"}' in body
    assert "data: [DONE]" in body

    profile_resp = client.get(f"/profile-helper/profile/{session_id}")
    assert profile_resp.status_code == 200
    profile = profile_resp.json()
    assert "profile updated: hello" in profile["profile"]
    assert profile["forum_profile"].startswith("# Test Forum Profile")

    forum_download = client.get(f"/profile-helper/download/{session_id}/forum")
    assert forum_download.status_code == 200
    assert "attachment; filename=\"forum-profile.md\"" in forum_download.headers.get("content-disposition", "")


def test_profile_helper_auto_saves_profiles_to_workspace(isolated_workspace: Path):
    from app.services.profile_helper import sessions as profile_sessions

    profile_sessions._sessions.clear()
    session_id, session = profile_sessions.get_or_create("persisted-session")

    profile_path = profile_sessions.save_profile(
        session,
        "# 科研人员画像 — Test User\n\nAuto-saved profile",
    )
    forum_path = profile_sessions.save_forum_profile(
        session,
        "# Test Forum Profile\n\nAuto-saved forum profile",
    )

    expected_dir = isolated_workspace / "profile_helper" / "profiles"
    assert profile_path.parent == expected_dir
    assert forum_path.parent == expected_dir
    assert profile_path.exists()
    assert forum_path.exists()
    assert "Auto-saved profile" in profile_path.read_text(encoding="utf-8")
    assert "Auto-saved forum profile" in forum_path.read_text(encoding="utf-8")


def test_profile_helper_chat_rejects_empty_message(client: TestClient):
    resp = client.post("/profile-helper/chat", json={"message": "   "})
    assert resp.status_code == 400


def test_import_profile_to_experts_success(client: TestClient, isolated_workspace: Path, monkeypatch):
    experts_root = isolated_workspace / "libs" / "experts"
    experts_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("app.api.experts.get_experts_dir", lambda: experts_root)
    monkeypatch.setattr("app.api.experts.reload_expert_specs", lambda: None)
    monkeypatch.setattr("app.core.libs_service.invalidate_libs_cache", lambda: None)

    forum_profile = "# Cognitive Mentor\n\nA shared expert profile"
    resp = client.post("/experts/import-profile", json={"forum_profile": forum_profile})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["expert_name"] == "Cognitive_Mentor"

    shared_file = experts_root / "topiclab_shared" / "Cognitive_Mentor.md"
    assert shared_file.exists()
    assert "A shared expert profile" in shared_file.read_text(encoding="utf-8")

    shared_meta_path = experts_root / "topiclab_shared" / "meta.json"
    assert shared_meta_path.exists()
    shared_meta = json.loads(shared_meta_path.read_text(encoding="utf-8"))
    assert "Cognitive_Mentor" in shared_meta.get("experts", {})

    main_meta_path = experts_root / "meta.json"
    assert main_meta_path.exists()
    main_meta = json.loads(main_meta_path.read_text(encoding="utf-8"))
    assert "topiclab_shared" in main_meta.get("sources", {})


def test_import_profile_to_experts_rejects_empty_content(client: TestClient):
    resp = client.post("/experts/import-profile", json={"forum_profile": "   "})
    assert resp.status_code == 400


def test_import_profile_to_experts_rejects_builtin_name(client: TestClient):
    # "physicist" is a built-in expert in default source.
    forum_profile = "# physicist\n\ncontent"
    resp = client.post("/experts/import-profile", json={"forum_profile": forum_profile})
    assert resp.status_code == 409
