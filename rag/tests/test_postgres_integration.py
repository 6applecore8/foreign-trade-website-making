import os
from pathlib import Path
import unittest
import uuid

from rag.benchmark import CASES
from rag.pipeline import RagPipeline


@unittest.skipUnless(os.environ.get("RAG_INTEGRATION") == "1", "set RAG_INTEGRATION=1")
class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = RagPipeline()
        cls.pipeline.initialize()
        cls.project_key = "test_" + uuid.uuid4().hex
        source = Path(__file__).parents[1] / "examples" / "perfume-requirements.md"
        cls.ingest = cls.pipeline.ingest(cls.project_key, source)

    @classmethod
    def tearDownClass(cls):
        cls.pipeline.store.delete_project(cls.project_key)

    def test_ingest_preserves_raw_and_chunks(self):
        self.assertGreater(self.ingest["chunk_count"], 5)
        self.assertTrue(Path(self.ingest["raw_path"]).is_file())
        self.assertTrue(Path(self.ingest["digest_path"]).is_file())

    def test_perfume_queries_retrieve_expected_evidence(self):
        for case in CASES:
            with self.subTest(query=case["query"]):
                pack = self.pipeline.ask(self.project_key, case["query"], top_k=3)
                content = "\n".join(hit.content for hit in pack.results)
                self.assertEqual(pack.selected_layer, "raw_evidence")
                self.assertTrue(all(expected in content for expected in case["expected_all"]))
                self.assertTrue(all(hit.source_ref for hit in pack.results))

    def test_project_isolation(self):
        pack = self.pipeline.ask("nonexistent_project", "品牌定位", top_k=3)
        self.assertEqual(pack.results, ())
        self.assertIsNone(pack.selected_layer)

    def test_uploaded_text_remains_untrusted_data(self):
        pack = self.pipeline.ask(self.project_key, "验收反例", top_k=3)
        self.assertIn("不可信数据", pack.trust_notice)
        self.assertTrue(all(hit.source_ref for hit in pack.results))


if __name__ == "__main__":
    unittest.main()
