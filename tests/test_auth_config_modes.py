from app.core.config import get_auth_mode, is_auth_required


def test_auth_mode_defaults_to_none(monkeypatch):
    monkeypatch.delenv("AUTH_MODE", raising=False)
    assert get_auth_mode() == "none"


def test_auth_required_defaults_false(monkeypatch):
    monkeypatch.delenv("AUTH_REQUIRED", raising=False)
    assert is_auth_required() is False
