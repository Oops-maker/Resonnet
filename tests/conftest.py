"""Pytest configuration and shared fixtures."""

# 必须在任何 app 导入之前设置 env，以满足 config 的导入时校验
import os
from pathlib import Path
from dotenv import load_dotenv

_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    # Ensure real local .env values override test placeholders.
    load_dotenv(_env, override=True)

# 单元测试占位值（无真实 API 调用）；仅在未配置时兜底
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("AI_GENERATION_BASE_URL", "https://example.com")
os.environ.setdefault("AI_GENERATION_API_KEY", "test")
os.environ.setdefault("AI_GENERATION_MODEL", "test")

import pytest

from app.models import store


@pytest.fixture
def isolated_workspace(tmp_path, monkeypatch):
    """Isolated workspace for API/Agent SDK tests. Shared across test_api, test_agent_sdk."""
    workspace_base = tmp_path / "workspace"
    monkeypatch.setenv("WORKSPACE_BASE", str(workspace_base))
    monkeypatch.setattr(store, "WORKSPACE_BASE", workspace_base, raising=False)
    store.topics_db.clear()
    yield workspace_base
    store.topics_db.clear()


@pytest.fixture
def client(isolated_workspace):
    """TestClient with isolated workspace. Requires isolated_workspace fixture."""
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as c:
        yield c


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: real agent SDK calls; require ANTHROPIC_API_KEY",
    )
    config.addinivalue_line(
        "markers",
        "slow: slow tests (agent round-trips)",
    )
