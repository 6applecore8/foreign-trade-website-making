# Weaving Contracts

| input_artifact | decision | target | required_evidence | reviewer | failure_mode |
|---|---|---|---|---|---|
| source digest | stay/link/promote | source archive / review / compiled wiki | source_refs + raw backlink | owner | 未确认需求污染长期知识 |
| review item | merge/contradict/defer | compiled wiki / review queue | 冲突双方引用 | owner + Agent | 静默覆盖甲方新旧要求 |
| retrieval context pack | use for task only | Agent Prompt | chunk refs + scores + fallback trace | Agent harness | 将低分结果当事实 |
| site output | suggest weave-back | review queue | 用户确认 + source_refs backcheck + tests | owner | 产物反向创造虚假需求 |

## Wiki Page Contract

- source_refs: required
- aliases: optional controlled list
- tags: controlled project vocabulary
- semantic_keywords: LLM-proposed, owner-reviewed
- related: script-generated candidates, Agent-reviewed
- relationship_types: supports / conflicts_with / supersedes / implements
- maturity: draft / reviewed / approved
- confidence: 0..1 with evidence note
- boundaries: project、run、privacy、validity period

## Output Feedback Loop

- output_is_fact_source: no
- confirmation_required: owner 明确确认“可作为后续项目经验”。
- source_refs_backcheck: 每个候选规则必须能回到原始需求或测试证据。
- update_target: review queue；批准后才进入 compiled wiki。
- review_fallback: 无法证明来源时保留在 output，不写回长期知识。
