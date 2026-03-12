"""Optional sync to external account system."""

from __future__ import annotations

import httpx

from app.core.config import get_auth_service_base_url, is_account_sync_enabled


async def sync_twin_record(token: str | None, payload: dict) -> dict:
    if not is_account_sync_enabled():
        return {"status": "skipped", "reason": "disabled"}
    if not token:
        return {"status": "skipped", "reason": "missing_token"}

    auth_base = get_auth_service_base_url().rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{auth_base}/auth/digital-twins/upsert",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}

    if resp.status_code != 200:
        detail = f"{resp.status_code}"
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        return {"status": "failed", "reason": detail}

    return {"status": "ok"}
