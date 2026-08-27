from __future__ import annotations

import json
import time
from pathlib import Path

from .chunker import chunk_document
from .config import RagConfig
from .embeddings import DeterministicFeatureEmbedding, EmbeddingProvider
from .parser import parse_and_preserve
from .store import PostgresRagStore
from .types import Chunk, ContextPack


class RagPipeline:
    def __init__(
        self,
        config: RagConfig | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        store: PostgresRagStore | None = None,
    ) -> None:
        self.config = config or RagConfig()
        self.embedding_provider = embedding_provider or DeterministicFeatureEmbedding(
            self.config.embedding_dimension
        )
        if self.embedding_provider.dimension != self.config.embedding_dimension:
            raise ValueError("embedding provider dimension does not match PostgreSQL schema")
        self.store = store or PostgresRagStore(self.config)

    def initialize(self) -> None:
        self.config.ensure_runtime_dirs()
        self.store.initialize()

    def ingest(self, project_key: str, source_path: str | Path) -> dict[str, object]:
        _validate_project_key(project_key)
        document = parse_and_preserve(source_path, self.config)
        chunks = chunk_document(
            document,
            target_chars=self.config.target_chunk_chars,
            max_chars=self.config.max_chunk_chars,
            overlap_chars=self.config.overlap_chars,
        )
        if not chunks:
            raise ValueError("source contains no retrievable text")
        digest = _structural_digest(document, chunks)
        digest_path = self.config.digest_dir / f"{document.content_sha256}.json"
        digest_path.write_text(
            json.dumps(digest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        embeddings = self.embedding_provider.embed([chunk.content for chunk in chunks])
        document_id = self.store.replace_document(
            project_key, document, chunks, embeddings, digest
        )
        return {
            "project_key": project_key,
            "document_id": document_id,
            "title": document.title,
            "content_sha256": document.content_sha256,
            "raw_path": str(document.raw_path),
            "digest_path": str(digest_path),
            "chunk_count": len(chunks),
            "status": "ingested",
        }

    def ask(self, project_key: str, query: str, top_k: int | None = None) -> ContextPack:
        _validate_project_key(project_key)
        if not query.strip():
            raise ValueError("query must not be empty")
        started = time.perf_counter()
        vector = self.embedding_provider.embed([query])[0]
        fallback_trace: list[dict[str, object]] = []
        selected = None
        results = []
        plan = (
            ("compiled_wiki", 0.68),
            ("source_digest", 0.90),
            ("raw_evidence", 0.0),
        )
        for layer, threshold in plan:
            hits = self.store.search(
                project_key, query, vector, [layer], top_k or self.config.top_k
            )
            top_score = hits[0].score if hits else None
            accepted = bool(hits and top_score is not None and top_score >= threshold)
            fallback_trace.append(
                {
                    "layer": layer,
                    "hits": len(hits),
                    "top_score": round(top_score, 6) if top_score is not None else None,
                    "threshold": threshold,
                    "accepted": accepted,
                }
            )
            if accepted:
                selected = layer
                results = hits
                break
        elapsed_ms = (time.perf_counter() - started) * 1000
        return ContextPack(
            project_key=project_key,
            query=query,
            selected_layer=selected,
            fallback_trace=tuple(fallback_trace),
            results=tuple(results),
            retrieval_ms=elapsed_ms,
        )


def _structural_digest(document, chunks: list[Chunk]) -> dict[str, object]:
    headings: list[str] = []
    for chunk in chunks:
        label = " > ".join(chunk.heading_path)
        if label and label not in headings:
            headings.append(label)
    return {
        "schema_version": "1.0",
        "title": document.title,
        "source_name": document.source_name,
        "content_sha256": document.content_sha256,
        "raw_backlink": str(document.raw_path),
        "headings": headings,
        "chunk_count": len(chunks),
        "promotion_decision": "stay_in_source",
        "notes": "结构性摘要，不替代原文，不推断未写明事实。",
    }


def _validate_project_key(value: str) -> None:
    if not value or len(value) > 80:
        raise ValueError("project_key length must be 1..80")
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in value):
        raise ValueError("project_key may contain only letters, numbers, '-' and '_'")
