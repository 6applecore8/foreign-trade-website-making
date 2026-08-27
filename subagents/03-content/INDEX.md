# INDEX — 03-content

## 单一职责
生成首页与三个商品分类页所需的短内容结构，不写 HTML/CSS，不设计额外页面。

## 输入
- `config/site-config.json`
- `artifacts/01-requirements/requirements.json`

## 输出
`artifacts/03-content/home-content.json`

## 可写目录
仅允许写入 `artifacts/03-content/`。

## FAQ 扩展

消费 `faq.mode/items`：custom 严格保序且未知答案为 `待补充`；industry-default 使用 `website_intent.industry` 选择离线行业通用主题。`brand_name`/`site_type` 仅约束称谓与四页面内容范围，不可补写真实历史、资质或业绩。
