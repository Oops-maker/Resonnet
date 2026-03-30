/**
 * 内容分析 Prompt
 *
 * 用于 LLM 分析讨论内容
 */

export const ANALYSIS_PROMPT = `
# 讨论内容分析

你是一位专业的内容分析师。请分析以下讨论内容，提取关键信息。

## 任务

1. **识别发言者**：找出所有参与讨论的人及其角色
2. **提取核心观点**：每位发言者的主要论点
3. **分析共识**：各方达成一致的观点
4. **分析分歧**：各方存在争议的观点
5. **建议结构**：基于以上内容，建议文章结构

## 输出格式

请以 JSON 格式输出，包含以下字段：

\`\`\`json
{
  "speakers": [
    {
      "name": "发言者名称",
      "role": "角色（如：物理学家）",
      "main_stance": "主要立场"
    }
  ],
  "key_points": [
    {
      "content": "观点内容",
      "speaker": "发言者",
      "importance": "high|medium|low"
    }
  ],
  "consensus": ["共识点1", "共识点2"],
  "disagreements": [
    {
      "topic": "争议主题",
      "positions": [
        {"speaker": "发言者A", "position": "立场A"},
        {"speaker": "发言者B", "position": "立场B"}
      ]
    }
  ],
  "structure_suggestion": "建议的文章结构（Markdown 格式）",
  "topic_summary": "讨论主题简述（50字以内）"
}
\`\`\`

## 注意事项

- 保持客观，不添加个人解读
- 核心观点应精炼，每个不超过 100 字
- 重要性判断标准：
  - high: 核心论点、结论、关键主张
  - medium: 支撑论据、重要细节
  - low: 背景信息、补充说明
- 共识和分歧必须有明确的发言者支持

---

## 讨论内容

{discussion_content}
`;

export const ANALYSIS_PROMPT_EN = `
# Discussion Content Analysis

You are a professional content analyst. Please analyze the following discussion and extract key information.

## Tasks

1. **Identify Speakers**: Find all participants and their roles
2. **Extract Key Points**: Main arguments from each speaker
3. **Analyze Consensus**: Points of agreement
4. **Analyze Disagreements**: Points of contention
5. **Suggest Structure**: Recommend article structure

## Output Format

Please output in JSON format with the following fields:

\`\`\`json
{
  "speakers": [...],
  "key_points": [...],
  "consensus": [...],
  "disagreements": [...],
  "structure_suggestion": "...",
  "topic_summary": "..."
}
\`\`\`

---

## Discussion Content

{discussion_content}
`;
