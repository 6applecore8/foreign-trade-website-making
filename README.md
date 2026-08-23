# Site Workflow MVP

一个“主 Agent + Subagent”自动创建本地静态网站的最小可行工作流。

## MVP 目标

- 只生成本地可运行的网站，不做公共部署。
- 用户可以自由指定 `title`、`description`、`keywords`。
- 主 Agent 只负责调度、传递 JSON 和汇总结果。
- 每个 Subagent 只拥有自己的工作目录，避免互相覆盖文件。
- 节点之间通过 `artifacts/` 中的 JSON 文件交接，不依赖数据库。
- 首版只生成 `index.html`、`styles.css` 和 `site-spec.json`。

## 目录约束

```text
site-workflow-mvp/
├─ INDEX.md
├─ README.md
├─ workflow.json
├─ scripts/
│  ├─ INDEX.md
│  └─ archive_run.py
├─ archive/
│  ├─ INDEX.md
│  └─ runs/
│     └─ INDEX.md
├─ intake/                 # 可选本地前置 UI/append-only 请求存储（不是 Agent 节点）
├─ config/
│  ├─ INDEX.md
│  └─ site-config.schema.json
├─ main-agent/
│  ├─ INDEX.md
│  └─ PROMPT.md
├─ subagents/
│  ├─ 01-requirements/
│  │  ├─ INDEX.md
│  │  └─ PROMPT.md
│  ├─ 02-metadata/
│  │  ├─ INDEX.md
│  │  └─ PROMPT.md
│  ├─ 03-content/
│  │  ├─ INDEX.md
│  │  └─ PROMPT.md
│  ├─ 04-implementation/
│  │  ├─ INDEX.md
│  │  └─ PROMPT.md
│  └─ 05-validation/
│     ├─ INDEX.md
│     └─ PROMPT.md
└─ artifacts/
   ├─ INDEX.md
   ├─ 01-requirements/
   ├─ 02-metadata/
   ├─ 03-content/
   ├─ 04-implementation/
   └─ 05-validation/
```

## 执行顺序

```text
用户输入 ──可选→ Intake UI（工作流外；只追加 request，不写 active config）
                         ↓ 明确选择 request + 当前 Schema/完整性门禁 + archive gate verified
   ↓
主 Agent：校验并拆分需求
   ↓
01 requirements ──┐
02 metadata ───────┼─→ 主 Agent 汇总 site-spec
03 content ────────┘
   ↓
04 implementation：写本地网站文件
   ↓
05 validation：检查元数据、文件、引用和本地运行条件
   ↓
主 Agent：返回结果与本地启动命令
```

## 运行约定

1. 可直接使用 legacy 自然语言输入；若使用 Intake，提交只写 `intake/requests/<request_id>/`。用户必须明确选择项目根相对请求目录，不得隐式选择 `latest`。主 Agent 在归档旧运行之前，先按当前 `intake/request.schema.json`/`config/site-config.schema.json` 校验所选快照，并验证目录身份、必需文件、size/签名及路径 containment；旧格式必须 fail closed，提示“不可导入；请重新提交”，且不写 active config、不派发、不迁移或修改历史。该门禁和 archive gate 均通过后，才把候选配置导入 active `config/site-config.json`。Intake UI 不是 Agent 节点。
2. 每个 Subagent 读取前置 artifact，但只能写自己的 artifact 子目录。
3. 实现 Subagent 生成网站到 `artifacts/04-implementation/site/`。
4. 验证 Subagent 生成 `artifacts/05-validation/validation-report.json`。
5. 验证通过后，在工作流根目录执行：

```bash
python -m http.server 4173 --directory artifacts/04-implementation/site
```

然后打开 `http://localhost:4173`。

## 超时策略

本 MVP **取消固定 90 秒硬超时限制**。具体超时由实际运行平台或调用方配置决定；工作流通过限制每个节点的职责、输出数量和文件范围来降低超时风险。节点超时必须返回失败状态和可操作原因，不得伪造成功结果。

## MVP 明确不做

- 公网部署、域名、HTTPS、云存储。
- 登录、数据库、支付、后台管理。
- 图片生成与外部 API 集成。
- 多页面路由和复杂 SPA 架构。
- 自动反复修复循环。验证失败时只返回明确错误列表。
## 不可破坏的运行归档契约

- 写入新 `config/site-config.json` **之前**，必须先成功执行 `python scripts/archive_run.py <run-id>`；归档外部旧快照时使用 `--source-root <run-root>`。
- 归档历史是 append-only：不得清空、删除或覆盖 `archive/runs/` 中任何既有运行。
- 只有归档命令成功后，各 artifacts Owner 才可覆盖自己负责的固定输出槽位；归档失败时不得写入新 config，也不得覆盖任何 artifact。
- `run-manifest.json` 保留源路径、时间戳、验证状态以及每个复制文件的字节数和 SHA-256。


## Intake 向后兼容字段

Schema 可选支持 `intake`、`website_intent`、`reference_assets`（最多 6）、`faq` 与 `seo`；不提供时沿用现有 config。规范 Intake 的 top-level `industry`/`site_type`/`brand` 在 archive gate verified 后分别保真导入 `website_intent.industry`/`site_type`/`brand_name`，参考图不能作为身份或品牌事实。SEO 按字段采用 `nested explicit > imported source_document > legacy top-level > generated default`。自定义 FAQ 保持顺序，未知答案为 `待补充`；行业默认 FAQ 只是模板，不代表竞品或市场研究。引用资产只能按声明用途使用真实存在的项目相对本地文件，且不增加单页/3 实现文件限制。
