"""Unified auth context consumed by API routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuthContext(BaseModel):
    subject: str
    tenant: str | None = None
    scopes: list[str] = Field(default_factory=list)
    is_anonymous: bool = False
    raw: dict = Field(default_factory=dict)
