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
05 validation：Runner 代码负责确定性与浏览器证据门禁，LLM 只复核可读性、风格一致性和事实风险

## 仓库内执行引擎

`orchestrator/` 会加载并校验 `workflow.json`、按拓扑顺序执行节点、通过 `AgentExecutor` 对接模型 Provider、校验声明产物、记录运行状态，并比较执行前后的全仓库文件哈希以拒绝越权写入。路径在执行前做项目根 containment 和符号链接检查；Intake 上传文本在 Provider manifest 中明确标为不可信数据。

`DeterministicValidator` 读取 config、requirements、metadata、content 和 implementation，负责文件集合、元数据、需求及内容覆盖率、引用与禁止事实检查。`BrowserEvidenceValidator` 要求截图及哈希、DOM、overflow、CTA 和 console error 证据作为运行产物持久化。`LLMReviewValidator` 只处理主观质量，不能覆盖前两层失败。

Runner 在 implementation 完成后强制调用 `BrowserEvidenceCollector`。未配置真实浏览器收集器、桌面截图缺失、标题行盒重叠、标题越出容器、横向溢出、截图哈希不一致或控制台报错时，运行会在进入 LLM Validation 前失败关闭，不能把首版交给用户。

运行执行引擎反例测试：

```text
python -m unittest discover -s orchestrator/tests -p "test_*.py" -v
```

用 Hermes 命令执行工作流（Runner 会把节点 manifest 路径追加到命令末尾）：

```text
python -m orchestrator --run-id demo hermes run-node
```

## 甲方需求文档 RAG

`rag/` 提供 PostgreSQL 16 + pgvector 的本地需求检索层。甲方 Markdown、TXT 或 JSON 文档按 SHA-256 保存为不可变原文，经过标题感知切分后写入独立 `project_key`；Main Agent 只接收带 `source_ref` 的只读 context pack，并把上传文本视为不可信数据。

```text
docker compose -f rag/docker-compose.yml up -d
python -m pip install -r rag/requirements.txt
python -m rag.cli init-db
python -m rag.cli ingest --project-key client-a --document path/to/requirements.md
python -m rag.cli build-context --project-key client-a --questions-file rag/site-questions.json --output rag-data/outputs/client-a-context.json
```

完整契约、测试和香水行业基准见 `rag/README.md`。调用方必须明确把生成的 context pack 传给 Main Agent；RAG 不会绕过 Intake、归档、Schema、目录 ACL 或浏览器证据门禁。
   ↓
主 Agent：返回结果与本地启动命令
```

## 运行约定

Windows 桌面一键打开建站需求采集页面：双击 `C:\Users\HP\Desktop\启动独立站工作流.bat`。版本化的启动逻辑位于 `scripts/start-site-intake.bat`，会启动只绑定 loopback 的 Intake 服务，并打开 `http://127.0.0.1:4180/`。该入口用于填写行业、品牌、参考资料、FAQ 与 SEO 等创建独立站所需信息，不会启动生成后的网站或覆盖 active config。只检查依赖而不启动服务时执行：

```text
scripts\start-site-intake.bat --check
```

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
- 生成的网站运行时不含登录、业务数据库、支付或后台管理；设计期 RAG 的 PostgreSQL 仅保存甲方需求证据。
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
