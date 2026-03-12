"""Auth provider trusting upstream gateway identity headers."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import HTTPException

from app.auth.context import AuthContext


class ProxyHeaderAuthProvider:
    def resolve_from_headers(self, headers: Mapping[str, str]) -> AuthContext:
        uid = headers.get("x-user-id", "").strip()
        if not uid:
            raise HTTPException(status_code=401, detail="missing x-user-id")
        tenant = headers.get("x-tenant-id")
        scopes_raw = headers.get("x-user-scopes", "")
        scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]
        return AuthContext(
            subject=uid,
            tenant=tenant.strip() if tenant else None,
            scopes=scopes,
            is_anonymous=False,
            raw=dict(headers),
        )
