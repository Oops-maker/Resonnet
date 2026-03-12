"""Token validation against external auth service."""

from __future__ import annotations

import httpx
from fastapi import HTTPException

from app.core.config import get_auth_service_base_url


async def get_user_from_token(token: str) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    auth_base = get_auth_service_base_url().rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{auth_base}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"账号服务不可用: {exc}"
        ) from exc

    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="登录已过期")
    if resp.status_code != 200:
        raise HTTPException(status_code=503, detail="账号服务响应异常")

    data = resp.json()
    user = data.get("user")
    if not user or "id" not in user:
        raise HTTPException(status_code=503, detail="账号服务返回数据不完整")
    return user
