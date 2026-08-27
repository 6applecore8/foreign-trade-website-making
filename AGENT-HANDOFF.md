# Agent 交接入口

## 先说结论

工作空间里的文件**不是全部同时执行**。当前仓库包含工作流规则、Agent 提示词、输入数据、节点产物、Intake 前端源码、测试、构建文件和历史归档。

当前项目已有仓库内置的、Provider 中立的 AgentRunner。`workflow.json` 是可执行工作流合同；Hermes Agent 通过 adapter 接入，不再承担仓库唯一的调度职责。

给其他 Agent 时，优先让它读取机器清单 `agent-context.json`，再按自己承担的角色读取下列最小文件集。不要把整个工作空间全部塞进上下文。

## 真正参与 Agent 工作流的核心文件

| 文件 | 作用 |
|---|---|
| `workflow.json` | 节点、依赖关系、读写范围与工作流限制 |
| `orchestrator/` | 图校验、节点调度、Provider 接口、强制路径权限、状态与三层验证 |
| `main-agent/PROMPT.md` | Main Agent 的调度和失败关闭规则 |
| `subagents/*/PROMPT.md` | 5 个 Subagent 各自的执行提示词 |
| `config/site-config.json` | 当前一次建站任务的活动输入 |
| `config/site-config.schema.json` | 活动输入的数据合同 |
| `scripts/archive_run.py` | 新运行覆盖固定产物前的归档门禁 |
| `artifacts/**` | 各 Agent 的当前输入/输出交接文件 |

## 每个 Agent 应读取的最小文件

### Main Agent

```text
agent-context.json
workflow.json
main-agent/PROMPT.md
config/site-config.schema.json
config/site-config.json
scripts/archive_run.py
artifacts/**
```

如果任务来自需求采集页，还需读取用户明确选中的：

```text
intake/request.schema.json
intake/requests/<selected_request_id>/site-request.json
intake/requests/<selected_request_id>/site-config.json
intake/requests/<selected_request_id>/references/**
intake/requests/<selected_request_id>/seo/**
```

### Requirements Agent

```text
subagents/01-requirements/PROMPT.md
config/site-config.json
```

只允许写：

```text
artifacts/01-requirements/requirements.json
```

### Metadata Agent

```text
subagents/02-metadata/PROMPT.md
config/site-config.json
artifacts/01-requirements/requirements.json
```

只允许写：

```text
artifacts/02-metadata/metadata.json
```

### Content Agent

```text
subagents/03-content/PROMPT.md
config/site-config.json
artifacts/01-requirements/requirements.json
```

只允许写：

```text
artifacts/03-content/home-content.json
```

### Implementation Agent

```text
subagents/04-implementation/PROMPT.md
config/site-config.json
artifacts/01-requirements/requirements.json
artifacts/02-metadata/metadata.json
artifacts/03-content/home-content.json
```

只允许写 12 个交付文件：

```text
artifacts/04-implementation/site/index.html
artifacts/04-implementation/site/shoes.html
artifacts/04-implementation/site/apparel.html
artifacts/04-implementation/site/looks.html
artifacts/04-implementation/site/styles.css
artifacts/04-implementation/site/site-spec.json
artifacts/04-implementation/site/hero-campaign.png
artifacts/04-implementation/site/product-footwear.png
artifacts/04-implementation/site/product-apparel.png
artifacts/04-implementation/site/catalog-shoes.png
artifacts/04-implementation/site/catalog-apparel.png
artifacts/04-implementation/site/catalog-looks.png
```

### Validation Agent

```text
subagents/05-validation/PROMPT.md
config/site-config.json
artifacts/01-requirements/requirements.json
artifacts/02-metadata/metadata.json
artifacts/03-content/home-content.json
artifacts/04-implementation/site/**
```

只允许写：

```text
artifacts/05-validation/validation-report.json
```

## 其他目录为什么存在

| 目录 | 是否为 Agent 核心输入 | 说明 |
|---|---:|---|
| `intake/src/` | 否 | Vue 需求采集页面源码，仅开发 Intake 时使用 |
| `intake/dist/` | 否 | Vue 构建产物，由 Python 服务提供给浏览器 |
| `intake/server.py` | 否 | 本地需求采集 HTTP 服务，不是 Agent 节点 |
| `intake/requests/` | 条件读取 | 客户历史提交；Main Agent 只读取被明确选中的一个请求 |
| `intake/tests/` | 否 | Intake 自动化测试 |
| `main-agent/tests/` | 否 | Main Agent 合同测试 |
| `archive/runs/` | 否 | 历史运行快照，默认不应作为新任务输入 |
| `screenshots/` | 否 | 项目展示截图 |
| `*/INDEX.md` | 导航用 | 帮助 Agent 和开发者理解目录，不执行任务 |
| `package-lock.json` | 否 | 锁定前端开发依赖版本 |
| `server-4180.log` | 否 | 运行日志，不应交给业务 Agent |
| `node_modules/` | 否 | 第三方依赖，绝不能塞进 Agent 上下文 |

## 推荐交接方式

不要说“读取整个项目”。应给每个 Agent：

1. 它自己的 `PROMPT.md`；
2. 上表列出的最小输入文件；
3. 唯一允许写入的目标路径；
4. 完成后返回状态、产物路径和错误；
5. 由 Main Agent 在当前磁盘重新校验，不直接相信口头成功声明。
