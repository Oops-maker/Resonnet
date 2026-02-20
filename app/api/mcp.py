"""MCP API: list assignable MCPs from libs/mcps/ (read-only)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from app.core.config import get_mcps_dir
from app.core.libs_service import get_cached_mcps_meta, list_assignable_items

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/assignable/categories")
def list_assignable_mcp_categories():
    """List MCP categories from mcps (main meta + per-source meta)."""
    base_dir = get_mcps_dir()
    categories, _ = get_cached_mcps_meta(base_dir)
    return [
        {
            "id": c.get("id", k),
            "name": c.get("name", k),
            "description": c.get("description", ""),
        }
        for k, c in categories.items()
        if isinstance(c, dict)
    ]


@router.get("/assignable", response_model=list)
def list_assignable_mcps(
    category: str | None = None,
    q: str | None = None,
    fields: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    """List available assignable MCPs from libs/mcps/.

    Query params (all optional):
    - category: filter by category id
    - q: search in id, name, description (case-insensitive)
    - fields: "minimal" = id, name, category, category_name only
    - limit, offset: pagination
    """
    base_dir = get_mcps_dir()
    categories, mcps = get_cached_mcps_meta(base_dir)
    try:
        minimal = (fields or "").strip().lower() == "minimal"
        return list_assignable_items(
            categories,
            mcps,
            category=category,
            q=q,
            minimal=minimal,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"Failed to load assignable MCPs: {e}")
        raise HTTPException(status_code=500, detail="Failed to load assignable MCPs")


@router.get("/assignable/{mcp_id}/content")
def get_mcp_content(mcp_id: str):
    """Return the MCP server config (command, args) as JSON."""
    base_dir = get_mcps_dir()
    _, mcps_meta = get_cached_mcps_meta(base_dir)

    raw = mcp_id.removesuffix(".json") if mcp_id.endswith(".json") else mcp_id
    mcp_info = mcps_meta.get(raw, {}) if isinstance(mcps_meta.get(raw), dict) else {}
    if not mcp_info:
        raise HTTPException(status_code=404, detail="MCP not found")

    config = {
        "command": mcp_info.get("command", ""),
        "args": mcp_info.get("args", []),
    }
    if mcp_info.get("env"):
        config["env"] = mcp_info["env"]
    return {"content": json.dumps(config, indent=2, ensure_ascii=False)}
