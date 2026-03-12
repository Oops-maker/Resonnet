"""Defaults and compatibility helpers for newly created topics."""

from __future__ import annotations

DEFAULT_TOPIC_EXPERT_NAMES = [
    "physicist",
    "biologist",
    "computer_scientist",
    "ethicist",
]

DEFAULT_TOPIC_SKILL_IDS = [
    "web_search",
    "image_generation",
]

SKILL_ID_ALIASES = {
    "image_video_generation": "image_generation",
}


def normalize_skill_id(skill_id: str) -> str:
    raw = skill_id.removesuffix(".md") if skill_id.endswith(".md") else skill_id
    return SKILL_ID_ALIASES.get(raw, raw)


def normalize_skill_ids(skill_ids: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for skill_id in skill_ids or []:
        normalized_id = normalize_skill_id(skill_id)
        if normalized_id in seen:
            continue
        seen.add(normalized_id)
        normalized.append(normalized_id)
    return normalized
