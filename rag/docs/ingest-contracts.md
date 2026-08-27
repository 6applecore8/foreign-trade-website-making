# Ingest Contracts

| source | trigger | raw_format | preprocessing | metadata | authority | quality_gate |
|---|---|---|---|---|---|---|
| 甲方需求文档 | CLI/API 显式摄取 | Markdown/TXT/JSON | UTF-8 校验、SHA-256、结构解析、语义边界切分 | project_key、owner、filename、hash、ingested_at | client-provided raw evidence | 路径 containment、大小、扩展名、解码、哈希 |
| 已确认站点配置 | owner 确认后 | JSON | Schema 校验、字段投影 | run_id、config hash、source_refs | user-approved | site-config schema + archive gate |
| Agent 输出 | 用户明确确认可复用 | JSON/Markdown | 引用回查、差异检查 | reviewer、confirmed_at、source_refs | agent-draft until approved | human approval required |

## Raw Evidence Rules

- immutable_material: `rag-data/raw/<sha256>/<filename>` 中的原始字节。
- allowed_normalization: 仅在内存中统一换行、解析 Markdown heading、格式化 JSON；数据库必须保存 raw SHA。
- forbidden_rewrite: 禁止覆盖同 SHA 路径、禁止把摘要写回 raw、禁止用新上传替换旧 raw。
- required_backlinks: chunk 和 digest 都必须回链到 raw 相对路径及行号范围。

## Notes

MVP 支持的格式故意较窄。PDF、DOCX、扫描件在 vNext 通过独立解析适配器加入，不能把乱码或 OCR 猜测当原文。
