# Storage Architecture

| layer | purpose | stores | serves_contracts | mvp_status | owner |
|---|---|---|---|---|---|
| Raw Evidence | 保存不可变甲方原文 | hash-addressed files + rag_documents | ingest / fallback raw | MVP | RAG service |
| Source Digest | 记录单来源结构与去向 | digest JSON + rag_source_digests | source-digest / fallback | MVP | RAG service |
| Review Queue | 承接冲突与提升候选 | review records | weaving | vNext | owner |
| Compiled Wiki | 保存批准的复用规则 | approved knowledge chunks | retrieval first layer | vNext | owner |
| Output / Task Deliverables | 保存 context pack 和测试报告 | JSON reports | task handoff | MVP | Main Agent |
| Operational State | 数据库版本与 ingest 状态 | PostgreSQL schema、timestamps | health / retry | MVP | RAG service |
| Retrieval Package | 向 Agent 提供最小引用上下文 | ranked chunks、scores、trace | all retrieval contracts | MVP | RAG service |
| Release Share | 对外可分享知识 | approved export | customer delivery | Deferred | owner |
| Governance | 合同、门禁、健康规则 | `rag/docs/` | all governance | MVP | repository owner |

## Deferred Layers

- Review Queue 与 Compiled Wiki 的编辑 UI 延后；MVP 先保留表结构和契约。
- Release Share 在权限与脱敏流程完成前不创建。
