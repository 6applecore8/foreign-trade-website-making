# Site Intake

Vue 3 + Vite 单文件组件（SFC）桌面需求采集 UI，以及仅绑定 loopback 的 Python 保存/生产静态服务。

## 开发

在 `intake/` 安装依赖后，分别运行：

```text
python -m pip install -r requirements.txt
python server.py --port 4180
npm run dev
```

Vite 固定监听 `127.0.0.1`，并把 `/api` 代理到 `http://127.0.0.1:4180`。开发页面使用 Vite 输出的本地地址。

## 生产

```text
npm run build
python server.py --port 4180
```

打开 `http://127.0.0.1:4180/`。Python 单命令从生成的 `dist/` 服务 `/`、`/index.html` 与 Vite 哈希 `/assets/*`，不会对任意路径做 SPA fallback。每次前端变更后先重新构建。

成功提交原子发布到 `intake/requests/<request_id>/`。

页面元素批注采用固定元素 ID 白名单。用户可以选择导航、首屏、商品分类、热销产品、商品网格、商品卡片、公司介绍、FAQ、联系、页脚、颜色字体和图片风格，并为每项填写作用页面、优先级与备注。批注会同时保存到 `site-request.json.element_annotations` 和 `site-config.json.website_intent.element_annotations`，不会变成 CSS 选择器或可执行指令。

提交成功后页面显示“通知 Agent 开始运行”按钮。后端 `POST /api/runs` 只接受不可变 `request_id`，重新校验请求与配置后，才调用服务端预先配置的 Agent 命令。HTTP 请求不能传命令、参数或路径。

生产 Agent 通过环境变量配置为 JSON 字符串数组，例如：

```text
set SITE_AGENT_COMMAND_JSON=["hermes","run-intake"]
python server.py --port 4180
```

服务端会在固定命令后追加 `--intake-manifest <path>`。Manifest 将上传内容标记为 `untrusted-user-data`，限定只读请求文件与建议写入的 `runs/<run_id>`。未配置命令、不可变请求被篡改、重复启动或启动进程失败时接口会明确失败，绝不返回伪造的 running 状态。运行期 manifest/stdout/stderr 位于被 Git 忽略的 `intake/run-status/`。

## 测试

```text
npm test
python -m unittest discover -s tests -p test_*.py -v
npm run build
```

## 目录所有权

- `src/`：Vue 3 SFC 与核心 ESM 源码；`src/main.js` 是入口。
- `tests/`：Vitest/jsdom 前端合同与 Python HTTP/安全合同。
- `dist/`：Vite 生成物，由 `npm run build` 整体重建，不手工维护业务代码。
- `server.py`：生产静态分发、multipart 校验、安全上传、不可变原子发布，以及只接受服务端命令配置的 Agent 启动桥接。
- `request.schema.json`：权威请求 schema。
- `node_modules/`：本地依赖缓存，不是交付物，也不应被文档或生产服务引用。

## 限制与保证

- 最多 6 张 PNG/JPEG/GIF/WebP 参考图，每张 8 MiB；按文件内容验证。
- 可选 UTF-8 txt/json/csv SEO 文件，最大 2 MiB；请求体最大 60 MiB。
- 上传文件名、目录 traversal、非本地 Origin、symlink/junction 与 containment escape 均 fail closed。
- Publication uses same-parent staging plus a platform atomic no-replace primitive (`MoveFileW` on Windows; `renameat2(RENAME_NOREPLACE)` on Linux). If unavailable or exceptional it fails closed; every fallback must never overwrite an existing request directory.
- `site-config.json` 路径为 project-root-relative POSIX 路径，且必须存在并包含于所选不可变请求目录。
- 仅桌面合同，不包含移动适配。
