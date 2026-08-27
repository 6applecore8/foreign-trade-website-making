from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class RagConfig:
    dsn: str = os.environ.get(
        "RAG_DSN",
        "postgresql://rag_user:rag_local_only@127.0.0.1:55433/site_workflow_rag",
    )
    data_dir: Path = Path(os.environ.get("RAG_DATA_DIR", PROJECT_ROOT / "rag-data"))
    embedding_dimension: int = 384
    target_chunk_chars: int = 760
    max_chunk_chars: int = 980
    overlap_chars: int = 120
    top_k: int = 5
    vector_weight: float = 0.78
    lexical_weight: float = 0.22

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def digest_dir(self) -> Path:
        return self.data_dir / "digests"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "outputs"

    def ensure_runtime_dirs(self) -> None:
        for directory in (self.raw_dir, self.digest_dir, self.output_dir):
            directory.mkdir(parents=True, exist_ok=True)
