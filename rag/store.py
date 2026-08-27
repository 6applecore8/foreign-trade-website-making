from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .config import RagConfig
from .embeddings import vector_literal
from .types import Chunk, ParsedDocument, RetrievalHit


class PostgresRagStore:
    def __init__(self, config: RagConfig) -> None:
        self.config = config

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required; run: python -m pip install -r rag/requirements.txt"
            ) from exc
        return psycopg.connect(self.config.dsn)

    def initialize(self) -> None:
        schema = (Path(__file__).parent / "sql" / "schema.sql").read_text(encoding="utf-8")
        with self._connect() as connection:
            connection.execute(schema)

    def health(self) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT current_database(), current_setting('server_version'),
                       EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector'),
                       EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'),
                       EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rag_chunks')
                """
            ).fetchone()
        return {
            "database": row[0],
            "postgres_version": row[1],
            "vector_extension": row[2],
            "pg_trgm_extension": row[3],
            "schema_ready": row[4],
        }

    def replace_document(
        self,
        project_key: str,
        document: ParsedDocument,
        chunks: Sequence[Chunk],
        embeddings: Sequence[Sequence[float]],
        digest: dict[str, object],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO rag_documents
                    (project_key, title, source_name, raw_path, content_sha256, media_type, byte_size)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_key, content_sha256) DO UPDATE SET
                    title = EXCLUDED.title,
                    source_name = EXCLUDED.source_name,
                    raw_path = EXCLUDED.raw_path,
                    media_type = EXCLUDED.media_type,
                    byte_size = EXCLUDED.byte_size,
                    ingested_at = now()
                RETURNING id
                """,
                (
                    project_key,
                    document.title,
                    document.source_name,
                    str(document.raw_path),
                    document.content_sha256,
                    document.media_type,
                    document.byte_size,
                ),
            ).fetchone()
            document_id = int(row[0])
            connection.execute("DELETE FROM rag_chunks WHERE document_id = %s", (document_id,))
            for chunk, vector in zip(chunks, embeddings):
                connection.execute(
                    """
                    INSERT INTO rag_chunks
                        (document_id, project_key, ordinal, layer, heading_path, content,
                         source_ref, start_line, end_line, token_count, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s::jsonb)
                    """,
                    (
                        document_id,
                        project_key,
                        chunk.ordinal,
                        chunk.layer,
                        list(chunk.heading_path),
                        chunk.content,
                        chunk.source_ref,
                        chunk.start_line,
                        chunk.end_line,
                        chunk.token_count,
                        vector_literal(vector),
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    ),
                )
            connection.execute(
                """
                INSERT INTO rag_source_digests
                    (document_id, project_key, digest_json, raw_backlink, promotion_decision)
                VALUES (%s, %s, %s::jsonb, %s, 'stay_in_source')
                ON CONFLICT (document_id) DO UPDATE SET
                    digest_json = EXCLUDED.digest_json,
                    raw_backlink = EXCLUDED.raw_backlink,
                    promotion_decision = 'stay_in_source',
                    created_at = now()
                """,
                (
                    document_id,
                    project_key,
                    json.dumps(digest, ensure_ascii=False),
                    str(document.raw_path),
                ),
            )
        return document_id

    def search(
        self,
        project_key: str,
        query: str,
        query_vector: Sequence[float],
        layers: Sequence[str],
        top_k: int,
    ) -> list[RetrievalHit]:
        candidate_limit = max(20, top_k * 5)
        vector = vector_literal(query_vector)
        sql = """
            WITH vector_candidates AS (
                SELECT id FROM rag_chunks
                WHERE project_key = %s AND layer = ANY(%s)
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            ), lexical_candidates AS (
                SELECT id FROM rag_chunks
                WHERE project_key = %s AND layer = ANY(%s)
                ORDER BY similarity(content, %s) DESC
                LIMIT %s
            ), candidate_ids AS (
                SELECT id FROM vector_candidates
                UNION
                SELECT id FROM lexical_candidates
            )
            SELECT c.id, c.document_id, d.title, c.layer, c.heading_path, c.content,
                   c.source_ref,
                   GREATEST(0, 1 - (c.embedding <=> %s::vector)) AS vector_score,
                   GREATEST(0, similarity(c.content, %s)) AS lexical_score,
                   (%s * GREATEST(0, 1 - (c.embedding <=> %s::vector)) +
                    %s * GREATEST(0, similarity(c.content, %s))) AS score
            FROM candidate_ids x
            JOIN rag_chunks c ON c.id = x.id
            JOIN rag_documents d ON d.id = c.document_id
            ORDER BY score DESC, c.id ASC
            LIMIT %s
        """
        params = (
            project_key,
            list(layers),
            vector,
            candidate_limit,
            project_key,
            list(layers),
            query,
            candidate_limit,
            vector,
            query,
            self.config.vector_weight,
            vector,
            self.config.lexical_weight,
            query,
            top_k,
        )
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [
            RetrievalHit(
                chunk_id=int(row[0]),
                document_id=int(row[1]),
                title=row[2],
                layer=row[3],
                heading_path=tuple(row[4]),
                content=row[5],
                source_ref=row[6],
                vector_score=float(row[7]),
                lexical_score=float(row[8]),
                score=float(row[9]),
            )
            for row in rows
        ]

    def delete_project(self, project_key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM rag_documents WHERE project_key = %s", (project_key,))
