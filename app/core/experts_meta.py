"""Load aggregated experts meta (sources registry + per-source meta).

Unified with moderator_modes, mcps, assignable_skills structure.
Merges from both built-in and LIBS_PATH (primary) when both exist.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import get_experts_dir, get_expert_source_dir, get_libs_builtin_root

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


def _load_source_meta(base_dir: Path, source_id: str) -> tuple[dict, dict, str] | None:
    """Load one source's meta. Returns (categories, experts, common_sections) or None."""
    src_meta = base_dir / source_id / "meta.json"
    if not src_meta.exists():
        return None
    try:
        data = json.loads(src_meta.read_text(encoding="utf-8"))
        categories = dict(data.get("categories") or {})
        experts = {}
        for k, v in (data.get("experts") or {}).items():
            if isinstance(v, dict):
                v = dict(v)
                v.setdefault("source", source_id)
                if all(key in v for key in ["name", "skill_file", "description"]):
                    experts[k] = v
                else:
                    logger.warning(f"Skipping invalid expert '{k}': missing required fields")
        common_sections = data.get("common_sections", "expert_common.md")
        return categories, experts, common_sections
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load experts {source_id}/meta.json: {e}")
        return None


def load_aggregated_experts_meta(base_dir: Path | None = None) -> tuple[dict, dict, dict]:
    """Load and merge meta from built-in + primary. default→builtin, topiclab_shared→primary.

    Returns:
        (categories, experts, source_common_sections) - merged dicts.
    """
    primary = base_dir or get_experts_dir()
    builtin = get_libs_builtin_root()
    builtin_experts = (builtin / "experts") if builtin else None

    categories: dict = {}
    experts: dict = {}
    source_common_sections: dict = {}

    # Merge sources from both meta.json
    sources = load_expert_sources(primary)
    if builtin_experts and builtin_experts.exists():
        builtin_sources = load_expert_sources(builtin_experts)
        sources = {**builtin_sources, **sources}  # primary overrides builtin

    for source_id in sources:
        base = get_expert_source_dir(source_id)
        result = _load_source_meta(base, source_id)
        if result:
            cat, exp, common = result
            for k, v in cat.items():
                if isinstance(v, dict):
                    categories[k] = v
            source_common_sections[source_id] = common
            for k, v in exp.items():
                experts[k] = v

    return categories, experts, source_common_sections


def get_experts_and_common(base_dir: Path | None = None) -> tuple[dict, dict]:
    """Convenience: load experts and source_common_sections from experts_dir.

    Returns:
        (experts, source_common_sections) for use by experts.py
    """
    base = base_dir or get_experts_dir()
    _, experts, source_common_sections = load_aggregated_experts_meta(base)
    return experts, source_common_sections
