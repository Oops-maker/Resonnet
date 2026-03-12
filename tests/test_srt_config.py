"""Unit tests for app.agent.srt_config — srt settings generation."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# build_srt_settings
# ---------------------------------------------------------------------------


class TestBuildSrtSettings:
    """Tests for build_srt_settings()."""

    def test_basic_settings_structure(self, tmp_path: Path):
        from app.agent.srt_config import build_srt_settings

        ws = str(tmp_path / "workspace")
        ipc = str(tmp_path / "ipc")
        settings = build_srt_settings(topic_workspace=ws, ipc_dir=ipc)

        assert "filesystem" in settings
        fs = settings["filesystem"]
        assert "denyRead" in fs
        assert "allowWrite" in fs
        assert "denyWrite" in fs

    def test_allow_write_includes_workspace_and_ipc(self, tmp_path: Path):
        from app.agent.srt_config import build_srt_settings

        ws = str(tmp_path / "workspace")
        ipc = str(tmp_path / "ipc")
        settings = build_srt_settings(topic_workspace=ws, ipc_dir=ipc)

        allow_write = settings["filesystem"]["allowWrite"]
        assert ws in allow_write
        assert ipc in allow_write
        assert "/tmp" in allow_write

    def test_deny_read_includes_sensitive_paths(self, tmp_path: Path):
        from app.agent.srt_config import build_srt_settings

        settings = build_srt_settings(
            topic_workspace=str(tmp_path / "ws"),
            ipc_dir=str(tmp_path / "ipc"),
        )
        deny_read = settings["filesystem"]["denyRead"]
        assert "**/.env" in deny_read
        assert "**/.env.*" in deny_read
        home = str(Path.home())
        assert os.path.join(home, ".ssh") in deny_read

    def test_custom_claude_config_dir(self, tmp_path: Path):
        from app.agent.srt_config import build_srt_settings

        custom_dir = str(tmp_path / "custom_claude")
        settings = build_srt_settings(
            topic_workspace=str(tmp_path / "ws"),
            ipc_dir=str(tmp_path / "ipc"),
            claude_config_dir=custom_dir,
        )
        assert custom_dir in settings["filesystem"]["allowWrite"]

    def test_custom_uv_cache_dir(self, tmp_path: Path):
        from app.agent.srt_config import build_srt_settings

        custom_cache = str(tmp_path / "uv_cache")
        settings = build_srt_settings(
            topic_workspace=str(tmp_path / "ws"),
            ipc_dir=str(tmp_path / "ipc"),
            uv_cache_dir=custom_cache,
        )
        assert custom_cache in settings["filesystem"]["allowWrite"]

    def test_no_network_isolation_by_default(self, tmp_path: Path):
        from app.agent.srt_config import build_srt_settings

        settings = build_srt_settings(
            topic_workspace=str(tmp_path / "ws"),
            ipc_dir=str(tmp_path / "ipc"),
        )
        # No strict network config when allowed_domains is None
        assert "network" not in settings
        assert settings.get("enableWeakerNetworkIsolation") is True

    def test_network_isolation_with_domains(self, tmp_path: Path):
        from app.agent.srt_config import build_srt_settings

        domains = ["api.anthropic.com", "*.dashscope.aliyuncs.com"]
        settings = build_srt_settings(
            topic_workspace=str(tmp_path / "ws"),
            ipc_dir=str(tmp_path / "ipc"),
            allowed_domains=domains,
        )
        assert settings["network"]["allowedDomains"] == domains
        assert settings["enableWeakerNetworkIsolation"] is False


# ---------------------------------------------------------------------------
# build_mcp_srt_settings
# ---------------------------------------------------------------------------


class TestBuildMcpSrtSettings:
    """Tests for build_mcp_srt_settings()."""

    def test_write_limited_to_shared_dir(self, tmp_path: Path):
        from app.agent.srt_config import build_mcp_srt_settings

        ws = str(tmp_path / "workspace")
        settings = build_mcp_srt_settings(topic_workspace=ws)

        allow_write = settings["filesystem"]["allowWrite"]
        shared_dir = os.path.join(ws, "shared")
        assert shared_dir in allow_write
        # Full workspace should NOT be in allow_write for MCP
        assert ws not in allow_write

    def test_deny_read_same_as_main_sandbox(self, tmp_path: Path):
        from app.agent.srt_config import build_mcp_srt_settings, build_srt_settings

        ws = str(tmp_path / "workspace")
        main_settings = build_srt_settings(
            topic_workspace=ws, ipc_dir=str(tmp_path / "ipc"),
        )
        mcp_settings = build_mcp_srt_settings(topic_workspace=ws)
        assert (
            mcp_settings["filesystem"]["denyRead"]
            == main_settings["filesystem"]["denyRead"]
        )

    def test_no_network_isolation_by_default(self, tmp_path: Path):
        from app.agent.srt_config import build_mcp_srt_settings

        settings = build_mcp_srt_settings(
            topic_workspace=str(tmp_path / "ws"),
        )
        assert "network" not in settings
        assert settings.get("enableWeakerNetworkIsolation") is True


# ---------------------------------------------------------------------------
# write_srt_settings_file
# ---------------------------------------------------------------------------


class TestWriteSrtSettingsFile:
    """Tests for write_srt_settings_file()."""

    def test_writes_valid_json(self, tmp_path: Path):
        from app.agent.srt_config import build_srt_settings, write_srt_settings_file

        settings = build_srt_settings(
            topic_workspace=str(tmp_path / "ws"),
            ipc_dir=str(tmp_path / "ipc"),
        )
        path = write_srt_settings_file(settings, target_dir=str(tmp_path))
        try:
            data = json.loads(Path(path).read_text())
            assert data == settings
        finally:
            os.unlink(path)

    def test_file_has_correct_prefix(self, tmp_path: Path):
        from app.agent.srt_config import build_srt_settings, write_srt_settings_file

        settings = build_srt_settings(
            topic_workspace=str(tmp_path / "ws"),
            ipc_dir=str(tmp_path / "ipc"),
        )
        path = write_srt_settings_file(settings, target_dir=str(tmp_path))
        try:
            assert Path(path).name.startswith("srt_settings_")
            assert Path(path).name.endswith(".json")
        finally:
            os.unlink(path)

    def test_target_dir_respected(self, tmp_path: Path):
        from app.agent.srt_config import build_srt_settings, write_srt_settings_file

        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        settings = build_srt_settings(
            topic_workspace=str(tmp_path / "ws"),
            ipc_dir=str(tmp_path / "ipc"),
        )
        path = write_srt_settings_file(settings, target_dir=str(custom_dir))
        try:
            assert str(custom_dir) in path
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# sandbox_exec srt detection
# ---------------------------------------------------------------------------


class TestSrtDetection:
    """Tests for srt availability detection in sandbox_exec."""

    def test_srt_available_flag_is_bool(self):
        from app.agent.sandbox_exec import SRT_AVAILABLE
        assert isinstance(SRT_AVAILABLE, bool)

    def test_is_srt_available_returns_bool(self):
        from app.agent.sandbox_exec import is_srt_available
        assert isinstance(is_srt_available(), bool)


# ---------------------------------------------------------------------------
# config: get_sandbox_use_srt
# ---------------------------------------------------------------------------


class TestSandboxUseSrtConfig:
    """Tests for get_sandbox_use_srt() in config."""

    def test_default_is_true(self, monkeypatch):
        monkeypatch.delenv("SANDBOX_USE_SRT", raising=False)
        from app.core.config import get_sandbox_use_srt
        assert get_sandbox_use_srt() is True

    def test_false_string(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_USE_SRT", "false")
        from app.core.config import get_sandbox_use_srt
        assert get_sandbox_use_srt() is False

    def test_zero_is_false(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_USE_SRT", "0")
        from app.core.config import get_sandbox_use_srt
        assert get_sandbox_use_srt() is False

    def test_yes_is_true(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_USE_SRT", "yes")
        from app.core.config import get_sandbox_use_srt
        assert get_sandbox_use_srt() is True
