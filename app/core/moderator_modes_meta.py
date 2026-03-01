"""Load aggregated moderator modes meta (sources registry + per-source meta).

Merges from both built-in and LIBS_PATH (primary) when both exist.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import get_moderator_mode_source_dir, get_moderator_modes_dir, get_libs_builtin_root

logger = logging.getLogger(__name__)


def load_moderator_mode_sources(base_dir: Path) -> dict:
    """Load sources registry from meta.json. Returns {source_id: {id, name, description?}}."""
    main_meta = base_dir / "meta.json"
    if not main_meta.exists():
        return {}
    try:
        data = json.loads(main_meta.read_text(encoding="utf-8"))
        return data.get("sources", {})
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load moderator mode sources: {e}")
        return {}


def _load_mode_source_meta(base_dir: Path, source_id: str) -> tuple[dict, dict, str] | None:
    """Load one source's meta. Returns (categories, modes, common_sections) or None."""
    src_meta = base_dir / source_id / "meta.json"
    if not src_meta.exists():
        return None
    try:
        data = json.loads(src_meta.read_text(encoding="utf-8"))
        categories = dict(data.get("categories") or {})
        modes = {}
        for k, v in (data.get("modes") or {}).items():
            if isinstance(v, dict):
                v = dict(v)
                v.setdefault("source", source_id)
                modes[k] = v
        common_sections = data.get("common_sections", "moderator_common.md")
        return categories, modes, common_sections
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load moderator modes {source_id}/meta.json: {e}")
        return None


def load_aggregated_modes_meta(base_dir: Path | None = None) -> tuple[dict, dict, dict]:
    """Load and merge meta from built-in + primary. default→builtin, topiclab_shared→primary."""
    primary = base_dir or get_moderator_modes_dir()
    builtin = get_libs_builtin_root()
    builtin_modes = (builtin / "moderator_modes") if builtin else None

    categories: dict = {}
    modes: dict = {}
    source_common_sections: dict = {}

    sources = load_moderator_mode_sources(primary)
    if builtin_modes and builtin_modes.exists():
        builtin_sources = load_moderator_mode_sources(builtin_modes)
        sources = {**builtin_sources, **sources}

    for source_id in sources:
        base = get_moderator_mode_source_dir(source_id)
        result = _load_mode_source_meta(base, source_id)
        if result:
            cat, mod, common = result
            for k, v in cat.items():
                if isinstance(v, dict):
                    categories[k] = v
            source_common_sections[source_id] = common
            for k, v in mod.items():
                modes[k] = v

    return categories, modes, source_common_sections


def get_modes_and_common(base_dir: Path | None = None) -> tuple[dict, dict]:
    """Convenience: load modes and source_common_sections from moderator_modes_dir.

    Returns:
        (modes, source_common_sections) for use by moderator_modes.py
    """
    base = base_dir or get_moderator_modes_dir()
    _, modes, source_common_sections = load_aggregated_modes_meta(base)
    return modes, source_common_sections
