---
name: skills-submodule-guide
description: Guides how to update skills via submodule, add new skills submodules, and find skills in complex directory structures. Use when the user asks about updating imported skills, adding a new skill library, importing skill repos, or locating skills in assignable_skills.
---

# Skills Submodule Guide

When working with assignable skills submodules in Agent Topic Lab, follow these procedures.

## 1. Update Existing Skill Library

When upstream (e.g. AI-Research-SKILLs, anthropics/skills) has new commits:

```bash
# From backend root — script pulls submodule and updates meta
./scripts/import_skill_repo.sh git@github.com:Orchestra-Research/AI-Research-SKILLs.git ai-research
./scripts/import_skill_repo.sh git@github.com:anthropics/skills.git anthropics
```

Restart backend after update.

## 2. Add New Skills Submodule

1. Ensure the repo contains `SKILL.md` files (various structures supported).
2. Run:
   ```bash
   ./scripts/import_skill_repo.sh <repo_url> [source_name]
   ```
3. `source_name` is optional; derived from URL if omitted (e.g. `AI-Research-SKILLs` → `ai-research`).
4. Commit: `_submodules/<source>/`, `assignable_skills/<source>/`, `meta.json`, `.gitmodules`.

**Examples**:
- `./scripts/import_skill_repo.sh git@github.com:Orchestra-Research/AI-Research-SKILLs.git`
- `./scripts/import_skill_repo.sh git@github.com:anthropics/skills.git anthropics`

## 3. Find Skills in Complex Directories

### Discovery Rule

The import script recursively finds all `SKILL.md`:

- **Skill dir** = directory containing `SKILL.md`
- **slug** = skill dir name
- **category** = parent dir name (or `general` if at repo root)

### Common Structures

| Pattern | Example | category | slug |
|---------|---------|----------|------|
| `{category}/{skill}/SKILL.md` | `01-model-architecture/litgpt/SKILL.md` | `01-model-architecture` | `litgpt` |
| `skills/{skill}/SKILL.md` | `skills/theme-factory/SKILL.md` | `skills` | `theme-factory` |
| `{skill}/SKILL.md` at root | `20-ml-paper-writing/SKILL.md` | `general` | `20-ml-paper-writing` |

### Search Commands

```bash
# All SKILL.md (skills stay in _submodules; no symlinks)
find skills/assignable_skills/_submodules -name "SKILL.md"

# By keyword in meta
cat skills/assignable_skills/ai-research/meta.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
q='rag'
for sid,s in d['skills'].items():
    if q in (s.get('name','')+s.get('description','')).lower():
        print(sid, s.get('name'))
"
```

### Path Mapping

- **Default**: `assignable_skills/{source}/{category}/{slug}.md`
- **Imported** (submodule): `assignable_skills/_submodules/{source}/{skills_dir}/{category}/{slug}/SKILL.md` — no symlinks; `skills_dir` in meta (e.g. `"."` for ai-research, `"skills"` for anthropics)
- Skill ID: `{source}:{slug}` (e.g. `ai-research:litgpt`). Default source has no prefix.

## Quick Reference

| Action | Command |
|--------|---------|
| Update/add skill library | `./scripts/import_skill_repo.sh <url> [source]` |
| List sources | `cat skills/assignable_skills/meta.json` |
| List skills by source | `cat skills/assignable_skills/<source>/meta.json` |
| Find SKILL.md | `find skills/assignable_skills/_submodules -name "SKILL.md"` |

## Related Docs

- [docs/skills-submodule-guide.md](../../../docs/skills-submodule-guide.md) — Brief overview, points to this skill
- [docs/import-skill-repo.md](../../../docs/import-skill-repo.md) — Import script quick reference
