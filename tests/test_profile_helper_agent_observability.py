from app.services.profile_helper import agent


def test_summarize_tool_arguments_uses_compact_json():
    args = {"skill_name": "collect-basic-info", "step": 1}
    summary = agent._summarize_tool_arguments(args, max_len=120)
    assert summary == '{"skill_name":"collect-basic-info","step":1}'


def test_summarize_tool_arguments_truncates_long_payload():
    args = {"content": "x" * 200}
    summary = agent._summarize_tool_arguments(args, max_len=40)
    assert summary.endswith("...")
    assert len(summary) == 40


def test_normalize_tool_call_maps_skill_name_alias(monkeypatch):
    monkeypatch.setattr(
        agent,
        "list_skill_names",
        lambda: ["infer-profile-dimensions", "collect-basic-info"],
    )
    normalized_name, normalized_args = agent._normalize_tool_call(
        "infer-profile-dimensions",
        {},
    )
    assert normalized_name == "read_skill"
    assert normalized_args == {"skill_name": "infer-profile-dimensions"}


def test_next_read_only_streak_increments_for_read_tools():
    streak = agent._next_read_only_streak(3, ["read_profile", "read_doc"])
    assert streak == 4


def test_next_read_only_streak_resets_when_write_tool_present():
    streak = agent._next_read_only_streak(5, ["read_profile", "write_profile"])
    assert streak == 0
