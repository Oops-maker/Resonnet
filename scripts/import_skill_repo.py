#!/usr/bin/env python3
"""Scan imported skill repo and update meta. No symlinks; skills stay in _submodules.

Universal discovery: find all SKILL.md files recursively. The directory
containing each SKILL.md = skill dir, its name = slug; parent dir = category.

Supports:
- AI-Research-SKILLs: {category}/{skill_dir}/SKILL.md
- anthropics/skills: skills/{skill_dir}/SKILL.md (flat under skills/)

Output: assignable_skills/{source}/meta.json with skills_dir, categories, skills.
Runtime resolves paths to _submodules/{source}/{skills_dir}/{category}/{slug}/SKILL.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Dirs to skip when scanning (template, spec, etc.)
SKIP_DIRS = frozenset({".git", "template", "spec", "node_modules", "__pycache__"})


def extract_skill_meta(skill_md_path: Path) -> tuple[str, str]:
    """Extract name and description from SKILL.md.

    Tries: (1) YAML frontmatter name/description, (2) first # line + first paragraph.
    """
    try:
        text = skill_md_path.read_text(encoding="utf-8")
    except OSError:
        return ("", "")

    name = ""
    desc = ""

    # Try YAML frontmatter
    if text.strip().startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            n = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE | re.IGNORECASE)
            d = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE | re.IGNORECASE)
            if n:
                name = n.group(1).strip()
            if d:
                desc = d.group(1).strip().replace("\n", " ")[:200]

    if not name or not desc:
        lines = text.splitlines()
        for line in lines:
            s = line.strip()
            if s.startswith("# "):
                if not name:
                    name = s[2:].strip()
                break
        if not desc:
            buf = []
            for line in lines:
                s = line.strip()
                if s.startswith("#"):
                    if buf:
                        break
                    continue
                if s:
                    buf.append(s)
                elif buf:
                    break
            desc = " ".join(buf)[:200].strip() if buf else ""

    if not name:
        name = skill_md_path.parent.name.replace("-", " ").title()
    return (name, desc)


def discover_skills(submodule_path: Path, skills_dir: str = ".") -> list[tuple[str, str, Path]]:
    """Find all SKILL.md; return [(category, slug, path), ...].

    skills_dir: root within submodule to scan (e.g. "skills" for anthropics).
    category = parent dir name (relative to scan root); use 'general' if at root.
    slug = skill dir name (dir containing SKILL.md).
    """
    scan_root = (submodule_path / skills_dir).resolve() if skills_dir else submodule_path.resolve()
    if not scan_root.exists():
        scan_root = submodule_path.resolve()
    found: list[tuple[str, str, Path]] = []

    for skill_md in sorted(scan_root.rglob("SKILL.md")):
        skill_dir = skill_md.parent
        if any(p in skill_dir.parts for p in SKIP_DIRS):
            continue
        try:
            rel = skill_dir.relative_to(scan_root)
        except ValueError:
            continue
        slug = skill_dir.name
        if rel.parent == Path("."):
            cat_id = "general"
        else:
            cat_id = rel.parent.name
        found.append((cat_id, slug, skill_md))

    return found


def infer_skills_dir(submodule_path: Path) -> str:
    """Infer skills_dir from SKILL.md locations. Returns common path prefix or '.'."""
    submodule_path = submodule_path.resolve()
    prefixes = []
    for skill_md in submodule_path.rglob("SKILL.md"):
        if any(p in skill_md.parts for p in SKIP_DIRS):
            continue
        try:
            rel = skill_md.parent.relative_to(submodule_path)
            prefixes.append(rel.parent)  # parent of skill dir
        except ValueError:
            continue
    if not prefixes:
        return "."
    parts_list = [p.parts for p in prefixes]
    common = []
    for i, seg in enumerate(parts_list[0]):
        if all(len(p) > i and p[i] == seg for p in parts_list):
            common.append(seg)
        else:
            break
    return str(Path(*common)) if common else "."


def scan_and_import(
    source_name: str,
    submodules_dir: Path,
    assignable_dir: Path,
    meta_file: Path,
) -> None:
    submodule_path = submodules_dir / source_name
    if not submodule_path.exists():
        print(f"Error: submodule not found at {submodule_path}")
        sys.exit(1)

    skills_dir = infer_skills_dir(submodule_path)
    skills_found = discover_skills(submodule_path, skills_dir)
    if not skills_found:
        print("No SKILL.md files found")
        return

    # Remove old symlinks (no longer created; skills stay in _submodules)
    source_dir = assignable_dir / source_name
    if source_dir.exists():
        for f in source_dir.rglob("*.md"):
            f.unlink()
        for sub in sorted(source_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()

    # No symlinks: skills stay in _submodules; runtime resolves via skills_dir in meta
    print(f"  Discovered {len(skills_found)} skills (skills_dir={skills_dir})")

    def cat_display_name(cid: str) -> str:
        if cid == "general":
            return "General"
        m = re.match(r"^\d+-(.+)", cid)
        if m:
            return m.group(1).replace("-", " ").title()
        return cid.replace("-", " ").title()

    categories = {cat: {"id": cat, "name": cat_display_name(cat), "description": ""}
                  for cat in {c for c, _, _ in skills_found}}
    skills = {}
    for cat_id, slug, skill_md in skills_found:
        skill_id = f"{source_name}:{slug}"
        name, desc = extract_skill_meta(skill_md)
        if not name:
            name = slug.replace("-", " ").title()
        skills[skill_id] = {
            "id": skill_id,
            "source": source_name,
            "name": name,
            "description": desc,
            "category": cat_id,
        }

    # Write per-source meta (includes skills_dir for runtime path resolution)
    out_file = assignable_dir / source_name / "meta.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    meta = {"skills_dir": skills_dir, "categories": categories, "skills": skills}
    out_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {source_name}/meta.json: {len(skills)} skills, {len(categories)} categories")

    # Update sources registry in main meta.json
    main_meta = assignable_dir / "meta.json"
    if main_meta.exists():
        try:
            data = json.loads(main_meta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    sources = data.setdefault("sources", {})
    if source_name not in sources:
        sources[source_name] = {
            "id": source_name,
            "name": source_name.replace("-", " ").title(),
            "description": "",
        }
        main_meta.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Added {source_name} to sources registry")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: import_skill_repo.py <source_name> <submodules_dir> <assignable_dir> <meta_file>")
        sys.exit(1)
    _, source_name, submodules_dir, assignable_dir, meta_file = sys.argv
    scan_and_import(
        source_name,
        Path(submodules_dir),
        Path(assignable_dir),
        Path(meta_file),
    )
