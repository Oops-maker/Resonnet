/**
 * Topic to Article - OpenClaw Plugin Entry
 *
 * 将讨论内容一键生成高质量文章
 */

import { Type } from "@sinclair/typebox";

// Plugin entry definition (OpenClaw SDK compatible)
interface OpenClawPluginApi {
  id: string;
  name: string;
  version?: string;
  config: Record<string, unknown>;
  pluginConfig: Record<string, unknown>;
  logger: {
    debug: (msg: string, ...args: unknown[]) => void;
    info: (msg: string, ...args: unknown[]) => void;
    warn: (msg: string, ...args: unknown[]) => void;
    error: (msg: string, ...args: unknown[]) => void;
  };
  registerTool: (tool: ToolDefinition, opts?: { optional?: boolean }) => void;
  registerCommand: (command: CommandDefinition) => void;
}

interface ToolDefinition {
  name: string;
  description: string;
  parameters: unknown;
  execute: (id: string, params: Record<string, unknown>) => Promise<ToolResult>;
}

interface ToolResult {
  content: Array<{ type: string; text: string }>;
}

interface CommandDefinition {
  name: string;
  description: string;
  args?: Array<{ name: string; description: string; optional?: boolean }>;
  execute: (ctx: unknown, args: string[]) => Promise<void>;
}

// Import tool implementations
import { analyzeDiscussion } from "./tools/analyze.js";
import { generateArticle } from "./tools/generate.js";
import { reviewArticle } from "./tools/review.js";
import { formatArticle } from "./tools/format.js";

// Plugin configuration type
import type { PluginConfig } from "./types.js";

/**
 * Plugin entry point
 */
export function register(api: OpenClawPluginApi): void {
  const config = api.pluginConfig as Partial<PluginConfig>;
  const logger = api.logger;

  logger.info("Topic to Article plugin initializing...");

  // ========================================
  // Tool: analyze_discussion
  // ========================================
  api.registerTool({
    name: "analyze_discussion",
    description:
      "分析讨论内容，提取核心观点、共识与分歧、发言者立场。输出结构化分析结果供文章生成使用。",
    parameters: Type.Object({
      discussion_content: Type.String({
        description: "讨论内容（Markdown 格式，包含多人发言）",
      }),
      language: Type.Optional(
        Type.String({
          description: "输出语言",
          default: config.default_language || "zh",
        })
      ),
    }),
    async execute(_id, params) {
      const result = await analyzeDiscussion(
        params.discussion_content as string,
        (params.language as string) || config.default_language || "zh"
      );
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    },
  });

  // ========================================
  // Tool: generate_article
  // ========================================
  api.registerTool({
    name: "generate_article",
    description:
      "基于分析结果生成文章草稿。支持多种标题风格和输出格式。",
    parameters: Type.Object({
      analysis: Type.String({
        description: "analyze_discussion 的输出结果（JSON 字符串）",
      }),
      title_style: Type.Optional(
        Type.Union([
          Type.Literal("question"),
          Type.Literal("statement"),
          Type.Literal("insight"),
        ], {
          description: "标题风格：question(问题式)、statement(陈述式)、insight(洞见式)",
          default: "statement",
        })
      ),
      output_format: Type.Optional(
        Type.Union([
          Type.Literal("markdown"),
          Type.Literal("wechat_html"),
          Type.Literal("zhihu"),
          Type.Literal("juejin"),
        ], {
          description: "输出格式",
          default: config.default_format || "markdown",
        })
      ),
      max_length: Type.Optional(
        Type.Number({
          description: "最大字数限制",
          default: 3000,
        })
      ),
      style_profile: Type.Optional(
        Type.Union([
          Type.Literal("academic"),
          Type.Literal("casual"),
          Type.Literal("news"),
        ], {
          description: "写作风格",
          default: config.style_profile || "academic",
        })
      ),
    }),
    async execute(_id, params) {
      const analysis = JSON.parse(params.analysis as string);
      const result = await generateArticle(analysis, {
        titleStyle: (params.title_style as string) || "statement",
        outputFormat:
          (params.output_format as string) || config.default_format || "markdown",
        maxLength: (params.max_length as number) || 3000,
        styleProfile:
          (params.style_profile as string) || config.style_profile || "academic",
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    },
  });

  // ========================================
  // Tool: review_article
  // ========================================
  api.registerTool({
    name: "review_article",
    description:
      "对文章进行 5 轮质量审核：AI腔检测、标题质量、绝对表达、结构合理性、结语完整性。返回评分和修订建议。",
    parameters: Type.Object({
      article: Type.String({
        description: "待审核的文章内容（Markdown 格式）",
      }),
      strict_mode: Type.Optional(
        Type.Boolean({
          description: "严格模式：更严格的评判标准",
          default: true,
        })
      ),
    }),
    async execute(_id, params) {
      if (!config.review_enabled) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                score: 100,
                passed: true,
                rounds: [],
                suggestions: ["审稿功能已禁用"],
              }),
            },
          ],
        };
      }
      const result = await reviewArticle(
        params.article as string,
        (params.strict_mode as boolean) ?? true
      );
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    },
  });

  // ========================================
  // Tool: format_article (optional)
  // ========================================
  api.registerTool(
    {
      name: "format_article",
      description:
        "将文章转换为指定格式。支持：markdown、wechat_html（公众号）、zhihu、juejin。",
      parameters: Type.Object({
        article: Type.String({
          description: "文章内容（Markdown 格式）",
        }),
        target_format: Type.Union(
          [
            Type.Literal("markdown"),
            Type.Literal("wechat_html"),
            Type.Literal("zhihu"),
            Type.Literal("juejin"),
          ],
          {
            description: "目标格式",
          }
        ),
      }),
      async execute(_id, params) {
        const result = await formatArticle(
          params.article as string,
          params.target_format as string
        );
        return {
          content: [{ type: "text", text: result.content }],
        };
      },
    },
    { optional: true }
  );

  // ========================================
  // Command: /article
  // ========================================
  api.registerCommand({
    name: "article",
    description: "一键生成文章命令",
    args: [
      {
        name: "action",
        description: "操作：analyze | generate | review | export",
      },
      {
        name: "options",
        description: "选项（JSON 格式，可选）",
        optional: true,
      },
    ],
    async execute(_ctx, args) {
      const [action, optionsStr] = args;
      const options = optionsStr ? JSON.parse(optionsStr) : {};

      logger.info(`Article command: ${action}`, options);

      switch (action) {
        case "analyze":
          logger.info("请使用 analyze_discussion 工具分析内容");
          break;
        case "generate":
          logger.info("请使用 generate_article 工具生成文章");
          break;
        case "review":
          logger.info("请使用 review_article 工具审核文章");
          break;
        case "export":
          logger.info("请使用 format_article 工具导出文章");
          break;
        default:
          logger.warn(`未知操作: ${action}`);
      }
    },
  });

  logger.info("Topic to Article plugin initialized successfully!");
}

// Export for OpenClaw plugin system
export default {
  id: "topic-to-article",
  name: "Topic to Article",
  register,
};
