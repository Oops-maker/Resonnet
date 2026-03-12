from pathlib import Path

import pytest

from app.api.auth_bridge import get_current_auth_context, get_current_user_from_auth_service
from app.services.profile_helper import sessions as profile_sessions
from main import app


@pytest.fixture
def auth_override():
    async def _fake_ctx():
        return {
            "auth_context": type("Ctx", (), {"subject": "1", "raw": {"user": {"id": 1}}})(),
            "user": {"id": 1},
            "token": None,
        }

    async def _fake_user():
        return {"id": 1}

    app.dependency_overrides[get_current_auth_context] = _fake_ctx
    app.dependency_overrides[get_current_user_from_auth_service] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_auth_context, None)
    app.dependency_overrides.pop(get_current_user_from_auth_service, None)


def test_publish_succeeds_when_sync_fails(
    client, auth_override, isolated_workspace: Path, monkeypatch
):
    monkeypatch.setenv("ACCOUNT_SYNC_ENABLED", "true")

    def _fake_import_profile(req):
        return {"message": "ok", "expert_name": "my_twin_expert"}

    async def _fake_record(*args, **kwargs):
        return {"status": "failed", "reason": "down"}

    monkeypatch.setattr("app.api.experts.import_profile_to_experts", _fake_import_profile)
    monkeypatch.setattr("app.api.profile_helper._record_twin_to_account_service", _fake_record)

    session_resp = client.get("/profile-helper/session")
    session_id = session_resp.json()["session_id"]
    session = profile_sessions.get(session_id)
    session["forum_profile"] = "# 我的分身\n\n## Identity\n\n测试"

    publish_resp = client.post(
        "/profile-helper/publish-to-library",
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
    assert body["sync_status"] == "failed"

    role_path = isolated_workspace / "users" / "1" / "agents" / "my_twin" / "role.md"
    assert role_path.exists()
