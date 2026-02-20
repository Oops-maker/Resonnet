# Skills Directory

Skills are organized by **scenario**. Each scenario contains expert role definitions, moderator modes, and optionally AI prompts.

## Component Comparison

| Component | Purpose | When to Add | Nature |
|-----------|---------|-------------|--------|
| **experts/** | **Who** participates in discussions. Defines domain roles (e.g. physicist, biologist) with identity, expertise, thinking style. | New expert persona for your scenario | Content / identity |
| **moderator_modes/** | **How** discussions are organized. Defines modes (standard, brainstorm, debate, review) with round flow and convergence strategy. Unified with assignable_skills, mcps. | New discussion format (e.g. risk assessment, design sprint) | Process / format |
| **prompts/** | **How** the AI behaves in specific features. System prompts for: expert generation, moderator generation, round discussion, @mention reply. | Customize AI behavior for a feature (e.g. different generation style, reply constraints) | Functional / mechanism |

**Quick guide:**
- Adding a new **persona** (e.g. economist, designer) → `experts/`
- Adding a new **discussion style** (e.g. risk review, ideation) → `moderator_modes/`
- Adding **assignable skills** (skills the moderator can assign to experts) → `assignable_skills/` (scenario-agnostic, sibling to scenarios)
- Changing **AI generation or reply behavior** → `prompts/` (or override specific files)

## Structure

```
skills/
├── assignable_skills/       # Assignable skills library (scenario-agnostic)
│   ├── meta.json           # Sources registry only
│   ├── default/meta.json   # categories + skills
│   └── ...
├── mcps/                   # MCP servers library (scenario-agnostic)
│   ├── meta.json           # Sources registry only
│   ├── default/meta.json   # categories + mcps
│   └── ...
├── moderator_modes/        # Moderator modes (unified with assignable_skills, mcps)
│   ├── meta.json           # Sources registry only
│   └── default/
│       ├── meta.json       # categories + modes + common_sections
│       ├── moderator_common.md
│       └── *.md            # Mode-specific: standard, brainstorm, debate, review
├── scenarios/
│   └── topic-lab/          # Research scenario (default)
│       ├── experts/
│       ├── moderator/      # DEPRECATED: use moderator_modes/ instead
│       └── prompts/
└── README.md
```

## Adding a New Scenario

1. Create `skills/scenarios/<scenario_name>/`
2. Add `experts/` with `meta.json` and `.md` skill files
3. Add moderator modes to `moderator_modes/` (see default/ for meta format)
4. Add `prompts/` (optional) with AI generation/discussion prompts; fallback to `app/prompts/`
5. Set `SCENARIO_PRESET=<scenario_name>` or `SKILLS_BASE=./skills/scenarios/<scenario_name>`

## Meta Format

- **experts/meta.json**: `{"experts": {"<name>": {"name", "label", "skill_file", "description"}}}`
- **moderator_modes/meta.json**: `{"sources": {"default": {...}}}` (sources registry only)
- **moderator_modes/{source}/meta.json**: `{"common_sections": "moderator_common.md", "categories": {...}, "modes": {"<id>": {"id", "source", "name", "description", "category", "num_rounds", "convergence_strategy", "prompt_file", "summary_scope"}}}`
- **assignable_skills/meta.json**: Sources registry only: `{"sources": {"<id>": {"id", "name", "description"}}}`
- **assignable_skills/{source}/meta.json**: Per-source `{"skills_dir"?, "categories": {...}, "skills": {...}}`. Built-in: path `{source}/{category}/{slug}.md`; imported: `skills_dir` points to root in `_submodules/{source}/`, runtime resolves `{skills_dir}/{category}/{slug}/SKILL.md`

**Add/modify skill libraries**: See [.cursor/skills/skills-submodule-guide/SKILL.md](../.cursor/skills/skills-submodule-guide/SKILL.md) or [docs/skills-submodule-guide.md](../docs/skills-submodule-guide.md).

See `scenarios/topic-lab/` for reference.

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

To customize a feature: copy the relevant file(s) from `app/prompts/` into your scenario's `prompts/`, then edit. Missing files fall back to `app/prompts/`.
