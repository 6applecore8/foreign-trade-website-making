from __future__ import annotations

import re
from dataclasses import dataclass

from .types import Chunk, ParsedDocument


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SENTENCE_RE = re.compile(r"(?<=[。！？；.!?;])")


@dataclass(frozen=True)
class _Block:
    heading_path: tuple[str, ...]
    text: str
    start_line: int
    end_line: int


def chunk_document(
    document: ParsedDocument,
    target_chars: int = 760,
    max_chars: int = 980,
    overlap_chars: int = 120,
) -> list[Chunk]:
    if not (0 < overlap_chars < target_chars <= max_chars):
        raise ValueError("chunk size settings must satisfy 0 < overlap < target <= max")
    blocks = _markdown_blocks(document.content, max_chars=max_chars)
    chunks: list[Chunk] = []
    current: list[_Block] = []
    current_path: tuple[str, ...] = ()

    def flush() -> None:
        nonlocal current
        if not current:
            return
        chunks.append(_make_chunk(document, len(chunks), current))
        current = []

    for block in blocks:
        if current and block.heading_path != current_path:
            flush()
        current_path = block.heading_path
        prospective = current + [block]
        if current and len(_render(prospective)) > max_chars:
            previous = current[-1]
            flush()
            overlap = _overlap_block(previous, overlap_chars)
            if overlap is not None and len(_render([overlap, block])) <= max_chars:
                current = [overlap]
        current.append(block)
        if len(_render(current)) >= target_chars:
            flush()
    flush()
    return chunks


def _markdown_blocks(text: str, max_chars: int) -> list[_Block]:
    lines = text.splitlines()
    heading_stack: list[str] = []
    blocks: list[_Block] = []
    paragraph: list[str] = []
    paragraph_start = 1

    def emit(end_line: int) -> None:
        nonlocal paragraph
        body = "\n".join(paragraph).strip()
        if body:
            for part in _split_long_text(body, max_chars=max_chars - 80):
                blocks.append(
                    _Block(tuple(heading_stack), part, paragraph_start, end_line)
                )
        paragraph = []

    for index, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            emit(index - 1)
            level = len(match.group(1))
            heading_stack[:] = heading_stack[: level - 1]
            heading_stack.append(match.group(2).strip())
            continue
        if not line.strip():
            emit(index - 1)
            continue
        if not paragraph:
            paragraph_start = index
        paragraph.append(line.rstrip())
    emit(len(lines))
    return blocks


def _split_long_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = [item for item in SENTENCE_RE.split(text) if item]
    if len(sentences) == 1:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
    result: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > max_chars:
            result.append(current.strip())
            current = ""
        while len(sentence) > max_chars:
            result.append(sentence[:max_chars].strip())
            sentence = sentence[max_chars:]
        current += sentence
    if current.strip():
        result.append(current.strip())
    return result


def _overlap_block(block: _Block, limit: int) -> _Block | None:
    if not block.text:
        return None
    text = block.text[-limit:].lstrip()
    if not text:
        return None
    return _Block(block.heading_path, text, block.start_line, block.end_line)


def _render(blocks: list[_Block]) -> str:
    if not blocks:
        return ""
    path = blocks[0].heading_path
    # The H1 document title is common to every section and harms ranking if it is
    # repeated in every vector. Keep the specific section path in retrievable text.
    visible_path = path[1:] if len(path) > 1 else path
    heading = " > ".join(visible_path)
    body = "\n\n".join(item.text for item in blocks)
    return f"{heading}\n{body}" if heading else body


def _make_chunk(document: ParsedDocument, ordinal: int, blocks: list[_Block]) -> Chunk:
    content = _render(blocks)
    start_line = min(item.start_line for item in blocks)
    end_line = max(item.end_line for item in blocks)
    return Chunk(
        ordinal=ordinal,
        layer="raw_evidence",
        heading_path=blocks[0].heading_path,
        content=content,
        source_ref=f"{document.source_name}#L{start_line}-L{end_line}",
        start_line=start_line,
        end_line=end_line,
        token_count=max(1, len(content)),
        metadata={"content_sha256": document.content_sha256},
    )
