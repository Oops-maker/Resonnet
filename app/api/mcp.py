"""MCP API: list assignable MCPs from libs/mcps/ (read-only)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from app.core.config import get_mcps_dir
from app.core.mcps_meta import load_aggregated_mcps_meta

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/assignable/categories")
def list_assignable_mcp_categories():
    """List MCP categories from mcps (main meta + per-source meta)."""
    base_dir = get_mcps_dir()
    categories, _ = load_aggregated_mcps_meta(base_dir)
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
    fields: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    """List available assignable MCPs from libs/mcps/.

    Query params (all optional):
    - category: filter by category id
    - fields: "minimal" = id, name, category, category_name only
    - limit, offset: pagination
    """
    base_dir = get_mcps_dir()
    categories, mcps = load_aggregated_mcps_meta(base_dir)

    try:
        minimal = (fields or "").strip().lower() == "minimal"

        result = []
        for mcp_id, mcp_data in mcps.items():
            if isinstance(mcp_data, dict) and "id" in mcp_data:
                cat_id = mcp_data.get("category", "")
                if category is not None and category != "" and cat_id != category:
                    continue
                cat_info = categories.get(cat_id, {}) if isinstance(categories.get(cat_id), dict) else {}
                item = {
                    "id": mcp_data["id"],
                    "name": mcp_data.get("name", mcp_id),
                    "category": cat_id,
                    "category_name": cat_info.get("name", cat_id),
                }
                if not minimal:
                    item["source"] = mcp_data.get("source", "default")
                    item["description"] = mcp_data.get("description", "")
                result.append(item)
            else:
                if category is not None and category != "":
                    continue
                item = {"id": mcp_id, "name": mcp_id, "category": "", "category_name": ""}
                if not minimal:
                    item["source"] = ""
                    item["description"] = ""
                result.append(item)

        if offset > 0:
            result = result[offset:]
        if limit is not None and limit > 0:
            result = result[:limit]

        return result
    except Exception as e:
        logger.error(f"Failed to load assignable MCPs: {e}")
        raise HTTPException(status_code=500, detail="Failed to load assignable MCPs")


@router.get("/assignable/{mcp_id}/content")
def get_mcp_content(mcp_id: str):
    """Return the MCP server config (command, args) as JSON."""
    base_dir = get_mcps_dir()
    _, mcps_meta = load_aggregated_mcps_meta(base_dir)

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
