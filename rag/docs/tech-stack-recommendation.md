# Tech Stack Recommendation

## requirements_summary

单项目/小团队、本地私有、事件触发摄取、中小文档量、需要严格引用与审计、维护能力中等。RAG 的下一动作是把 context pack 交给建站 Agent，而不是面向公众直接回答。

## recommendation

- PostgreSQL 16 + pgvector 0.8.6：统一保存文档、chunk、metadata、向量和检索状态。
- pg_trgm + cosine hybrid：中文需求既有精确术语，也有近似表达，单一全文索引或单一向量都不够稳。
- Psycopg 3 binary：Windows 本地测试无需单独安装 libpq。
- Python 标准库解析器 + 可插拔 EmbeddingProvider：MVP 可重复，vNext 可换真实语义模型。
- Code Agent CLI：负责带引用地解释检索结果和生成站点；脚本负责边界、排名、Schema 与安全写入。

## automation_boundary

| activity | llm_role | script_role | human_gate | failure_if_misassigned |
|---|---|---|---|---|
| raw -> source digest | 提议摘要与 claims | hash、解析、source_refs、结构 digest | 高影响 claims 复核 | 脚本冒充理解或 LLM 改写原文 |
| source digest -> wiki/review/source | 判断复用价值和冲突 | 校验引用、写入允许目标 | owner 决定 promote | wiki 污染 |
| ask retrieval fallback | 解释证据并综合答案 | 强制 wiki -> digest -> raw、阈值和权限 | 低置信度问题复核 | 无证据回答或错误回退 |
| output -> weave-back | 提议可复用经验 | 回查 source_refs 与测试 | owner 明确确认 | 产物反向创造事实 |
| lint / health-check / related candidates | 解释异常 | 自动检测、打分、候选生成 | P0/冲突需批准 | 漂移、漏引用、静默损坏 |

## rejected_options

- 仅文件夹搜索：无法稳定排名、审计响应时间或支持多项目过滤。
- 仅 PostgreSQL FTS：中文分词与同义表达不足。
- 直接接云向量服务：MVP 会把甲方原文带出本地边界。
- 直接把 raw 塞入 Prompt：容易超长、无引用、受 Prompt Injection 影响。

## migration_path

当文档超过 10 万 chunks、需要多租户权限或语义召回不足时，引入生产 embedding、cross-encoder rerank、队列 worker 和行级安全策略；`EmbeddingProvider` 与 context pack Schema 保持不变。

## operational_cost

MVP 为一个本地 PostgreSQL 容器和 Python 进程；无外部模型费用。生产语义模型、备份与权限服务按实际规模增加。
