# Topic to Article - OpenClaw Plugin

将讨论内容一键生成高质量文章（支持公众号、知乎等格式）。

## 功能特性

- **内容分析**：自动提取讨论中的核心观点、共识与分歧
- **文章生成**：基于分析结果生成结构化文章
- **5 轮审稿**：AI 腔检测、标题质量、绝对表达、结构合理性、结语完整性
- **多格式输出**：Markdown、微信公众号 HTML、知乎、掘金

## 安装

```bash
openclaw plugins install @resonnet/topic-to-article
```

或通过 ClawHub：

```bash
openclaw plugins install clawhub:@resonnet/topic-to-article
```

## 使用方式

### 方式 1：对话式使用

直接在对话中让 AI 调用工具：

```
用户: 这是我们关于 AI 安全的讨论记录，帮我整理成一篇公众号文章
      [粘贴讨论内容]

AI: [自动调用工具] 分析完成，已生成文章...
```

### 方式 2：命令调用

```bash
/article generate --format wechat_html
/article review --strict
/article export --filename output.html
```

### 方式 3：工具直接调用

```
用户: 使用 analyze_discussion 分析这段内容...
用户: 使用 generate_article 生成文章，格式为 wechat_html
```

## 配置

在 OpenClaw 配置文件中设置：

```json
{
  "plugins": {
    "entries": {
      "topic-to-article": {
        "enabled": true,
        "config": {
          "default_format": "wechat_html",
          "default_language": "zh",
          "review_enabled": true,
          "style_profile": "academic"
        }
      }
    }
  }
}
```

### 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `default_format` | string | `"markdown"` | 默认输出格式 |
| `default_language` | string | `"zh"` | 默认语言 |
| `review_enabled` | boolean | `true` | 是否启用审稿 |
| `style_profile` | string | `"academic"` | 写作风格 |

### 输出格式

| 格式 | 说明 |
|------|------|
| `markdown` | 标准 Markdown |
| `wechat_html` | 微信公众号 HTML（内联样式） |
| `zhihu` | 知乎专栏格式 |
| `juejin` | 掘金格式 |

### 写作风格

| 风格 | 说明 |
|------|------|
| `academic` | 学术风格，严谨客观 |
| `casual` | 轻松随意，口语化 |
| `news` | 新闻风格，简洁明了 |

## Agent Tools

### analyze_discussion

分析讨论内容，提取核心观点和共识/分歧。

**参数**：
- `discussion_content` (string, required): 讨论内容（Markdown 格式）
- `language` (string, optional): 输出语言，默认 "zh"

**返回**：
```json
{
  "key_points": [...],
  "consensus": [...],
  "disagreements": [...],
  "speakers": [...],
  "structure_suggestion": "..."
}
```

### generate_article

从分析结果生成文章草稿。

**参数**：
- `analysis` (string, required): 分析结果 JSON
- `title_style` (string, optional): 标题风格 ("question" | "statement" | "insight")
- `output_format` (string, optional): 输出格式
- `max_length` (number, optional): 最大字数，默认 3000

**返回**：
```json
{
  "title": "...",
  "subtitle": "...",
  "body": "...",
  "citations": [...]
}
```

### review_article

对文章进行 5 轮质量审核。

**参数**：
- `article` (string, required): 文章内容
- `strict_mode` (boolean, optional): 严格模式，默认 true

**返回**：
```json
{
  "score": 85,
  "passed": true,
  "rounds": [...],
  "suggestions": [...]
}
```

### format_article

将文章转换为指定格式。

**参数**：
- `article` (string, required): 文章内容
- `target_format` (string, required): 目标格式

**返回**：格式化后的文章内容

## 审稿标准

基于 [tashan-writing-system](https://github.com/TashanGKD/tashan-writing-system) 的 5 轮审稿标准：

| 轮次 | 检查项 | 说明 |
|------|--------|------|
| 1 | AI 腔检测 | 翻译感、元评论、防守修饰、套话 |
| 2 | 标题质量 | 避免话题描述、机制、定性表述 |
| 3 | 绝对表达 | 软化"只/仅/必须/无法"等词 |
| 4 | 结构合理性 | 概念污染、引用位置、标注准确 |
| 5 | 结语完整性 | 涵盖全文、核心句位置、可独立传播 |

## 开发

```bash
# 安装依赖
pnpm install

# 开发模式
pnpm dev

# 构建
pnpm build

# 测试
pnpm test
```

## 许可证

MIT License
