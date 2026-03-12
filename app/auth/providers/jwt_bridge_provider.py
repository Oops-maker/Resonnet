"""JWT provider built on existing auth bridge validation."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import HTTPException

from app.auth.context import AuthContext
from app.auth.token_bridge import get_user_from_token


class JwtBridgeAuthProvider:
    async def resolve_from_bearer(self, token: str) -> AuthContext:
        user = await get_user_from_token(token)
        return AuthContext(
            subject=str(user["id"]),
            is_anonymous=False,
            raw={"user": user, "token": token},
        )

    async def resolve_from_headers(self, headers: Mapping[str, str]) -> AuthContext:
        auth = headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="未登录")
        token = auth.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(status_code=401, detail="未登录")
        return await self.resolve_from_bearer(token)
