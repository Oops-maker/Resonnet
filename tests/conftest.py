"""Pytest configuration and shared fixtures."""

# 必须在任何 app 导入之前设置 env，以满足 config 的导入时校验
import os
from pathlib import Path
from dotenv import load_dotenv

# 与 config.py 一致：加载项目根 .env；若不存在则尝试 backend/.env
_env_root = Path(__file__).resolve().parent.parent.parent / ".env"
_env_backend = Path(__file__).resolve().parent.parent / ".env"
if _env_root.exists():
    load_dotenv(_env_root, override=True)
elif _env_backend.exists():
    load_dotenv(_env_backend, override=True)

# 单元测试占位值（无真实 API 调用）；仅在未配置时兜底
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("AI_GENERATION_BASE_URL", "https://example.com")
os.environ.setdefault("AI_GENERATION_API_KEY", "test")
os.environ.setdefault("AI_GENERATION_MODEL", "test")
os.environ.setdefault("RESONNET_MODE", "standalone")

import pytest
import importlib

from app.db.session import reset_db_state


@pytest.fixture
def isolated_workspace(tmp_path, monkeypatch):
    """Isolated workspace for API/Agent SDK tests. Shared across test_api, test_agent_sdk."""
    workspace_base = tmp_path / "workspace"
    database_path = tmp_path / "resonnet-test.db"
    monkeypatch.setenv("WORKSPACE_BASE", str(workspace_base))
    monkeypatch.setenv("TOPICDATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("RESONNET_MODE", "standalone")
    reset_db_state()
    yield workspace_base
    reset_db_state()


@pytest.fixture
def client(isolated_workspace):
    """TestClient with isolated workspace. Requires isolated_workspace fixture."""
    from fastapi.testclient import TestClient
    import main as main_module

    main_module = importlib.reload(main_module)

    with TestClient(main_module.app) as c:
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
