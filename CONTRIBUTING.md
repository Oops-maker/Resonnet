# Contributing to Resonnet

Thank you for your interest in Resonnet! Contributions via Issues and Pull Requests are welcome.

## Code of Conduct

Please maintain a respectful and inclusive environment. Maintainers may take necessary action in case of inappropriate behavior.

## How to Contribute

### Reporting Bugs

- Submit bug reports via [GitHub Issues](https://github.com/YOUR_ORG/resonnet/issues)
- Include: environment info, reproduction steps, expected vs actual behavior
- If possible, attach a minimal reproducible example

### Proposing Features

- Describe the feature and use cases in an Issue
- Discuss before implementing to avoid duplicate work

### Submitting Code

1. **Fork the repo** and create a branch locally:
   ```bash
   git checkout -b feature/your-feature   # or fix/your-fix
   ```

2. **Follow project conventions**:
   - Code style: follow existing style (e.g. `ruff` / `black`)
   - Tests: new logic should have corresponding tests
   - Unit tests must pass: `pytest -q -m "not integration"`

3. **Submit a Pull Request**:
   - Clear, concise title
   - Describe changes, motivation, and related Issues
   - Ensure CI passes (GitHub Actions runs `not integration` only)

## Development Environment

```bash
uv sync
cp .env.example .env   # fill required vars (unit tests can skip)
pytest -q -m "not integration"
uv run uvicorn main:app --reload
```

## Testing Requirements

- Unit tests must pass before PR merge
- For changes to `app/api`, `app/agent`, or AgentSDK call paths, run AgentSDK integration tests with a real `.env`:
  - `pytest tests/test_agent_sdk.py -m integration -v -s`
  - `ANTHROPIC_API_KEY` must be a real, valid key (not a `test` placeholder)
  - Verify reply status completes and conversation records are written to `workspace/topics/{topic_id}/posts/*.json`
- One-shot local CI (unit + integration):
  - `bash scripts/ci_local.sh`

## Contributing Skills (No Code Changes)

You can add or customize without modifying backend code:

- **Expert roles** (who): Add `.md` under `skills/scenarios/topic-lab/experts/`, register in `meta.json`
- **Discussion modes** (how discussions run): Add `.md` under `skills/moderator_modes/default/`, register in `default/meta.json` (same structure as assignable_skills, mcps)
- **AI prompts** (how features behave): Override files in `skills/scenarios/topic-lab/prompts/` to change generation, discussion, or @mention behavior

See [skills/README.md](skills/README.md) for component comparison and [docs/skills-generalization.md](docs/skills-generalization.md) for scenario design.

## Documentation

- When changing API or config, update the relevant docs under `docs/`
- New features should be documented in README or the appropriate doc

## Questions and Discussion

- Technical discussion: via Issues
- Security-related: see [SECURITY.md](SECURITY.md)
