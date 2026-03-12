"""Auth bridge for validating JWT via topiclab-backend /auth/me."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.context import AuthContext
from app.auth.providers.factory import get_auth_provider
from app.auth.token_bridge import get_user_from_token
from app.core.config import get_auth_mode, is_auth_required

security = HTTPBearer(auto_error=False)


async def get_current_auth_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Return unified auth context with backward-compatible fields."""
    mode = get_auth_mode()
    provider = get_auth_provider()
    token = credentials.credentials if credentials else None

    if mode == "none":
        auth_context = provider.resolve_from_headers({})
    elif mode == "proxy":
        headers = {k.lower(): v for k, v in request.headers.items()}
        auth_context = provider.resolve_from_headers(headers)
    elif mode == "jwt":
        if not token:
            if is_auth_required():
                raise HTTPException(status_code=401, detail="未登录")
            auth_context = AuthContext(subject="anonymous", is_anonymous=True)
        else:
            auth_context = await provider.resolve_from_bearer(token)
    else:
        raise HTTPException(status_code=500, detail=f"未知认证模式: {mode}")

    legacy_user = {"id": auth_context.subject}
    if isinstance(auth_context.raw, dict):
        legacy_user = auth_context.raw.get("user") or legacy_user

    return {
        "auth_context": auth_context,
        "user": legacy_user,
        "token": token,
    }


async def get_current_user_from_auth_service(
    auth_ctx: dict = Depends(get_current_auth_context),
) -> dict:
    """Backward-compatible dependency to access current user payload."""
    user = auth_ctx.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user
