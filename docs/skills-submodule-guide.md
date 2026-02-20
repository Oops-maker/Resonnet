# Skills Submodule Guide

> To **add or modify skill libraries** (update, import, find skills), see the Cursor skill:  
> **`.cursor/skills/skills-submodule-guide/SKILL.md`**

That skill contains full procedures, commands, and lookup tips. AI will auto-reference it by description.

**Deploy**: Ensure `git submodule update --init --recursive` so `_submodules/` is available. Skills are read directly from submodules (no symlinks).

---

## Quick Command

```bash
# Update / add skill library (from backend root)
./scripts/import_skill_repo.sh <repo_url> [source_name]
```

When backend is a submodule, run from repo root: `./backend/scripts/import_skill_repo.sh`.

Restart backend after update.
