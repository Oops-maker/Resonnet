# API Test Writing Guide (Based on Implemented Endpoints)

## When to Use

- You added or changed routes in `app/api/*.py`
- You want to add tests that match current code behavior, not just docs
- You need to verify file persistence, state transitions, background tasks, and integration paths
- When Agent SDK is involved, tests must use a real `.env` and verify conversation records

## Hard Requirements

- AgentSDK integration tests must run with a real `.env`
- `ANTHROPIC_API_KEY` must not be the placeholder `test`
- A `skip` due to placeholder does not count as "AgentSDK verified"

## Principles

1. Read the implementation first, then write tests: follow the actual logic in route handlers.
2. Cover the happy path first, then error paths: both `200/201/202` and `4xx/5xx`.
3. Tests must be reproducible: each test uses an isolated `WORKSPACE_BASE` and separate data dir.
4. Separate integration from unit tests: integration tests use `integration` + `slow` markers.
5. Agent SDK assertions: check not only API responses but also that conversation records are persisted.

## Standard Workflow

### 1) Extract Test Points from Implementation

For each route, extract:

- HTTP method and path (e.g. `POST /topics/{topic_id}/posts/mention`)
- Input validation (required fields, length limits, enum constraints)
- Business preconditions (topic exists, expert exists, state allows action)
- Side effects (file creation, state updates, background task start)
- Response shape (field presence, status values, correct related ids)

### 2) Build Test Matrix

Each endpoint should have at least:

- **Success case**: Correct structure and status code for typical input
- **Invalid params**: `422` or `400` (per implementation)
- **Resource not found**: `404`
- **Conflict**: `409` or `400` (per implementation)
- **Persistence check**: Key data exists under `workspace/topics/{topic_id}/...`

### 3) Shared Fixtures

Use fixtures from `conftest.py`:

- `isolated_workspace`: Isolated `tmp_path/workspace`, env patched, `topics_db` reset
- `client`: `TestClient(app)` with isolated workspace

For Agent SDK–specific workspaces (e.g. expert role files), add local fixtures in `test_agent_sdk.py`.

### 4) Agent SDK Integration Test Rules

Run only when a real key is present:

- Condition: `ANTHROPIC_API_KEY` is non-empty and not `test`
- Flow:
  1. Create topic
  2. Call mention endpoint to trigger expert reply
  3. Poll `GET /topics/{topic_id}/posts/mention/{reply_post_id}` until `completed` or `failed`
  4. Assert reply completed, body non-empty, `in_reply_to_id` correct
  5. Call `GET /topics/{topic_id}/posts` to verify conversation chain
  6. Read `workspace/topics/{topic_id}/posts/*.json` to verify disk records
  7. Inspect logs for `fail`, `error`, `timeout`, `exception`, `warning`; avoid "pass but with anomalies"

## Assertion Checklist (Reusable)

- Status code correct: `200`, `201`, `202`, `400`, `404`, `409`, `422`
- Response JSON has key fields: `id`, `status`, `created_at`, related fields
- List endpoints return correct type and include new entities
- Error responses include `detail` with correct semantics
- File system side effects exist and content matches (JSON fields align with API response)
- Async tasks reach a final state (not stuck in pending)

## File Layout

- `tests/test_api.py`: API coverage (topics, posts, experts; no real external services)
- `tests/test_agent_sdk.py`: Agent SDK — unit (mock, CI) + integration (real API, requires ANTHROPIC_API_KEY)
- Run fast tests: `pytest -m "not integration"`
- Run integration: `pytest tests/test_agent_sdk.py -m integration -v -s`
- GitHub CI runs only `not integration`; full local CI: `bash scripts/ci_local.sh`

## Minimal Template (Local API)

```python
def test_create_xxx(client):
    resp = client.post("/xxx", json={"name": "demo"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"]
    assert data["name"] == "demo"
```

## Minimal Template (Real Agent SDK)

```python
import os

def _has_real_api_key() -> bool:
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    return bool(key and key != "test")

@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(not _has_real_api_key(), reason="需要 ANTHROPIC_API_KEY")
def test_agentsdk_flow(client, isolated_workspace):
    # 1) create topic
    # 2) mention expert
    # 3) poll status
    # 4) assert completed + body non-empty
    # 5) assert posts api + disk json
    ...
```

## Anti-Patterns (Avoid)

- Asserting only `status_code == 200` without checking business fields
- Checking only API response, not disk records and state transitions
- Integration tests without markers, causing slow and flaky default runs
- Using a shared global directory so tests pollute each other
- Integration tests using mocks (unit tests are mock-based; integration must use real API)
