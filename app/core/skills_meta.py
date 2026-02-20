"""Load aggregated assignable skills meta (sources registry + per-source meta)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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


def load_aggregated_meta(base_dir: Path) -> tuple[dict, dict]:
    """Load and merge meta from per-source {source}/meta.json.

    Sources are read from meta.json "sources" registry. Each source dir must have meta.json
    with categories and skills. Adds skills_dir to each skill when present in source meta.

    Returns:
        (categories, skills) - merged dicts
    """
    categories: dict = {}
    skills: dict = {}

    sources = load_sources(base_dir)
    for source_id in sources:
        src_meta = base_dir / source_id / "meta.json"
        if not src_meta.exists():
            continue
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
                    skills[k] = v
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load {source_id}/meta.json: {e}")

    return categories, skills
