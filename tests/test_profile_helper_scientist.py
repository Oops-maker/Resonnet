"""
Profile Helper - scientist_match 单元测试
覆盖沙盘：SB-S01 ~ SB-S10
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.services.profile_helper.scientist_match import (
    match_famous_scientists,
    recommend_field_scientists,
    _generate_personalized_reasons,
)
from app.services.profile_helper.scientists_db import SCIENTISTS


# ──────────────────────────────────────────────
# 共用测试数据构建器
# ──────────────────────────────────────────────

def _make_parsed(
    csi: float | None = 7.0,
    rai: float | None = 13.0,
    primary="物理学",
    secondary="生物物理",
    cross="AI for Science",
    method="计算建模",
    extraversion=3.5,
    agreeableness=3.5,
    conscientiousness=4.5,
    neuroticism=3.0,
    openness=5.0,
) -> dict:
    return {
        "cognitive_style": {"csi": csi} if csi is not None else {},
        "motivation": {"rai": rai, "dimensions": {}} if rai is not None else {"dimensions": {}},
        "identity": {
            "primary_field": primary,
            "secondary_field": secondary,
            "cross_field": cross,
            "method": method,
        },
        "personality": {
            "extraversion": {"score": extraversion},
            "agreeableness": {"score": agreeableness},
            "conscientiousness": {"score": conscientiousness},
            "neuroticism": {"score": neuroticism},
            "openness": {"score": openness},
        },
    }


# ──────────────────────────────────────────────
# SB-S01  返回结构验证
# ──────────────────────────────────────────────

def test_sb_s01_match_returns_correct_structure():
    """SB-S01：返回结构含 top3 / scatter_data / user_point"""
    with patch("app.services.profile_helper.scientist_match._generate_personalized_reasons",
               side_effect=lambda top3, parsed: top3):
        result = match_famous_scientists(_make_parsed())

    assert "top3" in result
    assert "scatter_data" in result
    assert "user_point" in result
    assert len(result["top3"]) == 3
    for s in result["top3"]:
        assert all(k in s for k in ["name", "name_en", "field", "era", "similarity", "reason", "signature", "csi", "rai"])


# ──────────────────────────────────────────────
# SB-S02 ~ SB-S03  匹配方向验证
# ──────────────────────────────────────────────

def test_sb_s02_integration_type_user_matches_integration_scientists():
    """SB-S02：高整合型用户（CSI=+20）Top 3 主要来自正 CSI 科学家"""
    with patch("app.services.profile_helper.scientist_match._generate_personalized_reasons",
               side_effect=lambda top3, parsed: top3):
        result = match_famous_scientists(_make_parsed(csi=20.0, rai=50.0))

    positive_csi = [s for s in result["top3"] if s["csi"] > 0]
    assert len(positive_csi) >= 2, f"正 CSI 科学家少于 2 个: {[s['name'] for s in result['top3']]}"


def test_sb_s03_depth_type_user_matches_depth_scientists():
    """SB-S03：深度型用户（CSI=-20）Top 3 主要来自负 CSI 科学家"""
    with patch("app.services.profile_helper.scientist_match._generate_personalized_reasons",
               side_effect=lambda top3, parsed: top3):
        result = match_famous_scientists(_make_parsed(csi=-20.0, rai=55.0, openness=4.0))

    negative_csi = [s for s in result["top3"] if s["csi"] < 0]
    assert len(negative_csi) >= 2, f"负 CSI 科学家少于 2 个: {[s['name'] for s in result['top3']]}"


# ──────────────────────────────────────────────
# SB-S04  空值处理
# ──────────────────────────────────────────────

def test_sb_s04_none_csi_and_rai_uses_defaults():
    """SB-S04：csi / rai 均为 None 时使用默认值，不抛出异常"""
    parsed = {"cognitive_style": {}, "motivation": {}, "identity": {}, "personality": {}}
    with patch("app.services.profile_helper.scientist_match._generate_personalized_reasons",
               side_effect=lambda top3, parsed: top3):
        result = match_famous_scientists(parsed)

    assert result["user_point"]["csi"] == 0
    assert result["user_point"]["rai"] == 25
    assert len(result["top3"]) == 3


# ──────────────────────────────────────────────
# SB-S05 ~ SB-S06  scatter_data / similarity 范围
# ──────────────────────────────────────────────

def test_sb_s05_scatter_data_contains_all_30_scientists():
    """SB-S05：scatter_data 包含全部 30 位科学家"""
    with patch("app.services.profile_helper.scientist_match._generate_personalized_reasons",
               side_effect=lambda top3, parsed: top3):
        result = match_famous_scientists(_make_parsed())

    assert len(result["scatter_data"]) == len(SCIENTISTS)
    top3_names = {s["name"] for s in result["top3"]}
    top3_in_scatter = [s for s in result["scatter_data"] if s["is_top3"]]
    assert len(top3_in_scatter) == 3
    assert {s["name"] for s in top3_in_scatter} == top3_names


def test_sb_s06_similarity_in_valid_range():
    """SB-S06：similarity 值在 0-100 范围内（整数）"""
    with patch("app.services.profile_helper.scientist_match._generate_personalized_reasons",
               side_effect=lambda top3, parsed: top3):
        result = match_famous_scientists(_make_parsed())

    for s in result["top3"]:
        assert 0 <= s["similarity"] <= 100
        assert isinstance(s["similarity"], int)


# ──────────────────────────────────────────────
# SB-S07 ~ SB-S08  个性化理由 LLM
# ──────────────────────────────────────────────

@pytest.mark.integration
def test_sb_s07_personalized_reason_generated(monkeypatch):
    """SB-S07：LLM 调用成功时生成个性化理由（非模板原文）[需真实 API]"""
    result = match_famous_scientists(_make_parsed())
    for s in result["top3"]:
        original_template = next(
            sci["match_reason_template"] for sci in SCIENTISTS if sci["name"] == s["name"]
        )
        assert s["reason"] != original_template, (
            f"{s['name']} 的理由仍是模板原文，未个性化"
        )


def test_sb_s08_llm_failure_falls_back_to_template():
    """SB-S08：LLM 调用抛出异常时降级为模板理由"""
    top3 = [
        {
            "name": "弗朗西斯·克里克",
            "name_en": "Francis Crick",
            "field": "分子生物学",
            "era": "1916–2004",
            "csi": 14,
            "rai": 20,
            "signature": "从物理学转向生物学",
            "similarity": 88,
            "reason": "模板原文",
        }
    ]
    # create_client 是在函数内部 lazy import 的，patch 模块级路径
    with patch("app.services.profile_helper.llm_client.create_client",
               side_effect=Exception("LLM 不可用")):
        result = _generate_personalized_reasons(top3, _make_parsed())

    assert result[0]["reason"] == "模板原文"


# ──────────────────────────────────────────────
# SB-S09 ~ SB-S10  领域推荐
# ──────────────────────────────────────────────

@pytest.mark.integration
def test_sb_s09_recommend_field_scientists_returns_list():
    """SB-S09：recommend_field_scientists 返回 3-5 位科学家 [需真实 API]"""
    parsed = _make_parsed(primary="生物物理", secondary="统计物理")
    result = recommend_field_scientists(parsed)
    assert 3 <= len(result) <= 5
    for item in result:
        assert all(k in item for k in ["name", "name_en", "institution", "field", "reason"])


def test_sb_s10_recommend_empty_field_returns_empty_list():
    """SB-S10：研究领域为空时返回空列表，不调用 LLM"""
    parsed = {"identity": {"primary_field": "", "secondary_field": "", "cross_field": "", "method": ""}}
    with patch("app.services.profile_helper.llm_client.create_client") as mock_client:
        result = recommend_field_scientists(parsed)

    assert result == []
    mock_client.assert_not_called()
