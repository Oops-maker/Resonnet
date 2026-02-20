# AI Prompt Management

This directory contains system prompts used for AI generation and agent invocation.

## File Layout

```
prompts/
├── README.md                 # This file
├── expert_generation.md      # Expert role generation (system prompt, role-only output)
├── expert_user_message.md   # Expert generation user message template
├── moderator_generation.md   # Moderator mode generation (system prompt)
├── moderator_user_message.md # Moderator generation user message template
├── moderator_system.md       # Round discussion moderator system prompt
├── expert_reply_skill.md    # Expert reply skill (@mention scenario)
└── expert_reply_user_message.md # Expert reply user message template
```

## Prompt Files

### Expert Generation (generation.py)

| File | Purpose |
|------|---------|
| `expert_generation.md` | System prompt for generating expert role definitions (role-only) |
| `expert_user_message.md` | User message template with `{expert_name}`, `{expert_label}`, `{expert_bio}` |

**Trigger**: User enters name, label, and bio when creating a new expert, then clicks "AI generate role definition".

**Output**: Role-specific content (Identity, Expertise, Thinking Style, Discussion Style). Workspace, Discussion Rules, Language are appended from expert_common.md at load time.

### Moderator Mode Generation (generation.py)

| File | Purpose |
|------|---------|
| `moderator_generation.md` | System prompt for generating moderator mode prompts (role-only) |
| `moderator_user_message.md` | User message template with `{user_prompt}` |

**Trigger**: User enters a description in the "Edit custom moderator prompt" dialog, then clicks "AI generate prompt".

**Output**: Role-specific content (role, Goal, Phases). Workspace, Rules, Language are appended from moderator_common.md at load time.

### Round Discussion (discussion.py)

| File | Purpose |
|------|---------|
| `moderator_system.md` | Moderator system prompt for round discussion, with `{ws_abs}` placeholder |

### Expert Reply (expert_reply.py)

| File | Purpose |
|------|---------|
| `expert_reply_skill.md` | Expert reply skill definition (@mention scenario) |
| `expert_reply_user_message.md` | User message template with `{topic_title}`, `{user_author}`, `{expert_label}`, `{user_question}` |

## Design Principles

1. **Clarity**: Clearly specify what the AI should generate
2. **Format**: Define strict output format for parsing
3. **Examples**: Provide concrete examples to guide output
4. **Extensibility**: Do not limit length; allow full expression
5. **Placeholders**: For templates, explicitly require placeholders to remain unchanged

## Modifying Prompts

After editing prompt files, the backend loads new content on the next call (no restart needed).

## Call Chain

```
Frontend UI
  ↓
API (topicExpertsApi.generate / moderatorModesApi.generate)
  ↓
Backend endpoints (topic_experts.py / moderator_modes.py)
  ↓
Generation (generation.py)
  ↓
Load prompt (load_prompt())
  ↓
Call AI API (OpenAI-compatible, e.g. ZhipuAI)
  ↓
Parse response
  ↓
Return to frontend
```

## Load Path

- **Primary**: Scenario `prompts/` (e.g. `skills/scenarios/topic-lab/prompts/`) when it exists
- **Fallback**: `app/prompts/` when scenario has no prompts subdir
- **Code**: `app/core/config.get_prompts_dir()`; used by `generation.py`, `expert_reply.py`, `discussion.py`

## Notes

- Prompt files use UTF-8 encoding
- Markdown format for readability and maintenance
- Prompts are independent of business logic for easier tuning by non-developers
