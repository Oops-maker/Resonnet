"""Load aggregated moderator modes meta (sources registry + per-source meta)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import get_moderator_modes_dir

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


def load_aggregated_modes_meta(base_dir: Path) -> tuple[dict, dict, dict]:
    """Load and merge meta from per-source {source}/meta.json.

    Returns:
        (categories, modes, source_common_sections) - merged dicts.
        source_common_sections: {source_id: common_sections_filename}
        Each mode has id, name, description, category, source, num_rounds, convergence_strategy, prompt_file, summary_scope.
    """
    categories: dict = {}
    modes: dict = {}
    source_common_sections: dict = {}

    sources = load_moderator_mode_sources(base_dir)
    for source_id in sources:
        src_meta = base_dir / source_id / "meta.json"
        if not src_meta.exists():
            continue
        try:
            data = json.loads(src_meta.read_text(encoding="utf-8"))
            for k, v in (data.get("categories") or {}).items():
                if isinstance(v, dict):
                    categories[k] = v
            common_sections = data.get("common_sections", "moderator_common.md")
            source_common_sections[source_id] = common_sections
            for k, v in (data.get("modes") or {}).items():
                if isinstance(v, dict):
                    v = dict(v)
                    v.setdefault("source", source_id)
                    modes[k] = v
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load moderator modes {source_id}/meta.json: {e}")

    return categories, modes, source_common_sections


def get_modes_and_common(base_dir: Path | None = None) -> tuple[dict, dict]:
    """Convenience: load modes and source_common_sections from moderator_modes_dir.

    Returns:
        (modes, source_common_sections) for use by moderator_modes.py
    """
    base = base_dir or get_moderator_modes_dir()
    _, modes, source_common_sections = load_aggregated_modes_meta(base)
    return modes, source_common_sections
