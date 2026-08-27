import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.validators import BrowserEvidenceValidator


class BrowserEvidenceTests(unittest.TestCase):
    def evidence(self, root: Path, overlap=False):
        shot = root / "shot.png"; shot.write_bytes(b"png-evidence")
        return {"url":"http://127.0.0.1/","viewport":{"width":1440,"height":900},"document":{"scroll_width":1440,"client_width":1440},"dom":{},"overflow":False,"cta":True,"console_errors":[],"screenshot_path":str(shot),"screenshot_sha256":hashlib.sha256(shot.read_bytes()).hexdigest(),"headings":[{"id":"hero","bounds":{"left":20,"right":500},"container":{"left":0,"right":600},"lines":[{"top":10,"bottom":80},{"top":70 if overlap else 80,"bottom":150}]}]}

    def test_valid_desktop_evidence_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); path=root/"evidence.json"; path.write_text(json.dumps(self.evidence(root)),encoding="utf-8")
            self.assertEqual("passed",BrowserEvidenceValidator().validate(path)["status"])

    def test_overlapping_heading_lines_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); path=root/"evidence.json"; path.write_text(json.dumps(self.evidence(root,True)),encoding="utf-8")
            result=BrowserEvidenceValidator().validate(path)
            self.assertEqual("failed",result["status"]); self.assertTrue(any("overlap" in error for error in result["errors"]))
