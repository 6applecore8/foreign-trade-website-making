# Source Digest Contracts

| digest_artifact | source_refs | reusable_claims | promotion_decision | review_rule | raw_backlink |
|---|---|---|---|---|---|
| requirement-structure-digest | 原始文档 SHA、raw path、heading 行号 | MVP 仅记录标题、章节清单和文档身份；不自动生成事实声明 | stay_in_source | 甲方确认后才能把稳定规则提升为 wiki | `rag-data/raw/<sha>/<name>:Lx-Ly` |
| reviewed-requirement-claim | digest id + 精确 chunk refs | 经甲方确认的目标用户、页面、商品数量、业务边界 | promote_to_wiki 或 route_to_review | 高影响字段需 owner 批准 | chunk source_ref |

## Promotion Outcomes

- promote_to_wiki: 稳定、跨运行复用、证据完整且 owner 确认。
- route_to_review: 有用但冲突、模糊或会影响价格、合规、品牌事实。
- stay_in_source: 项目局部需求、一次性文档或仅用于当前站点。

## Notes

结构性 digest 不冒充语义摘要。语义 claims 由 LLM 提议、脚本校验引用、人工决定去向。
