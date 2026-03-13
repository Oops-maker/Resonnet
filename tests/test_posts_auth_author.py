from app.api.posts import _resolve_author_name
from app.auth.context import AuthContext


def test_resolve_author_name_prefers_authenticated_username():
    auth_ctx = {
        "auth_context": AuthContext(subject="42", is_anonymous=False),
        "user": {"id": 42, "username": "alice", "phone": "13800138000"},
    }

    assert _resolve_author_name("user", auth_ctx) == "alice"


def test_resolve_author_name_falls_back_to_request_author_for_anonymous():
    auth_ctx = {
        "auth_context": AuthContext(subject="anonymous", is_anonymous=True),
        "user": {"id": 42, "username": "alice", "phone": "13800138000"},
    }

    assert _resolve_author_name("guest-user", auth_ctx) == "guest-user"
