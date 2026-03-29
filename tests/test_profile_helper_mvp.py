from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.auth_bridge import (
    get_current_auth_context,
    get_current_user_from_auth_service,
)
from app.services.profile_helper import sessions as profile_sessions


@pytest.fixture
def auth_override(client):
    async def _fake_user():
        return {"id": 1, "phone": "13800138000", "username": "tester"}

    async def _fake_auth_context():
        return {
            "user": {"id": 1, "phone": "13800138000", "username": "tester"},
            "token": "test-token",
        }

    app = client.app
    app.dependency_overrides[get_current_user_from_auth_service] = _fake_user
    app.dependency_overrides[get_current_auth_context] = _fake_auth_context
    yield
    app.dependency_overrides.pop(get_current_user_from_auth_service, None)
    app.dependency_overrides.pop(get_current_auth_context, None)


def test_profile_helper_requires_auth(client, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "jwt")
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    resp = client.get("/profile-helper/session")
    assert resp.status_code == 401


def test_profile_helper_scales_roundtrip(client, auth_override):
    session_resp = client.get(
        "/profile-helper/session", headers={"Authorization": "Bearer test-token"}
    )
    assert session_resp.status_code == 200
    session_id = session_resp.json()["session_id"]

    submit_resp = client.post(
        "/profile-helper/scales/submit",
        headers={"Authorization": "Bearer test-token"},
        json={
            "session_id": session_id,
            "scale_name": "rcss",
            "answers": {"q1": 4, "q2": 5},
            "scores": {"integration": 4.5},
            "result_summary": {"CSI": 1.2},
        },
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["ok"] is True

    get_resp = client.get(
        f"/profile-helper/scales/{session_id}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert get_resp.status_code == 200
    scales = get_resp.json()["scales"]
    assert "rcss" in scales
    assert scales["rcss"]["scores"]["integration"] == 4.5


def test_profile_helper_structured_endpoint(client, auth_override):
    session_resp = client.get(
        "/profile-helper/session", headers={"Authorization": "Bearer test-token"}
    )
    assert session_resp.status_code == 200
    session_id = session_resp.json()["session_id"]

    structured_resp = client.get(
        f"/profile-helper/profile/{session_id}/structured",
        headers={"Authorization": "Bearer test-token"},
    )
    assert structured_resp.status_code == 200
    data = structured_resp.json()
    assert "completion" in data
    assert "identity" in data


def test_profile_helper_session_ignores_undefined_session_id(client, auth_override):
    resp = client.get(
        "/profile-helper/session?session_id=undefined",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    sid = resp.json()["session_id"]
    assert sid
    assert sid != "undefined"


def test_profile_helper_publish_to_library_writes_twin_agent(
    client, auth_override, isolated_workspace: Path, monkeypatch
):
    def _fake_import_profile(req):
        return {"message": "ok", "expert_name": "my_twin_expert"}

    monkeypatch.setattr("app.api.experts.import_profile_to_experts", _fake_import_profile)
    async def _fake_record(*args, **kwargs):
        return None
    monkeypatch.setattr("app.api.profile_helper._record_twin_to_account_service", _fake_record)

    session_resp = client.get(
        "/profile-helper/session", headers={"Authorization": "Bearer test-token"}
    )
    assert session_resp.status_code == 200
    session_id = session_resp.json()["session_id"]

    session = profile_sessions.get(session_id)
    assert session is not None
    session["forum_profile"] = "# 我的分身\n\n## Identity\n\n测试"

    publish_resp = client.post(
        "/profile-helper/publish-to-library",
        headers={"Authorization": "Bearer test-token"},
        json={
            "session_id": session_id,
            "visibility": "private",
            "exposure": "brief",
            "display_name": "我的分身",
        },
    )
    assert publish_resp.status_code == 200
    body = publish_resp.json()
    assert body["ok"] is True
    assert body["agent_name"] == "my_twin_expert"

    role_path = isolated_workspace / "users" / "1" / "agents" / "my_twin" / "role.md"
    meta_path = isolated_workspace / "users" / "1" / "agents" / "my_twin" / "meta.json"
    assert role_path.exists()
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["visibility"] == "private"
