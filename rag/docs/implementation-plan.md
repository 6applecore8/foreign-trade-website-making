# Implementation Plan

## MVP

1. 支持 Markdown/TXT/JSON 摄取和 raw hash-addressed 保存。
2. 按 Markdown heading + 段落窗口切分，保留行号与 heading_path。
3. 使用可替换 EmbeddingProvider；测试默认使用 384 维中文字符 n-gram hashing embedding。
4. PostgreSQL 16 + pgvector 0.8.6 存储，pg_trgm + cosine 混合检索。
5. 输出 context pack、fallback trace、分数、响应时间和引用。
6. 香水需求文档端到端基准与正确性断言。

## vNext

- 接入生产 Embedding Provider、reranker、PDF/DOCX 解析。
- 实现 review queue、approved wiki、租户与文档权限。
- Main Agent 在 dispatch 前自动构建多个主题 context pack。

## Deferred

- OCR、音视频、公共分享、实时协作、自动部署。

## validation_commands

```powershell
docker compose -f rag/docker-compose.yml up -d
python -m unittest discover -s rag/tests -p "test_*.py" -v
python -m rag.cli health
python -m rag.cli benchmark --document rag/examples/perfume-requirements.md --project-key perfume-e2e
```

## acceptance_checklist

- [ ] raw SHA 与落盘字节一致且不会被覆盖。
- [ ] 每个 chunk 有 heading_path、行号和 source_ref。
- [ ] PostgreSQL vector 与 pg_trgm 扩展可用。
- [ ] 三层 fallback 轨迹可见。
- [ ] 香水测试问题 top-3 全部正确。
- [ ] p95 检索响应小于 300ms。
- [ ] 输出不自动写回 wiki 或 active config。
