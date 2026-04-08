# Profile Helper 功能测试规格文档

**版本**：v1.0  
**日期**：2026-04-08  
**覆盖范围**：`/profile-helper/*` 全部端点 + Block 协议交互流 + 解析层 + 科学家匹配

---

## 通过门槛

| 层次 | 通过标准 |
|------|---------|
| L1 单元测试 | profile_parser / scientist_match 所有函数 100% 通过 |
| L2 API 集成 | 所有 HTTP 端点正常路径 100% 通过；错误路径 ≥ 90% 通过 |
| L3 Block 交互流 | 欢迎流/AI记忆流/B路径 主干流程通过（fast path 不调用 LLM，可 mock）|
| 人工验收 | 画像页完整度显示 7/7；科学家匹配理由为个性化文字（非模板）|

---

## 一、profile_parser 单元测试（25个沙盘）

### 1.1 基础身份解析

**SB-P01：标准完整画像解析**
```
输入：包含所有字段的完整 _template.md 填充版本
期望：identity 字典含 research_stage / primary_field / secondary_field / cross_field / method / institution / network，均非空
```

**SB-P02：空白模板解析（字段为 HTML 注释）**
```
输入：_template.md 原始空白版本（字段值为 <!-- ... -->）
期望：identity 字典所有字段为空字符串，不抛出异常
```

**SB-P03：「研究阶段」字段含附加备注**
```
输入：`- **研究阶段**：博士生（来源：用户确认）`
期望：research_stage = "博士生（来源：用户确认）"（不截断）
```

**SB-P04：机构字段含导师信息（历史兼容）**
```
输入：`- **所在机构**：中国科学院物理研究所（导师：叶方富）`
期望：institution = "中国科学院物理研究所（导师：叶方富）"（完整保留，parser 不做字段分割）
```

**SB-P05：标题行姓名提取**
```
输入：`# 科研人员画像 — 郑博元`
期望：name = "郑博元"
```

**SB-P06：姓名为占位符时返回空**
```
输入：`# 科研人员画像 — [姓名/标识]`
期望：name = ""
```

**SB-P07：`unnamed-2026-04-08` 格式姓名**
```
输入：`# 科研人员画像 — unnamed-2026-04-08`
期望：name = ""（占位符格式，同上）
```

---

### 1.2 能力解析

**SB-P08：科研流程能力表格解析**
```
输入：含完整 2.2 科研流程能力表格（6行，含评分 1-5）
期望：capability.process 含 problem_definition/literature/design/execution/writing/management，每项含 score（float）
```

**SB-P09：流程能力评分含附加文字**
```
输入：`| 问题定义 | 4 | 擅长把大问题拆成层级结构（来源：AI 记忆） |`
期望：score = 4.0，description 保留简要说明文字
```

**SB-P10：流程能力表格部分为空**
```
输入：6 行中 3 行评分为空（`|  |`）
期望：空行不加入 process 字典，只有有评分的行存在
```

**SB-P11：技术能力表格解析**
```
输入：含 3 行技术能力表格（类别/技术/熟练度）
期望：capability.tech_stack 为长度 3 的列表，每项含 category/tech/level
```

**SB-P12：代表性产出解析**
```
输入：`**代表性产出**：SAM2 细胞追踪流程代码`
期望：capability.outputs 为该字符串
```

---

### 1.3 RCSS 解析（关键，之前有 bug）

**SB-P13：RCSS 维度汇总解析（正常情况）**
```
输入：含「### 题目原始评分」表 + 「### 维度汇总」表的完整 RCSS 章节
期望：cognitive_style.integration / depth / csi 均为 float，type 非空
```

**SB-P14：RCSS 汇总表中含「AI 推断」标注**
```
输入：`| 认知风格指数 (CSI = I−D) | +7（AI 推断） |`
期望：csi = 7.0（正确提取，不受「AI 推断」文字影响）
```

**SB-P15：RCSS 负值 CSI 提取**
```
输入：`| 认知风格指数 (CSI = I−D) | -12 |`
期望：csi = -12.0
```

**SB-P16：无 RCSS 章节时 cognitive_style 为空字典**
```
输入：不含第四章的画像
期望：cognitive_style = {} 或 {"source": ""}，不抛出异常
```

**SB-P17：completion.cognitive_style 正确反映 csi 是否有值**
```
输入：csi = 7.0
期望：completion.cognitive_style = True
输入：csi = None 或 0.0（零值视为有值）
期望：completion.cognitive_style = True（零值是合法分数）
```

---

### 1.4 AMS / Mini-IPIP 解析

**SB-P18：AMS 7 维度解析**
```
输入：含完整 AMS 维度得分表（7行）
期望：motivation.dimensions 含 know/accomplishment/stimulation/identified/introjected/external/amotivation，均为 float
```

**SB-P19：AMS 综合指标 RAI 解析**
```
输入：`| 自主动机指数（RAI） | +13（AI 推断） |`
期望：motivation.rai = 13.0
```

**SB-P20：Mini-IPIP 5 维度解析**
```
输入：含完整人格维度表（5行，含水平描述）
期望：personality 含 extraversion/agreeableness/conscientiousness/neuroticism/openness，每项含 score 和 level
```

**SB-P21：personality 维度中「开放性/智力」匹配**
```
输入：`| 开放性/智力 (Intellect) | 5.0 | 很高 |`
期望：personality.openness.score = 5.0（斜杠前半部分匹配）
```

---

### 1.5 综合解读 / 完成度

**SB-P22：综合解读三个子章节解析**
```
输入：含「### 核心驱动模式」「### 潜在风险与发展建议」「### 适合的发展路径」的第七章
期望：interpretation.core_driver / risks / path 均非空
```

**SB-P23：completion 7/7 全满**
```
输入：包含所有维度数据的完整画像
期望：completion 所有 7 个 key 均为 True
```

**SB-P24：completion 空画像**
```
输入：空白模板（_template.md）
期望：completion 所有 7 个 key 均为 False
```

**SB-P25：capability 完成度判断**
```
输入：process 含至少 3 个有评分的维度
期望：completion.capability = True
输入：process 为空或全为空
期望：completion.capability = False
```

---

## 二、scientist_match 单元测试（10个沙盘）

**SB-S01：Top 3 匹配返回结构**
```
输入：parse_profile 返回的完整 parsed 字典（含 csi/rai/personality）
期望：返回 {top3: [...], scatter_data: [...], user_point: {csi, rai}}
top3 长度 = 3，每项含 name/name_en/field/era/similarity/reason/signature/csi/rai
```

**SB-S02：整合型用户匹配整合型科学家**
```
输入：user_csi = +20, user_rai = 50
期望：Top 3 中至少 2 位来自 scientists_db 的正 CSI 科学家（费曼/达芬奇/冯诺依曼等）
```

**SB-S03：深度型用户匹配深度型科学家**
```
输入：user_csi = -20, user_rai = 55
期望：Top 3 中至少 2 位来自负 CSI 科学家（怀尔斯/拉马努金等）
```

**SB-S04：CSI 和 RAI 均为 None 时的默认值处理**
```
输入：parsed 中 cognitive_style 和 motivation 均为空
期望：不抛出异常，使用默认值（csi=0, rai=25）正常运行
```

**SB-S05：scatter_data 包含全部 30 位科学家**
```
期望：scatter_data 长度 = 30，is_top3 字段正确标注 Top 3 成员
```

**SB-S06：similarity 值在 0-100 范围内**
```
期望：top3 每项 similarity ∈ [0, 100]（整数）
```

**SB-S07：个性化理由生成（LLM 调用，需真实 API Key）**
```
前提：.env 中 AI_GENERATION_API_KEY 有效
期望：top3 每项 reason 为 LLM 生成的个性化文字（含数值比较），不是 match_reason_template 原文
标记：@pytest.mark.integration
```

**SB-S08：LLM 调用失败时降级为模板理由**
```
输入：mock LLM 调用抛出 Exception
期望：top3 每项 reason 为 match_reason_template 原文（降级成功，不抛出异常）
```

**SB-S09：recommend_field_scientists 返回结构**
```
输入：parsed 含 primary_field="物理学", secondary_field="生物物理"
前提：LLM API 可用
期望：返回列表长度 3-5，每项含 name/name_en/institution/field/reason
标记：@pytest.mark.integration
```

**SB-S10：recommend_field_scientists 领域为空时返回空列表**
```
输入：parsed.identity.primary_field = ""
期望：返回 []，不调用 LLM
```

---

## 三、API 端点测试（15个沙盘）

### 3.1 Session 管理

**SB-A01：GET /profile-helper/session 创建新 session**
```
请求：GET /profile-helper/session（无 session_id）
期望：200，返回 {session_id: <uuid>}
```

**SB-A02：GET /profile-helper/session 复用已有 session**
```
请求：GET /profile-helper/session?session_id=<已有 UUID>
期望：200，返回相同 session_id
```

**SB-A03：GET /profile-helper/session 忽略无效 session_id**
```
请求：session_id = "undefined" / "null" / ""
期望：200，创建新 session，返回 session_id ≠ 输入值
```

**SB-A04：AUTH_MODE=jwt 时未认证请求返回 401**
```
前提：AUTH_MODE=jwt, AUTH_REQUIRED=true
请求：无 Authorization header
期望：401
```

---

### 3.2 画像读取

**SB-A05：GET /profile/{session_id} 返回画像内容**
```
前提：session 中有 profile 内容
期望：200，返回 {profile: str, forum_profile: str}
```

**SB-A06：GET /profile/{session_id}/structured 返回结构化数据**
```
前提：session 中有完整画像
期望：200，返回含 completion/identity/cognitive_style 等字段的 JSON
```

**SB-A07：GET /profile/{session_id}/scientists/famous 返回 Top 3**
```
前提：画像含 csi/rai 数值
期望：200，返回 {top3: [3项], scatter_data: [30项], user_point: {csi, rai}}
```

**SB-A08：GET /profile/{session_id}/scientists/famous 画像无量表数据时使用默认值**
```
前提：画像无 csi/rai（空白模板）
期望：200，正常返回 Top 3（使用 csi=0, rai=25 默认值）
```

---

### 3.3 量表提交

**SB-A09：POST /scales/submit 写入量表数据**
```
请求：scale_name="rcss", answers={A1:6,...}, scores={integration:23, depth:16}, result_summary={CSI:7}
期望：200，{ok: true}
验证：GET /scales/{session_id} 返回该量表数据
```

**SB-A10：GET /scales/{session_id} 返回所有已提交量表**
```
前提：已提交 rcss 量表
期望：200，{scales: {rcss: {...}}}
```

**SB-A11：POST /scales/submit session 不存在返回 404**
```
请求：session_id = "nonexistent-id"
期望：404
```

---

### 3.4 画像下载 / 发布

**SB-A12：GET /download/{session_id} 下载 Markdown 画像文件**
```
期望：200，Content-Type: text/markdown，内容为画像 Markdown 文本
```

**SB-A13：GET /download/{session_id}/forum 下载论坛分身**
```
期望：200，内容为论坛分身 Markdown 文本
```

**SB-A14：POST /publish-to-library 匿名用户返回 401**
```
前提：AUTH_MODE=none，session 未绑定 user_id
期望：401，detail = "请先登录后再发布数字分身"
```

**SB-A15：POST /session/reset/{session_id} 清空 session**
```
前提：session 含画像数据
期望：200，session 中 profile 重置为空白模板，messages 清空
```

---

## 四、Block 协议交互流测试（10个沙盘）

> 这些沙盘测试快速路径（不调用 LLM），通过检查返回的 Block 列表验证。

**SB-B01：首次消息触发欢迎 Block**
```
输入：空 session + message = "建立我的分身"
期望：返回 Block 列表，含 type=text（隐私说明）+ type=choice（A/B 两选项）
不调用 LLM（fast path）
```

**SB-B02：欢迎页选项只有 A 和 B（C 已关闭）**
```
期望：choice Block 的 options 长度 = 2，不含 id="ai_memory_enhanced"
```

**SB-B03：选 A 触发 AI 记忆提示词 Block**
```
输入：message = "A. 有，先从 AI 记忆中提取信息（标准版）"
期望：返回含 type=copyable 的 Block（AI 记忆提取提示词）
不调用 LLM（fast path）
```

**SB-B04：选 B 后的消息触发 LLM 路径（mock LLM）**
```
输入：message = "B. 没有，直接开始填写"
期望：调用 LLM（或 mock），返回至少一个 Block
```

**SB-B05：用户粘贴 AI 记忆后触发 LLM 路径**
```
前提：session messages 含「已生成 AI 记忆提取提示词」
输入：长文本（模拟 ChatGPT 回复）
期望：触发 LLM 路径（非 fast path），返回 Block 列表
```

**SB-B06：LLM 返回 ask_choice Block 结构正确**
```
期望：choice Block 含 id/question/options，options 每项含 id/label
（可选）含 text_prompt 的选项，前端可渲染内联输入框
```

**SB-B07：同一轮内多个 ask_choice 调用被截断为一个**
```
前提：mock LLM 返回 2 个 ask_choice 调用
期望：Block 列表中只有 1 个 choice Block，第 2 个被系统拦截
```

**SB-B08：write_profile 调用后 .md 文件落盘**
```
前提：session 中有 profile 内容，LLM 调用 write_profile
期望：workspace/profile_helper/profiles/ 下有对应 .md 文件
```

**SB-B09：messages 历史在 session 重启后从磁盘恢复**
```
前提：session 有对话历史，GET /session 重建 session
期望：session 中 messages 从 messages-{sid}.json 恢复
```

**SB-B10：GET /chat-history/{session_id} 过滤 tool 角色消息**
```
前提：session messages 含 user/assistant/tool 角色消息
期望：返回 {messages: [...]} 只含 user 和有实质内容的 assistant 消息，不含 tool
```

---

## 五、端到端用户流沙盘（人工验收，5个）

> 以下沙盘需要真实 LLM API 和浏览器操作，标记为手动验收。

**SB-E01：A 路径完整流程**
```
步骤：
1. 选 A → 复制提示词 → 粘贴模拟 AI 记忆回复
2. 回答姓名问题
3. 确认机构
4. 等待推断完成
期望：
- 画像文件 .md 落盘
- ProfilePage 显示完整度 ≥ 6/7
- RCSS / AMS / Mini-IPIP 均有 AI 推断值（非「尚未评估」）
- 科学家匹配理由为个性化文字（含数值比较）
```

**SB-E02：B 路径（直接问答）完整流程**
```
步骤：
1. 选 B → 逐步回答 Q1-Q5 + 能力评分 + 当前需求
2. 等待推断完成
期望：同 SB-E01
```

**SB-E03：量表路径（手动填写 RCSS）**
```
步骤：
1. 进入 /profile-helper/scales → 选 RCSS → 填写 8 题
2. 提交
期望：
- ProfilePage RCSS 显示量表实测数据（非 AI 推断）
- 完成度 RCSS 维度为 True
```

**SB-E04：修改画像流程**
```
步骤：
1. 画像完成后，在聊天框输入「修改」
2. 选择「基础身份」
3. 修改研究阶段
期望：
- 画像文件中研究阶段更新
- ProfilePage 显示新值
```

**SB-E05：跨 session 恢复**
```
步骤：
1. 完成画像后关闭浏览器
2. 重新打开，localStorage 中 session_id 仍在
期望：
- 画像内容从磁盘恢复
- ProfilePage 正常显示之前的画像
```

---

## 六、边界与异常测试（补充）

**SB-X01：画像 Markdown 含特殊字符（emoji、数学符号）**
```
输入：字段值含 🧪、∑、≥ 等字符
期望：parse_profile 正常解析，不抛出异常
```

**SB-X02：画像文件极大（>100KB）**
```
期望：parse_profile 在 2 秒内完成，内存无异常
```

**SB-X03：GET /profile/{session_id} session 不属于当前用户**
```
前提：session 绑定 user_id=1，请求 user_id=2
期望：404
```

**SB-X04：POST /chat/blocks 消息为空字符串**
```
请求：message = ""
期望：400，detail = "消息不能为空"
```

**SB-X05：session TTL 过期后 session 被清理**
```
前提：SESSION_TTL_SECONDS=1
期望：1 秒后 session 被 cleanup 移除，再次请求创建新 session
```

---

## 测试执行命令

```bash
# 单元测试（无需 LLM）
cd tests && .venv-mac/bin/pytest test_profile_helper_mvp.py -v

# 集成测试（需要真实 API Key）
.venv-mac/bin/pytest -m integration -v

# 全量测试
.venv-mac/bin/pytest -v --tb=short
```

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-04-08 | v1.0 初版，50个沙盘，覆盖 parser/scientist_match/API/Block/E2E |
