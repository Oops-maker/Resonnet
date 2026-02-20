"""Load aggregated experts meta (sources registry + per-source meta).

Unified with moderator_modes, mcps, assignable_skills structure.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import get_experts_dir

logger = logging.getLogger(__name__)


def load_expert_sources(base_dir: Path) -> dict:
    """Load sources registry from meta.json. Returns {source_id: {id, name, description?}}."""
    main_meta = base_dir / "meta.json"
    if not main_meta.exists():
        return {}
    try:
        data = json.loads(main_meta.read_text(encoding="utf-8"))
        return data.get("sources", {})
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load expert sources: {e}")
        return {}


def load_aggregated_experts_meta(base_dir: Path) -> tuple[dict, dict, dict]:
    """Load and merge meta from per-source {source}/meta.json.

    Returns:
        (categories, experts, source_common_sections) - merged dicts.
        source_common_sections: {source_id: common_sections_filename}
        Each expert has id, source, name, label, description, category, skill_file, perspective.
    """
    categories: dict = {}
    experts: dict = {}
    source_common_sections: dict = {}

    sources = load_expert_sources(base_dir)
    for source_id in sources:
        src_meta = base_dir / source_id / "meta.json"
        if not src_meta.exists():
            continue
        try:
            data = json.loads(src_meta.read_text(encoding="utf-8"))
            for k, v in (data.get("categories") or {}).items():
                if isinstance(v, dict):
                    categories[k] = v
            common_sections = data.get("common_sections", "expert_common.md")
            source_common_sections[source_id] = common_sections
            for k, v in (data.get("experts") or {}).items():
                if isinstance(v, dict):
                    v = dict(v)
                    v.setdefault("source", source_id)
                    if all(key in v for key in ["name", "skill_file", "description"]):
                        experts[k] = v
                    else:
                        logger.warning(f"Skipping invalid expert '{k}': missing required fields")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load experts {source_id}/meta.json: {e}")

    return categories, experts, source_common_sections


def get_experts_and_common(base_dir: Path | None = None) -> tuple[dict, dict]:
    """Convenience: load experts and source_common_sections from experts_dir.

    Returns:
        (experts, source_common_sections) for use by experts.py
    """
    base = base_dir or get_experts_dir()
    _, experts, source_common_sections = load_aggregated_experts_meta(base)
    return experts, source_common_sections
