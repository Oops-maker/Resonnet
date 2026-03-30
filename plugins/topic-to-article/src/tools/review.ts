/**
 * 文章审稿工具
 *
 * 5 轮审稿（参考 tashan-writing-system）：
 * 1. AI 腔检测
 * 2. 标题质量
 * 3. 绝对表达
 * 4. 结构合理性
 * 5. 结语完整性
 */

import type { ReviewResult, ReviewRound, ReviewIssue } from "../types.js";
import { REVIEW_PROMPTS } from "../prompts/review.js";

/**
 * 审稿主函数
 *
 * @param article - 文章内容
 * @param strictMode - 严格模式
 * @returns 审稿结果
 */
export async function reviewArticle(
  article: string,
  strictMode: boolean = true
): Promise<ReviewResult> {
  const rounds: ReviewRound[] = [];
  let totalScore = 100;
  const allSuggestions: string[] = [];

  // Round 1: AI 腔检测
  const round1 = reviewAITone(article, strictMode);
  rounds.push(round1);
  totalScore -= round1.issues.length * (strictMode ? 5 : 3);

  // Round 2: 标题质量
  const round2 = reviewTitleQuality(article, strictMode);
  rounds.push(round2);
  totalScore -= round2.issues.length * (strictMode ? 8 : 5);

  // Round 3: 绝对表达
  const round3 = reviewAbsoluteExpressions(article, strictMode);
  rounds.push(round3);
  totalScore -= round3.issues.length * (strictMode ? 3 : 2);

  // Round 4: 结构合理性
  const round4 = reviewStructure(article, strictMode);
  rounds.push(round4);
  totalScore -= round4.issues.length * (strictMode ? 5 : 3);

  // Round 5: 结语完整性
  const round5 = reviewConclusion(article, strictMode);
  rounds.push(round5);
  totalScore -= round5.issues.length * (strictMode ? 5 : 3);

  // 收集建议
  for (const round of rounds) {
    for (const issue of round.issues) {
      allSuggestions.push(issue.suggestion);
    }
  }

  // 确保分数在 0-100 之间
  totalScore = Math.max(0, Math.min(100, totalScore));

  return {
    score: totalScore,
    passed: totalScore >= (strictMode ? 80 : 60),
    rounds,
    suggestions: allSuggestions.slice(0, 10),
  };
}

/**
 * Round 1: AI 腔检测
 *
 * 检测常见的 AI 写作痕迹：
 * - 翻译感
 * - 元评论
 * - 防守修饰
 * - 套话
 */
function reviewAITone(article: string, strictMode: boolean): ReviewRound {
  const issues: ReviewIssue[] = [];

  // AI 套话关键词
  const aiPhrases = [
    { pattern: /综上所述/g, suggestion: "直接陈述结论，无需过渡词" },
    { pattern: /值得注意的是/g, suggestion: "直接说明要点" },
    { pattern: /不难发现/g, suggestion: "直接陈述发现的内容" },
    { pattern: /众所周知/g, suggestion: "如果真的众所周知，无需声明" },
    { pattern: /毋庸置疑/g, suggestion: "用证据说话，而非空洞断言" },
    { pattern: /总而言之/g, suggestion: "直接给出总结" },
    { pattern: /首先[，,]其次[，,]最后/g, suggestion: "考虑用更自然的逻辑连接" },
    { pattern: /一方面.*另一方面/g, suggestion: "直接阐述两个方面" },
    { pattern: /换句话说/g, suggestion: "直接用更清晰的表述替代原句" },
    { pattern: /简而言之/g, suggestion: "直接简述" },
  ];

  // 翻译腔
  const translationPhrases = [
    { pattern: /在.*的情况下/g, suggestion: "简化为「若」「当」等" },
    { pattern: /对于.*而言/g, suggestion: "考虑简化句式" },
    { pattern: /就.*来说/g, suggestion: "直接陈述" },
    { pattern: /从.*的角度来看/g, suggestion: "简化为「从X角度」或直接陈述" },
  ];

  // 元评论
  const metaComments = [
    { pattern: /本文将/g, suggestion: "直接展开内容" },
    { pattern: /接下来我们/g, suggestion: "直接展开" },
    { pattern: /如前所述/g, suggestion: "如需回顾，直接重述要点" },
    { pattern: /正如我们所见/g, suggestion: "直接陈述" },
  ];

  const allPatterns = strictMode
    ? [...aiPhrases, ...translationPhrases, ...metaComments]
    : aiPhrases;

  for (const { pattern, suggestion } of allPatterns) {
    let match;
    while ((match = pattern.exec(article)) !== null) {
      issues.push({
        type: "ai_tone",
        location: `位置 ${match.index}`,
        description: `发现 AI 腔表达：「${match[0]}」`,
        suggestion,
        severity: strictMode ? "major" : "minor",
      });
    }
  }

  return {
    name: "AI 腔检测",
    passed: issues.length === 0,
    issues,
  };
}

/**
 * Round 2: 标题质量
 *
 * 检查标题的常见问题：
 * - 话题描述 → 应改为结论
 * - 机制描述 → 应改为本质
 * - 定性描述 → 应改为推导原则
 */
function reviewTitleQuality(article: string, strictMode: boolean): ReviewRound {
  const issues: ReviewIssue[] = [];

  // 提取标题
  const titleMatch = article.match(/^#\s+(.+)$/m);
  if (!titleMatch) {
    issues.push({
      type: "title_missing",
      location: "文章开头",
      description: "未找到一级标题",
      suggestion: "在文章开头添加 # 标题",
      severity: "critical",
    });
    return { name: "标题质量", passed: false, issues };
  }

  const title = titleMatch[1];

  // 检查标题长度
  if (title.length > 30) {
    issues.push({
      type: "title_too_long",
      location: "标题",
      description: `标题过长（${title.length} 字）`,
      suggestion: "标题建议控制在 25 字以内",
      severity: "minor",
    });
  }

  // 检查标题是否太泛泛
  const vaguePatterns = [
    /关于.*的讨论/,
    /浅谈/,
    /试论/,
    /初探/,
    /.*之我见/,
  ];

  for (const pattern of vaguePatterns) {
    if (pattern.test(title)) {
      issues.push({
        type: "title_vague",
        location: "标题",
        description: "标题过于泛泛，缺乏信息量",
        suggestion: "用具体观点或结论作为标题",
        severity: strictMode ? "major" : "minor",
      });
      break;
    }
  }

  // 检查是否只是话题描述
  if (/^.{2,6}是什么[？?]?$/.test(title)) {
    issues.push({
      type: "title_topic_only",
      location: "标题",
      description: "标题只是话题描述，未给出观点",
      suggestion: "将「X是什么」改为「X的本质是Y」",
      severity: strictMode ? "major" : "minor",
    });
  }

  return {
    name: "标题质量",
    passed: issues.filter((i) => i.severity !== "minor").length === 0,
    issues,
  };
}

/**
 * Round 3: 绝对表达软化
 *
 * 检查过于绝对的表达：
 * - 只/仅 → 大体/主要
 * - 必须 → 需要/应该
 * - 无法 → 难以/不易
 */
function reviewAbsoluteExpressions(article: string, strictMode: boolean): ReviewRound {
  const issues: ReviewIssue[] = [];

  const absolutePatterns = [
    { pattern: /只有[^。]+才能/g, suggestion: "考虑用「主要通过」「一般需要」替代" },
    { pattern: /必须[^，。]+/g, suggestion: "考虑用「需要」「应该」替代" },
    { pattern: /无法[^，。]+/g, suggestion: "考虑用「难以」「不易」替代" },
    { pattern: /绝对[^，。]+/g, suggestion: "考虑删除「绝对」或改用更谨慎的表述" },
    { pattern: /完全[^，。]+/g, suggestion: "考虑用「大体」「基本」替代" },
    { pattern: /肯定[^，。]+/g, suggestion: "考虑用「很可能」「大概率」替代" },
    { pattern: /永远[^，。]+/g, suggestion: "考虑限定时间范围或条件" },
    { pattern: /所有[^，。]+都/g, suggestion: "考虑用「大多数」「绝大部分」替代" },
  ];

  for (const { pattern, suggestion } of absolutePatterns) {
    let match;
    while ((match = pattern.exec(article)) !== null) {
      // 允许在引用中使用绝对表达
      const context = article.slice(Math.max(0, match.index - 10), match.index);
      if (/[「"']/.test(context)) continue;

      issues.push({
        type: "absolute_expression",
        location: `位置 ${match.index}`,
        description: `发现绝对表达：「${match[0].slice(0, 20)}」`,
        suggestion,
        severity: "minor",
      });
    }
  }

  // 严格模式下，超过 5 个绝对表达视为问题
  const passed = strictMode ? issues.length <= 3 : issues.length <= 5;

  return {
    name: "绝对表达检查",
    passed,
    issues: issues.slice(0, 10), // 最多报告 10 个
  };
}

/**
 * Round 4: 结构合理性
 *
 * 检查文章结构：
 * - 是否有目录/大纲
 * - 段落长度是否合理
 * - 是否存在概念污染
 */
function reviewStructure(article: string, strictMode: boolean): ReviewRound {
  const issues: ReviewIssue[] = [];

  // 检查是否有二级标题
  const h2Count = (article.match(/^##\s+/gm) || []).length;
  if (h2Count < 2) {
    issues.push({
      type: "structure_flat",
      location: "全文",
      description: "文章结构过于平铺，缺少分节",
      suggestion: "使用二级标题划分内容",
      severity: strictMode ? "major" : "minor",
    });
  }

  // 检查段落长度
  const paragraphs = article.split(/\n\n+/);
  for (let i = 0; i < paragraphs.length; i++) {
    const para = paragraphs[i];
    if (para.length > 500 && !para.startsWith("#")) {
      issues.push({
        type: "paragraph_too_long",
        location: `第 ${i + 1} 段`,
        description: `段落过长（${para.length} 字）`,
        suggestion: "将长段落拆分为 2-3 个短段落",
        severity: "minor",
      });
    }
  }

  // 检查是否有结论/总结部分
  const hasConclusion = /##\s*(总结|结论|结语|Summary|Conclusion)/i.test(article);
  if (!hasConclusion && strictMode) {
    issues.push({
      type: "missing_conclusion",
      location: "文章末尾",
      description: "缺少总结/结论部分",
      suggestion: "添加「## 总结」部分",
      severity: "major",
    });
  }

  return {
    name: "结构合理性",
    passed: issues.filter((i) => i.severity !== "minor").length === 0,
    issues,
  };
}

/**
 * Round 5: 结语完整性
 *
 * 检查结语是否：
 * - 涵盖全文要点
 * - 核心句位置正确
 * - 可独立传播
 */
function reviewConclusion(article: string, strictMode: boolean): ReviewRound {
  const issues: ReviewIssue[] = [];

  // 提取结语部分
  const conclusionMatch = article.match(/##\s*(总结|结论|结语|Summary|Conclusion)\s*\n([\s\S]+?)(?=\n##|$)/i);

  if (!conclusionMatch) {
    if (strictMode) {
      issues.push({
        type: "conclusion_missing",
        location: "文章末尾",
        description: "未找到结语部分",
        suggestion: "添加结语，总结全文核心观点",
        severity: "major",
      });
    }
    return { name: "结语完整性", passed: !strictMode, issues };
  }

  const conclusion = conclusionMatch[2];

  // 检查结语长度
  if (conclusion.length < 50) {
    issues.push({
      type: "conclusion_too_short",
      location: "结语",
      description: "结语过短，可能未能涵盖全文",
      suggestion: "扩充结语，确保涵盖文章核心观点",
      severity: strictMode ? "major" : "minor",
    });
  }

  if (conclusion.length > 500) {
    issues.push({
      type: "conclusion_too_long",
      location: "结语",
      description: "结语过长，不利于独立传播",
      suggestion: "精简结语至 200 字以内",
      severity: "minor",
    });
  }

  // 检查是否有核心句
  const sentences = conclusion.split(/[。！？.!?]/);
  const hasCoreSentence = sentences.some(
    (s) => s.length >= 20 && s.length <= 80 && !/^[所因此]/.test(s.trim())
  );

  if (!hasCoreSentence && strictMode) {
    issues.push({
      type: "conclusion_no_core",
      location: "结语",
      description: "结语中未找到明确的核心句",
      suggestion: "在结语开头或中间放置一个 20-80 字的核心观点句",
      severity: "minor",
    });
  }

  return {
    name: "结语完整性",
    passed: issues.filter((i) => i.severity !== "minor").length === 0,
    issues,
  };
}

export { REVIEW_PROMPTS };
