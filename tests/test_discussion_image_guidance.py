from __future__ import annotations

from pathlib import Path

from app.agent.experts import build_experts_from_workspace
from app.agent.moderator_modes import prepare_moderator_skill
from app.agent.workspace import ensure_topic_workspace


def test_prepare_moderator_skill_includes_image_guidance_when_skill_present(
    isolated_workspace: Path,
):
    ws_path = ensure_topic_workspace(isolated_workspace, "discussion-image-guidance")
    skills_dir = ws_path / "config" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "image_generation.md").write_text("# image skill", encoding="utf-8")

    skill_file = prepare_moderator_skill(
        ws_path=ws_path,
        topic="测试讨论图片规范",
        expert_names=["physicist"],
        num_rounds=2,
    )

    content = skill_file.read_text(encoding="utf-8")
    assert "学术讨论风格" in content
    assert "shared/generated_images/" in content
    assert "![图示说明](/api/topics/discussion-image-guidance/assets/generated_images/" in content
    assert "Do not return raw temporary DashScope URLs" in content
    assert "config/skills/image_generation.md" in content
    assert "Required Visual Deliverable" in content


def test_prepare_moderator_skill_requires_image_delivery_without_first_round_force(
    isolated_workspace: Path,
):
    ws_path = ensure_topic_workspace(isolated_workspace, "discussion-image-required")
    skills_dir = ws_path / "config" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "image_generation.md").write_text("# image skill", encoding="utf-8")

    skill_file = prepare_moderator_skill(
        ws_path=ws_path,
        topic="生成一张各领域的芯片架构图",
        expert_names=["physicist"],
        num_rounds=2,
    )

    content = skill_file.read_text(encoding="utf-8")
    assert "Every discussion must produce at least one image artifact" in content
    assert "treat at least one image as a required deliverable" in content
    assert "assign the image generation skill in round 1" not in content
    assert "produce a first visual draft in round 1" not in content
    assert "Do not end the discussion with text-only output" in content


def test_prepare_moderator_skill_includes_source_citation_guardrails(
    isolated_workspace: Path,
):
    ws_path = ensure_topic_workspace(isolated_workspace, "discussion-source-guardrails")
    skill_file = prepare_moderator_skill(
        ws_path=ws_path,
        topic="芯片架构设计方案",
        expert_names=["physicist"],
        num_rounds=2,
    )

    content = skill_file.read_text(encoding="utf-8")
    assert "Source Citation Guardrails" in content
    assert "Only cite verifiable external sources using full `https://`" in content
    assert "Never use placeholder or internal pseudo-source paths such as `/api/2026-" in content


def test_build_experts_from_workspace_includes_discussion_image_guidance(
    isolated_workspace: Path,
):
    ws_path = ensure_topic_workspace(isolated_workspace, "discussion-image-expert-prompt")
    role_file = ws_path / "agents" / "physicist" / "role.md"
    role_file.parent.mkdir(parents=True, exist_ok=True)
    role_file.write_text("# Physicist\n\nYou are a physicist.", encoding="utf-8")

    experts = build_experts_from_workspace(
        workspace_dir=ws_path,
        expert_names=["physicist"],
        ws_abs=str(ws_path.resolve()),
    )

    prompt_text = experts["physicist"].prompt
    assert "学术讨论风格" in prompt_text
    assert "shared/generated_images/" in prompt_text
    assert "![图示说明](/api/topics/discussion-image-expert-prompt/assets/generated_images/" in prompt_text
    assert "Do not return raw temporary DashScope URLs" in prompt_text


def test_topic_generated_image_asset_is_served(client, isolated_workspace: Path):
    topic_id = "discussion-image-asset"
    ws_path = ensure_topic_workspace(isolated_workspace, topic_id)
    image_dir = ws_path / "shared" / "generated_images"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / "figure.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nmock")

    response = client.get(f"/topics/{topic_id}/assets/generated_images/figure.png")

    assert response.status_code == 200
    assert response.content.startswith(b"\x89PNG")
