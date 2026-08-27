# INDEX — Site Workflow MVP

## 文件用途

| 路径 | 用途 | 写入者 |
|---|---|---|
| `workflow.json` | 节点、边、输入输出契约；Intake 仅作非节点前置入口 | 人工维护 / 主 Agent 读取 |
| `AGENT-HANDOFF.md` | 给 Main Agent/Subagent 的最小文件交接说明 | 人工维护 / 所有 Agent 读取 |
| `agent-context.json` | 机器可读的 Agent 文件、读写权和入口清单 | 人工维护 / 所有 Agent 读取 |
| `intake/` | 可选本地 UI 与 append-only request 快照（不是 Agent 节点） | Intake 服务（工作流只读选定请求） |
| `scripts/archive_run.py` | 运行快照的安全归档工具 | workflow-maintenance Owner |
| `archive/runs/` | append-only 历史运行快照 | 归档工具 |
| `config/site-config.schema.json` | 用户请求格式 | 人工维护 |
| `main-agent/PROMPT.md` | 主 Agent 系统提示词 | 主 Agent |
| `subagents/*/PROMPT.md` | 对应 Subagent 的系统提示词 | 对应 Subagent |
| `artifacts/01-requirements/` | 需求分析结果 | requirements Subagent |
| `artifacts/02-metadata/` | title/description/keywords | metadata Subagent |
| `artifacts/03-content/` | 首页内容 | content Subagent |
| `artifacts/04-implementation/site/` | 最终本地网站 | implementation Subagent |
| `artifacts/05-validation/` | 验证报告 | validation Subagent |

## 节点索引

1. `main-agent`：解析输入、调度、合并、输出结果。
2. `01-requirements`：只分析网站目标、受众、页面范围和 CTA。
3. `02-metadata`：只处理 HTML head 所需的 title、description、keywords。
4. `03-content`：生成首页与三个商品分类页内容，不写代码。
5. `04-implementation`：只在自己的输出目录生成静态网站文件。
6. `05-validation`：只检查 MVP 验收条件，不改其他 Agent 的文件。

## 最小输入示例

```json
{
  "project_name": "coffee-demo",
  "title": "城市咖啡馆",
  "description": "一家适合工作日午后的社区咖啡馆。",
  "keywords": ["咖啡馆", "手冲咖啡", "社区空间"],
  "language": "zh-CN",
  "user_request": "制作一个简洁、温暖的咖啡馆介绍网站"
}
```

## 超时策略

不使用固定 90 秒硬超时。使用运行平台默认值或调用方传入的节点级超时；通过缩小节点职责、限制输出数量和拆分任务来控制执行时间。

## 最小成功标准

- `site/index.html` 存在并包含正确的 `title`、`description`、`keywords`。
- `site/styles.css` 存在且被 `index.html` 引用。
- 页面只有一个首页，CTA 至少有一个明确行为。
- 不引用不存在的本地文件。
- `validation-report.json` 的 `status` 为 `passed` 或列出可操作的失败项。

## 索引豁免

`artifacts/04-implementation/site/` 为交付产物目录（契约恰好 12 文件），不放置 INDEX.md，
其说明由 `artifacts/04-implementation/INDEX.md` 承担。
## 不可破坏的运行归档契约

- 写入新 `config/site-config.json` **之前**，必须先成功执行 `python scripts/archive_run.py <run-id>`；归档外部旧快照时使用 `--source-root <run-root>`。
- 归档历史是 append-only：不得清空、删除或覆盖 `archive/runs/` 中任何既有运行。
- 只有归档命令成功后，各 artifacts Owner 才可覆盖自己负责的固定输出槽位；归档失败时不得写入新 config，也不得覆盖任何 artifact。
- `run-manifest.json` 保留源路径、时间戳、验证状态以及每个复制文件的字节数和 SHA-256。


## Intake 导航（非 Agent 节点）

`intake/` 是可选的本地需求采集入口；提交只能追加 `intake/requests/<request_id>/`。用户必须明确选择项目根相对请求目录，不能隐式选择 `latest`。Main Agent 在 archive gate 之前按当前 Schema 校验所选快照并执行路径、媒体签名与 containment 门禁；旧格式失败即返回“不可导入；请重新提交”。门禁通过且 archive gate verified 后才可导入。真实执行图仍只有上列 1 个 Main Agent + 5 个 Owner；当前 NOVA MVP 范围为桌面端 4 页面和 12 个实现文件，不加入移动端或真实交易功能。
