"""Load aggregated assignable MCPs meta (sources registry + per-source meta)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import get_mcps_dir

logger = logging.getLogger(__name__)


def load_mcp_sources(base_dir: Path) -> dict:
    """Load sources registry from meta.json. Returns {source_id: {id, name, description?}}."""
    main_meta = base_dir / "meta.json"
    if not main_meta.exists():
        return {}
    try:
        data = json.loads(main_meta.read_text(encoding="utf-8"))
        return data.get("sources", {})
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load mcps sources: {e}")
        return {}


def load_aggregated_mcps_meta(base_dir: Path) -> tuple[dict, dict]:
    """Load and merge meta from per-source {source}/meta.json.

    Returns:
        (categories, mcps) - merged dicts. Each mcp has id, name, description, category, source, command, args.
    """
    categories: dict = {}
    mcps: dict = {}

    sources = load_mcp_sources(base_dir)
    for source_id in sources:
        src_meta = base_dir / source_id / "meta.json"
        if not src_meta.exists():
            continue
        try:
            data = json.loads(src_meta.read_text(encoding="utf-8"))
            for k, v in (data.get("categories") or {}).items():
                if isinstance(v, dict):
                    categories[k] = v
            for k, v in (data.get("mcps") or {}).items():
                if isinstance(v, dict):
                    v = dict(v)
                    v.setdefault("source", source_id)
                    mcps[k] = v
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load mcps {source_id}/meta.json: {e}")

    return categories, mcps
