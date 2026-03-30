/**
 * 内容分析工具
 *
 * 从讨论内容中提取：
 * - 核心观点
 * - 共识与分歧
 * - 发言者立场
 * - 建议文章结构
 */

import type { AnalysisResult, KeyPoint, Disagreement, Speaker } from "../types.js";
import { ANALYSIS_PROMPT } from "../prompts/analysis.js";

/**
 * 分析讨论内容
 *
 * @param discussionContent - 讨论内容（Markdown 格式）
 * @param language - 输出语言
 * @returns 结构化分析结果
 */
export async function analyzeDiscussion(
  discussionContent: string,
  language: string = "zh"
): Promise<AnalysisResult> {
  // 解析讨论内容，提取发言者和观点
  const speakers = extractSpeakers(discussionContent);
  const keyPoints = extractKeyPoints(discussionContent, speakers);
  const { consensus, disagreements } = analyzeConsensusAndDisagreements(keyPoints, speakers);
  const structureSuggestion = generateStructureSuggestion(keyPoints, consensus, disagreements, language);
  const topicSummary = generateTopicSummary(discussionContent, language);

  return {
    key_points: keyPoints,
    consensus,
    disagreements,
    speakers,
    structure_suggestion: structureSuggestion,
    topic_summary: topicSummary,
  };
}

/**
 * 提取发言者信息
 */
function extractSpeakers(content: string): Speaker[] {
  const speakers: Map<string, Speaker> = new Map();

  // 匹配常见的发言格式：
  // - "## Round 1 - Physicist" (TopicLab 格式)
  // - "**张三**：" 或 "张三："
  // - "@physicist" 或 "[physicist]"
  const patterns = [
    /##\s*Round\s*\d+\s*-\s*(\w+)/gi,
    /\*\*([^*]+)\*\*[:：]/g,
    /^([^:：\n]{2,20})[:：]/gm,
    /@(\w+)/g,
    /\[(\w+)\]/g,
  ];

  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(content)) !== null) {
      const name = match[1].trim();
      if (name && name.length <= 20 && !speakers.has(name.toLowerCase())) {
        speakers.set(name.toLowerCase(), {
          name,
          role: inferRole(name),
          main_stance: "",
          contribution_count: 0,
        });
      }
    }
  }

  // 统计贡献次数
  for (const [key, speaker] of speakers) {
    const regex = new RegExp(speaker.name, "gi");
    speaker.contribution_count = (content.match(regex) || []).length;
  }

  return Array.from(speakers.values()).filter((s) => s.contribution_count > 0);
}

/**
 * 推断角色
 */
function inferRole(name: string): string | undefined {
  const roleMap: Record<string, string> = {
    physicist: "物理学家",
    economist: "经济学家",
    philosopher: "哲学家",
    engineer: "工程师",
    scientist: "科学家",
    expert: "专家",
    moderator: "主持人",
  };
  return roleMap[name.toLowerCase()];
}

/**
 * 提取核心观点
 */
function extractKeyPoints(content: string, speakers: Speaker[]): KeyPoint[] {
  const keyPoints: KeyPoint[] = [];

  // 按段落分析
  const paragraphs = content.split(/\n\n+/);

  for (const para of paragraphs) {
    if (para.trim().length < 20) continue;

    // 判断观点重要性
    const importance = assessImportance(para);
    if (importance === "low" && keyPoints.length > 10) continue;

    // 识别发言者
    let speaker: string | undefined;
    for (const s of speakers) {
      if (para.toLowerCase().includes(s.name.toLowerCase())) {
        speaker = s.name;
        break;
      }
    }

    // 提取核心句子（第一句或带有关键词的句子）
    const sentences = para.split(/[。！？.!?]/);
    const coreSentence = sentences[0]?.trim() || para.slice(0, 100);

    if (coreSentence.length > 10) {
      keyPoints.push({
        content: coreSentence,
        speaker,
        importance,
      });
    }
  }

  // 按重要性排序，保留前 15 个
  return keyPoints
    .sort((a, b) => {
      const order = { high: 0, medium: 1, low: 2 };
      return order[a.importance] - order[b.importance];
    })
    .slice(0, 15);
}

/**
 * 评估观点重要性
 */
function assessImportance(text: string): "high" | "medium" | "low" {
  const highKeywords = [
    "核心",
    "关键",
    "本质",
    "根本",
    "重要",
    "必须",
    "fundamental",
    "crucial",
    "essential",
    "therefore",
    "因此",
    "所以",
    "总结",
    "结论",
  ];
  const mediumKeywords = [
    "认为",
    "观点",
    "主张",
    "建议",
    "应该",
    "think",
    "believe",
    "suggest",
    "should",
  ];

  const lowerText = text.toLowerCase();

  if (highKeywords.some((kw) => lowerText.includes(kw.toLowerCase()))) {
    return "high";
  }
  if (mediumKeywords.some((kw) => lowerText.includes(kw.toLowerCase()))) {
    return "medium";
  }
  return "low";
}

/**
 * 分析共识与分歧
 */
function analyzeConsensusAndDisagreements(
  keyPoints: KeyPoint[],
  speakers: Speaker[]
): { consensus: string[]; disagreements: Disagreement[] } {
  const consensus: string[] = [];
  const disagreements: Disagreement[] = [];

  // 简化实现：基于关键词匹配相似观点
  const pointsByTopic: Map<string, KeyPoint[]> = new Map();

  for (const point of keyPoints) {
    // 提取主题关键词
    const topics = extractTopics(point.content);
    for (const topic of topics) {
      if (!pointsByTopic.has(topic)) {
        pointsByTopic.set(topic, []);
      }
      pointsByTopic.get(topic)!.push(point);
    }
  }

  // 分析每个主题下的观点
  for (const [topic, points] of pointsByTopic) {
    if (points.length < 2) continue;

    const speakerSet = new Set(points.map((p) => p.speaker).filter(Boolean));
    if (speakerSet.size > 1) {
      // 多人讨论同一主题
      const positions = points
        .filter((p) => p.speaker)
        .map((p) => ({
          speaker: p.speaker!,
          position: p.content.slice(0, 100),
        }));

      // 简单判断：如果包含否定词，可能是分歧
      const hasNegation = points.some((p) =>
        /不同意|反对|但是|however|disagree|but/i.test(p.content)
      );

      if (hasNegation) {
        disagreements.push({ topic, positions });
      } else {
        consensus.push(`${topic}: ${points[0].content.slice(0, 50)}...`);
      }
    }
  }

  return { consensus: consensus.slice(0, 5), disagreements: disagreements.slice(0, 3) };
}

/**
 * 提取主题关键词
 */
function extractTopics(text: string): string[] {
  // 简单实现：提取名词短语
  const topics: string[] = [];

  // 中文主题
  const zhPattern = /[\u4e00-\u9fa5]{2,6}(?:的)?[\u4e00-\u9fa5]{2,6}/g;
  let match;
  while ((match = zhPattern.exec(text)) !== null) {
    topics.push(match[0]);
  }

  // 英文主题
  const enPattern = /\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b/g;
  while ((match = enPattern.exec(text)) !== null) {
    topics.push(match[0]);
  }

  return topics.slice(0, 5);
}

/**
 * 生成结构建议
 */
function generateStructureSuggestion(
  keyPoints: KeyPoint[],
  consensus: string[],
  disagreements: Disagreement[],
  language: string
): string {
  const isZh = language === "zh";

  let structure = "";

  if (isZh) {
    structure = "## 建议文章结构\n\n";
    structure += "1. **引言**：引出讨论主题和背景\n";

    if (keyPoints.length > 0) {
      const highPoints = keyPoints.filter((p) => p.importance === "high");
      structure += `2. **核心观点**（${highPoints.length} 个重点）\n`;
    }

    if (consensus.length > 0) {
      structure += `3. **共识**：${consensus.length} 个共识点\n`;
    }

    if (disagreements.length > 0) {
      structure += `4. **分歧与讨论**：${disagreements.length} 个分歧点\n`;
    }

    structure += "5. **总结与展望**\n";
  } else {
    structure = "## Suggested Article Structure\n\n";
    structure += "1. **Introduction**: Topic background\n";
    structure += `2. **Key Points** (${keyPoints.filter((p) => p.importance === "high").length} highlights)\n`;
    structure += `3. **Consensus** (${consensus.length} points)\n`;
    structure += `4. **Disagreements** (${disagreements.length} points)\n`;
    structure += "5. **Conclusion**\n";
  }

  return structure;
}

/**
 * 生成主题摘要
 */
function generateTopicSummary(content: string, language: string): string {
  // 简单实现：提取前 200 字作为摘要
  const firstParagraphs = content.split(/\n\n+/).slice(0, 3).join("\n\n");
  const summary = firstParagraphs.slice(0, 200);

  return language === "zh"
    ? `本次讨论涉及：${summary}...`
    : `This discussion covers: ${summary}...`;
}

// 导出 prompt 供外部使用
export { ANALYSIS_PROMPT };
