# Core module index

- `request.js` — canonical JSON request and byte-free draft builders.
- `validation.js` — client-side required/upload limits; server schema remains authoritative.
- `api.js` — POST `/api/requests` multipart contract: `payload`, `reference:<client_id>`, optional `seo_file`.
- `storage.js` — localStorage draft persistence without file bytes.
