# Skills Generalization: From Topic Lab to a Generic Backend

> **Implemented**: This design has been applied. Skills have been migrated to `skills/scenarios/topic-lab/`. See `docs/config.md` for configuration.

## Pre-Migration Analysis

### Structure Before Migration

```
skills/
├── experts/
│   ├── meta.json          # physicist, biologist, computer_scientist, ethicist
│   ├── physicist.md
│   ├── biologist.md
│   ├── computer_scientist.md
│   └── ethicist.md
└── moderator/
    ├── meta.json          # standard, brainstorm, debate, review
    ├── standard.md
    ├── brainstorm.md
    ├── debate.md
    └── review.md
```

### Domain Binding

| Component | Binding | Notes |
|-----------|---------|-------|
| **experts** | Strong (research) | physicist, biologist, computer_scientist, ethicist are all "XX Researcher" identities |
| **moderator** | Weak | standard/brainstorm/debate/review are generic discussion patterns, reusable for business, product, etc. |
| **prompts/** | Partial | expert_generation, moderator_generation prompts may lean toward research wording |

### Hardcoded Paths in Code

| File | Path |
|------|------|
| `app/agent/experts.py` | `skills/experts/` |
| `app/agent/moderator_modes.py` | `skills/moderator/` |
| `app/api/experts.py` | `skills/` |
| `app/agent/discussion.py` | `skills/` |
| `app/agent/workspace.py` | `skills/` |
| `app/api/topic_experts.py` | `skills/` |

---

## Design: Scenario-Based Layering

### Goals

- Keep backend core logic **generic** (orchestration, API, workspace, discussion flow)
- Organize skills by **scenario**, switchable and extensible
- Default scenario is topic-lab for backward compatibility

### Recommended Directory Structure

```
skills/
├── scenarios/
│   └── topic-lab/              # Research scenario (experts + moderator + prompts)
│       ├── experts/
│       │   ├── meta.json
│       │   ├── physicist.md
│       │   ├── biologist.md
│       │   ├── computer_scientist.md
│       │   └── ethicist.md
│       ├── moderator/
│       │   ├── meta.json
│       │   ├── standard.md
│       │   ├── brainstorm.md
│       │   ├── debate.md
│       │   └── review.md
│       └── prompts/            # AI prompts (generation, discussion, expert reply)
│           └── *.md
│
├── default/                    # Minimal fallback (optional)
│   ├── experts/
│   │   └── meta.json           # Empty or minimal
│   └── moderator/
│       ├── meta.json          # standard only
│       └── standard.md
│
└── README.md                   # How to add new scenarios
```

### Configuration

Select scenario via environment variables:

```bash
# .env
SCENARIO_PRESET=topic-lab   # Default, compatible with topic-lab
# SCENARIO_PRESET=default   # Minimal set, no preset experts
# SCENARIO_PRESET=path/to/custom  # Custom path (optional)
```

Or use `SKILLS_BASE` to specify the skills root path:

```bash
SKILLS_BASE=./skills/scenarios/topic-lab   # Direct path to scenario directory
```

---

## Implementation Steps

### 1. Add Config Layer

In `app/core/config.py`:

```python
# Scenario preset: topic-lab | default | or custom path
SCENARIO_PRESET: str = os.getenv("SCENARIO_PRESET", "topic-lab")
SKILLS_BASE: Path | None = None  # If set, overrides SCENARIO_PRESET

def get_skills_dir() -> Path:
    """Return the skills root directory for the current scenario."""
    base = Path(__file__).parent.parent.parent / "skills"
    if SKILLS_BASE:
        return Path(SKILLS_BASE)
    if SCENARIO_PRESET == "topic-lab":
        return base / "scenarios" / "topic-lab"
    if SCENARIO_PRESET == "default":
        return base / "default"
    # Custom path
    return base / "scenarios" / SCENARIO_PRESET
```

### 2. Migrate Existing Skills

- Move `skills/experts/` → `skills/scenarios/topic-lab/experts/`
- Move `skills/moderator/` → `skills/scenarios/topic-lab/moderator/`

### 3. Replace Hardcoded Paths

Replace all `skills/` references with `get_skills_dir()`:

| Module | Change |
|--------|--------|
| `app/agent/experts.py` | `_EXPERTS_SKILLS_DIR = get_skills_dir() / "experts"` |
| `app/agent/moderator_modes.py` | `_MODERATOR_SKILLS_DIR = get_skills_dir() / "moderator"` |
| `app/api/experts.py` | `SKILLS_DIR = get_skills_dir()` |
| `app/agent/discussion.py` | `skills_dir = get_skills_dir()` |
| `app/agent/workspace.py` | Same as above |
| `app/api/topic_experts.py` | Same as above |

### 4. Create default Scenario (Optional)

For a generic mode with no preset experts:

- `skills/default/experts/meta.json`: `{"experts": {}}`
- `skills/default/moderator/meta.json`: Keep standard mode only

### 5. Backward Compatibility

- If `SCENARIO_PRESET` is unset, default is `topic-lab`; behavior matches current
- For pre-migration deployments, use a one-time migration script or symlink for smooth transition

---

## Optional: External Scenarios

To keep Topic Lab fully independent from the Resonnet repo, support "scenario packages":

```
# Scenario provided as separate package/directory
SCENARIO_PRESET=@tashan/topic-lab
# or
SKILLS_BASE=/path/to/Tashan-TopicLab/skills
```

Tashan-TopicLab maintains its own `skills/`; Resonnet only loads from it.

---

## Decision Matrix

| Requirement | Recommended Approach |
|-------------|---------------------|
| Need "generic backend" concept; Topic Lab remains primary | Use `scenarios/topic-lab` structure, default to it |
| Support multiple preset scenarios (research, business, product) | One subdirectory per scenario; switch via `SCENARIO_PRESET` |
| Decouple Topic Lab from Resonnet | Use `SKILLS_BASE` to point to external path |
| Minimal changes | Directory migration + config only; keep default topic-lab |

---

## Summary

- **experts** and **moderator** are scenario-level config; place under `skills/scenarios/<scenario_name>/`
- Backend uses `get_skills_dir()` to resolve paths and stay generic
- Default `topic-lab` keeps existing deployments and Tashan-TopicLab upgrades seamless
