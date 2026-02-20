---
name: code-contribution
description: Guides coding agents on how to contribute code to Resonnet. Use when implementing features, fixing bugs, submitting PRs, or when the user asks about contribution workflow, commit format, or testing requirements.
---

# Code Contribution Guide

When contributing code to Resonnet, follow this workflow.

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]
```

**Types**: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

**Examples**:
```
feat(api): add POST /topics/{id}/experts/share endpoint
fix(posts): handle empty body in mention reply
docs(readme): add skill contribution table
test(api): add 404 cases for topic experts
```

**Rules**:
- Lowercase subject; no period at end
- Scope is optional but preferred for `app/api`, `app/agent`, etc.
- Breaking changes: `feat(api)!: remove deprecated field`

## Unit Tests

- **Required**: New or changed logic must have corresponding tests
- **Run before PR**: `pytest -q -m "not integration"`
- **CI**: GitHub Actions runs only `not integration`; must pass
- **Fixtures**: Use `tmp_path` for isolated workspace; `monkeypatch.setenv("WORKSPACE_BASE", ...)`
- **API tests**: See [tests/API_TEST_GUIDE.md](../../tests/API_TEST_GUIDE.md)

**Integration tests** (Agent SDK):
- Mark with `@pytest.mark.integration` and `@pytest.mark.slow`
- Require real `.env`; `ANTHROPIC_API_KEY` must not be `test`
- Run: `pytest tests/test_agent_sdk.py -m integration -v -s`
- Full local CI: `bash scripts/ci_local.sh`

## Code Style

- Follow existing style; use `ruff` or `black`
- No logic changes when translating comments or error messages

## PR Checklist

Before submitting:

- [ ] Unit tests pass: `pytest -q -m "not integration"`
- [ ] If touching `app/api` or `app/agent`: run integration tests with real `.env`
- [ ] Commit messages follow Conventional Commits
- [ ] Docs updated when API or config changes
- [ ] No sensitive data (API keys, secrets) in code or commits

## File Layout

| Change type | Update |
|-------------|--------|
| API routes | `app/api/*.py` + tests in `tests/test_api.py` |
| Agent logic | `app/agent/*.py` + integration tests if Agent SDK |
| Config | `app/core/config.py` + `docs/config.md` |
| Schemas | `app/models/schemas.py` |
| Skills | `libs/experts/default/` or `libs/moderator_modes/default/` (see README Contributing) |

## References

- [CONTRIBUTING.md](../../CONTRIBUTING.md) — Full contribution guide
- [tests/API_TEST_GUIDE.md](../../tests/API_TEST_GUIDE.md) — API test writing
