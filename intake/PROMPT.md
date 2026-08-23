# Intake handoff prompt

## Runtime handoff

The intake editor is implemented as Vue 3 + Vite single-file components under `intake/src/`. For development run `python intake/server.py --port 4180` and `npm run dev` from `intake/`; Vite proxies `/api` to the loopback Python service. For production run `npm run build` first, then `python intake/server.py --port 4180`; the server safely serves only the generated `intake/dist/` index and hashed assets plus the existing API. `dist/` is generated output owned by the Vite build. `node_modules/` is never a delivery artifact.

## Generation contract

Use `site-request.json` as submitted facts and `site-config.json` as the normalized generation input. Do not invent business facts. FAQ answers marked `待补充` are unresolved placeholders, not approved claims. Preserve the user's required-section order, custom FAQ order, image purposes and notes, explicit SEO title/description/keywords, and uploaded SEO source path.

Path anchors are artifact-specific:

1. In `site-request.json`, upload paths such as `reference_assets[].stored_path` (emitted as `references[].stored_path`) and `seo.source_document.stored_path` (emitted under `seo.upload.stored_path`) are relative to the immutable request directory.
2. In the `site-config.json` projection, each path is a project-root-relative POSIX path (relative to the project root), for example `intake/requests/<request_id>/references/01-hero.png`.

A consumer must resolve each path using the anchor defined by its containing artifact. A project-root-relative `site-config.json` path must not be joined to the request directory again. Fail closed unless the resolved path exists and is contained within the selected immutable `intake/requests/<request_id>/` directory.

Keep request publication as same-parent staging plus a platform atomic no-replace primitive. If that primitive is unavailable or raises an exception, fail closed; any fallback must never overwrite an existing request directory.

Generate a desktop site only; mobile adaptation is outside this intake contract.
