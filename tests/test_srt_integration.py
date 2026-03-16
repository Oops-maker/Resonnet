# tests/test_srt_integration.py
import os
import sys
import json
import importlib
from pathlib import Path

def make_fake_srt(shim_dir: Path):
    shim = shim_dir / "srt"
    shim.write_text(
        "#!/bin/sh\n"
        "for last; do :; done\n"
        "output_path=\"$last\"\n"
        "printf '{\"success\": true, \"result_info\": {\"from_shim\": true}}' > \"$output_path\"\n"
        "exit 0\n"
    )
    shim.chmod(0o755)
    return shim

def test_run_in_os_sandbox_with_fake_srt(tmp_path: Path, monkeypatch):
    # 1) create shim in tmp_path
    shim_dir = tmp_path / "shim_bin"
    shim_dir.mkdir()
    make_fake_srt(shim_dir)

    # 2) Prepend shim_dir to PATH before importing sandbox_exec
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(shim_dir) + os.pathsep + old_path

    # Force reimport to pick up the fake srt
    sys.modules.pop("app.agent.sandbox_exec", None)
    import app.agent.sandbox_exec as sandbox_exec
    importlib.reload(sandbox_exec)

    assert sandbox_exec.is_srt_available() is True or sandbox_exec.SRT_AVAILABLE is True

    # 3) Prepare workspace and minimal task_config
    ws = tmp_path / "workspace" / "topics" / "1"
    ws.mkdir(parents=True)
    task_config = {
        "task_type": "expert_reply",
        "ws_path": str(ws),
        "api_key": "placeholder",
        "topic_id": "1",
        "topic_title": "t",
        "expert_name": "e",
        "expert_label": "l",
        "user_post_id": "u1",
        "user_author": "author",
        "user_question": "q",
        "reply_post_id": "r1",
        "reply_created_at": "2026-01-01T00:00:00Z",
    }

    # 4) Run
    result = sandbox_exec.run_in_os_sandbox(task_config)
    assert isinstance(result, dict)
    assert result.get("success") is True
    assert result.get("result_info", {}).get("from_shim") is True

    # 5) Ensure IPC dir was cleaned up - run_in_os_sandbox removes it in finally
    # We cannot obtain the exact ipc path easily; but the tmp_path is the parent for shim and ws,
    # and run_in_os_sandbox uses /tmp or /private/tmp. Ensure no stray files in tmp_path were left by shim.
    # Primary check is successful result and no exceptions. (Detailed IPC existence checks require capturing IPC dir path from logs.)
