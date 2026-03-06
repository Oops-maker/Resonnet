"""Agent link blueprints for link-as-agent."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from app.core.config import get_agent_links_dir

_SUPPORTED_MODULES = {"profile_helper"}
_DEFAULT_WELCOME = "你好，我是科研数字分身采集助手。"
_DEFAULT_BASE = Path("/Users/zeruifang/Documents/tashanlink")
_DEFAULT_RULE_REL = Path(".cursor/rules/profile-collector.mdc")
_DEFAULT_SKILLS_REL = Path(".cursor/skills")
_DEFAULT_DOCS_REL = Path("doc")
_DEFAULT_TEMPLATE_REL = Path("profiles/_template.md")


def _slugify(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace(" ", "-")
        .replace("_", "-")
    )


def _build_link_from_root(root: Path) -> dict[str, Any] | None:
    if not root.exists() or not root.is_dir():
        return None
    slug = _slugify(root.name)
    rule = root / _DEFAULT_RULE_REL
    skills = root / _DEFAULT_SKILLS_REL
    docs = root / _DEFAULT_DOCS_REL
    template = root / _DEFAULT_TEMPLATE_REL
    if not rule.exists():
        return None
    return {
        "slug": slug,
        "name": root.name,
        "description": f"Blueprint from {root}",
        "module": "profile_helper",
        "entry_skill": "collect-basic-info",
        "blueprint_root": str(root),
        "agent_workdir": str(root),
        "rule_file_path": str(rule),
        "skills_path": str(skills),
        "docs_path": str(docs),
        "template_path": str(template),
        "welcome_message": _DEFAULT_WELCOME,
        "default_model": "",
    }


def _normalize_link(raw: dict[str, Any], fallback_slug: str) -> dict[str, Any] | None:
    slug = _slugify(str(raw.get("slug") or fallback_slug))
    if not slug:
        return None
    module = str(raw.get("module") or "profile_helper").strip()
    if module not in _SUPPORTED_MODULES:
        return None
    blueprint_root = str(raw.get("blueprint_root") or "").strip()
    agent_workdir = str(raw.get("agent_workdir") or blueprint_root).strip()
    rule_file_path = str(raw.get("rule_file_path") or "").strip()
    return {
        "slug": slug,
        "name": str(raw.get("name") or slug),
        "description": str(raw.get("description") or ""),
        "module": module,
        "entry_skill": str(raw.get("entry_skill") or ""),
        "blueprint_root": blueprint_root,
        "agent_workdir": agent_workdir,
        "rule_file_path": rule_file_path,
        "skills_path": str(raw.get("skills_path") or ""),
        "docs_path": str(raw.get("docs_path") or ""),
        "template_path": str(raw.get("template_path") or ""),
        "welcome_message": str(raw.get("welcome_message") or _DEFAULT_WELCOME),
        "default_model": str(raw.get("default_model") or ""),
    }


def _load_links_from_disk() -> dict[str, dict[str, Any]]:
    root = get_agent_links_dir()
    if not root.exists() or not root.is_dir():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for d in root.iterdir():
        if not d.is_dir():
            continue
        config_path = d / "agent.json"
        if not config_path.exists():
            continue
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        link = _normalize_link(raw, d.name)
        if link:
            result[link["slug"]] = link
    return result


def _load_host_blueprints() -> dict[str, dict[str, Any]]:
    base = Path(os.getenv("AGENT_BLUEPRINT_BASE", str(_DEFAULT_BASE)))
    if not base.exists() or not base.is_dir():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for d in base.iterdir():
        if not d.is_dir():
            continue
        link = _build_link_from_root(d)
        if link:
            result[link["slug"]] = link
    return result


def _default_links() -> dict[str, dict[str, Any]]:
    # Explicit fallback for the provided demo path, even if base scanning is not configured.
    demo_root = _DEFAULT_BASE / "tashan-profile-helper_demo"
    link = _build_link_from_root(demo_root)
    links: dict[str, dict[str, Any]] = {}
    if link:
        links[link["slug"]] = link
    return links


def _resolve_inside_blueprint(blueprint_root: Path, raw_path: str) -> Path:
    p = Path(raw_path.strip())
    if not p.is_absolute():
        resolved = (blueprint_root / p).resolve()
    else:
        resolved = p.resolve()
    root_resolved = blueprint_root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"Path must be inside blueprint: {raw_path}")
    return resolved


def import_blueprint(
    source_path: str,
    *,
    overwrite: bool = False,
    slug_override: str | None = None,
    name_override: str | None = None,
    description_override: str | None = None,
    rule_file_path_override: str | None = None,
    welcome_message_override: str | None = None,
    default_model_override: str | None = None,
) -> dict[str, Any]:
    src = Path(source_path).expanduser().resolve()
    if not src.exists() or not src.is_dir():
        raise FileNotFoundError(f"Blueprint path not found: {source_path}")

    raw_cfg_path = src / "agent.json"
    raw_cfg: dict[str, Any] = {}
    if raw_cfg_path.exists():
        try:
            raw_cfg = json.loads(raw_cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid agent.json: {e}") from e

    slug_candidate = str(slug_override or raw_cfg.get("slug") or src.name)
    slug = _slugify(slug_candidate)
    if not slug:
        raise ValueError("Invalid slug")

    target_root = get_agent_links_dir() / slug
    target_root.parent.mkdir(parents=True, exist_ok=True)

    if target_root.exists():
        if not overwrite:
            raise FileExistsError(f"Target already exists: {target_root}")
        shutil.rmtree(target_root)

    try:
        shutil.copytree(src, target_root)

        rule_rel = rule_file_path_override or raw_cfg.get("rule_file_path") or str(_DEFAULT_RULE_REL)
        skills_rel = raw_cfg.get("skills_path") or str(_DEFAULT_SKILLS_REL)
        docs_rel = raw_cfg.get("docs_path") or str(_DEFAULT_DOCS_REL)
        template_rel = raw_cfg.get("template_path") or str(_DEFAULT_TEMPLATE_REL)

        rule_path = _resolve_inside_blueprint(target_root, str(rule_rel))
        if not rule_path.exists() or not rule_path.is_file():
            raise ValueError(f"Rule file not found in blueprint: {rule_path}")

        meta = {
            "slug": slug,
            "name": str(name_override or raw_cfg.get("name") or target_root.name),
            "description": str(description_override or raw_cfg.get("description") or f"Blueprint from {target_root}"),
            "module": "profile_helper",
            "entry_skill": str(raw_cfg.get("entry_skill") or "collect-basic-info"),
            "blueprint_root": str(target_root),
            "agent_workdir": str(target_root),
            "rule_file_path": str(rule_path),
            "skills_path": str(_resolve_inside_blueprint(target_root, str(skills_rel))),
            "docs_path": str(_resolve_inside_blueprint(target_root, str(docs_rel))),
            "template_path": str(_resolve_inside_blueprint(target_root, str(template_rel))),
            "welcome_message": str(welcome_message_override or raw_cfg.get("welcome_message") or _DEFAULT_WELCOME),
            "default_model": str(default_model_override or raw_cfg.get("default_model") or ""),
        }

        link = _normalize_link(meta, slug)
        if not link:
            raise ValueError("Invalid blueprint metadata")

        (target_root / "agent.json").write_text(
            json.dumps(link, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return link
    except Exception:
        if target_root.exists():
            shutil.rmtree(target_root, ignore_errors=True)
        raise


def list_agent_links() -> list[dict[str, Any]]:
    merged = _default_links()
    merged.update(_load_host_blueprints())
    merged.update(_load_links_from_disk())
    return sorted(merged.values(), key=lambda x: x["slug"])


def get_agent_link(slug: str) -> dict[str, Any] | None:
    target = _slugify(slug)
    for link in list_agent_links():
        if link["slug"] == target:
            return link
    return None


def load_template_for_link(link: dict[str, Any]) -> str | None:
    template_path = str(link.get("template_path") or "").strip()
    if not template_path:
        return None
    path = Path(template_path)
    if not path.exists() or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def load_rule_prompt_for_link(link: dict[str, Any]) -> tuple[str, str | None]:
    """Return (rule_path, rule_content)."""
    rule_path = str(link.get("rule_file_path") or "").strip()
    if not rule_path:
        return "", None
    path = Path(rule_path)
    if not path.exists() or not path.is_file():
        return rule_path, None
    return rule_path, path.read_text(encoding="utf-8")
