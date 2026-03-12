"""Factory for selecting configured auth provider."""

from __future__ import annotations

from app.auth.providers.jwt_bridge_provider import JwtBridgeAuthProvider
from app.auth.providers.none_provider import NoneAuthProvider
from app.auth.providers.proxy_header_provider import ProxyHeaderAuthProvider
from app.core.config import get_auth_mode


def get_auth_provider():
    mode = get_auth_mode()
    if mode == "jwt":
        return JwtBridgeAuthProvider()
    if mode == "proxy":
        return ProxyHeaderAuthProvider()
    return NoneAuthProvider()
