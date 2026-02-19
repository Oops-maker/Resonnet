# Configuration Guide

## Environment Variables

### Scenario / Skills Preset (Optional)

```bash
# Default: topic-lab (research scenario with physicist, biologist, etc.)
SCENARIO_PRESET=topic-lab

# Or use a custom path (absolute or relative to project root)
SKILLS_BASE=./skills/scenarios/topic-lab
```

- **SCENARIO_PRESET**: `topic-lab` (default) | `default` | `<custom_scenario_name>`
- **SKILLS_BASE**: Overrides SCENARIO_PRESET; points to scenario directory containing `experts/`, `moderator/`, and optionally `prompts/`

---

Resonnet uses **two separate API configurations**; do not mix them:

### 1. Claude Agent SDK (Round Discussion Orchestration)

```bash
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
ANTHROPIC_MODEL=glm-4.7-flashx
```

**Use for:**
- Round discussion orchestration (`app/agent/discussion.py`)
- Multi-agent coordination via Claude Agent SDK

**Warning:** Do not use OpenAI/ZhipuAI coding-style APIs here.

---

### 2. AI Generation (Expert/Moderator Generation)

```bash
AI_GENERATION_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4
AI_GENERATION_API_KEY=your_key_here
AI_GENERATION_MODEL=glm-4-flash
```

**Use for:**
- Expert role generation (`app/agent/generation.py`)
- Moderator mode generation
- Direct HTTP API calls (not Anthropic SDK)

**Warning:** Do not use Claude Agent SDK–compatible APIs here.

---

## Rules

1. **Do not mix the two configs**
   - ANTHROPIC_* for Claude Agent SDK
   - AI_GENERATION_* for direct HTTP API calls

2. **No fallback**
   - Missing AI_GENERATION_API_KEY does not fall back to ANTHROPIC_API_KEY
   - Each config must be set explicitly

3. **Different API formats**
   - ANTHROPIC_BASE_URL expects Anthropic-compatible API
   - AI_GENERATION_BASE_URL expects OpenAI-compatible API (e.g. ZhipuAI)

## Validation

The app will not start if these are unset:
- AI_GENERATION_BASE_URL
- AI_GENERATION_API_KEY
- AI_GENERATION_MODEL
- ANTHROPIC_API_KEY

This is intentional to avoid misconfiguration.

## Unit Tests

Unit tests use conftest placeholders; no real API keys needed. See [testing.md](testing.md).

## AgentSDK Real-Env Testing

- Integration tests require a real `.env`; `ANTHROPIC_API_KEY` must not be empty or `test`
- Recommended:

```bash
pytest tests/test_agent_sdk.py -m integration -v -s
```

- Acceptance criteria:
  - API returns success
  - Post conversation records written to `workspace/topics/{topic_id}/posts/*.json`
