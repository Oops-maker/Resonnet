import pytest

from app.auth.providers.factory import get_auth_provider


@pytest.mark.asyncio
async def test_jwt_provider_maps_user_id(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "jwt")

    async def _fake_get_user_from_token(token: str) -> dict:
        assert token == "token-x"
        return {"id": 123, "username": "tester"}

    monkeypatch.setattr(
        "app.auth.providers.jwt_bridge_provider.get_user_from_token",
        _fake_get_user_from_token,
    )

    provider = get_auth_provider()
    ctx = await provider.resolve_from_bearer("token-x")
    assert ctx.subject == "123"
    assert ctx.is_anonymous is False
