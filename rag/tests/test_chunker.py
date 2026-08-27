from pathlib import Path
import unittest

from rag.chunker import chunk_document
from rag.types import ParsedDocument


class ChunkerTests(unittest.TestCase):
    def _document(self, content: str) -> ParsedDocument:
        return ParsedDocument(
            title="test",
            source_name="test.md",
            raw_path=Path("test.md"),
            content=content,
            content_sha256="0" * 64,
            media_type="text/markdown",
            byte_size=len(content.encode("utf-8")),
        )

    def test_heading_boundaries_are_not_mixed(self):
        document = self._document(
            "# 需求\n\n## 页面\n\n" + "分类页面内容。" * 130 + "\n\n## FAQ\n\n" + "退换问题。" * 80
        )
        chunks = chunk_document(document, target_chars=300, max_chars=420, overlap_chars=60)
        self.assertGreaterEqual(len(chunks), 3)
        self.assertTrue(all(len(chunk.content) <= 420 for chunk in chunks))
        self.assertFalse(
            any("分类页面内容" in chunk.content and "退换问题" in chunk.content for chunk in chunks)
        )
        self.assertTrue(all(chunk.source_ref.startswith("test.md#L") for chunk in chunks))

    def test_bad_size_configuration_fails_closed(self):
        with self.assertRaises(ValueError):
            chunk_document(self._document("文本"), 100, 80, 20)


if __name__ == "__main__":
    unittest.main()
