# Libs Directory

Libraries for experts, moderator modes, MCP servers, assignable skills, and AI prompts. All configurable via library imports; no scenario preset.

## Component Comparison

| Component | Purpose | When to Add | Nature |
|-----------|---------|-------------|--------|
| **experts/** | **Who** participates in discussions. Defines domain roles (e.g. physicist, biologist) with identity, expertise, thinking style. | New expert persona (scholar) | Content / identity |
| **moderator_modes/** | **How** discussions are organized. Defines modes (standard, brainstorm, debate, review) with round flow and convergence strategy. | New discussion format (e.g. risk assessment, design sprint) | Process / format |
| **assignable_skills/** | Skills the moderator can assign to experts. | New methodology or thinking skill | Content / mechanism |
| **mcps/** | MCP servers available for topics. | New MCP server | Tool / integration |
| **prompts/** | **How** the AI behaves in specific features. System prompts for: expert generation, moderator generation, round discussion, @mention reply. | Customize AI behavior for a feature | Functional / mechanism |

**Quick guide:**
- Adding a new **persona** (e.g. economist, designer) → `experts/default/` (register in meta.json)
- Adding a new **discussion style** (e.g. risk review, ideation) → `moderator_modes/default/`
- Adding **assignable skills** → `assignable_skills/default/` or import via submodule
- Adding **MCP server** → `mcps/default/`
- Changing **AI generation or reply behavior** → `prompts/` (fallback to `app/prompts/` if missing)

## Structure

```
libs/
├── assignable_skills/       # Assignable skills library
│   ├── meta.json           # Sources registry only
│   ├── default/meta.json   # categories + skills
│   └── _submodules/        # Imported repos
├── mcps/                   # MCP servers library
│   ├── meta.json           # Sources registry only
│   └── default/meta.json   # categories + mcps
├── moderator_modes/        # Moderator modes
│   ├── meta.json           # Sources registry only
│   └── default/
│       ├── meta.json       # categories + modes + common_sections
│       ├── moderator_common.md
│       └── *.md            # Mode-specific: standard, brainstorm, debate, review
├── experts/                # Role library
│   ├── meta.json           # Sources registry only
│   └── default/
│       ├── meta.json       # categories + experts + common_sections
│       ├── expert_common.md
│       └── *.md            # Role-specific: physicist, biologist, etc.
├── prompts/                # AI functional prompts
│   ├── expert_generation.md
│   ├── moderator_system.md
│   └── ...
└── README.md
```

## Meta Format

- **experts/meta.json**: `{"sources": {"default": {...}}}` (sources registry only)
- **experts/{source}/meta.json**: `{"common_sections": "expert_common.md", "categories": {...}, "experts": {"<id>": {"id", "source", "name", "label", "description", "category", "skill_file", "perspective"}}}`
- Built-in experts are all in `category: scholar` (学者); API returns `category` and `category_name` for grouping.
- **moderator_modes/meta.json**: `{"sources": {"default": {...}}}` (sources registry only)
- **moderator_modes/{source}/meta.json**: `{"common_sections": "moderator_common.md", "categories": {...}, "modes": {...}}`
- **assignable_skills/meta.json**: Sources registry only
- **assignable_skills/{source}/meta.json**: Per-source `{"skills_dir"?, "categories": {...}, "skills": {...}}`

**Add/modify skill libraries**: See [.cursor/skills/skills-submodule-guide/SKILL.md](../.cursor/skills/skills-submodule-guide/SKILL.md) or [docs/skills-submodule-guide.md](../docs/skills-submodule-guide.md).

## Prompts: Functional Override

`prompts/` files drive **feature behavior**, not content. Each file maps to a specific function:

| File | Function | Used By |
|------|----------|---------|
| `expert_generation.md` | AI generates expert role (role-only) from name/label/bio | POST .../experts/generate |
| `expert_user_message.md` | User message template for expert generation | generation.py |
| `moderator_generation.md` | AI generates moderator prompt (role-only) from user description | POST .../moderator-mode/generate |
| `moderator_user_message.md` | User message template for moderator generation | generation.py |
| `moderator_system.md` | Moderator system prompt for round discussion | discussion.py |
| `expert_reply_skill.md` | Skill definition for @mention expert reply | expert_reply.py |
| `expert_reply_user_message.md` | User message template for expert reply | expert_reply.py |

`libs/prompts/` takes precedence; missing files fall back to `app/prompts/`.
