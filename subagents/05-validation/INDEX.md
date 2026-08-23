# INDEX — 05-validation

## 单一职责
对生成的网站做浅层、可重复的 MVP 验证，不负责修复。

## 输入
- `config/site-config.json`
- `artifacts/02-metadata/metadata.json`
- `artifacts/04-implementation/site/`

## 输出
`artifacts/05-validation/validation-report.json`

## 检查项
文件存在、HTML metadata、CSS 引用、明显的本地引用错误、范围是否仍为单页、外部依赖是否被引入。

## 可写目录
仅允许写入 `artifacts/05-validation/`。

## Intake 扩展检查

除原检查外，验证 active config schema、本地引用路径/存在性/类型/用途、custom FAQ 顺序与 `待补充`、SEO 字段级优先级与 provenance，并拒绝无证据的研究声明。
