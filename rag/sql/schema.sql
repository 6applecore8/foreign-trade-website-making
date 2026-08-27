CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS rag_documents (
    id BIGSERIAL PRIMARY KEY,
    project_key TEXT NOT NULL,
    title TEXT NOT NULL,
    source_name TEXT NOT NULL,
    raw_path TEXT NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    authority TEXT NOT NULL DEFAULT 'client-provided',
    media_type TEXT NOT NULL,
    byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_key, content_sha256)
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    project_key TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    layer TEXT NOT NULL CHECK (layer IN ('compiled_wiki', 'source_digest', 'raw_evidence')),
    heading_path TEXT[] NOT NULL DEFAULT '{}',
    content TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    start_line INTEGER NOT NULL CHECK (start_line >= 0),
    end_line INTEGER NOT NULL CHECK (end_line >= start_line),
    token_count INTEGER NOT NULL CHECK (token_count > 0),
    embedding vector(384) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, layer, ordinal)
);

CREATE TABLE IF NOT EXISTS rag_source_digests (
    document_id BIGINT PRIMARY KEY REFERENCES rag_documents(id) ON DELETE CASCADE,
    project_key TEXT NOT NULL,
    digest_json JSONB NOT NULL,
    raw_backlink TEXT NOT NULL,
    promotion_decision TEXT NOT NULL DEFAULT 'stay_in_source',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS rag_chunks_project_layer_idx
    ON rag_chunks (project_key, layer);
CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS rag_chunks_content_trgm_idx
    ON rag_chunks USING gin (content gin_trgm_ops);
