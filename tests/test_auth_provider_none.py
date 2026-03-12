from app.auth.providers.factory import get_auth_provider


def test_none_provider_returns_anonymous_context(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "none")
    provider = get_auth_provider()
    ctx = provider.resolve_from_headers({})
    assert ctx.is_anonymous is True
    assert ctx.subject == "anonymous"
