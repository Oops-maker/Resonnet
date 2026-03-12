from app.auth.providers.factory import get_auth_provider


def test_proxy_provider_reads_user_header(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "proxy")
    provider = get_auth_provider()
    ctx = provider.resolve_from_headers({"x-user-id": "u-42"})
    assert ctx.subject == "u-42"
    assert ctx.is_anonymous is False
