# Directory Blueprint

## Tree

    rag/
    ├── README.md
    ├── cli.py
    ├── config.py
    ├── parser.py
    ├── chunker.py
    ├── embeddings.py
    ├── store.py
    ├── pipeline.py
    ├── sql/schema.sql
    ├── docs/
    ├── examples/
    ├── tests/
    └── reports/
    rag-data/
    ├── raw/<sha256>/
    ├── digests/
    └── outputs/

## Mapping

| path | serves_contract | owner | required | notes |
|---|---|---|---|---|
| rag/ | ingest、retrieval、governance contracts | repository owner | MVP | 可测试的 Python 子系统 |
| README.md | operator contract | repository owner | MVP | 本地启动、摄取、检索与基准命令 |
| cli.py | execution entrypoint | RAG service | MVP | init-db、health、ingest、ask、benchmark |
| config.py | runtime configuration | RAG service | MVP | DSN、目录和检索阈值 |
| parser.py | ingest contract | RAG service | MVP | UTF-8/类型/哈希和 immutable raw |
| chunker.py | chunking contract | RAG service | MVP | Markdown 标题感知、段落窗口切分 |
| embeddings.py | retrieval contract | RAG service | MVP | 可替换 Provider；MVP 为本地确定性特征向量 |
| store.py | storage/retrieval contract | RAG service | MVP | PostgreSQL/pgvector hybrid retrieval |
| pipeline.py | orchestration contract | RAG service | MVP | ingest、fallback 与可引用 context pack |
| sql/schema.sql | Operational State schema | RAG service | MVP | vector、pg_trgm、documents/chunks/digests |
| docs/ | Governance storage layer | repository owner | MVP | 十项设计与门禁文档 |
| examples/ | ingest fixture | test owner | MVP | 香水行业完整需求文档 |
| tests/ | Acceptance Gate | test owner | MVP | 单元与 PostgreSQL 集成测试 |
| reports/ | Output / Task Deliverables | Main Agent | MVP | 响应时间与正确性报告 |
| raw/<sha256>/ | Raw Evidence item | RAG service | MVP | 每个 source hash 的不可变原文目录 |
| digests/ | Source Digest | RAG service | MVP | 结构性 digest 和 raw backlink |
| outputs/ | Retrieval Package | RAG service | MVP | Agent context packs |

## Deferred Directories

- `rag-data/review/`: 待 owner review UI 与冲突流程实现。
- `rag-data/wiki/`: 待人工提升规则和版本治理实现。
- `rag-data/release/`: 待权限、脱敏与甲方交付策略明确。
