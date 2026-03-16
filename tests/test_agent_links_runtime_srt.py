"""Tests for Agent Links runtime SRT integration."""

from __future__ import annotations

from pathlib import Path


def test_make_sdk_options_without_srt(tmp_path: Path, monkeypatch):
    from app.services import agent_links_runtime as runtime

    monkeypatch.setenv("SANDBOX_USE_SRT", "false")
    monkeypatch.setattr("app.agent.sandbox_exec.SRT_AVAILABLE", True)

    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    opts = runtime._make_sdk_options(
        workdir=str(ws),
        system_prompt="sys",
        model=None,
    )
    assert opts.cli_path is None


def test_make_sdk_options_with_srt_wrapper(tmp_path: Path, monkeypatch):
    from app.services import agent_links_runtime as runtime

    monkeypatch.setenv("SANDBOX_USE_SRT", "true")
    monkeypatch.setattr("app.agent.sandbox_exec.SRT_AVAILABLE", True)

    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    opts = runtime._make_sdk_options(
        workdir=str(ws),
        system_prompt="sys",
        model=None,
    )
    assert opts.cli_path
    wrapper = Path(str(opts.cli_path))
    assert wrapper.exists()
    assert wrapper.name == "claude_srt_wrapper.sh"
    text = wrapper.read_text(encoding="utf-8")
    assert "srt --settings" in text
    assert ' claude "$@"' in text
    settings = ws / "config" / "agent_links_srt_settings.json"
    assert settings.exists()


def test_make_sdk_options_reuses_existing_srt_wrapper(tmp_path: Path, monkeypatch):
    from app.services import agent_links_runtime as runtime

    monkeypatch.setenv("SANDBOX_USE_SRT", "true")
    monkeypatch.setattr("app.agent.sandbox_exec.SRT_AVAILABLE", True)

    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    opts1 = runtime._make_sdk_options(
        workdir=str(ws),
        system_prompt="sys",
        model=None,
    )
    opts2 = runtime._make_sdk_options(
        workdir=str(ws),
        system_prompt="sys2",
        model=None,
    )
    assert opts1.cli_path == opts2.cli_path
