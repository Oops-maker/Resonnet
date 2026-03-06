"""Tools: read_skill, read_doc, read_profile, write_profile."""
from app.core.config import get_profile_helper_root

PROFILE_HELPER_ROOT = get_profile_helper_root()
SKILLS_DIR = PROFILE_HELPER_ROOT / "skills"
DOCS_DIR = PROFILE_HELPER_ROOT / "docs"
TEMPLATE_PATH = PROFILE_HELPER_ROOT / "_template.md"

SKILL_NAMES = [
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

DOC_NAMES = [
    "academic-motivation-scale",
    "mini-ipip-scale",
    "researcher-cognitive-style",
    "tashan-profile-outline",
    "tashan-profile-examples",
    "multidimensional-work-motivation-scale",
    "implementation-guide",
]


def read_skill(skill_name: str) -> str:
    """Read specified Skill file content."""
    if skill_name not in SKILL_NAMES:
        return f"错误：未知的 skill 名称 '{skill_name}'。可用：{', '.join(SKILL_NAMES)}"
    path = SKILLS_DIR / skill_name / "SKILL.md"
    if not path.exists():
        return f"错误：文件不存在 {path}"
    return path.read_text(encoding="utf-8")


def read_doc(doc_name: str) -> str:
    """Read reference doc from docs directory."""
    if doc_name not in DOC_NAMES:
        return f"错误：未知的 doc 名称 '{doc_name}'。可用：{', '.join(DOC_NAMES)}"
    path = DOCS_DIR / f"{doc_name}.md"
    if not path.exists():
        return f"错误：文件不存在 {path}"
    return path.read_text(encoding="utf-8")


def load_template() -> str:
    """Load profile template."""
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    return "# 科研发展画像\n\n（空白模板）\n"
