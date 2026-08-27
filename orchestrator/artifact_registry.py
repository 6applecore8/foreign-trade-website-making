from __future__ import annotations

import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ArtifactRegistry:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def receipt_hashes(self, paths: list[Path]) -> dict[str, str]:
        return {path.resolve().relative_to(self.root).as_posix(): sha256(path) for path in paths if path.is_file()}
