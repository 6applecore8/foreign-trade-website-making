# INDEX — 01-requirements

## 单一职责
把自然语言需求压缩为一个单页网站需求规格，不写代码、不写 HTML/CSS。

## 输入
`config/site-config.json`

## 输出
`artifacts/01-requirements/requirements.json`

## 可写目录
仅允许写入 `artifacts/01-requirements/`。

## Intake 扩展

若 config 提供 nested Intake 字段，消费 `website_intent` 的目标/受众/sections；对实际存在的 `industry`、`site_type`、`brand_name` 在 `website_identity` 中按原值保真，不补齐或据此捏造品牌事实。另消费 `reference_assets` 的图片用途与说明以及 `faq.mode`；输出中携带 `reference_assets` 与 `faq_mode`，仍保持单页和区块上限。
