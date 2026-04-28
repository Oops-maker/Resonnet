import pytest

from app.integrations import account_sync


class _FakeResponse:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.mark.asyncio
async def test_sync_twin_record_returns_upstream_twin_identity(monkeypatch):
    monkeypatch.setattr(account_sync, "is_account_sync_enabled", lambda: True)
    monkeypatch.setattr(account_sync, "get_auth_service_base_url", lambda: "http://topiclab-backend:8000")

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return _FakeResponse(200, {"twin_id": "twin_abc", "twin_version": 3})

    monkeypatch.setattr(account_sync.httpx, "AsyncClient", _FakeClient)

    result = await account_sync.sync_twin_record("token-1", {"agent_name": "my_twin"})
    assert result == {"status": "ok", "twin_id": "twin_abc", "twin_version": 3}


@pytest.mark.asyncio
async def test_sync_twin_record_returns_failed_shape_on_non_200(monkeypatch):
    monkeypatch.setattr(account_sync, "is_account_sync_enabled", lambda: True)
    monkeypatch.setattr(account_sync, "get_auth_service_base_url", lambda: "http://topiclab-backend:8000")

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return _FakeResponse(503, {"detail": "upstream unavailable"})

    monkeypatch.setattr(account_sync.httpx, "AsyncClient", _FakeClient)

    result = await account_sync.sync_twin_record("token-1", {"agent_name": "my_twin"})
    assert result == {"status": "failed", "reason": "upstream unavailable"}


@pytest.mark.asyncio
async def test_sync_twin_record_returns_failed_shape_on_exception(monkeypatch):
    monkeypatch.setattr(account_sync, "is_account_sync_enabled", lambda: True)
    monkeypatch.setattr(account_sync, "get_auth_service_base_url", lambda: "http://topiclab-backend:8000")

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(account_sync.httpx, "AsyncClient", _FakeClient)

    result = await account_sync.sync_twin_record("token-1", {"agent_name": "my_twin"})
    assert result == {"status": "failed", "reason": "network down"}
