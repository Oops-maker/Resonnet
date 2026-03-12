"""Base protocol for auth providers."""

from __future__ import annotations

from typing import Mapping, Protocol

from app.auth.context import AuthContext


class AuthProvider(Protocol):
    def resolve_from_headers(self, headers: Mapping[str, str]) -> AuthContext:
        """Resolve auth context from incoming headers."""
