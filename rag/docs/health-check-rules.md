# Health Check Rules

## triggers

- 数据库启动、Schema migration、文档摄取、benchmark、工作流 dispatch 前、检索低分或无命中时。

## P0

- PostgreSQL/vector 扩展不可用；raw 哈希不一致；source_ref 缺失；路径逃逸；跨 project_key 泄漏；输出自动写 active config。
- 处理: fail closed，不派发建站 Agent。

## P1

- chunk 超过上限、重复 chunk、top-3 未命中验收证据、p95 超过 300ms、digest 没有 promotion decision。
- 处理: 写 fix queue，允许人工复核后重试，不宣告 RAG 可用。

## P2

- 标题层级不完整、低价值短 chunk、词汇表覆盖不足、未使用的 metadata。
- 处理: 记录优化建议，不阻塞已有高置信度结果。

## auto_detectable

- DB/extension/schema、文件 SHA、UTF-8、路径 containment、chunk 数量与长度、引用字段、project 过滤、响应时间、expected substring 命中。

## agent_review_required

- 检索结果是否完整回答需求、两个文档是否冲突、claim 是否可跨项目复用、低分结果是否仍有业务价值。

## owner_approval_required

- 将需求提升到 Compiled Wiki、覆盖旧规则、公开分享、引入云模型、将输出回写为长期经验。

## fix_queue

- P0 立即修复并重新全测；P1 在下一次 dispatch 前清理；P2 可按检索日志批量迭代。
