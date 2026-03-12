"""No-auth provider for open-source / local MVP mode."""

from __future__ import annotations

from typing import Mapping

from app.auth.context import AuthContext


class NoneAuthProvider:
    def resolve_from_headers(self, headers: Mapping[str, str]) -> AuthContext:
        _ = headers
        return AuthContext(subject="anonymous", is_anonymous=True)
