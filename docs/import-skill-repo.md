# Import Skill Repo

> One-click import of external skill libraries as submodule.  
> **Full guide**: `.cursor/skills/skills-submodule-guide/SKILL.md`

```bash
./scripts/import_skill_repo.sh <repo_url> [source_name]
```

When backend is a submodule, run from repo root: `./backend/scripts/import_skill_repo.sh`.

- Clones to `skills/assignable_skills/_submodules/<source>`
- Recursively scans `SKILL.md`, infers `skills_dir`, writes `{source}/meta.json` (no symlinks)
- Runtime resolves paths to `_submodules/{source}/{skills_dir}/{category}/{slug}/SKILL.md`
