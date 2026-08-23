import hashlib
import json
import unittest
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SHA256 = "904f31436f20b127bf0b69c6a25b3192ffde34d6988b02d684a9a224375f40e8"
ACTIVE_CONFIG_SHA256 = "fca56e7e9f7a981574797b2231a203761deba03e4c6286bc6359bd590acd435b"
CURRENT_REQUEST = "intake/requests/req-20260822T163205Z-4128f061e2"  # current Schema + reference + SEO files
LEGACY_REQUEST = "intake/requests/req-20260822T145213Z-d6a2781cb7"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_selected_request(selected):
    """Read-only executable model of the Main Agent pre-archive gate."""
    if not selected or selected in {"latest", "intake/requests/latest"}:
        return ["explicit request selection required; latest is forbidden"]

    rel = PurePosixPath(selected)
    if rel.is_absolute() or len(rel.parts) != 3 or rel.parts[:2] != ("intake", "requests"):
        return ["selected path must be project-root-relative intake/requests/<request_id>"]
    if str(rel) != selected or any(part in {"", ".", ".."} for part in rel.parts):
        return ["selected path is not canonical"]

    request_id = rel.parts[2]
    request_dir = (ROOT / Path(*rel.parts)).resolve()
    requests_root = (ROOT / "intake" / "requests").resolve()
    try:
        request_dir.relative_to(requests_root)
    except ValueError:
        return ["selected request escapes intake/requests"]
    if request_id.startswith(".staging-") or not request_dir.is_dir():
        return ["selected request directory is absent or staging"]

    issues = []
    documents = {}
    for filename, schema_name in (
        ("site-request.json", "intake/request.schema.json"),
        ("site-config.json", "config/site-config.schema.json"),
    ):
        path = request_dir / filename
        if not path.is_file() or path.is_symlink() or path.resolve().parent != request_dir:
            issues.append(f"missing or unsafe required file: {filename}")
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            schema = json.loads((ROOT / schema_name).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            issues.append(f"unreadable JSON {filename}: {exc}")
            continue
        documents[filename] = document
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for error in sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path)):
            location = "/".join(map(str, error.absolute_path)) or "<root>"
            issues.append(f"{filename} schema-invalid at {location}: {error.message}")

    request = documents.get("site-request.json")
    if not isinstance(request, dict):
        return issues
    if request.get("request_id") != request_id:
        issues.append("request_id must equal the selected directory name")

    generated = documents.get("site-config.json")
    intake = generated.get("intake") if isinstance(generated, dict) else None
    if isinstance(intake, dict):
        expected_dir = selected
        expected_source = f"{selected}/site-request.json"
        if intake.get("request_id") != request_id:
            issues.append("site-config intake.request_id identity mismatch")
        if intake.get("request_path") != expected_dir or intake.get("source_request") != expected_source:
            issues.append("site-config request path identity mismatch")

    declared = list(request.get("references", []))
    upload = request.get("seo", {}).get("upload")
    if upload is not None:
        declared.append(upload)
    for item in declared:
        stored = item.get("stored_path")
        if not stored:
            continue
        stored_rel = PurePosixPath(stored)
        if stored_rel.is_absolute() or str(stored_rel) != stored or any(p in {"", ".", ".."} for p in stored_rel.parts):
            issues.append(f"noncanonical stored_path: {stored!r}")
            continue
        candidate = (ROOT / Path(*rel.parts) / Path(*stored_rel.parts)).resolve()
        try:
            candidate.relative_to(request_dir)
        except ValueError:
            issues.append(f"stored_path escapes selected request: {stored}")
            continue
        if not candidate.is_file() or candidate.is_symlink():
            issues.append(f"declared file missing or unsafe: {stored}")
            continue
        if item.get("size") != candidate.stat().st_size:
            issues.append(f"declared size mismatch: {stored}")
        media_type = item.get("media_type", "")
        data = candidate.read_bytes()
        signatures = {
            "image/png": b"\x89PNG\r\n\x1a\n",
            "image/jpeg": b"\xff\xd8\xff",
            "image/gif": b"GIF8",
            "image/webp": b"RIFF",
        }
        if media_type in signatures and not data.startswith(signatures[media_type]):
            issues.append(f"media signature mismatch: {stored}")
        if media_type == "image/webp" and data[8:12] != b"WEBP":
            issues.append(f"media signature mismatch: {stored}")
        if media_type in {"text/plain", "text/csv", "application/json"}:
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                issues.append(f"SEO source is not UTF-8: {stored}")
    return issues


class IntakeCompatibilityGateContractTests(unittest.TestCase):
    def test_prompt_places_fail_closed_compatibility_gate_before_archive(self):
        prompt = (ROOT / "main-agent" / "PROMPT.md").read_text(encoding="utf-8")
        compatibility = prompt.index("CURRENT_INTAKE_COMPATIBILITY_GATE")
        archive = prompt.index("ARCHIVE_GATE")
        self.assertLess(compatibility, archive)
        for required in (
            "intake/request.schema.json",
            "config/site-config.schema.json",
            "项目根",
            "选定 request 目录",
            "不得隐式选择 `latest`",
            "不可导入；请重新提交",
            "不得写 `config/site-config.json`",
            "不得派发",
            "不得迁移、补字段或修改历史请求",
            "只做桌面网页，不加入移动端要求",
        ):
            self.assertIn(required, prompt)

    def test_explicit_current_request_passes_and_legacy_request_fails_closed(self):
        self.assertEqual([], validate_selected_request(CURRENT_REQUEST))
        legacy_issues = validate_selected_request(LEGACY_REQUEST)
        self.assertTrue(legacy_issues)
        self.assertTrue(any("schema-invalid" in issue for issue in legacy_issues), legacy_issues)
        self.assertNotEqual([], validate_selected_request("latest"))

    def test_graph_limits_active_config_and_exact_three_files_are_unchanged(self):
        self.assertEqual(WORKFLOW_SHA256, sha256(ROOT / "workflow.json"))
        self.assertEqual(ACTIVE_CONFIG_SHA256, sha256(ROOT / "config" / "site-config.json"))
        workflow = json.loads((ROOT / "workflow.json").read_text(encoding="utf-8"))
        self.assertEqual(6, len(workflow["nodes"]))
        self.assertEqual(11, len(workflow["edges"]))
        self.assertNotIn("intake", {node["id"] for node in workflow["nodes"]})
        self.assertEqual(1, workflow["limits"]["pages"])
        self.assertEqual(3, workflow["limits"]["implementation_files"])
        site = ROOT / "artifacts" / "04-implementation" / "site"
        self.assertEqual({"index.html", "styles.css", "site-spec.json"}, {p.name for p in site.iterdir() if p.is_file()})


if __name__ == "__main__":
    unittest.main()
