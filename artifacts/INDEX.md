# INDEX — artifacts

本目录只存放运行时产物，不存放提示词。

| 子目录 | 唯一写入者 | 主要文件 |
|---|---|---|
| `01-requirements/` | requirements | `requirements.json` |
| `02-metadata/` | metadata | `metadata.json` |
| `03-content/` | content | `home-content.json` |
| `04-implementation/` | implementation | 4 个 HTML、`site/styles.css`、`site/site-spec.json`、6 张本地图片 |
| `05-validation/` | validation | `validation-report.json` |

所有 JSON 都应为 UTF-8、合法 JSON。不得清空或删除运行历史。开始新任务前必须先成功归档旧运行；归档成功后，每个 Subagent 才可覆盖自己拥有的 artifact 固定槽位，且不能覆盖别的 Subagent 的目录。
## 不可破坏的运行归档契约

- 写入新 `config/site-config.json` **之前**，必须先成功执行 `python scripts/archive_run.py <run-id>`；归档外部旧快照时使用 `--source-root <run-root>`。
- 归档历史是 append-only：不得清空、删除或覆盖 `archive/runs/` 中任何既有运行。
- 只有归档命令成功后，各 artifacts Owner 才可覆盖自己负责的固定输出槽位；归档失败时不得写入新 config，也不得覆盖任何 artifact。
- `run-manifest.json` 保留源路径、时间戳、验证状态以及每个复制文件的字节数和 SHA-256。
