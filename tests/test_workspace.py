"""Unit tests for workspace module (skill path resolution, copy logic)."""

from __future__ import annotations

from pathlib import Path

from app.agent.workspace import (
    _sanitize_turn_source_links,
    _parse_skill_id,
    _resolve_skill_path,
    _skill_dest_filename,
    validate_discussion_outputs,
    sync_claude_skill_discovery_files,
)


class TestParseSkillId:
    """Tests for _parse_skill_id."""

    def test_plain_slug_returns_empty_source(self):
        source, slug = _parse_skill_id("research_methodology")
        assert source == ""
        assert slug == "research_methodology"

    def test_source_prefixed_returns_both(self):
        source, slug = _parse_skill_id("awesome:critical_thinking")
        assert source == "awesome"
        assert slug == "critical_thinking"

    def test_strips_md_suffix(self):
        source, slug = _parse_skill_id("research_methodology.md")
        assert source == ""
        assert slug == "research_methodology"

    def test_source_prefixed_with_md_suffix(self):
        source, slug = _parse_skill_id("awesome:critical_thinking.md")
        assert source == "awesome"
        assert slug == "critical_thinking"


class TestSkillDestFilename:
    """Tests for _skill_dest_filename."""

    def test_plain_slug_returns_slug_md(self):
        assert _skill_dest_filename("research_methodology") == "research_methodology.md"

    def test_source_prefixed_replaces_colon_with_underscore(self):
        assert _skill_dest_filename("awesome:critical_thinking") == "awesome_critical_thinking.md"

    def test_strips_md_suffix_before_processing(self):
        assert _skill_dest_filename("research_methodology.md") == "research_methodology.md"


class TestResolveSkillPath:
    """Tests for _resolve_skill_path."""

    def test_default_source_with_category(self, tmp_path: Path):
        base = tmp_path / "assignable_skills"
        (base / "default" / "methodology").mkdir(parents=True)
        (base / "default" / "methodology" / "research_methodology.md").write_text("# test")

        skill_info = {"source": "default", "category": "methodology"}
        path = _resolve_skill_path(base, "research_methodology", skill_info)
        assert path is not None
        assert path == base / "default" / "methodology" / "research_methodology.md"
        assert path.exists()

    def test_third_party_source_with_category(self, tmp_path: Path):
        base = tmp_path / "assignable_skills"
        (base / "awesome" / "thinking").mkdir(parents=True)
        (base / "awesome" / "thinking" / "critical_thinking.md").write_text("# test")

        skill_info = {"source": "awesome", "category": "thinking"}
        path = _resolve_skill_path(base, "awesome:critical_thinking", skill_info)
        assert path is not None
        assert path == base / "awesome" / "thinking" / "critical_thinking.md"

    def test_missing_source_defaults_to_default(self, tmp_path: Path):
        base = tmp_path / "assignable_skills"
        (base / "default" / "methodology").mkdir(parents=True)
        (base / "default" / "methodology" / "evidence_based.md").write_text("# test")

        skill_info = {"category": "methodology"}  # no source
        path = _resolve_skill_path(base, "evidence_based", skill_info)
        assert path is not None
        assert path == base / "default" / "methodology" / "evidence_based.md"

    def test_empty_category_fallback_flat_under_source(self, tmp_path: Path):
        base = tmp_path / "assignable_skills"
        (base / "default").mkdir(parents=True)
        (base / "default" / "flat_skill.md").write_text("# test")

        skill_info = {"source": "default", "category": ""}
        path = _resolve_skill_path(base, "flat_skill", skill_info)
        assert path is not None
        assert path == base / "default" / "flat_skill.md"


class TestSyncClaudeSkillDiscoveryFiles:
    """Tests for sync_claude_skill_discovery_files."""

    def test_syncs_config_skills_and_moderator_skill(self, tmp_path: Path):
        ws = tmp_path / "topic_ws"
        skills_dir = ws / "config" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "critical_thinking.md").write_text("# critical", encoding="utf-8")
        (ws / "config" / "moderator_skill.md").write_text("# moderator", encoding="utf-8")

        synced = sync_claude_skill_discovery_files(ws)

        assert sorted(synced) == ["critical_thinking", "moderator_orchestrator"]
        assert (ws / ".claude" / "skills" / "critical_thinking" / "SKILL.md").read_text(encoding="utf-8") == "# critical"
        assert (ws / ".claude" / "skills" / "moderator_orchestrator" / "SKILL.md").read_text(
            encoding="utf-8"
        ) == "# moderator"

    def test_removes_stale_skill_directories(self, tmp_path: Path):
        ws = tmp_path / "topic_ws"
        (ws / "config" / "skills").mkdir(parents=True)
        (ws / "config" / "skills" / "critical_thinking.md").write_text("# critical", encoding="utf-8")
        stale = ws / ".claude" / "skills" / "legacy_skill"
        stale.mkdir(parents=True)
        (stale / "SKILL.md").write_text("# stale", encoding="utf-8")

        sync_claude_skill_discovery_files(ws)

        assert not stale.exists()


class TestSourceCitationGuardrails:
    """Tests for source citation filtering in discussion turns."""

    def test_sanitize_turn_source_links_filters_non_verifiable_links(self):
        raw = (
            "1. 方案 A（来源：[芯片白皮书](/api/2026-chip-6789)）\n"
            "2. 方案 B（来源：[ArXiv](https://arxiv.org/abs/2501.00001)）"
        )

        sanitized, filtered = _sanitize_turn_source_links(raw)

        assert filtered == 1
        assert "/api/2026-chip-6789" not in sanitized
        assert "https://arxiv.org/abs/2501.00001" in sanitized
        assert "来源链接已过滤：非可核验URL" in sanitized

    def test_sanitize_turn_source_links_ignores_non_citation_lines(self):
        raw = "[项目看板](/api/topics/demo/assets/generated_images/figure.png)"

        sanitized, filtered = _sanitize_turn_source_links(raw)

        assert sanitized == raw
        assert filtered == 0


class TestDiscussionOutputValidation:
    """Tests for strict discussion completion validation."""

    def test_validate_discussion_outputs_requires_all_turns_and_image_reference(self, tmp_path: Path):
        ws = tmp_path / "topic_ws"
        turns_dir = ws / "shared" / "turns"
        turns_dir.mkdir(parents=True)
        (turns_dir / "round1_physicist.md").write_text("第一轮", encoding="utf-8")
        (turns_dir / "round1_biologist.md").write_text("第一轮", encoding="utf-8")
        (turns_dir / "round2_physicist.md").write_text("第二轮", encoding="utf-8")
        (turns_dir / "round2_biologist.md").write_text(
            "第二轮\n\n![图](../generated_images/figure.png)",
            encoding="utf-8",
        )
        generated_dir = ws / "shared" / "generated_images"
        generated_dir.mkdir(parents=True)
        (generated_dir / "figure.png").write_bytes(b"\x89PNG\r\n\x1a\nmock")
        (ws / "shared" / "discussion_summary.md").write_text(
            "总结\n\n![图](../generated_images/figure.png)",
            encoding="utf-8",
        )

        validate_discussion_outputs(
            ws,
            expert_names=["physicist", "biologist"],
            num_rounds=2,
            require_image=True,
        )

    def test_validate_discussion_outputs_fails_when_round_is_missing(self, tmp_path: Path):
        ws = tmp_path / "topic_ws"
        turns_dir = ws / "shared" / "turns"
        turns_dir.mkdir(parents=True)
        (turns_dir / "round1_physicist.md").write_text("第一轮", encoding="utf-8")
        (ws / "shared" / "discussion_summary.md").write_text("总结", encoding="utf-8")

        try:
            validate_discussion_outputs(
                ws,
                expert_names=["physicist", "biologist"],
                num_rounds=2,
                require_image=False,
            )
        except ValueError as exc:
            assert "did not complete all configured rounds" in str(exc)
            assert "round1_biologist.md" in str(exc)
        else:
            raise AssertionError("Expected validate_discussion_outputs to fail when a round is missing")
