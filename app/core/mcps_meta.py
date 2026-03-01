"""Load aggregated assignable MCPs meta (sources registry + per-source meta).

Merges from both built-in and LIBS_PATH (primary) when both exist.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import _libs_root, get_libs_builtin_root, get_mcps_dir

logger = logging.getLogger(__name__)


def _get_mcps_base_dirs() -> tuple[Path, Path | None]:
    """Return (primary, builtin) for mcps."""
    primary = _libs_root() / "mcps"
    builtin = get_libs_builtin_root()
    builtin_mcps = (builtin / "mcps") if builtin else None
    if builtin_mcps and builtin_mcps.exists():
        return primary, builtin_mcps
    return primary, None


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


def load_aggregated_mcps_meta(base_dir: Path | None = None) -> tuple[dict, dict]:
    """Load and merge meta from built-in + primary."""
    primary, builtin = _get_mcps_base_dirs()
    base_dir = base_dir or primary

    categories: dict = {}
    mcps: dict = {}

    sources = load_mcp_sources(base_dir)
    if builtin:
        builtin_sources = load_mcp_sources(builtin)
        sources = {**builtin_sources, **sources}

    for source_id in sources:
        for candidate in ([base_dir] if not builtin else [builtin, base_dir]):
            src_meta = candidate / source_id / "meta.json"
            if src_meta.exists():
                try:
                    data = json.loads(src_meta.read_text(encoding="utf-8"))
                    for k, v in (data.get("categories") or {}).items():
                        if isinstance(v, dict):
                            categories[k] = v
                    for k, v in (data.get("mcps") or {}).items():
                        if isinstance(v, dict):
                            v = dict(v)
                            v.setdefault("source", source_id)
                            v["_base_dir"] = candidate
                            mcps[k] = v
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"Failed to load mcps {source_id}/meta.json: {e}")
                break

    return categories, mcps
