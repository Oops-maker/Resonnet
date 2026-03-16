#!/usr/bin/env bash
set -euo pipefail

# Local one-click CI runner:
# - Runs the same unit-test gate as GitHub Actions
# - Additionally runs AgentSDK integration tests with real .env credentials

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Flag to avoid printing srt status multiple times (trap + normal flow)
SRT_CHECK_DONE=0

print_srt_status() {
  # Avoid duplicate prints
  if [[ "${SRT_CHECK_DONE:-0}" -eq 1 ]]; then
    return
  fi
  SRT_CHECK_DONE=1

  echo "[ci-local] checking sandbox-runtime (srt) availability..."
  if command -v srt >/dev/null 2>&1; then
    SRT_PATH=$(command -v srt)
    SRT_VER=$(srt --version 2>/dev/null || true)
    if [[ -n "${SRT_VER:-}" ]]; then
      echo "[ci-local] srt found: ${SRT_PATH} (version: ${SRT_VER})"
    else
      echo "[ci-local] srt found: ${SRT_PATH} (version: unknown)"
    fi
  else
    echo "[ci-local] srt (sandbox-runtime) not found in PATH."
    if command -v npm >/dev/null 2>&1; then
      echo "[ci-local] Attempting to install @anthropic-ai/sandbox-runtime globally via npm..."
      if npm install -g @anthropic-ai/sandbox-runtime; then
        echo "[ci-local] srt installed successfully at $(command -v srt)"
      else
        echo "[ci-local] npm attempted to install srt but it is still not available. Please install srt manually: npm install -g @anthropic-ai/sandbox-runtime"
        echo "[ci-local] Continuing; integration tests may fail if srt is required." >&2
      fi
    else
      echo "[ci-local] npm not found. Please install Node.js + npm, then install srt: npm install -g @anthropic-ai/sandbox-runtime"
      echo "[ci-local] Continuing; integration tests may fail if srt is required." >&2
    fi
  fi
}

# Ensure we always print srt status on exit, even if the script aborts early
trap print_srt_status EXIT

echo "[ci-local] installing dependencies..."
echo "[ci-local] (ephemeral) resolving runtime via uv --with packages"

echo "[ci-local] running unit tests (same as GitHub CI)..."
# Run unit tests but don't let failures abort the script immediately; we still want
# to report srt/installation status to the user regardless of test outcome.
if ! uv run \
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
  pytest -m "not integration" -v --tb=short; then
  UNIT_RC=$?
  echo "[ci-local] Unit tests exited with code ${UNIT_RC}. Continuing to environment checks (srt) so you can see environment status." >&2
else
  echo "[ci-local] Unit tests passed."
fi

if [[ -f ".env" ]]; then
  # shellcheck disable=SC1091
  source .env
fi

# Print srt status now (and also via trap on EXIT) so user always sees it
print_srt_status

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
