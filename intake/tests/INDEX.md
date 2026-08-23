# Test index

- `app.test.js` — Vue SFC rendering, draft, accessibility/focus, validation, multipart submit, saving/saved/failure states, and receipt lifecycle (Vitest + jsdom).
- `request.test.js` — pure request/draft builder contracts (Vitest).
- `test_server.py` — HTTP API, schema, uploads, atomic publication, generated Vite dist delivery, traversal and symlink/junction containment security (unittest).

Run from `intake/`:

```text
npm test
python -m unittest discover -s tests -p test_*.py -v
```

`tests/.tmp/` is test-owned scratch state. Do not treat it as source or delivery content.
