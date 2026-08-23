# INDEX — config

本目录存放用户输入契约和工作流级配置。

## 文件

- `site-config.schema.json`：输入 JSON Schema。
- `site-config.example.json`：可复制的兼容输入示例（含可选网站身份）。
- `site-config.json`：运行时由主 Agent 根据用户需求创建。

## 可变字段

- `title`：网站 `<title>` 和首页主标题的默认值。
- `description`：网站 `<meta name="description">`。
- `keywords`：网站 `<meta name="keywords">`，支持字符串数组或逗号分隔字符串。
- `user_request`：自然语言网站需求。

不要在这里放生成后的 HTML/CSS；实现文件必须归 implementation Subagent 所有。

## Optional Intake 字段

- `intake`：append-only request 的 ID、目录、源请求与提交时间身份。
- `website_intent`：目标、受众、声明 sections 与样式说明；可选 `industry`、`site_type`、`brand_name` 均为用户声明的非空字符串，最长 120 字符。
- `reference_assets`：最多 6 个项目相对本地引用，包含 original name、verified media type、purpose、usage note。
- `faq`：`industry-default|custom`；custom 保持数组顺序，未知答案必须为 `待补充`。
- `seo`：显式字段与可选 source document；字段级优先级为 nested explicit > imported document > legacy top-level > generated default。

这些对象全部可选，因此当前 legacy `site-config.json` 保持合法。Intake UI 提交只创建请求快照，不能直接覆盖本目录 active config。
