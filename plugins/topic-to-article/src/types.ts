/**
 * Topic to Article - OpenClaw Plugin
 *
 * 将讨论内容一键生成高质量文章（支持公众号、知乎等格式）
 *
 * Tools:
 * - analyze_discussion: 分析讨论内容
 * - generate_article: 生成文章草稿
 * - review_article: 5 轮审稿
 * - format_article: 格式转换
 */

// Types for plugin configuration
export interface PluginConfig {
  default_format: "markdown" | "wechat_html" | "zhihu" | "juejin";
  default_language: "zh" | "en";
  review_enabled: boolean;
  style_profile: "academic" | "casual" | "news";
}

// Analysis result types
export interface AnalysisResult {
  key_points: KeyPoint[];
  consensus: string[];
  disagreements: Disagreement[];
  speakers: Speaker[];
  structure_suggestion: string;
  topic_summary: string;
}

export interface KeyPoint {
  content: string;
  speaker?: string;
  importance: "high" | "medium" | "low";
}

export interface Disagreement {
  topic: string;
  positions: { speaker: string; position: string }[];
}

export interface Speaker {
  name: string;
  role?: string;
  main_stance: string;
  contribution_count: number;
}

// Article types
export interface ArticleResult {
  title: string;
  subtitle?: string;
  body: string;
  summary: string;
  citations: Citation[];
  word_count: number;
}

export interface Citation {
  speaker: string;
  quote: string;
  context: string;
}

// Review types
export interface ReviewResult {
  score: number;
  passed: boolean;
  rounds: ReviewRound[];
  revised_article?: string;
  suggestions: string[];
}

export interface ReviewRound {
  name: string;
  passed: boolean;
  issues: ReviewIssue[];
}

export interface ReviewIssue {
  type: string;
  location: string;
  description: string;
  suggestion: string;
  severity: "critical" | "major" | "minor";
}

// Format types
export type OutputFormat = "markdown" | "wechat_html" | "zhihu" | "juejin";

export interface FormatResult {
  content: string;
  format: OutputFormat;
  metadata: {
    title: string;
    word_count: number;
    char_count: number;
  };
}

// Title styles
export type TitleStyle = "question" | "statement" | "insight";
