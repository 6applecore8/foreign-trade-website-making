from pathlib import Path
import tempfile
import unittest

from rag.config import RagConfig
from rag.parser import parse_and_preserve


class ParserCounterexampleTests(unittest.TestCase):
    def test_binary_upload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "requirements.md"
            source.write_bytes(b"valid-prefix\x00hidden-instruction")
            config = RagConfig(data_dir=root / "data")
            with self.assertRaisesRegex(ValueError, "binary"):
                parse_and_preserve(source, config)

    def test_unsupported_document_type_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "requirements.html"
            source.write_text("<p>requirements</p>", encoding="utf-8")
            config = RagConfig(data_dir=root / "data")
            with self.assertRaisesRegex(ValueError, "unsupported"):
                parse_and_preserve(source, config)


if __name__ == "__main__":
    unittest.main()
