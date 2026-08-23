# INDEX — 04-implementation

## 单一职责
把前置 JSON 组装为一个可直接用浏览器打开的静态网站。

## 输入
- `config/site-config.json`
- requirements、metadata、content 三个 JSON artifact

## 输出
只写入 `artifacts/04-implementation/site/`：

- `index.html`
- `styles.css`
- `site-spec.json`

## 可写目录
仅允许写入自己的 `artifacts/04-implementation/`，不得改动其他目录。

## Intake 引用扩展

仅使用 config 中真实存在、媒体类型已验证的本地 `reference_assets`，严格按 purpose/usage_note 放置；可嵌入现有 HTML/CSS，但不得增加第 4 个实现文件。`site-spec.json` 记录使用/未使用原因。
