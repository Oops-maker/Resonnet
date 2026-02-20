"""Unified libs service: cached meta loading + common list/search logic for skills, mcps, moderator_modes."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable

from app.core.config import get_libs_cache_ttl_seconds
from app.core.mcps_meta import load_aggregated_mcps_meta
from app.core.moderator_modes_meta import load_aggregated_modes_meta
from app.core.skills_meta import load_aggregated_meta

logger = logging.getLogger(__name__)

# TTL cache: {key: (data, timestamp)}
_skills_cache: dict[str, tuple[tuple[dict, dict], float]] = {}
_mcps_cache: dict[str, tuple[tuple[dict, dict], float]] = {}
_modes_cache: dict[str, tuple[tuple[dict, dict, dict], float]] = {}

# Locks to prevent cache stampede: only one request loads on miss, others wait
_skills_lock = threading.Lock()
_mcps_lock = threading.Lock()
_modes_lock = threading.Lock()


def _path_cache_key(p: Path) -> str:
    return str(p.resolve())


def _is_expired(ts: float, ttl: int) -> bool:
    return ttl == 0 or (time.monotonic() - ts) > ttl


def get_cached_skills_meta(base_dir: Path) -> tuple[dict, dict]:
    """Load skills meta with TTL cache. LIBS_CACHE_TTL_SECONDS=0 disables cache (hot-reload)."""
    key = _path_cache_key(base_dir)
    ttl = get_libs_cache_ttl_seconds()
    if key in _skills_cache:
        data, ts = _skills_cache[key]
        if not _is_expired(ts, ttl):
            return data
    if ttl == 0:
        return load_aggregated_meta(base_dir)
    with _skills_lock:
        if key in _skills_cache:
            data, ts = _skills_cache[key]
            if not _is_expired(ts, ttl):
                return data
        data = load_aggregated_meta(base_dir)
        _skills_cache[key] = (data, time.monotonic())
        return data


def get_cached_mcps_meta(base_dir: Path) -> tuple[dict, dict]:
    """Load MCPs meta with TTL cache."""
    key = _path_cache_key(base_dir)
    ttl = get_libs_cache_ttl_seconds()
    if key in _mcps_cache:
        data, ts = _mcps_cache[key]
        if not _is_expired(ts, ttl):
            return data
    if ttl == 0:
        return load_aggregated_mcps_meta(base_dir)
    with _mcps_lock:
        if key in _mcps_cache:
            data, ts = _mcps_cache[key]
            if not _is_expired(ts, ttl):
                return data
        data = load_aggregated_mcps_meta(base_dir)
        _mcps_cache[key] = (data, time.monotonic())
        return data


def get_cached_modes_meta(base_dir: Path) -> tuple[dict, dict, dict]:
    """Load moderator modes meta with TTL cache."""
    key = _path_cache_key(base_dir)
    ttl = get_libs_cache_ttl_seconds()
    if key in _modes_cache:
        data, ts = _modes_cache[key]
        if not _is_expired(ts, ttl):
            return data
    if ttl == 0:
        return load_aggregated_modes_meta(base_dir)
    with _modes_lock:
        if key in _modes_cache:
            data, ts = _modes_cache[key]
            if not _is_expired(ts, ttl):
                return data
        data = load_aggregated_modes_meta(base_dir)
        _modes_cache[key] = (data, time.monotonic())
        return data


def invalidate_libs_cache() -> None:
    """Clear meta cache immediately (e.g. after libs hot-reload)."""
    with _skills_lock:
        _skills_cache.clear()
    with _mcps_lock:
        _mcps_cache.clear()
    with _modes_lock:
        _modes_cache.clear()


def _matches_search(item: dict, q: str, search_fields: tuple[str, ...]) -> bool:
    """Check if item matches search query (case-insensitive substring)."""
    if not q or not q.strip():
        return True
    q_lower = q.strip().lower()
    for key in search_fields:
        val = item.get(key)
        if val and isinstance(val, str) and q_lower in val.lower():
            return True
    return False


def list_assignable_items(
    categories: dict,
    items: dict,
    *,
    category: str | None = None,
    q: str | None = None,
    minimal: bool = False,
    limit: int | None = None,
    offset: int = 0,
    search_fields: tuple[str, ...] = ("id", "name", "description"),
    extra_item_fields: Callable[[dict, dict], dict] | None = None,
) -> list[dict]:
    """Generic list logic for assignable skills/mcps/moderator_modes.

    Args:
        categories: category id -> {id, name, description}
        items: item_id -> {id, name, description, category, source, ...}
        category: filter by category id
        q: optional search query (matches id, name, description)
        minimal: if True, return only id, name, category, category_name
        limit, offset: pagination
        search_fields: keys to search when q is set
        extra_item_fields: fn(item, cat_info) -> dict for mode-specific fields (e.g. num_rounds)

    Returns:
        List of item dicts.
    """
    result = []
    for item_id, item_data in items.items():
        if not isinstance(item_data, dict):
            continue
        if "id" not in item_data:
            if category and category != "":
                continue
            item = {"id": item_id, "name": item_id, "category": "", "category_name": ""}
            if not minimal:
                item["source"] = ""
                item["description"] = ""
        else:
            cat_id = item_data.get("category", "")
            if category is not None and category != "" and cat_id != category:
                continue
            cat_info = categories.get(cat_id, {}) if isinstance(categories.get(cat_id), dict) else {}
            item = {
                "id": item_data["id"],
                "name": item_data.get("name", item_id),
                "category": cat_id,
                "category_name": cat_info.get("name", cat_id),
            }
            if not minimal:
                item["source"] = item_data.get("source", "default")
                item["description"] = item_data.get("description", "")
            if extra_item_fields:
                item.update(extra_item_fields(item_data, cat_info))

        if q and not _matches_search(item, q, search_fields):
            continue
        result.append(item)

    if offset > 0:
        result = result[offset:]
    if limit is not None and limit > 0:
        result = result[:limit]
    return result


