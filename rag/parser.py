from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from .config import RagConfig
from .types import ParsedDocument


SUPPORTED_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
}
MAX_SOURCE_BYTES = 5 * 1024 * 1024


def parse_and_preserve(path: str | Path, config: RagConfig) -> ParsedDocument:
    candidate = Path(path).absolute()
    if _contains_symlink(candidate):
        raise ValueError("source path must not contain symlinks")
    source = candidate.resolve(strict=True)
    if not source.is_file():
        raise ValueError("source must be a regular, non-symlink file")
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported source type: {suffix or '<none>'}")

    raw = source.read_bytes()
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    if b"\x00" in raw:
        raise ValueError("binary/NUL-containing source is not accepted")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source must be UTF-8") from exc

    if suffix == ".json":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON source") from exc
        text = json.dumps(parsed, ensure_ascii=False, indent=2)

    digest = hashlib.sha256(raw).hexdigest()
    config.ensure_runtime_dirs()
    target_dir = config.raw_dir / digest
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError("immutable raw target exists with a different hash")
    else:
        shutil.copyfile(source, target)

    title = _infer_title(text, source.stem)
    return ParsedDocument(
        title=title,
        source_name=source.name,
        raw_path=target,
        content=text.replace("\r\n", "\n").replace("\r", "\n"),
        content_sha256=digest,
        media_type=SUPPORTED_TYPES[suffix],
        byte_size=len(raw),
    )


def _infer_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def _contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.exists() and current.is_symlink():
            return True
        if current.parent == current:
            return False
        current = current.parent
