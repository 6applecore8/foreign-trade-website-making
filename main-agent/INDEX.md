# INDEX — main-agent

## 职责

主 Agent 是唯一的编排者，不直接设计大量页面内容，也不把不同 Subagent 的文件混写在一起。

## 输入

- 用户自然语言需求。
- `config/site-config.schema.json`。
- 各 Subagent 的 artifact 结果。

## 输出

- 在新 config 前调用归档工具，且仅在归档成功后开放 artifact Owner 覆盖槽位。
- 调度 5 个 Subagent。
- 最终返回：网站目录、验证状态、本地启动命令、必要的失败信息。

## 文件权限

主 Agent 可以读取全部目录；Subagent 只写自己的 `artifacts/<编号>-<名称>/` 目录。
## 不可破坏的运行归档契约

- 写入新 `config/site-config.json` **之前**，必须先成功执行 `python scripts/archive_run.py <run-id>`；归档外部旧快照时使用 `--source-root <run-root>`。
- 归档历史是 append-only：不得清空、删除或覆盖 `archive/runs/` 中任何既有运行。
- 只有归档命令成功后，各 artifacts Owner 才可覆盖自己负责的固定输出槽位；归档失败时不得写入新 config，也不得覆盖任何 artifact。
- `run-manifest.json` 保留源路径、时间戳、验证状态以及每个复制文件的字节数和 SHA-256。

## Intake 导入门禁

- `intake/` 是可选的本地前置 UI/append-only 请求存储，**不是 Agent 节点**。
- Intake 提交不能覆盖 active `config/site-config.json`；主 Agent 只导入调用方明确选定的完整请求。
- 用户必须明确给出项目根相对路径 `intake/requests/<request_id>`；不得选择或回退到 `latest`。主 Agent 必须在 archive gate **之前**，以当前 `intake/request.schema.json` 校验 `site-request.json`、以当前 `config/site-config.schema.json` 校验请求内 `site-config.json`，并检查目录/request_id 身份、必需文件、声明 size/媒体签名，以及所有项目根相对路径 resolved 后仍 containment 到选定 request 目录。
- 旧格式或任一不兼容请求必须 fail closed：返回“不可导入；请重新提交”，不写 active config、不归档推进、不派发、不迁移/补字段/修改 append-only 历史。兼容性门禁通过后，才验证 archive 命令成功、目标唯一以及 manifest 内每个归档副本的 bytes/SHA-256；然后在内存中转换、通过 schema 后才能写 active config。
- 规范 `site-request.json` 的 top-level `industry`、`site_type`、`brand` 必须分别原样映射为 `website_intent.industry`、`website_intent.site_type`、`website_intent.brand_name`；参考图不是身份或品牌事实来源。
- nested 字段为 `intake`、`website_intent`、`reference_assets`（最多 6）、`faq`、`seo`；legacy active config 仍合法。
