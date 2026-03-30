/**
 * 微信公众号 HTML 模板和样式
 *
 * 公众号编辑器要求内联样式，不支持外部 CSS
 */

export const WECHAT_STYLES = {
  // 容器
  container: `
    max-width: 100%;
    padding: 20px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 16px;
    line-height: 1.8;
    color: #333;
  `.replace(/\n\s*/g, " "),

  // 标题
  h1: `
    font-size: 24px;
    font-weight: bold;
    color: #1a1a1a;
    margin: 30px 0 20px 0;
    padding-bottom: 10px;
    border-bottom: 2px solid #07c160;
  `.replace(/\n\s*/g, " "),

  h2: `
    font-size: 20px;
    font-weight: bold;
    color: #1a1a1a;
    margin: 25px 0 15px 0;
    padding-left: 10px;
    border-left: 4px solid #07c160;
  `.replace(/\n\s*/g, " "),

  h3: `
    font-size: 18px;
    font-weight: bold;
    color: #333;
    margin: 20px 0 10px 0;
  `.replace(/\n\s*/g, " "),

  // 段落
  paragraph: `
    margin: 15px 0;
    text-align: justify;
    line-height: 2;
  `.replace(/\n\s*/g, " "),

  // 强调
  bold: `
    font-weight: bold;
    color: #07c160;
  `.replace(/\n\s*/g, " "),

  italic: `
    font-style: italic;
    color: #666;
  `.replace(/\n\s*/g, " "),

  // 列表
  list: `
    margin: 15px 0;
    padding-left: 20px;
  `.replace(/\n\s*/g, " "),

  listItem: `
    margin: 8px 0;
    line-height: 1.8;
  `.replace(/\n\s*/g, " "),

  // 引用块
  blockquote: `
    margin: 20px 0;
    padding: 15px 20px;
    background-color: #f8f8f8;
    border-left: 4px solid #07c160;
    color: #666;
    font-style: italic;
  `.replace(/\n\s*/g, " "),

  // 代码
  codeBlock: `
    margin: 15px 0;
    padding: 15px;
    background-color: #f6f8fa;
    border-radius: 6px;
    overflow-x: auto;
    font-family: Consolas, Monaco, "Courier New", monospace;
    font-size: 14px;
    line-height: 1.6;
  `.replace(/\n\s*/g, " "),

  inlineCode: `
    padding: 2px 6px;
    background-color: #f0f0f0;
    border-radius: 3px;
    font-family: Consolas, Monaco, "Courier New", monospace;
    font-size: 14px;
    color: #e83e8c;
  `.replace(/\n\s*/g, " "),

  // 图片
  image: `
    max-width: 100%;
    margin: 20px auto;
    display: block;
    border-radius: 8px;
  `.replace(/\n\s*/g, " "),

  imageCaption: `
    text-align: center;
    color: #999;
    font-size: 14px;
    margin-top: 10px;
  `.replace(/\n\s*/g, " "),

  // 分割线
  hr: `
    margin: 30px 0;
    border: none;
    border-top: 1px dashed #ddd;
  `.replace(/\n\s*/g, " "),

  // 链接
  link: `
    color: #07c160;
    text-decoration: none;
  `.replace(/\n\s*/g, " "),

  // 表格
  table: `
    width: 100%;
    margin: 20px 0;
    border-collapse: collapse;
    font-size: 14px;
  `.replace(/\n\s*/g, " "),

  tableHeader: `
    background-color: #07c160;
    color: white;
    padding: 12px;
    text-align: left;
    font-weight: bold;
  `.replace(/\n\s*/g, " "),

  tableCell: `
    padding: 10px 12px;
    border-bottom: 1px solid #eee;
  `.replace(/\n\s*/g, " "),
};

export const WECHAT_TEMPLATE = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>公众号文章</title>
</head>
<body>
<section style="${WECHAT_STYLES.container}">
{content}

<hr style="${WECHAT_STYLES.hr}">

<p style="text-align: center; color: #999; font-size: 14px;">
  — END —
</p>

<p style="text-align: center; color: #999; font-size: 12px; margin-top: 20px;">
  如果觉得有收获，欢迎点赞、在看、转发~
</p>
</section>
</body>
</html>
`.trim();

export default WECHAT_TEMPLATE;
