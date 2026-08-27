# INDEX — 01-requirements

## 单一职责
把自然语言需求压缩为首页加三个商品分类页的网站需求规格，不写代码、不写 HTML/CSS。

## 输入
`config/site-config.json`

## 输出
`artifacts/01-requirements/requirements.json`

## 可写目录
仅允许写入 `artifacts/01-requirements/`。

## Intake 扩展

若 config 提供 nested Intake 字段，消费 `website_intent` 的目标/受众/sections；对实际存在的 `industry`、`site_type`、`brand_name` 按原值保真，不补齐或据此捏造品牌事实。当前范围固定为首页、鞋履、服装、穿搭系列四个页面。
