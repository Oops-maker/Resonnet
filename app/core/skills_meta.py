"""Load aggregated assignable skills meta (sources registry + per-source meta).

Merges from both built-in and LIBS_PATH (primary) when both exist.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_skills_base_dirs() -> tuple[Path, Path | None]:
    """Return (primary, builtin) for assignable_skills."""
    from app.core.config import _libs_root, get_libs_builtin_root

    primary = _libs_root() / "assignable_skills"
    builtin = get_libs_builtin_root()
    builtin_skills = (builtin / "assignable_skills") if builtin else None
    if builtin_skills and builtin_skills.exists():
        return primary, builtin_skills
    return primary, None


def load_sources(base_dir: Path) -> dict:
    """Load sources registry from meta.json. Returns {source_id: {id, name, description?}}."""
    main_meta = base_dir / "meta.json"
    if not main_meta.exists():
        return {}
    try:
        data = json.loads(main_meta.read_text(encoding="utf-8"))
        return data.get("sources", {})
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load sources: {e}")
        return {}


def load_aggregated_meta(base_dir: Path | None = None) -> tuple[dict, dict]:
    """Load and merge meta from built-in + primary.

    Returns:
        (categories, skills) - merged dicts
    """
    primary, builtin = _get_skills_base_dirs()
    base_dir = base_dir or primary

    categories: dict = {}
    skills: dict = {}

    sources = load_sources(base_dir)
    if builtin:
        builtin_sources = load_sources(builtin)
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
                    skills_dir = data.get("skills_dir", ".") or "."
                    for k, v in (data.get("skills") or {}).items():
                        if isinstance(v, dict):
                            v = dict(v)
                            v["_skills_dir"] = skills_dir
                            v["_base_dir"] = candidate
                            skills[k] = v
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"Failed to load {source_id}/meta.json: {e}")
                break

    return categories, skills
