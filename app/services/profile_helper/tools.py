"""Tools: read_skill, read_doc, read_profile, write_profile."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_profile_helper_root

_DEFAULT_SKILL_NAMES = [
    "collect-basic-info",
    "administer-ams",
    "administer-rcss",
    "administer-mini-ipip",
    "infer-profile-dimensions",
    "review-profile",
    "update-profile",
    "generate-forum-profile",
    "generate-ai-memory-prompt",
    "import-ai-memory",
    "modify-profile-schema",
]

_DEFAULT_DOC_NAMES = [
    "academic-motivation-scale",
    "mini-ipip-scale",
    "researcher-cognitive-style",
    "tashan-profile-outline",
    "tashan-profile-examples",
    "multidimensional-work-motivation-scale",
    "implementation-guide",
]


def _candidate_roots() -> list[Path]:
    primary = get_profile_helper_root()
    backend_root = Path(__file__).resolve().parents[3]
    local = backend_root / "libs" / "profile_helper"
    builtin = Path("/app/libs_builtin/profile_helper")
    candidates = [primary, builtin, local]
    deduped: list[Path] = []
    for path in candidates:
        path = path.resolve()
        if path not in deduped:
            deduped.append(path)
    return deduped


def _resolve_profile_helper_root() -> Path:
    for root in _candidate_roots():
        if root.exists() and root.is_dir():
            return root
    return _candidate_roots()[0]


def _skills_dir() -> Path:
    return _resolve_profile_helper_root() / "skills"


def _docs_dir() -> Path:
    return _resolve_profile_helper_root() / "docs"


def _template_path() -> Path:
    return _resolve_profile_helper_root() / "_template.md"


def list_skill_names() -> list[str]:
    skills_dir = _skills_dir()
    if skills_dir.exists() and skills_dir.is_dir():
        names = sorted(
            p.name
            for p in skills_dir.iterdir()
            if p.is_dir() and (p / "SKILL.md").exists()
        )
        if names:
            return names
    return _DEFAULT_SKILL_NAMES.copy()


def list_doc_names() -> list[str]:
    docs_dir = _docs_dir()
    if docs_dir.exists() and docs_dir.is_dir():
        names = sorted(p.stem for p in docs_dir.glob("*.md") if p.is_file())
        if names:
            return names
    return _DEFAULT_DOC_NAMES.copy()


SKILL_NAMES = list_skill_names()
DOC_NAMES = list_doc_names()


def read_skill(skill_name: str) -> str:
    """Read specified Skill file content."""
    skill_names = list_skill_names()
    if skill_name not in skill_names:
        return f"错误：未知的 skill 名称 '{skill_name}'。可用：{', '.join(skill_names)}"
    path = _skills_dir() / skill_name / "SKILL.md"
    if not path.exists():
        return f"错误：文件不存在 {path}"
    return path.read_text(encoding="utf-8")


def read_doc(doc_name: str) -> str:
    """Read reference doc from docs directory."""
    doc_names = list_doc_names()
    if doc_name not in doc_names:
        return f"错误：未知的 doc 名称 '{doc_name}'。可用：{', '.join(doc_names)}"
    path = _docs_dir() / f"{doc_name}.md"
    if not path.exists():
        return f"错误：文件不存在 {path}"
    return path.read_text(encoding="utf-8")


def load_template() -> str:
    """Load profile template."""
    template_path = _template_path()
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "# 科研数字分身\n\n（空白模板）\n"
