/**
 * 文章生成工具
 *
 * 基于分析结果生成文章草稿
 */

import type { AnalysisResult, ArticleResult, Citation, TitleStyle } from "../types.js";
import { GENERATION_PROMPT, TITLE_PROMPTS } from "../prompts/generation.js";

interface GenerateOptions {
  titleStyle: string;
  outputFormat: string;
  maxLength: number;
  styleProfile: string;
}

/**
 * 生成文章
 *
 * @param analysis - 分析结果
 * @param options - 生成选项
 * @returns 文章结果
 */
export async function generateArticle(
  analysis: AnalysisResult,
  options: GenerateOptions
): Promise<ArticleResult> {
  const { titleStyle, outputFormat, maxLength, styleProfile } = options;

  // 1. 生成标题
  const title = generateTitle(analysis, titleStyle as TitleStyle);

  // 2. 生成正文
  const body = generateBody(analysis, styleProfile, maxLength);

  // 3. 提取引用
  const citations = extractCitations(analysis);

  // 4. 生成摘要
  const summary = generateSummary(analysis, body);

  // 5. 计算字数
  const wordCount = countWords(body);

  return {
    title,
    subtitle: generateSubtitle(analysis),
    body,
    summary,
    citations,
    word_count: wordCount,
  };
}

/**
 * 生成标题
 */
function generateTitle(analysis: AnalysisResult, style: TitleStyle): string {
  const topicSummary = analysis.topic_summary || "";
  const highPoints = analysis.key_points.filter((p) => p.importance === "high");

  switch (style) {
    case "question":
      // 问题式标题
      if (analysis.disagreements.length > 0) {
        return `${analysis.disagreements[0].topic}：谁的观点更有道理？`;
      }
      return `关于${topicSummary.slice(0, 10)}，我们应该如何看待？`;

    case "insight":
      // 洞见式标题
      if (highPoints.length > 0) {
        const insight = highPoints[0].content.slice(0, 30);
        return `深度解读：${insight}`;
      }
      return `${topicSummary.slice(0, 15)}的本质`;

    case "statement":
    default:
      // 陈述式标题
      if (analysis.consensus.length > 0) {
        return analysis.consensus[0].slice(0, 30);
      }
      if (highPoints.length > 0) {
        return highPoints[0].content.slice(0, 30);
      }
      return topicSummary.slice(0, 30);
  }
}

/**
 * 生成副标题
 */
function generateSubtitle(analysis: AnalysisResult): string | undefined {
  const speakers = analysis.speakers;
  if (speakers.length > 1) {
    const names = speakers.slice(0, 3).map((s) => s.name).join("、");
    return `${names}等专家的多维对话`;
  }
  return undefined;
}

/**
 * 生成正文
 */
function generateBody(
  analysis: AnalysisResult,
  styleProfile: string,
  maxLength: number
): string {
  const sections: string[] = [];

  // 引言
  sections.push(generateIntroduction(analysis, styleProfile));

  // 核心观点
  const keyPointsSection = generateKeyPointsSection(analysis, styleProfile);
  sections.push(keyPointsSection);

  // 共识部分
  if (analysis.consensus.length > 0) {
    sections.push(generateConsensusSection(analysis, styleProfile));
  }

  // 分歧部分
  if (analysis.disagreements.length > 0) {
    sections.push(generateDisagreementsSection(analysis, styleProfile));
  }

  // 结语
  sections.push(generateConclusion(analysis, styleProfile));

  // 合并并截断
  let body = sections.join("\n\n");

  if (countWords(body) > maxLength) {
    body = truncateToWordLimit(body, maxLength);
  }

  return body;
}

/**
 * 生成引言
 */
function generateIntroduction(analysis: AnalysisResult, style: string): string {
  const topic = analysis.topic_summary;
  const speakerCount = analysis.speakers.length;

  let intro = "";

  switch (style) {
    case "academic":
      intro = `本文基于${speakerCount}位专家的深入讨论，探讨${topic}。`;
      intro += `讨论涉及${analysis.key_points.length}个核心观点`;
      if (analysis.consensus.length > 0) {
        intro += `，其中${analysis.consensus.length}个方面达成共识`;
      }
      if (analysis.disagreements.length > 0) {
        intro += `，${analysis.disagreements.length}个方面存在分歧`;
      }
      intro += "。";
      break;

    case "casual":
      intro = `最近，${speakerCount}位大佬聊了聊${topic}，`;
      intro += `观点碰撞挺有意思，整理出来和大家分享。`;
      break;

    case "news":
    default:
      intro = `${topic}——这是近期${speakerCount}位专家热议的话题。`;
      intro += `本文梳理讨论要点，供读者参考。`;
      break;
  }

  return `## 引言\n\n${intro}`;
}

/**
 * 生成核心观点部分
 */
function generateKeyPointsSection(analysis: AnalysisResult, style: string): string {
  const highPoints = analysis.key_points.filter((p) => p.importance === "high");
  const mediumPoints = analysis.key_points.filter((p) => p.importance === "medium");

  let section = "## 核心观点\n\n";

  // 高优先级观点
  for (const point of highPoints.slice(0, 5)) {
    const speaker = point.speaker ? `**${point.speaker}**：` : "";
    section += `### ${speaker}${point.content.slice(0, 50)}\n\n`;
    section += `${point.content}\n\n`;
  }

  // 中等优先级观点（简要提及）
  if (mediumPoints.length > 0 && style === "academic") {
    section += "### 其他观点\n\n";
    for (const point of mediumPoints.slice(0, 3)) {
      section += `- ${point.content.slice(0, 80)}\n`;
    }
    section += "\n";
  }

  return section;
}

/**
 * 生成共识部分
 */
function generateConsensusSection(analysis: AnalysisResult, style: string): string {
  let section = "## 达成共识\n\n";

  if (style === "academic") {
    section += "讨论中，专家们在以下方面达成了共识：\n\n";
  } else {
    section += "大家都认同的点：\n\n";
  }

  for (const c of analysis.consensus) {
    section += `- ${c}\n`;
  }

  return section + "\n";
}

/**
 * 生成分歧部分
 */
function generateDisagreementsSection(analysis: AnalysisResult, style: string): string {
  let section = "## 观点分歧\n\n";

  if (style === "academic") {
    section += "在以下议题上，专家们持有不同看法：\n\n";
  } else {
    section += "但在这些问题上，大家看法不一：\n\n";
  }

  for (const d of analysis.disagreements) {
    section += `### ${d.topic}\n\n`;
    for (const pos of d.positions) {
      section += `- **${pos.speaker}**：${pos.position}\n`;
    }
    section += "\n";
  }

  return section;
}

/**
 * 生成结语
 */
function generateConclusion(analysis: AnalysisResult, style: string): string {
  let conclusion = "## 总结\n\n";

  const keyInsight = analysis.key_points.find((p) => p.importance === "high");

  switch (style) {
    case "academic":
      conclusion += "综合上述讨论，";
      if (keyInsight) {
        conclusion += `核心观点在于：${keyInsight.content.slice(0, 50)}。`;
      }
      conclusion += "这些讨论为相关领域提供了有价值的思考角度。";
      break;

    case "casual":
      conclusion += "聊到最后，";
      if (analysis.consensus.length > 0) {
        conclusion += `大家还是有不少共识的。`;
      } else {
        conclusion += `各有各的道理，值得继续思考。`;
      }
      break;

    case "news":
    default:
      if (keyInsight) {
        conclusion += `专家指出，${keyInsight.content.slice(0, 50)}。`;
      }
      conclusion += "后续发展值得持续关注。";
      break;
  }

  return conclusion;
}

/**
 * 提取引用
 */
function extractCitations(analysis: AnalysisResult): Citation[] {
  return analysis.key_points
    .filter((p) => p.speaker && p.importance === "high")
    .slice(0, 5)
    .map((p) => ({
      speaker: p.speaker!,
      quote: p.content,
      context: "讨论中",
    }));
}

/**
 * 生成摘要
 */
function generateSummary(analysis: AnalysisResult, body: string): string {
  const firstPara = body.split("\n\n").find((p) => p.length > 50);
  return firstPara?.slice(0, 150) || analysis.topic_summary;
}

/**
 * 计算字数（中英文）
 */
function countWords(text: string): number {
  // 中文字符
  const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length;
  // 英文单词
  const englishWords = (text.match(/\b[a-zA-Z]+\b/g) || []).length;
  return chineseChars + englishWords;
}

/**
 * 截断到字数限制
 */
function truncateToWordLimit(text: string, limit: number): string {
  let count = 0;
  let result = "";

  for (const char of text) {
    if (/[\u4e00-\u9fa5]/.test(char)) {
      count++;
    } else if (/\s/.test(char)) {
      // 简化：空格前可能是英文单词
      count++;
    }

    result += char;

    if (count >= limit) {
      // 找到最近的段落结束
      const lastPara = result.lastIndexOf("\n\n");
      if (lastPara > limit * 0.8) {
        result = result.slice(0, lastPara);
      }
      break;
    }
  }

  return result + "\n\n...(内容已截断)";
}

export { GENERATION_PROMPT, TITLE_PROMPTS };
