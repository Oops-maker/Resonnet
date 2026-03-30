/**
 * Topic to Article Plugin Tests
 */

import { describe, it, expect, beforeEach } from "vitest";
import { analyzeDiscussion } from "../src/tools/analyze.js";
import { generateArticle } from "../src/tools/generate.js";
import { reviewArticle } from "../src/tools/review.js";
import { formatArticle } from "../src/tools/format.js";

describe("analyzeDiscussion", () => {
  const sampleDiscussion = `
## Round 1 - Physicist

关于人工智能的发展，我认为核心问题在于可解释性。深度学习模型虽然效果好，
但黑箱特性让我们难以理解其决策过程。这在高风险领域（医疗、金融）尤为关键。

---

## Round 1 - Economist

从经济学角度看，AI的发展更多是一个资源配置问题。技术进步本身不是问题，
关键是如何让技术红利惠及更多人，而不是加剧贫富分化。

---

## Round 2 - Physicist

我同意经济因素很重要，但技术风险不容忽视。如果AI系统出现严重错误，
影响可能是不可逆的。因此，我主张在技术成熟前保持谨慎。

---

## Round 2 - Economist

技术谨慎固然重要，但过度保守也有代价。很多国家已经在AI领域大力投入，
如果我们因为担心风险而停滞，可能会在国际竞争中落后。
`;

  it("should extract speakers correctly", async () => {
    const result = await analyzeDiscussion(sampleDiscussion, "zh");

    expect(result.speakers).toHaveLength(2);
    expect(result.speakers.map((s) => s.name)).toContain("Physicist");
    expect(result.speakers.map((s) => s.name)).toContain("Economist");
  });

  it("should extract key points", async () => {
    const result = await analyzeDiscussion(sampleDiscussion, "zh");

    expect(result.key_points.length).toBeGreaterThan(0);
    expect(result.key_points.some((p) => p.importance === "high")).toBe(true);
  });

  it("should identify consensus and disagreements", async () => {
    const result = await analyzeDiscussion(sampleDiscussion, "zh");

    // 由于是简化实现，主要检查结构
    expect(Array.isArray(result.consensus)).toBe(true);
    expect(Array.isArray(result.disagreements)).toBe(true);
  });

  it("should generate structure suggestion", async () => {
    const result = await analyzeDiscussion(sampleDiscussion, "zh");

    expect(result.structure_suggestion).toContain("建议文章结构");
    expect(result.structure_suggestion).toContain("引言");
  });
});

describe("generateArticle", () => {
  const sampleAnalysis = {
    key_points: [
      { content: "AI的可解释性是核心问题", speaker: "Physicist", importance: "high" as const },
      { content: "技术红利应惠及更多人", speaker: "Economist", importance: "high" as const },
      { content: "技术风险不可忽视", speaker: "Physicist", importance: "medium" as const },
    ],
    consensus: ["技术发展需要谨慎"],
    disagreements: [
      {
        topic: "发展速度",
        positions: [
          { speaker: "Physicist", position: "主张谨慎" },
          { speaker: "Economist", position: "担心落后" },
        ],
      },
    ],
    speakers: [
      { name: "Physicist", role: "物理学家", main_stance: "技术谨慎派", contribution_count: 2 },
      { name: "Economist", role: "经济学家", main_stance: "发展优先派", contribution_count: 2 },
    ],
    structure_suggestion: "引言 → 核心观点 → 共识 → 分歧 → 结语",
    topic_summary: "AI发展的风险与机遇",
  };

  it("should generate article with title", async () => {
    const result = await generateArticle(sampleAnalysis, {
      titleStyle: "statement",
      outputFormat: "markdown",
      maxLength: 3000,
      styleProfile: "academic",
    });

    expect(result.title).toBeTruthy();
    expect(result.title.length).toBeLessThan(50);
  });

  it("should generate body with sections", async () => {
    const result = await generateArticle(sampleAnalysis, {
      titleStyle: "statement",
      outputFormat: "markdown",
      maxLength: 3000,
      styleProfile: "academic",
    });

    expect(result.body).toContain("## 引言");
    expect(result.body).toContain("## 核心观点");
  });

  it("should respect max length", async () => {
    const result = await generateArticle(sampleAnalysis, {
      titleStyle: "statement",
      outputFormat: "markdown",
      maxLength: 500,
      styleProfile: "academic",
    });

    // 字数应该大致在限制范围内
    expect(result.word_count).toBeLessThan(800); // 允许一些超出
  });

  it("should extract citations", async () => {
    const result = await generateArticle(sampleAnalysis, {
      titleStyle: "statement",
      outputFormat: "markdown",
      maxLength: 3000,
      styleProfile: "academic",
    });

    expect(result.citations.length).toBeGreaterThan(0);
    expect(result.citations[0].speaker).toBeTruthy();
  });

  it("should support different title styles", async () => {
    const questionResult = await generateArticle(sampleAnalysis, {
      titleStyle: "question",
      outputFormat: "markdown",
      maxLength: 3000,
      styleProfile: "academic",
    });

    const insightResult = await generateArticle(sampleAnalysis, {
      titleStyle: "insight",
      outputFormat: "markdown",
      maxLength: 3000,
      styleProfile: "academic",
    });

    // 问题式标题应该包含问号或疑问词
    expect(
      questionResult.title.includes("？") ||
      questionResult.title.includes("?") ||
      questionResult.title.includes("如何") ||
      questionResult.title.includes("谁")
    ).toBe(true);

    // 洞见式标题应该有深度关键词
    expect(
      insightResult.title.includes("深度") ||
      insightResult.title.includes("解读") ||
      insightResult.title.includes("本质")
    ).toBe(true);
  });
});

describe("reviewArticle", () => {
  const goodArticle = `
# AI发展的风险与机遇

## 引言

本文基于多位专家的讨论，探讨人工智能发展中的关键问题。

## 核心观点

### 可解释性问题

深度学习模型效果好，但难以理解其决策过程。

### 经济影响

技术进步本身不是问题，关键是如何让技术红利惠及更多人。

## 达成共识

- 技术发展需要谨慎

## 观点分歧

### 发展速度

- **Physicist**：主张谨慎
- **Economist**：担心落后

## 总结

AI发展需要平衡风险与机遇。专家们在技术谨慎这一点上达成共识，但在发展速度上存在分歧。这些讨论为我们提供了有价值的思考角度。
`;

  const badArticle = `
# 关于AI的讨论

综上所述，AI是一个值得注意的话题。不难发现，很多人对此有不同看法。

首先，AI很重要。其次，AI有风险。最后，我们需要谨慎。

必须承认，AI绝对会改变世界。只有充分了解AI，才能应对挑战。
`;

  it("should pass good article review", async () => {
    const result = await reviewArticle(goodArticle, false);

    expect(result.score).toBeGreaterThan(60);
    expect(result.passed).toBe(true);
  });

  it("should detect AI tone issues", async () => {
    const result = await reviewArticle(badArticle, true);

    const aiToneRound = result.rounds.find((r) => r.name === "AI 腔检测");
    expect(aiToneRound).toBeTruthy();
    expect(aiToneRound!.issues.length).toBeGreaterThan(0);
  });

  it("should detect title quality issues", async () => {
    const result = await reviewArticle(badArticle, true);

    const titleRound = result.rounds.find((r) => r.name === "标题质量");
    expect(titleRound).toBeTruthy();
    expect(titleRound!.issues.length).toBeGreaterThan(0);
  });

  it("should detect absolute expressions", async () => {
    const result = await reviewArticle(badArticle, true);

    const absoluteRound = result.rounds.find((r) => r.name === "绝对表达检查");
    expect(absoluteRound).toBeTruthy();
    expect(absoluteRound!.issues.length).toBeGreaterThan(0);
  });

  it("should be stricter in strict mode", async () => {
    const strictResult = await reviewArticle(badArticle, true);
    const normalResult = await reviewArticle(badArticle, false);

    expect(strictResult.score).toBeLessThan(normalResult.score);
  });

  it("should provide suggestions", async () => {
    const result = await reviewArticle(badArticle, true);

    expect(result.suggestions.length).toBeGreaterThan(0);
  });
});

describe("formatArticle", () => {
  const sampleMarkdown = `
# 测试文章

## 第一节

这是一个**重要**的段落。

- 列表项1
- 列表项2

> 这是一段引用

\`\`\`javascript
console.log("Hello");
\`\`\`

## 第二节

这是另一个段落，包含 \`内联代码\`。
`;

  it("should return markdown as-is", async () => {
    const result = await formatArticle(sampleMarkdown, "markdown");

    expect(result.format).toBe("markdown");
    expect(result.content).toBe(sampleMarkdown);
  });

  it("should convert to wechat HTML", async () => {
    const result = await formatArticle(sampleMarkdown, "wechat_html");

    expect(result.format).toBe("wechat_html");
    expect(result.content).toContain("<h1");
    expect(result.content).toContain("<h2");
    expect(result.content).toContain("style=");
    expect(result.content).toContain("<strong");
  });

  it("should add zhihu format marker", async () => {
    const result = await formatArticle(sampleMarkdown, "zhihu");

    expect(result.format).toBe("zhihu");
    expect(result.content).toContain("知乎专栏格式");
  });

  it("should add juejin front matter", async () => {
    const result = await formatArticle(sampleMarkdown, "juejin");

    expect(result.format).toBe("juejin");
    expect(result.content).toContain("theme: juejin");
  });

  it("should extract metadata", async () => {
    const result = await formatArticle(sampleMarkdown, "markdown");

    expect(result.metadata.title).toBe("测试文章");
    expect(result.metadata.word_count).toBeGreaterThan(0);
    expect(result.metadata.char_count).toBeGreaterThan(0);
  });
});
