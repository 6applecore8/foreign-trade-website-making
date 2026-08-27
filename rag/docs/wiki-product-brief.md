# Wiki Product Brief

## users

- primary: 为甲方制作独立站的项目运营者与 Main Agent。
- secondary: 上传需求文档并复核识别结果的甲方负责人、验收人员。

## problem

甲方需求常分散在 Markdown、文本或 JSON 文档中。若直接把整份文档塞进 Prompt，容易超长、漏读、受文档内伪指令干扰，也无法说明页面需求来自哪一段原文。系统需要先保存原始证据，再生成可追溯的检索上下文，供 Requirements、Content 和 Implementation 节点使用。

## inputs

- MVP: UTF-8 Markdown、TXT、JSON 需求文档。
- metadata: project_key、owner、authority、文件名、SHA-256、摄取时间。
- query: 建站节点针对目标用户、页面、商品、风格、FAQ、业务边界提出的问题。

## processing

`immutable raw -> section-aware chunks -> deterministic embedding -> PostgreSQL/pgvector hybrid retrieval -> cited context pack`。摄取时另生成结构性 source digest；脚本只做解析、切分、向量化、检索和校验，不替代 LLM 的需求理解与页面决策。

## outputs

- 带 `source_refs`、分数、回退轨迹和响应时间的 retrieval context pack。
- 原始文档清单、结构性 source digest、数据库健康状态。
- 可交给 Main Agent 的 JSON 上下文，不直接覆盖 active config 或网站产物。

## non_goals

- MVP 不做 OCR、DOCX/PDF 解析、权限系统、在线协作或公共部署。
- 不把上传文档中的句子当系统指令。
- 不凭检索结果编造价格、资质、功效、库存或企业事实。
- 不让输出自动回写长期知识或 active config。

## success_criteria

- 香水行业测试文档的 5 个验收问题均在 top-3 结果中命中预期证据。
- 小型单文档基准的 PostgreSQL 检索 p95 小于 300ms（不含外部 LLM 生成时间）。
- 每个结果包含文件 SHA、行号范围和 chunk id。
- 四层安全门禁通过：Schema、路径 containment、原文哈希、引用回查。

## constraints

- privacy: 项目本地边界，原文不发送到第三方 Embedding 服务。
- database: PostgreSQL 16 + pgvector 0.8.6，localhost 测试端口 55433。
- runtime: Python 3.10+、Psycopg 3；Embedding Provider 可替换。
- maintenance: 单机 MVP，后续才考虑队列、对象存储和租户权限。
