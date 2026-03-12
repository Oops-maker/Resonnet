def test_session_works_in_none_mode(client, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "none")
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    resp = client.get("/profile-helper/session")
    assert resp.status_code == 200
    assert resp.json()["session_id"]


def test_session_requires_proxy_header_in_proxy_mode(client, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "proxy")

    resp = client.get("/profile-helper/session")
    assert resp.status_code == 401

    ok_resp = client.get("/profile-helper/session", headers={"X-User-Id": "u-1"})
    assert ok_resp.status_code == 200
