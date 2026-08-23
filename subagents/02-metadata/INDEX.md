# INDEX — 02-metadata

## 单一职责
规范化网页 title、description、keywords，并保证用户明确输入优先。

## 输入
- `config/site-config.json`
- `artifacts/01-requirements/requirements.json`

## 输出
`artifacts/02-metadata/metadata.json`

## 可写目录
仅允许写入 `artifacts/02-metadata/`。

## SEO 优先级

按字段执行 `explicit nested seo > imported user source_document > legacy top-level > generated default`，并在 metadata provenance 记录实际来源，供 Validation 校验保真。
