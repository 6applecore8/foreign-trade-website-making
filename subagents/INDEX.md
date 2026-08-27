# INDEX — subagents

本目录存放 5 个 Subagent 的执行契约（PROMPT.md）与目录索引（INDEX.md）。

## 节点速查（供主 Agent 调度时读取）

| 目录 | 节点 ID | 唯一可写目录 | 主产出 | 依赖的上游产物 |
|---|---|---|---|---|
| `01-requirements/` | 01-requirements | `artifacts/01-requirements/` | `requirements.json` | `config/site-config.json` |
| `02-metadata/` | 02-metadata | `artifacts/02-metadata/` | `metadata.json` | config + requirements |
| `03-content/` | 03-content | `artifacts/03-content/` | `home-content.json` | config + requirements |
| `04-implementation/` | 04-implementation | `artifacts/04-implementation/site/` | 4 个 HTML、`styles.css`、`site-spec.json`、6 张本地图片 | config + requirements + metadata + content |
| `05-validation/` | 05-validation | `artifacts/05-validation/` | `validation-report.json` | config + metadata + site/ |

## 调用约定

- 主 Agent 按 `01 → 02/03 → 04 → 05` 顺序派发；02 与 03 无相互依赖。
- 每个 Subagent 的详细规则以其 `PROMPT.md` 为准，INDEX 只用于快速定位。
- 任何 Subagent 都禁止写入本目录之外的路径（见各自 PROMPT.md 的权限边界表）。
- `artifacts/04-implementation/site/` 是唯一不放置 INDEX.md 的目录（契约恰好 12 个产物文件）。
