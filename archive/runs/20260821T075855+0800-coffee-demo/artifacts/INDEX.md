# INDEX — artifacts

本目录只存放运行时产物，不存放提示词。

| 子目录 | 唯一写入者 | 主要文件 |
|---|---|---|
| `01-requirements/` | requirements | `requirements.json` |
| `02-metadata/` | metadata | `metadata.json` |
| `03-content/` | content | `home-content.json` |
| `04-implementation/` | implementation | `site/index.html`, `site/styles.css`, `site/site-spec.json` |
| `05-validation/` | validation | `validation-report.json` |

所有 JSON 都应为 UTF-8、合法 JSON。运行新任务前可清空旧 artifact，但不能在任务中途覆盖别的 Subagent 的目录。
