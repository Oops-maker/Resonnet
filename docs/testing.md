# Testing Guide

## Test Layers

| Layer | Command | Dependencies | Notes |
|-------|---------|--------------|-------|
| Unit | `pytest -q` or `pytest -q -m "not integration"` | conftest placeholders | Default; no real API calls |
| Integration | `pytest tests/test_agent_sdk.py -m integration -v -s` | `ANTHROPIC_API_KEY` (real) | Real Agent SDK; validates API and conversation records |

## Environment Setup

### Unit Tests (No Real API Key)

Unit tests use placeholders in `tests/conftest.py` to satisfy `app/core/config` import-time checks. **No real API keys needed.**

- Run `pytest -q` directly
- If `.env` exists, conftest loads it to override placeholders (for integration tests)

### Integration Tests (Real API Key Required)

Integration tests call the real Claude Agent SDK. Configure:

```bash
# In .env (do not commit)
ANTHROPIC_API_KEY=sk-...
```

Optional: `SANDBOX_TEST_MODEL=claude-haiku-4-5-20251001` for cheaper model.

> Note: `ANTHROPIC_API_KEY=test` or empty triggers test skip; not a pass.  
> Acceptance requires real `.env` and real call results.

### Local Commands

```bash
# Unit tests (recommended)
pytest -q -m "not integration"

# All unit tests
pytest -q

# AgentSDK integration (requires real .env)
pytest tests/test_agent_sdk.py -m integration -v -s

# One-shot local CI (unit + AgentSDK integration)
bash scripts/ci_local.sh
```

## Test Files

| File | Type | Description |
|------|------|-------------|
| `test_api.py` | Unit | API endpoints (topics/posts validation and persistence) |
| `test_agent_sdk.py` | Unit + Integration | Agent SDK: unit (mock, CI) + integration (real API, requires ANTHROPIC_API_KEY) |

## AgentSDK Integration Checklist

- Run `test_agent_sdk.py -m integration` with real `.env` (no placeholders)
- `POST /topics/{topic_id}/posts/mention` returns `202`
- Poll `GET /topics/{topic_id}/posts/mention/{reply_post_id}` until `completed`
- `GET /topics/{topic_id}/posts` shows user post and expert reply
- `workspace/topics/{topic_id}/posts/*.json` contains reply record with `status=completed`

## CI Notes

- **PR must pass**: `pytest -q -m "not integration"`
- **Integration**: Run as cron or manual; requires `ANTHROPIC_API_KEY` secret

## Docker API Test

To verify API calls against Docker deployment:

```bash
# Ensure Docker daemon is running, then:
./scripts/test_docker_api.sh
```

The script builds the image, starts the container, runs health/topics/experts/posts checks, then stops. Uses existing `.env` or creates a minimal one if missing (placeholder keys; no real AI calls).

## Agent SDK Testing Strategy

All Agent SDK tests live in **one file** `tests/test_agent_sdk.py`:

- **Unit** (CI, no API key): `_extract_reply_body`, `run_expert_reply` mocked, `run_discussion` mocked, mention API mocked
- **Integration** (manual/cron, needs ANTHROPIC_API_KEY): real mention and discussion flows; skip if no key

Contributors: add unit tests for new Agent SDK paths (CI coverage); add integration tests for real API validation.

For mock strategies and best practices, see [Agent SDK Testing Practices](agent-sdk-testing-practices.md).

## Configured CI Behavior

- GitHub Actions: `.github/workflows/tests-ci.yml`
- Triggers: `push`, `pull_request`, `workflow_dispatch`
- **Detect changes** job runs first (git diff); unit jobs skip when no relevant changes:
  - **Unit (API)**: runs when `app/api/**`, `app/models/**`, `app/core/**`, `main.py`, `tests/test_api.py`, `tests/conftest.py` change
  - **Unit (Agent SDK)**: runs when `app/agent/**`, `app/prompts/**`, `skills/**` (including `skills/scenarios/**`), `tests/test_agent_sdk.py`, `tests/conftest.py` change
  - **Integration (Agent SDK)**: depends on Unit (Agent SDK); also skipped when no API key
- `workflow_dispatch`: always runs all tests (no diff)
- To run integration on GitHub: add `ANTHROPIC_API_KEY` as a repository secret
- Full local CI (with AgentSDK): `bash scripts/ci_local.sh`
