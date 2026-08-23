# Site Intake

Vue 3 + Vite 单文件组件（SFC）桌面需求采集 UI，以及仅绑定 loopback 的 Python 保存/生产静态服务。

## 开发

在 `intake/` 安装依赖后，分别运行：

```text
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
- `server.py`：生产静态分发、multipart 校验、安全上传与不可变原子发布。
- `request.schema.json`：权威请求 schema。
- `node_modules/`：本地依赖缓存，不是交付物，也不应被文档或生产服务引用。

## 限制与保证

- 最多 6 张 PNG/JPEG/GIF/WebP 参考图，每张 8 MiB；按文件内容验证。
- 可选 UTF-8 txt/json/csv SEO 文件，最大 2 MiB；请求体最大 60 MiB。
- 上传文件名、目录 traversal、非本地 Origin、symlink/junction 与 containment escape 均 fail closed。
- Publication uses same-parent staging plus a platform atomic no-replace primitive (`MoveFileW` on Windows; `renameat2(RENAME_NOREPLACE)` on Linux). If unavailable or exceptional it fails closed; every fallback must never overwrite an existing request directory.
- `site-config.json` 路径为 project-root-relative POSIX 路径，且必须存在并包含于所选不可变请求目录。
- 仅桌面合同，不包含移动适配。
