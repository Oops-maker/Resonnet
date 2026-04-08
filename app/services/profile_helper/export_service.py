"""Export profile.md to PDF or long-image PNG using Edge headless.

Flow:
  profile.md (raw markdown)
    └─ parse_profile() → structured dict
         ├─ match_famous_scientists() → top3 + scatter data
         ├─ recommend_field_scientists() → field recs
         └─ render_profile_html() → styled HTML string
              ├─ Edge headless --print-to-pdf  → bytes (PDF)
              └─ Edge headless --screenshot    → bytes (PNG)
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from app.services.profile_helper.profile_parser import parse_profile

# ── Edge 路径（支持 macOS 生产环境降级）──────────────────────────────────────

_EDGE_CANDIDATES = [
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
]


def _find_browser() -> str | None:
    for p in _EDGE_CANDIDATES:
        if Path(p).exists():
            return p
    return None


# ── CSS 样式（品牌规范 Noto Serif SC，黑白极简）──────────────────────────────

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: "Noto Serif SC", "SimSun", "Source Han Serif SC", serif;
    font-size: 14px;
    line-height: 1.8;
    color: #1a1a1a;
    background: #fff;
    max-width: 860px;
    margin: 0 auto;
    padding: 48px 56px;
}

/* ── 页眉 ── */
.profile-header {
    border-bottom: 3px solid #000;
    padding-bottom: 20px;
    margin-bottom: 32px;
}
.profile-header h1 {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: 0.02em;
    margin-bottom: 6px;
}
.profile-header .meta-row {
    font-size: 13px;
    color: #666;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}
.profile-header .meta-item {
    display: flex;
    gap: 4px;
}
.meta-label { color: #999; }

/* ── 章节 ── */
.section {
    margin-bottom: 28px;
    padding-bottom: 20px;
    border-bottom: 1px solid #e5e7eb;
}
.section:last-child { border-bottom: none; }

.section-title {
    font-size: 17px;
    font-weight: 700;
    color: #000;
    margin-bottom: 14px;
    padding-left: 10px;
    border-left: 4px solid #000;
}

/* ── 表格 ── */
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin-top: 8px;
}
th {
    background: #f3f4f6;
    font-weight: 600;
    padding: 8px 12px;
    text-align: left;
    border-bottom: 2px solid #e5e7eb;
}
td {
    padding: 7px 12px;
    border-bottom: 1px solid #f0f0f0;
    vertical-align: top;
}
tr:last-child td { border-bottom: none; }

/* ── 分数条 ── */
.score-bar-wrap { display: flex; align-items: center; gap: 8px; }
.score-bar {
    flex: 1;
    height: 8px;
    background: #f0f0f0;
    border-radius: 4px;
    overflow: hidden;
}
.score-bar-fill {
    height: 100%;
    background: #1a1a1a;
    border-radius: 4px;
}
.score-val { font-size: 12px; color: #666; min-width: 28px; text-align: right; }

/* ── KV 对 ── */
.kv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 20px; }
.kv-item { display: flex; gap: 6px; font-size: 13px; }
.kv-key { color: #666; min-width: 80px; }
.kv-value { color: #1a1a1a; flex: 1; }

/* ── 综合解读 ── */
.interp-block {
    background: #fafafa;
    border-left: 4px solid #d1d5db;
    padding: 12px 16px;
    margin-bottom: 12px;
    font-size: 13px;
    line-height: 1.7;
    border-radius: 0 6px 6px 0;
}
.interp-label {
    font-weight: 700;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #666;
    margin-bottom: 6px;
}

/* ── CSI 指数 ── */
.csi-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    background: #1a1a1a;
    color: #fff;
    margin-bottom: 10px;
}

/* ── 页脚 ── */
.footer {
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
    font-size: 11px;
    color: #9ca3af;
    text-align: center;
}

/* ── 科学家卡片 ── */
.sci-cards { display: flex; flex-direction: column; gap: 12px; margin-bottom: 4px; }
.sci-card {
    display: flex;
    gap: 12px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 12px 14px;
    background: #fafafa;
}
.sci-card-rank {
    font-size: 22px;
    font-weight: 700;
    color: #d1d5db;
    min-width: 32px;
    line-height: 1;
    padding-top: 2px;
}
.sci-card-body { flex: 1; }
.sci-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; }
.sci-card-name { font-size: 15px; font-weight: 700; margin: 0; }
.sci-card-name-en { font-size: 11px; color: #6b7280; margin: 2px 0 0; }
.sci-card-similarity {
    font-size: 16px;
    font-weight: 700;
    color: #000;
    background: #f3f4f6;
    padding: 2px 8px;
    border-radius: 12px;
}
.sci-card-meta { font-size: 11px; color: #6b7280; margin: 4px 0; }
.sci-card-signature { font-size: 12px; color: #374151; font-style: italic; margin: 4px 0; }
.sci-card-reason { font-size: 12px; color: #374151; margin: 4px 0 0; line-height: 1.6; }

/* ── 领域推荐 ── */
.field-recs { display: flex; flex-direction: column; gap: 10px; }
.field-rec-item {
    padding: 10px 12px;
    border-left: 3px solid #e5e7eb;
    background: #fafafa;
    border-radius: 0 6px 6px 0;
}

/* ── 打印适配 ── */
@media print {
    body { padding: 24px 32px; }
    .section { page-break-inside: avoid; }
    h1, h2, h3 { page-break-after: avoid; }
    .sci-card { page-break-inside: avoid; }
}
"""


# ── HTML 渲染 ──────────────────────────────────────────────────────────────────

def _score_bar(value: float | None, max_val: float = 7.0) -> str:
    if value is None:
        return "<span style='color:#999'>—</span>"
    pct = min(100, max(0, value / max_val * 100))
    return (
        f'<div class="score-bar-wrap">'
        f'<div class="score-bar"><div class="score-bar-fill" style="width:{pct:.0f}%"></div></div>'
        f'<span class="score-val">{value:.1f}</span>'
        f"</div>"
    )


def _kv(key: str, value: str | None) -> str:
    if not value:
        return ""
    return f'<div class="kv-item"><span class="kv-key">{key}</span><span class="kv-value">{value}</span></div>'


def _section(title: str, body: str) -> str:
    return f'<div class="section"><h2 class="section-title">{title}</h2>{body}</div>'


def render_profile_html(md: str, session: dict | None = None) -> str:
    """Convert profile.md → full standalone HTML string.

    Pass `session` to reuse cached scientist/field-recommendation data.
    """
    p = parse_profile(md)

    # ── Header ──────────────────────────────────────────────────────
    name = p.get("name") or "科研数字分身"
    idt = p.get("identity") or {}
    meta_items = [
        ("研究阶段", idt.get("research_stage")),
        ("一级领域", idt.get("primary_field")),
        ("二级领域", idt.get("secondary_field")),
        ("方法范式", idt.get("method")),
        ("所在机构", idt.get("institution")),
    ]
    meta_html = "".join(
        f'<div class="meta-item"><span class="meta-label">{k}</span><span>{v}</span></div>'
        for k, v in meta_items
        if v
    )
    header = f"""
    <div class="profile-header">
        <h1>{name}</h1>
        <div class="meta-row">{meta_html}</div>
    </div>"""

    sections: list[str] = []

    # ── 一、基础身份 ──────────────────────────────────────────────────
    net = idt.get("network") or ""
    cross = idt.get("cross_field") or ""
    identity_kv = "".join(filter(None, [
        _kv("交叉方向", cross),
        _kv("学术网络", net[:120] + ("…" if len(net) > 120 else "") if net else ""),
    ]))
    if identity_kv:
        sections.append(_section("基础身份", f'<div class="kv-grid">{identity_kv}</div>'))

    # ── 二、能力 ─────────────────────────────────────────────────────
    cap = p.get("capability") or {}
    tech_stack = cap.get("tech_stack") or []
    proc = cap.get("process") or {}
    proc_labels = {
        "problem_definition": "问题定义",
        "literature": "文献整合",
        "design": "研究方案设计",
        "execution": "实验/计算执行",
        "writing": "论文写作",
        "management": "项目管理",
    }
    cap_rows = ""
    if tech_stack:
        tech_str = "、".join(
            f"{t['tech']}（{t['level']}）" if t.get("level") else t["tech"]
            for t in tech_stack[:8]
        )
        cap_rows += f'<tr><td style="color:#666;width:30%">技术工具</td><td>{tech_str}</td></tr>'
    if cap.get("outputs"):
        cap_rows += f'<tr><td style="color:#666">代表性产出</td><td>{cap["outputs"][:200]}</td></tr>'
    proc_body = ""
    for key, label in proc_labels.items():
        item = proc.get(key)
        if item:
            score = item.get("score")
            desc = item.get("description") or ""
            bar = _score_bar(score, 5.0) if score else "—"
            proc_body += (
                f"<tr><td style='color:#666;width:30%'>{label}</td>"
                f"<td>{bar}</td>"
                f"<td style='color:#666;font-size:12px'>{desc[:60]}</td></tr>"
            )
    cap_html = ""
    if cap_rows:
        cap_html += f"<table>{cap_rows}</table>"
    if proc_body:
        cap_html += f"<table style='margin-top:12px'><tr><th>环节</th><th>评分</th><th>说明</th></tr>{proc_body}</table>"
    if cap_html:
        sections.append(_section("能力", cap_html))

    # ── 三、当前需求 ──────────────────────────────────────────────────
    needs = p.get("needs") or {}
    needs_rows = ""
    for item in (needs.get("time_occupation") or [])[:3]:
        if item.get("item"):
            needs_rows += f"<tr><td style='color:#666'>时间占用</td><td>{item['item']}</td><td>{item.get('feeling','')}</td></tr>"
    for item in (needs.get("pain_points") or [])[:3]:
        if item.get("issue"):
            needs_rows += f"<tr><td style='color:#666'>核心难点</td><td>{item['issue']}</td><td>{item.get('detail','')[:60]}</td></tr>"
    if needs.get("want_to_change"):
        needs_rows += f"<tr><td style='color:#666'>最想改变</td><td colspan='2'>{needs['want_to_change'][:100]}</td></tr>"
    if needs_rows:
        sections.append(_section("当前需求", f"<table><tr><th>类别</th><th>内容</th><th>补充</th></tr>{needs_rows}</table>"))

    # ── 四、认知风格（RCSS）──────────────────────────────────────────
    cog = p.get("cognitive_style") or {}
    if cog.get("csi") is not None or cog.get("type"):
        csi = cog.get("csi")
        ctype = cog.get("type") or ""
        integ = cog.get("integration")
        depth = cog.get("depth")
        cog_html = ""
        if ctype:
            cog_html += f'<div class="csi-badge">CSI {csi:+.0f}｜{ctype}</div>' if csi is not None else f'<div class="csi-badge">{ctype}</div>'
        rows = ""
        if integ is not None:
            rows += f"<tr><td>横向整合分 (I)</td><td>{_score_bar(integ, 28)}</td></tr>"
        if depth is not None:
            rows += f"<tr><td>垂直深度分 (D)</td><td>{_score_bar(depth, 28)}</td></tr>"
        if rows:
            cog_html += f"<table>{rows}</table>"
        if cog_html:
            sections.append(_section("认知风格（RCSS）", cog_html))

    # ── 五、学术动机（AMS）──────────────────────────────────────────
    mot = p.get("motivation") or {}
    dims = mot.get("dimensions") or {}
    dim_labels = {
        "know": "内在-求知",
        "accomplishment": "内在-成就",
        "stimulation": "内在-体验",
        "identified": "外在-认同",
        "introjected": "外在-内化",
        "external": "外在-外部",
        "amotivation": "无动机",
    }
    mot_rows = ""
    for key, label in dim_labels.items():
        val = dims.get(key)
        if val is not None:
            mot_rows += f"<tr><td>{label}</td><td>{_score_bar(val, 7)}</td></tr>"
    rai = mot.get("rai")
    if rai is not None:
        mot_rows += f"<tr><td style='font-weight:600'>自主动机指数（RAI）</td><td><strong>{rai:.1f}</strong></td></tr>"
    if mot_rows:
        sections.append(_section("学术动机（AMS-GSR 28）", f"<table>{mot_rows}</table>"))

    # ── 六、人格（Mini-IPIP）────────────────────────────────────────
    per = p.get("personality") or {}
    per_labels = {
        "extraversion": "外向性",
        "agreeableness": "宜人性",
        "conscientiousness": "尽责性",
        "neuroticism": "神经质",
        "openness": "开放性/智力",
    }
    per_rows = ""
    for key, label in per_labels.items():
        item = per.get(key)
        if isinstance(item, dict) and item.get("score") is not None:
            desc = item.get("level") or ""
            per_rows += f"<tr><td>{label}</td><td>{_score_bar(item['score'], 5)}</td><td style='color:#666;font-size:12px'>{desc}</td></tr>"
    if per_rows:
        sections.append(_section("人格（Mini-IPIP）", f"<table><tr><th>维度</th><th>得分</th><th>描述</th></tr>{per_rows}</table>"))

    # ── 七、综合解读 ─────────────────────────────────────────────────
    interp = p.get("interpretation") or {}
    interp_html = ""
    if interp.get("core_driver"):
        interp_html += f'<div class="interp-block"><div class="interp-label">核心驱动模式</div>{interp["core_driver"]}</div>'
    if interp.get("risks"):
        interp_html += f'<div class="interp-block"><div class="interp-label">潜在风险与发展建议</div>{interp["risks"]}</div>'
    if interp.get("path"):
        interp_html += f'<div class="interp-block"><div class="interp-label">适合的发展路径</div>{interp["path"]}</div>'
    if interp_html:
        sections.append(_section("综合解读", interp_html))

    # ── 八、科研灵魂伴侣（科学家匹配）──────────────────────────────
    sci_html = _render_scientist_section(p, session=session)
    if sci_html:
        sections.append(sci_html)

    # ── 页脚 ─────────────────────────────────────────────────────────
    from datetime import date
    footer = f'<div class="footer">他山科研数字分身 · 生成日期 {date.today().strftime("%Y-%m-%d")}</div>'

    body = header + "".join(sections) + footer

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} · 科研数字分身</title>
<style>{_CSS}</style>
</head>
<body>{body}</body>
</html>"""


# ── 科学家匹配模块渲染 ──────────────────────────────────────────────────────────

def _render_scatter_svg(scatter_data: list, user_point: dict, top3_names: list[str]) -> str:
    """Replicate ScientistScatter.tsx as inline SVG."""
    W, H, PAD = 500, 380, 50
    csi_min, csi_max = -24, 24
    rai_min, rai_max = -10, 62

    def to_x(csi: float) -> float:
        return PAD + (csi - csi_min) / (csi_max - csi_min) * (W - 2 * PAD)

    def to_y(rai: float) -> float:
        return H - PAD - (rai - rai_min) / (rai_max - rai_min) * (H - 2 * PAD)

    cx = to_x(0)
    cy = to_y(rai_min + (rai_max - rai_min) / 2)
    ux = to_x(user_point.get("csi", 0))
    uy = to_y(user_point.get("rai", 0))

    lines = [
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;max-width:520px;display:block;margin:0 auto">',
        # background
        f'<rect x="{PAD}" y="{PAD}" width="{W-2*PAD}" height="{H-2*PAD}" fill="#fafafa" stroke="#e5e7eb"/>',
        # grid lines
        f'<line x1="{cx:.1f}" y1="{PAD}" x2="{cx:.1f}" y2="{H-PAD}" stroke="#d1d5db" stroke-width="1" stroke-dasharray="4,3"/>',
        f'<line x1="{PAD}" y1="{cy:.1f}" x2="{W-PAD}" y2="{cy:.1f}" stroke="#d1d5db" stroke-width="1" stroke-dasharray="4,3"/>',
        # quadrant labels
        f'<text x="{PAD+6}" y="{PAD+14}" font-size="9" fill="#9ca3af">自主专精型</text>',
        f'<text x="{W-PAD-6}" y="{PAD+14}" font-size="9" fill="#9ca3af" text-anchor="end">自主整合型</text>',
        f'<text x="{PAD+6}" y="{H-PAD-6}" font-size="9" fill="#9ca3af">策略专精型</text>',
        f'<text x="{W-PAD-6}" y="{H-PAD-6}" font-size="9" fill="#9ca3af" text-anchor="end">策略整合型</text>',
        # axis labels
        f'<text x="{W/2:.0f}" y="{H-6}" font-size="10" fill="#6b7280" text-anchor="middle">认知风格 (CSI: 深度← →整合)</text>',
        f'<text x="12" y="{H/2:.0f}" font-size="10" fill="#6b7280" text-anchor="middle" transform="rotate(-90,12,{H/2:.0f})">动机自主性 (RAI)</text>',
    ]

    # top3 dashed lines
    for pt in scatter_data:
        if pt.get("name") in top3_names:
            px, py = to_x(pt["csi"]), to_y(pt["rai"])
            lines.append(f'<line x1="{ux:.1f}" y1="{uy:.1f}" x2="{px:.1f}" y2="{py:.1f}" stroke="#000" stroke-width="1" stroke-dasharray="3,3" opacity="0.3"/>')

    # scientist dots
    for pt in scatter_data:
        px, py = to_x(pt["csi"]), to_y(pt["rai"])
        is_top3 = pt.get("is_top3", False)
        name = pt.get("name", "")
        label = name[:4] + ".." if len(name) > 4 else name
        if is_top3:
            lines.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="#000"/>')
        else:
            lines.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="none" stroke="#000" stroke-width="1.5"/>')
        lines.append(f'<text x="{px:.1f}" y="{py-9:.1f}" font-size="8" fill="#374151" text-anchor="middle">{label}</text>')

    # user point
    lines.append(f'<circle cx="{ux:.1f}" cy="{uy:.1f}" r="8" fill="#000" stroke="#fff" stroke-width="2"/>')
    lines.append(f'<text x="{ux:.1f}" y="{uy-14:.1f}" font-size="12" fill="#000" text-anchor="middle" font-weight="700">我</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _render_scientist_section(parsed: dict, session: dict | None = None) -> str:
    """Fetch and render the scientist match section (top3 + scatter + field recs).

    Uses session cache when available to avoid redundant LLM calls during export.
    """
    try:
        from app.services.profile_helper.scientist_match import (
            get_cached_match,
            get_cached_field_recommendations,
        )
        # Use session cache so no extra LLM call if data already computed
        if session is not None:
            match_result = get_cached_match(session, parsed)
            field_recs = get_cached_field_recommendations(session, parsed)
        else:
            from app.services.profile_helper.scientist_match import (
                match_famous_scientists,
                recommend_field_scientists,
            )
            match_result = match_famous_scientists(parsed)
            field_recs = recommend_field_scientists(parsed)
    except Exception:
        return ""

    top3 = match_result.get("top3") or []
    scatter_data = match_result.get("scatter_data") or []
    user_point = match_result.get("user_point") or {"csi": 0, "rai": 0}
    top3_names = [s["name"] for s in top3]

    html = '<h2 class="section-title">你的科研灵魂伴侣</h2>'

    # ── Top3 卡片 ──────────────────────────────────────────────────
    if top3:
        html += '<div class="sci-cards">'
        for i, s in enumerate(top3, 1):
            similarity = s.get("similarity", 0)
            html += f"""
            <div class="sci-card">
              <div class="sci-card-rank">#{i}</div>
              <div class="sci-card-body">
                <div class="sci-card-header">
                  <div>
                    <h4 class="sci-card-name">{s.get('name','')}</h4>
                    <p class="sci-card-name-en">{s.get('name_en','')}</p>
                  </div>
                  <span class="sci-card-similarity">{similarity}%</span>
                </div>
                <p class="sci-card-meta">{s.get('field','')} · {s.get('era','')}</p>
                <p class="sci-card-signature">{s.get('signature','')}</p>
                <p class="sci-card-reason">{s.get('reason','')}</p>
              </div>
            </div>"""
        html += "</div>"

    # ── 散点图 ──────────────────────────────────────────────────────
    if scatter_data:
        html += '<h4 style="margin:20px 0 10px;font-size:14px;font-weight:600">你在科学家图谱中的位置</h4>'
        html += _render_scatter_svg(scatter_data, user_point, top3_names)

    # ── 领域推荐 ─────────────────────────────────────────────────────
    if field_recs:
        html += '<h4 style="margin:20px 0 10px;font-size:14px;font-weight:600">值得关注的同领域学者</h4>'
        html += '<div class="field-recs">'
        for r in field_recs:
            html += f"""
            <div class="field-rec-item">
              <strong>{r.get('name','')}</strong>
              {f'<span style="color:#666;margin-left:6px">{r.get("name_en","")}</span>' if r.get("name_en") else ""}
              <p style="color:#666;font-size:12px;margin:3px 0">{r.get('institution','')} · {r.get('field','')}</p>
              <p style="font-size:13px">{r.get('reason','')}</p>
            </div>"""
        html += "</div>"

    return f'<div class="section">{html}</div>'


# ── 导出函数 ───────────────────────────────────────────────────────────────────

def export_to_pdf(md: str, session: dict | None = None) -> bytes:
    """Render profile.md → PDF bytes using Edge headless.

    Pass `session` to reuse cached scientist data (avoids LLM calls during export).
    """
    browser = _find_browser()
    if not browser:
        raise RuntimeError("未找到 Chrome/Edge，无法生成 PDF")

    html_content = render_profile_html(md, session=session)
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = Path(tmpdir) / "profile.html"
        pdf_path = Path(tmpdir) / "profile.pdf"
        html_path.write_text(html_content, encoding="utf-8")

        subprocess.run(
            [
                browser,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--run-all-compositor-stages-before-draw",
                f"--print-to-pdf={pdf_path}",
                "--print-to-pdf-no-header",
                "--no-pdf-header-footer",
                f"file://{html_path}",
            ],
            capture_output=True,
            timeout=30,
        )
        if not pdf_path.exists():
            raise RuntimeError("PDF 生成失败")
        return pdf_path.read_bytes()


def export_to_image(md: str) -> bytes:
    """Render profile.md → full-page PNG using a scroll-and-stitch strategy.

    Strategy:
      1. Render in a 960×1080 viewport, screenshot each "page"
      2. Stitch all pages vertically into one long PNG with Pillow
    """
    browser = _find_browser()
    if not browser:
        raise RuntimeError("未找到 Chrome/Edge，无法生成长图")

    html_content = render_profile_html(md)
    from PIL import Image
    import io as _io

    VIEWPORT_W = 960
    VIEWPORT_H = 1080
    # Estimated page count for a profile (safe upper bound)
    MAX_PAGES = 8

    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = Path(tmpdir) / "profile.html"
        html_path.write_text(html_content, encoding="utf-8")

        tiles: list[Image.Image] = []
        last_hash: bytes | None = None

        for page_idx in range(MAX_PAGES):
            offset_px = page_idx * VIEWPORT_H
            img_path = Path(tmpdir) / f"tile_{page_idx}.png"

            # Inject scroll offset via HTML wrapper so Edge renders the right slice
            scroll_html = html_content.replace(
                "<body>",
                f'<body style="margin-top:-{offset_px}px">',
            )
            tile_html_path = Path(tmpdir) / f"page_{page_idx}.html"
            tile_html_path.write_text(scroll_html, encoding="utf-8")

            subprocess.run(
                [
                    browser,
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--hide-scrollbars",
                    f"--window-size={VIEWPORT_W},{VIEWPORT_H}",
                    f"--screenshot={img_path}",
                    f"file://{tile_html_path}",
                ],
                capture_output=True,
                timeout=20,
            )
            if not img_path.exists():
                break

            tile = Image.open(img_path).convert("RGB")
            tile_bytes = tile.tobytes()

            # Stop when we see a blank/repeated tile (end of content)
            if tile_bytes == last_hash:
                break
            last_hash = tile_bytes

            # Check if tile is mostly white (end of content)
            pixels = list(tile.getdata())
            white_count = sum(1 for px in pixels if px[0] > 250 and px[1] > 250 and px[2] > 250)
            if white_count / len(pixels) > 0.98 and page_idx > 0:
                break

            tiles.append(tile)

        if not tiles:
            raise RuntimeError("长图生成失败：未能截取任何内容")

        # ── Stitch tiles vertically ──────────────────────────────────
        total_height = sum(t.height for t in tiles)
        stitched = Image.new("RGB", (VIEWPORT_W, total_height), (255, 255, 255))
        y_offset = 0
        for tile in tiles:
            stitched.paste(tile, (0, y_offset))
            y_offset += tile.height

        # ── Crop bottom whitespace ────────────────────────────────────
        bbox = stitched.getbbox()
        if bbox:
            stitched = stitched.crop((0, 0, bbox[2], min(bbox[3] + 20, total_height)))

        buf = _io.BytesIO()
        stitched.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
