"""
Profile Helper - profile_parser 单元测试
覆盖沙盘：SB-P01 ~ SB-P25
"""
from __future__ import annotations

import textwrap

import pytest

from app.services.profile_helper.profile_parser import parse_profile


# ──────────────────────────────────────────────
# 共用测试画像构建器
# ──────────────────────────────────────────────

def _make_profile(
    name="测试用户",
    research_stage="博士生",
    primary="物理学",
    secondary="生物物理",
    cross="AI for Science",
    method="混合",
    institution="中国科学院物理研究所",
    network="导师：叶方富；团队：统计物理",
    tech_rows: list[str] | None = None,
    process_rows: list[str] | None = None,
    outputs="SAM2 代码",
    occupation_rows: list[str] | None = None,
    pain_rows: list[str] | None = None,
    want_to_change="建立稳定可运行闭环系统",
    rcss_a=(6, 6, 6, 5),
    rcss_b=(4, 4, 4, 4),
    ams: dict | None = None,
    personality: dict | None = None,
    core_driver="核心驱动测试文字",
    risks="潜在风险测试文字",
    path="发展路径测试文字",
) -> str:
    tech_rows = tech_rows or [
        "| 编程语言 | Python | ★★★★ |",
        "| 深度学习 | PyTorch | ★★★ |",
    ]
    process_rows = process_rows or [
        "| 问题定义 | 4 | 擅长拆分 |",
        "| 文献整合 | 4 | 较强 |",
        "| 方案设计 | 4 | 擅长 |",
        "| 实验执行 | 3 | 一般 |",
        "| 论文写作 | 3 | 一般 |",
        "| 项目管理 | 3 | 一般 |",
    ]
    occupation_rows = occupation_rows or [
        "| 多智能体系统 | 推进认知重组 | 高度投入 |",
    ]
    pain_rows = pain_rows or [
        "| 工具限制 | CLI/网络受限 | 技术支援 |",
    ]
    ams = ams or {
        "求知内在动机": 6,
        "成就内在动机": 5,
        "体验刺激内在动机": 4,
        "认同调节": 5,
        "内摄调节": 3,
        "外部调节": 3,
        "无动机": 1,
    }
    personality = personality or {
        "外向性 (Extraversion)": (3.5, "中等"),
        "宜人性 (Agreeableness)": (3.5, "中等"),
        "尽责性 (Conscientiousness)": (4.5, "较高"),
        "神经质 (Neuroticism)": (3.0, "中等"),
        "开放性/智力 (Intellect)": (5.0, "很高"),
    }

    I = sum(rcss_a)
    D = sum(rcss_b)
    CSI = I - D

    ams_rows = "\n".join(f"| {k} | 内在 | {v}（AI 推断） |" for k, v in list(ams.items())[:3]) + "\n"
    ams_rows += "\n".join(f"| {k} | 外在 | {v}（AI 推断） |" for k, v in list(ams.items())[3:])
    per_rows = "\n".join(f"| {k} | {s}（AI 推断） | {l} |" for k, (s, l) in personality.items())

    return textwrap.dedent(f"""\
# 科研人员画像 — {name}

## 元信息

- **创建时间**：2026-04-08
- **最后更新**：2026-04-08
- **采集阶段**：`inferred_done`
- **数据来源**：`混合`

---

## 一、基础身份

- **研究阶段**：{research_stage}
- **一级领域**：{primary}
- **二级领域**：{secondary}
- **交叉方向**：{cross}
- **方法范式**：{method}
- **所在机构**：{institution}
- **学术网络**：{network}

---

## 二、能力

### 2.1 技术能力

| 类别 | 具体技术 | 熟练程度（★☆） |
|:---|:---|:---:|
{chr(10).join(tech_rows)}

**代表性产出**：
{outputs}

### 2.2 科研流程能力

> 评分：1（非常薄弱）→ 5（非常强）

| 环节 | 评分 | 简要说明 |
|:---|:---:|:---|
{chr(10).join(process_rows)}

---

## 三、当前需求

> 数据来源：`用户自述`

### 3.1 主要时间占用

| 事项 | 描述 | 感受 |
|:---|:---|:---|
{chr(10).join(occupation_rows)}

### 3.2 核心难点与卡点

| 难点 | 具体表现 | 期望获得的帮助类型 |
|:---|:---|:---|
{chr(10).join(pain_rows)}

### 3.3 近期最想改变的一件事

{want_to_change}

---

## 四、认知风格（RCSS）

> 数据来源：`AI 推断`

### 题目原始评分

| 编号 | 维度 | 得分（1–7） |
|:---:|:---:|:---:|
| A1 | 横向整合 | {rcss_a[0]}（AI 推断） |
| A2 | 横向整合 | {rcss_a[1]}（AI 推断） |
| A3 | 横向整合 | {rcss_a[2]}（AI 推断） |
| A4 | 横向整合 | {rcss_a[3]}（AI 推断） |
| B1 | 垂直深度 | {rcss_b[0]}（AI 推断） |
| B2 | 垂直深度 | {rcss_b[1]}（AI 推断） |
| B3 | 垂直深度 | {rcss_b[2]}（AI 推断） |
| B4 | 垂直深度 | {rcss_b[3]}（AI 推断） |

### 维度汇总

| 指标 | 得分 |
|:---|:---:|
| 横向整合分 (I = A1+A2+A3+A4) | {I}（AI 推断） |
| 垂直深度分 (D = B1+B2+B3+B4) | {D}（AI 推断） |
| 认知风格指数 (CSI = I−D) | {CSI}（AI 推断） |
| **认知风格类型** | 倾向整合型（AI 推断，置信度：高） |

---

## 五、学术动机（AMS-GSR 28）

> 数据来源：`AI 推断`
> 计分方式：1–7 分，各维度 4 题平均分

### 各维度得分

| 维度 | 分类 | 平均分（1–7） |
|:---|:---:|:---:|
{ams_rows}

### 综合指标

| 指标 | 数值 |
|:---|:---:|
| 内在动机总分 | 15（AI 推断） |
| 外在动机总分 | 11（AI 推断） |
| 自主动机指数（RAI） | +13（AI 推断） |

---

## 六、人格（Mini-IPIP）

> 数据来源：`AI 推断`
> 计分方式：1–5 分，各维度 4 题平均分

| 维度 | 平均分（1–5） | 水平描述 |
|:---|:---:|:---|
{per_rows}

---

## 七、综合解读

> 生成依据：全部维度

### 核心驱动模式

{core_driver}

### 潜在风险与发展建议

{risks}

### 适合的发展路径

{path}

---

## 八、审核记录

| 日期 | 审核字段 | 用户反馈 | 处理方式 |
|:---|:---|:---|:---|
| 2026-04-08 | 全部维度 | 待审核 | 待用户确认 |
""")


# ──────────────────────────────────────────────
# SB-P01 ~ SB-P07  基础身份 / 姓名
# ──────────────────────────────────────────────

def test_sb_p01_full_profile_identity():
    """SB-P01：标准完整画像 identity 字段全部非空"""
    result = parse_profile(_make_profile())
    identity = result["identity"]
    assert identity["research_stage"] == "博士生"
    assert identity["primary_field"] == "物理学"
    assert identity["secondary_field"] == "生物物理"
    assert identity["cross_field"] == "AI for Science"
    assert identity["method"] == "混合"
    assert identity["institution"] == "中国科学院物理研究所"
    assert "叶方富" in identity["network"]


def test_sb_p02_blank_template_no_exception():
    """SB-P02：空白模板（HTML 注释）不抛出异常，identity 字段为空"""
    blank = textwrap.dedent("""\
# 科研人员画像 — [姓名/标识]

## 元信息
- **创建时间**：YYYY-MM-DD
- **最后更新**：YYYY-MM-DD
- **采集阶段**：`未开始`
- **数据来源**：`量表实测`

---

## 一、基础身份

- **研究阶段**：<!-- 博士生 / 博后 -->
- **一级领域**：
- **二级领域**：
- **交叉方向**：
- **方法范式**：<!-- 实验 -->
- **所在机构**：
- **学术网络**：<!-- 导师 -->
""")
    result = parse_profile(blank)
    assert result["identity"]["research_stage"] == ""
    assert result["identity"]["primary_field"] == ""


def test_sb_p03_research_stage_with_annotation():
    """SB-P03：研究阶段含来源备注"""
    md = _make_profile(research_stage="博士生（来源：用户确认）")
    result = parse_profile(md)
    assert result["identity"]["research_stage"] == "博士生（来源：用户确认）"


def test_sb_p04_institution_with_advisor_inline():
    """SB-P04：机构字段含导师信息（历史兼容格式）"""
    md = _make_profile(institution="中国科学院物理研究所（导师：叶方富）")
    result = parse_profile(md)
    assert result["identity"]["institution"] == "中国科学院物理研究所（导师：叶方富）"


def test_sb_p05_name_extraction():
    """SB-P05：标题行姓名正常提取"""
    md = _make_profile(name="郑博元")
    result = parse_profile(md)
    assert result["name"] == "郑博元"


def test_sb_p06_placeholder_name_returns_empty():
    """SB-P06：占位符姓名返回空字符串"""
    md = _make_profile(name="[姓名/标识]")
    result = parse_profile(md)
    assert result["name"] == ""


def test_sb_p07_unnamed_date_format_preserved():
    """SB-P07：unnamed-YYYY-MM-DD 是有效姓名，parser 保留原值（不视为占位符）"""
    md = _make_profile(name="unnamed-2026-04-08")
    result = parse_profile(md)
    # parser 只过滤 "[姓名/标识]" 和 "姓名/标识"，不过滤 unnamed-日期格式
    assert result["name"] == "unnamed-2026-04-08"


# ──────────────────────────────────────────────
# SB-P08 ~ SB-P12  能力解析
# ──────────────────────────────────────────────

def test_sb_p08_process_capability_full():
    """SB-P08：科研流程能力 6 维度全部解析"""
    result = parse_profile(_make_profile())
    proc = result["capability"]["process"]
    assert set(proc.keys()) == {
        "problem_definition", "literature", "design",
        "execution", "writing", "management",
    }
    assert all(isinstance(v["score"], float) for v in proc.values())


def test_sb_p09_process_score_with_annotation():
    """SB-P09：评分含来源标注时正确提取数字"""
    rows = [
        "| 问题定义 | 4 | 擅长拆分（来源：AI 记忆） |",
        "| 文献整合 | 3 | 一般 |",
        "| 方案设计 | 5 | 很强 |",
        "| 实验执行 | 2 | 较弱 |",
        "| 论文写作 | 4 | 较强 |",
        "| 项目管理 | 3 | 一般 |",
    ]
    result = parse_profile(_make_profile(process_rows=rows))
    assert result["capability"]["process"]["problem_definition"]["score"] == 4.0
    assert "来源" in result["capability"]["process"]["problem_definition"]["description"]


def test_sb_p10_process_partial_empty_rows():
    """SB-P10：流程能力表部分行无评分，只保留有值的行"""
    rows = [
        "| 问题定义 | 4 | 好 |",
        "| 文献整合 |  |  |",   # 空评分
        "| 方案设计 | 3 | 一般 |",
        "| 实验执行 |  |  |",
        "| 论文写作 | 2 | 较弱 |",
        "| 项目管理 |  |  |",
    ]
    result = parse_profile(_make_profile(process_rows=rows))
    proc = result["capability"]["process"]
    assert "problem_definition" in proc
    assert "literature" not in proc
    assert proc["problem_definition"]["score"] == 4.0


def test_sb_p11_tech_stack_parsed():
    """SB-P11：技术能力表格解析为列表"""
    result = parse_profile(_make_profile())
    ts = result["capability"]["tech_stack"]
    assert len(ts) == 2
    assert ts[0]["tech"] == "Python"
    assert ts[1]["tech"] == "PyTorch"


def test_sb_p12_outputs_parsed():
    """SB-P12：代表性产出解析"""
    result = parse_profile(_make_profile(outputs="SAM2 细胞追踪流程代码"))
    assert "SAM2" in result["capability"]["outputs"]


# ──────────────────────────────────────────────
# SB-P13 ~ SB-P17  RCSS 解析
# ──────────────────────────────────────────────

def test_sb_p13_rcss_summary_parsed():
    """SB-P13：RCSS 维度汇总正确解析（含题目原始评分 + 汇总两张表）"""
    result = parse_profile(_make_profile(rcss_a=(6, 6, 6, 5), rcss_b=(4, 4, 4, 4)))
    cs = result["cognitive_style"]
    assert cs["integration"] == 23.0
    assert cs["depth"] == 16.0
    assert cs["csi"] == 7.0
    assert "整合" in cs["type"]


def test_sb_p14_rcss_csi_with_ai_annotation():
    """SB-P14：汇总表中含「AI 推断」标注，数字仍能正确提取"""
    # _make_profile 生成的格式已含「AI 推断」
    result = parse_profile(_make_profile(rcss_a=(7, 7, 7, 7), rcss_b=(1, 1, 1, 1)))
    assert result["cognitive_style"]["csi"] == 24.0


def test_sb_p15_rcss_negative_csi():
    """SB-P15：负值 CSI 正确提取"""
    result = parse_profile(_make_profile(rcss_a=(2, 2, 2, 2), rcss_b=(6, 6, 6, 6)))
    assert result["cognitive_style"]["csi"] == -16.0


def test_sb_p16_no_rcss_section_returns_empty():
    """SB-P16：无 RCSS 章节时 cognitive_style 为空，不抛出异常"""
    minimal = "# 科研人员画像 — 测试\n\n## 一、基础身份\n\n- **研究阶段**：博士生\n"
    result = parse_profile(minimal)
    assert result["cognitive_style"] == {}


def test_sb_p17_completion_cognitive_style_true_when_csi_present():
    """SB-P17：有 csi 值时 completion.cognitive_style = True"""
    result = parse_profile(_make_profile())
    assert result["completion"]["cognitive_style"] is True


def test_sb_p17b_completion_cognitive_style_false_when_empty():
    """SB-P17b：无 csi 值时 completion.cognitive_style = False"""
    minimal = "# 科研人员画像 — 测试\n\n"
    result = parse_profile(minimal)
    assert result["completion"]["cognitive_style"] is False


# ──────────────────────────────────────────────
# SB-P18 ~ SB-P21  AMS / Mini-IPIP
# ──────────────────────────────────────────────

def test_sb_p18_ams_7_dimensions_parsed():
    """SB-P18：AMS 7 维度全部解析"""
    result = parse_profile(_make_profile())
    dims = result["motivation"]["dimensions"]
    assert set(dims.keys()) == {
        "know", "accomplishment", "stimulation",
        "identified", "introjected", "external", "amotivation",
    }
    assert dims["know"] == 6.0
    assert dims["amotivation"] == 1.0


def test_sb_p19_ams_rai_parsed():
    """SB-P19：RAI 综合指数正确提取"""
    result = parse_profile(_make_profile())
    assert result["motivation"]["rai"] == 13.0


def test_sb_p20_mini_ipip_5_dimensions():
    """SB-P20：Mini-IPIP 5 维度全部解析"""
    result = parse_profile(_make_profile())
    p = result["personality"]
    for key in ["extraversion", "agreeableness", "conscientiousness", "neuroticism", "openness"]:
        assert key in p
        assert isinstance(p[key]["score"], float)
        assert p[key]["level"]


def test_sb_p21_openness_slash_match():
    """SB-P21：「开放性/智力」能被正确匹配为 openness"""
    result = parse_profile(_make_profile())
    assert result["personality"]["openness"]["score"] == 5.0


# ──────────────────────────────────────────────
# SB-P22 ~ SB-P25  综合解读 / 完成度
# ──────────────────────────────────────────────

def test_sb_p22_interpretation_three_sections():
    """SB-P22：综合解读三个子章节均非空"""
    result = parse_profile(_make_profile())
    interp = result["interpretation"]
    assert "核心驱动测试文字" in interp["core_driver"]
    assert "潜在风险测试文字" in interp["risks"]
    assert "发展路径测试文字" in interp["path"]


def test_sb_p23_completion_all_7_true():
    """SB-P23：完整画像 completion 7/7 全为 True"""
    result = parse_profile(_make_profile())
    comp = result["completion"]
    assert all(comp.values()), f"未全部通过：{comp}"


def test_sb_p24_completion_blank_template_all_false():
    """SB-P24：空白模板 completion 全部为 False"""
    blank = textwrap.dedent("""\
# 科研人员画像 — [姓名/标识]

## 元信息
- **创建时间**：YYYY-MM-DD
- **最后更新**：YYYY-MM-DD
- **采集阶段**：`未开始`
- **数据来源**：`量表实测`
""")
    result = parse_profile(blank)
    comp = result["completion"]
    assert not any(comp.values()), f"存在 True 项：{comp}"


def test_sb_p25_completion_capability_requires_3_process_scores():
    """SB-P25：至少 3 个流程维度有评分时 completion.capability = True"""
    rows_3 = [
        "| 问题定义 | 4 | 好 |",
        "| 文献整合 | 3 | 一般 |",
        "| 方案设计 | 5 | 很强 |",
        "| 实验执行 |  |  |",
        "| 论文写作 |  |  |",
        "| 项目管理 |  |  |",
    ]
    result = parse_profile(_make_profile(process_rows=rows_3))
    assert result["completion"]["capability"] is True

    rows_0 = [
        "| 问题定义 |  |  |",
        "| 文献整合 |  |  |",
        "| 方案设计 |  |  |",
        "| 实验执行 |  |  |",
        "| 论文写作 |  |  |",
        "| 项目管理 |  |  |",
    ]
    result2 = parse_profile(_make_profile(process_rows=rows_0))
    assert result2["completion"]["capability"] is False
