#!/usr/bin/env bash
set -euo pipefail

# Local one-click CI runner:
# - Runs the same unit-test gate as GitHub Actions
# - Additionally runs AgentSDK integration tests with real .env credentials

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[ci-local] installing dependencies..."
echo "[ci-local] (ephemeral) resolving runtime via uv --with packages"

echo "[ci-local] running unit tests (same as GitHub CI)..."
uv run \
  --with fastapi \
  --with uvicorn \
  --with pydantic \
  --with pydantic-settings \
  --with python-dotenv \
  --with claude-agent-sdk \
  --with anthropic \
  --with openai \
  --with pytest \
  --with pytest-asyncio \
  --with httpx \
  pytest -m "not integration" -v --tb=short

if [[ -f ".env" ]]; then
  # shellcheck disable=SC1091
  source .env
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" || "${ANTHROPIC_API_KEY:-}" == "test" ]]; then
  echo "[ci-local] ERROR: ANTHROPIC_API_KEY is missing or placeholder ('test')."
  echo "[ci-local] Please configure a real key in .env, then re-run scripts/ci_local.sh."
  exit 2
fi

echo "[ci-local] running AgentSDK integration tests (real env)..."
uv run \
  --with fastapi \
  --with uvicorn \
  --with pydantic \
  --with pydantic-settings \
  --with python-dotenv \
  --with claude-agent-sdk \
  --with anthropic \
  --with openai \
  --with pytest \
  --with pytest-asyncio \
  --with httpx \
  pytest tests/test_agent_sdk.py -m integration -v -s

echo "[ci-local] success: unit + AgentSDK integration tests passed."
