/**
 * 格式转换工具
 *
 * 支持的格式：
 * - markdown: 标准 Markdown
 * - wechat_html: 微信公众号 HTML（内联样式）
 * - zhihu: 知乎专栏格式
 * - juejin: 掘金格式
 */

import type { FormatResult, OutputFormat } from "../types.js";
import { WECHAT_TEMPLATE, WECHAT_STYLES } from "../templates/wechat.js";

/**
 * 格式转换主函数
 *
 * @param article - Markdown 文章内容
 * @param targetFormat - 目标格式
 * @returns 格式化结果
 */
export async function formatArticle(
  article: string,
  targetFormat: string
): Promise<FormatResult> {
  let content: string;

  switch (targetFormat as OutputFormat) {
    case "wechat_html":
      content = convertToWechatHtml(article);
      break;
    case "zhihu":
      content = convertToZhihu(article);
      break;
    case "juejin":
      content = convertToJuejin(article);
      break;
    case "markdown":
    default:
      content = article;
      break;
  }

  // 提取标题
  const titleMatch = article.match(/^#\s+(.+)$/m);
  const title = titleMatch ? titleMatch[1] : "无标题";

  return {
    content,
    format: targetFormat as OutputFormat,
    metadata: {
      title,
      word_count: countWords(article),
      char_count: article.length,
    },
  };
}

/**
 * 转换为微信公众号 HTML
 *
 * 特点：
 * - 内联样式（公众号编辑器要求）
 * - 合适的字体和行高
 * - 图片居中
 * - 代码块样式
 */
function convertToWechatHtml(markdown: string): string {
  let html = markdown;

  // 处理代码块
  html = html.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    (_, lang, code) => `
<pre style="${WECHAT_STYLES.codeBlock}">
<code>${escapeHtml(code.trim())}</code>
</pre>`
  );

  // 处理行内代码
  html = html.replace(
    /`([^`]+)`/g,
    `<code style="${WECHAT_STYLES.inlineCode}">$1</code>`
  );

  // 处理标题
  html = html.replace(
    /^# (.+)$/gm,
    `<h1 style="${WECHAT_STYLES.h1}">$1</h1>`
  );
  html = html.replace(
    /^## (.+)$/gm,
    `<h2 style="${WECHAT_STYLES.h2}">$1</h2>`
  );
  html = html.replace(
    /^### (.+)$/gm,
    `<h3 style="${WECHAT_STYLES.h3}">$1</h3>`
  );

  // 处理粗体和斜体
  html = html.replace(
    /\*\*([^*]+)\*\*/g,
    `<strong style="${WECHAT_STYLES.bold}">$1</strong>`
  );
  html = html.replace(
    /\*([^*]+)\*/g,
    `<em style="${WECHAT_STYLES.italic}">$1</em>`
  );

  // 处理列表
  html = html.replace(
    /^- (.+)$/gm,
    `<li style="${WECHAT_STYLES.listItem}">$1</li>`
  );
  html = html.replace(
    /(<li[^>]*>.*<\/li>\n?)+/g,
    (match) => `<ul style="${WECHAT_STYLES.list}">${match}</ul>`
  );

  // 处理引用块
  html = html.replace(
    /^> (.+)$/gm,
    `<blockquote style="${WECHAT_STYLES.blockquote}">$1</blockquote>`
  );

  // 处理段落
  const lines = html.split("\n");
  const processed: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (
      trimmed &&
      !trimmed.startsWith("<") &&
      !trimmed.startsWith("#")
    ) {
      processed.push(`<p style="${WECHAT_STYLES.paragraph}">${trimmed}</p>`);
    } else {
      processed.push(line);
    }
  }

  html = processed.join("\n");

  // 包装在模板中
  return WECHAT_TEMPLATE.replace("{content}", html);
}

/**
 * 转换为知乎格式
 *
 * 知乎使用标准 Markdown，但有一些特殊处理
 */
function convertToZhihu(markdown: string): string {
  let content = markdown;

  // 知乎不支持某些 Markdown 语法，需要调整
  // 例如：知乎的代码块需要指定语言

  // 添加知乎特有的格式提示
  content = `<!--知乎专栏格式-->\n\n${content}`;

  // 图片添加说明
  content = content.replace(
    /!\[([^\]]*)\]\(([^)]+)\)/g,
    "![$1]($2)\n<center><small>$1</small></center>"
  );

  return content;
}

/**
 * 转换为掘金格式
 *
 * 掘金使用标准 Markdown，但支持一些扩展
 */
function convertToJuejin(markdown: string): string {
  let content = markdown;

  // 添加掘金前言
  const titleMatch = markdown.match(/^# (.+)$/m);
  if (titleMatch) {
    const title = titleMatch[1];
    content = content.replace(
      /^# .+$/m,
      `---
theme: juejin
highlight: github
---

# ${title}`
    );
  }

  return content;
}

/**
 * HTML 转义
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * 计算字数
 */
function countWords(text: string): number {
  const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length;
  const englishWords = (text.match(/\b[a-zA-Z]+\b/g) || []).length;
  return chineseChars + englishWords;
}
