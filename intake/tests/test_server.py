import base64
import http.client
import importlib.util
import json
import re
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import unittest.mock
import zlib
from contextlib import contextmanager
from copy import deepcopy

from jsonschema import Draft202012Validator, FormatChecker

INTAKE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = INTAKE_ROOT.parent
TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)

REQUEST_SCHEMA = json.loads((INTAKE_ROOT / "request.schema.json").read_text(encoding="utf-8"))
WORKFLOW_SCHEMA = json.loads((PROJECT_ROOT / "config" / "site-config.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(REQUEST_SCHEMA)
Draft202012Validator.check_schema(WORKFLOW_SCHEMA)
FORMAT_CHECKER = FormatChecker()
REQUEST_VALIDATOR = Draft202012Validator(REQUEST_SCHEMA, format_checker=FORMAT_CHECKER)
WORKFLOW_VALIDATOR = Draft202012Validator(WORKFLOW_SCHEMA, format_checker=FORMAT_CHECKER)

spec = importlib.util.spec_from_file_location("intake_server", INTAKE_ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = server
spec.loader.exec_module(server)


@contextmanager
def running_server(requests_root):
    httpd = server.create_server(port=0, requests_root=Path(requests_root))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        thread.join(timeout=3)
        httpd.server_close()


def request(httpd, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    return response.status, response.getheaders(), raw


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
TRUNCATED_PNG = (
    b"\x89PNG\r\n\x1a\n"
    + (13).to_bytes(4, "big")
    + b"IHDR"
    + (1).to_bytes(4, "big")
    + (1).to_bytes(4, "big")
    + bytes((8, 2, 0, 0, 0))
    + b"\x00\x00\x00\x00"
)
INVALID_MARKER_ONLY_JPEG = bytes.fromhex("FFD8FFC00002FFDA0002FFD9")
INVALID_VP8X_ONLY_WEBP = bytes.fromhex(
    "524946461600000057454250565038580a00000000000000000000000000"
)
VALID_WEBP_1X1 = bytes.fromhex(
    "52494646220000005745425056503820160000003001009d012a0100010001402625004e8021f000fefe"
)
VALID_GIF_1X1 = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")


def valid_payload():
    return {
        "schema_version": "1.0",
        "project_id": "local-site-intake",
        "industry": "制造业",
        "site_type": "企业官网",
        "brand": "示例制造企业",
        "target_audience": "采购负责人",
        "primary_goal": "展示产品并获取询盘",
        "required_sections": ["首页", "产品服务", "关于", "联系"],
        "freeform_request": "包含首页、产品服务、关于与联系入口",
        "project": {"name": "本地官网采集"},
        "business": {
            "name": "示例制造企业",
            "industry": "制造业",
            "target_audience": "采购负责人",
            "facts": "企业事实均需提交方确认"
        },
        "website": {
            "primary_goal": "展示产品并获取询盘",
            "requirements": "包含首页、产品服务、关于与联系入口",
            "pages": ["首页", "产品服务", "关于", "联系"],
            "style_notes": "清晰可信"
        },
        "faq": {
            "mode": "industry-default",
            "items": [
                {
                    "question": f"行业常见问题 {index}？",
                    "answer": "待补充",
                    "source": "industry-template",
                    "generation_note": "请核实企业实际答案。"
                }
                for index in range(1, 6)
            ]
        },
        "seo": {
            "title": "制造业产品与服务",
            "description": "介绍经核实的产品与服务信息。",
            "keywords": ["制造业", "产品", "服务"],
            "upload": None
        },
        "references": []
    }


def canonical_ui_payload():
    required_sections = ["首页", "服务", "案例", "FAQ", "联系"]
    freeform_request = "制作清晰可信的桌面端官网，并提供咨询入口。"
    return {
        "schema_version": "1.0",
        "project_id": "acme-site-2026",
        "industry": "专业服务",
        "site_type": "企业官网",
        "brand": "Acme 咨询",
        "target_audience": "成长型企业负责人",
        "primary_goal": "获取咨询线索",
        "required_sections": required_sections,
        "freeform_request": freeform_request,
        # app-core.js emits these compatibility objects alongside canonical top-level fields.
        "project": {"name": "acme-site-2026"},
        "business": {
            "name": "Acme 咨询",
            "industry": "专业服务",
            "target_audience": "成长型企业负责人",
            "facts": "",
        },
        "website": {
            "primary_goal": "获取咨询线索",
            "requirements": freeform_request,
            "pages": required_sections,
            "style_notes": "",
        },
        "faq": {
            "mode": "custom",
            "items": [
                {"question": "如何开始咨询？", "answer": "提交需求后联系。", "source": "user-provided"},
                {"question": "服务周期多久？", "answer": "待补充", "source": "user-provided"},
            ],
        },
        "seo": {
            "title": "Acme 专业咨询官网",
            "description": "为成长型企业提供经核实的专业咨询服务。",
            "keywords": ["专业咨询", "企业服务", "增长"],
            "upload": {
                "original_name": "seo-notes.txt",
                "size": len("关键词：专业咨询\n意图：获取咨询\n".encode("utf-8")),
                "media_type": "text/plain",
                "field_name": "seo_file",
            },
        },
        "references": [{
            "client_id": "hero-ref",
            "field_name": "reference:hero-ref",
            "purpose": "hero",
            "notes": "首页首屏构图参考",
            "original_name": "hero.png",
            "size": len(PNG_1X1),
            "media_type": "image/png",
        }],
    }


def multipart_body(fields, files=()):
    boundary = "----IntakeBoundary7MA4YWxk"
    chunks = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode("utf-8"), b"\r\n",
        ])
    for field_name, filename, content_type, content in files:
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            content, b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class IntakeServerTests(unittest.TestCase):
    def _assert_payload_rejected_without_writes(self, payload):
        body, content_type = multipart_body({"payload": json.dumps(payload, ensure_ascii=False)})
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type,
                    "Content-Length": str(len(body)),
                    "Origin": f"http://127.0.0.1:{httpd.server_port}",
                })
            self.assertFalse(requests_root.exists(), raw.decode("utf-8", "replace"))
        self.assertEqual(status, 400, raw.decode("utf-8", "replace"))
        self.assertEqual(json.loads(raw)["error"], "validation_error")

    def test_health(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            with running_server(Path(temp_dir) / "requests") as httpd:
                status, headers, raw = request(httpd, "GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), {
            "status": "ok",
            "service": "local-site-intake",
            "version": "1.0"
        })
        self.assertIn(("Content-Type", "application/json; charset=utf-8"), headers)

    def test_required_fields_are_rejected_before_writes(self):
        body, content_type = multipart_body({"payload": "{}"})
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type,
                    "Content-Length": str(len(body)),
                    "Origin": f"http://127.0.0.1:{httpd.server_port}",
                })
            self.assertFalse(requests_root.exists())
        self.assertEqual(status, 400)
        response = json.loads(raw)
        self.assertEqual(response["error"], "validation_error")
        self.assertEqual(set(response["fields"]), {
            "project.name", "business.name", "business.industry",
            "website.primary_goal", "website.requirements"
        })

    def test_truncated_png_is_not_detected_as_an_image(self):
        self.assertEqual(len(TRUNCATED_PNG), 33)
        self.assertIsNone(server.detect_image(TRUNCATED_PNG))

    def test_png_requires_valid_crc_nonempty_idat_final_iend_and_no_trailing_data(self):
        def chunk(kind, content=b""):
            return (len(content).to_bytes(4, "big") + kind + content
                    + zlib.crc32(kind + content).to_bytes(4, "big"))

        ihdr_data = (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes((8, 2, 0, 0, 0))
        signature = b"\x89PNG\r\n\x1a\n"
        exact_repro = signature + (13).to_bytes(4, "big") + b"IHDR" + ihdr_data + b"BAD!"
        no_idat = signature + chunk(b"IHDR", ihdr_data) + chunk(b"IEND")
        empty_idat = signature + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT") + chunk(b"IEND")
        bad_crc = bytearray(PNG_1X1)
        bad_crc[29] ^= 1
        duplicate_ihdr = signature + chunk(b"IHDR", ihdr_data) + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", b"x") + chunk(b"IEND")
        trailing = PNG_1X1 + b"garbage"

        for candidate in (exact_repro, no_idat, empty_idat, bytes(bad_crc), duplicate_ihdr, trailing):
            with self.subTest(size=len(candidate)):
                self.assertIsNone(server.detect_image(candidate))
        self.assertEqual(server.detect_image(PNG_1X1), ("image/png", ".png"))

    def test_webp_requires_exact_complete_valid_primary_chunk_structure(self):
        def webp(chunks):
            content = b"WEBP"
            for kind, payload in chunks:
                content += kind + len(payload).to_bytes(4, "little") + payload
                if len(payload) & 1:
                    content += b"\x00"
            return b"RIFF" + len(content).to_bytes(4, "little") + content

        valid_vp8 = VALID_WEBP_1X1[20:]
        self.assertEqual(server.detect_image(VALID_WEBP_1X1), ("image/webp", ".webp"))
        self.assertEqual(server.detect_image(VALID_GIF_1X1), ("image/gif", ".gif"))

        truncated_later_chunk = webp([(b"VP8 ", valid_vp8)])
        content = truncated_later_chunk[8:] + b"JUNK" + (5).to_bytes(4, "little") + b"xx"
        truncated_later_chunk = b"RIFF" + len(content).to_bytes(4, "little") + content
        malformed = (
            b"RIFF\x04\x00\x00\x00WEBP",
            webp([(b"VP8 ", b"\x00" * 10)]),
            webp([(b"VP8L", b"\x2e\x00\x00\x00\x00")]),
            webp([(b"VP8X", b"\x00" * 9)]),
            INVALID_VP8X_ONLY_WEBP,
            truncated_later_chunk,
            webp([(b"JUNK", b"metadata")]),
        )
        for candidate in malformed:
            with self.subTest(candidate=candidate[:24]):
                self.assertIsNone(server.detect_image(candidate))

    def test_marker_only_jpeg_and_vp8x_only_webp_are_not_images(self):
        self.assertIsNone(server.detect_image(INVALID_MARKER_ONLY_JPEG))
        self.assertIsNone(server.detect_image(INVALID_VP8X_ONLY_WEBP))

    def test_marker_only_jpeg_and_vp8x_only_webp_uploads_return_415_without_writes(self):
        for client_id, filename, media_type, content in (
            ("bad-jpeg", "bad.jpg", "image/jpeg", INVALID_MARKER_ONLY_JPEG),
            ("bad-webp", "bad.webp", "image/webp", INVALID_VP8X_ONLY_WEBP),
        ):
            with self.subTest(filename=filename):
                payload = valid_payload()
                field_name = f"reference:{client_id}"
                payload["references"] = [{
                    "client_id": client_id,
                    "field_name": field_name,
                    "purpose": "hero",
                    "notes": "malformed image",
                    "original_name": filename,
                    "size": len(content),
                    "media_type": media_type,
                }]
                body, content_type = multipart_body(
                    {"payload": json.dumps(payload, ensure_ascii=False)},
                    [(field_name, filename, media_type, content)],
                )
                with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
                    requests_root = Path(temp_dir) / "requests"
                    with running_server(requests_root) as httpd:
                        status, _, raw = request(httpd, "POST", "/api/requests", body, {
                            "Content-Type": content_type,
                            "Content-Length": str(len(body)),
                            "Origin": f"http://127.0.0.1:{httpd.server_port}",
                        })
                    self.assertFalse(requests_root.exists(), raw.decode("utf-8", "replace"))
                self.assertEqual(status, 415, raw.decode("utf-8", "replace"))
                self.assertEqual(json.loads(raw)["error"], "invalid_image")

    def test_handoff_prompt_distinguishes_request_and_project_path_anchors(self):
        prompt = (INTAKE_ROOT / "PROMPT.md").read_text(encoding="utf-8")
        self.assertIn("site-request.json", prompt)
        self.assertIn("relative to the immutable request directory", prompt)
        self.assertIn("site-config.json", prompt)
        self.assertIn("relative to the project root", prompt)
        self.assertIn("intake/requests/<request_id>/", prompt)
        self.assertIn("must not be joined to the request directory", prompt)

    def test_unknown_top_level_and_nested_fields_are_rejected_without_writes(self):
        variants = []
        top_level = valid_payload()
        top_level["unexpected"] = "must not persist"
        variants.append(top_level)
        nested = valid_payload()
        nested["business"]["unexpected"] = "must not persist"
        variants.append(nested)
        deep_nested = valid_payload()
        deep_nested["website"]["unexpected"] = {"nested": True}
        variants.append(deep_nested)
        for payload in variants:
            with self.subTest(keys=tuple(payload)):
                self._assert_payload_rejected_without_writes(payload)

    def test_embedded_file_bytes_base64_and_data_uris_are_rejected_without_writes(self):
        variants = []
        file_bytes = valid_payload()
        file_bytes["file_bytes"] = list(PNG_1X1)
        variants.append(file_bytes)
        byte_array = valid_payload()
        byte_array["asset"] = list(PNG_1X1)
        variants.append(byte_array)
        encoded = valid_payload()
        encoded["business"]["facts"] = base64.b64encode(PNG_1X1).decode("ascii")
        variants.append(encoded)
        data_uri = valid_payload()
        data_uri["website"]["style_notes"] = "data:image/png;base64," + base64.b64encode(PNG_1X1).decode("ascii")
        variants.append(data_uri)
        named_base64 = valid_payload()
        named_base64["business"]["base64"] = "harmless-looking"
        variants.append(named_base64)
        for payload in variants:
            with self.subTest(keys=tuple(payload)):
                self._assert_payload_rejected_without_writes(payload)

    def test_truncated_png_upload_is_rejected_before_writes(self):
        payload = valid_payload()
        payload["references"] = [{
            "client_id": "truncated-1", "field_name": "reference:truncated-1",
            "purpose": "hero", "notes": "截断 PNG",
            "original_name": "truncated.png", "size": len(TRUNCATED_PNG),
            "media_type": "image/png",
        }]
        body, content_type = multipart_body(
            {"payload": json.dumps(payload, ensure_ascii=False)},
            [("reference:truncated-1", "truncated.png", "image/png", TRUNCATED_PNG)],
        )
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type,
                    "Content-Length": str(len(body)),
                    "Origin": f"http://127.0.0.1:{httpd.server_port}",
                })
            self.assertFalse(requests_root.exists())
        self.assertEqual(status, 415)
        self.assertEqual(json.loads(raw)["error"], "invalid_image")

    def test_disguised_image_is_rejected_before_writes(self):
        payload = valid_payload()
        payload["references"] = [{
            "client_id": "fake-1", "field_name": "reference:fake-1", "purpose": "hero", "notes": "伪装文件",
            "original_name": "fake.png", "size": 12, "media_type": "image/png"
        }]
        body, content_type = multipart_body(
            {"payload": json.dumps(payload, ensure_ascii=False)},
            [("reference:fake-1", "fake.png", "image/png", b"NOT AN IMAGE")]
        )
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type,
                    "Content-Length": str(len(body)),
                    "Origin": f"http://127.0.0.1:{httpd.server_port}",
                })
            self.assertFalse(requests_root.exists())
        self.assertEqual(status, 415)
        self.assertEqual(json.loads(raw)["error"], "invalid_image")

    def test_utf8_seo_source_file_is_saved(self):
        payload = valid_payload()
        seo_bytes = "关键词,意图\n工业设备,产品调研\n".encode("utf-8")
        payload["seo"]["upload"] = {
            "original_name": "research.csv",
            "size": len(seo_bytes),
            "media_type": "text/csv",
            "field_name": "seo_file"
        }
        body, content_type = multipart_body(
            {"payload": json.dumps(payload, ensure_ascii=False)},
            [("seo_file", "research.csv", "text/csv", seo_bytes)]
        )
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type,
                    "Content-Length": str(len(body)),
                    "Origin": f"http://127.0.0.1:{httpd.server_port}",
                })
            self.assertEqual(status, 201)
            request_dir = requests_root / json.loads(raw)["request_id"]
            seo_path = request_dir / "seo" / "source.csv"
            self.assertTrue(seo_path.is_file())
            self.assertEqual(seo_path.read_bytes(), seo_bytes)
            saved = json.loads((request_dir / "site-request.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["seo"]["upload"]["stored_path"], "seo/source.csv")
            self.assertEqual(saved["seo"]["upload"]["original_name"], "research.csv")

    def test_canonical_ui_submission_emits_schema_valid_workflow_config(self):
        payload = canonical_ui_payload()
        # Deliberately differ from compatibility objects: preserve top-level input, do not infer.
        payload.update({
            "industry": "鞋服",
            "site_type": "品牌展示独立站",
            "brand": "验收示例品牌",
        })
        seo_bytes = "关键词：专业咨询\n意图：获取咨询\n".encode("utf-8")
        body, content_type = multipart_body(
            {"payload": json.dumps(payload, ensure_ascii=False)},
            [
                ("reference:hero-ref", "hero.png", "image/png", PNG_1X1),
                ("seo_file", "seo-notes.txt", "text/plain", seo_bytes),
            ],
        )
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            project_root = Path(temp_dir)
            requests_root = project_root / "intake" / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type,
                    "Content-Length": str(len(body)),
                    "Origin": f"http://127.0.0.1:{httpd.server_port}",
                })
            self.assertEqual(status, 201, raw.decode("utf-8", "replace"))
            result = json.loads(raw)
            request_id = result["request_id"]
            request_dir = requests_root / request_id
            saved_request = json.loads(
                (request_dir / "site-request.json").read_text(encoding="utf-8")
            )
            REQUEST_VALIDATOR.validate(saved_request)
            saved_config = json.loads(
                (request_dir / "site-config.json").read_text(encoding="utf-8")
            )

            # Cross-consumer contract: the immutable Intake output is directly consumable.
            WORKFLOW_VALIDATOR.validate(saved_config)
            self.assertEqual(saved_config["project_name"], payload["project_id"])
            self.assertEqual(saved_config["user_request"], payload["freeform_request"])
            self.assertEqual(saved_config["language"], "zh-CN")
            for field in ("title", "description", "keywords"):
                self.assertEqual(saved_config[field], payload["seo"][field])
                self.assertEqual(saved_config["seo"][field], payload["seo"][field])
            self.assertNotIn("upload", saved_config["seo"])
            self.assertEqual(saved_config["faq"], payload["faq"])
            self.assertEqual(saved_config["website_intent"], {
                "industry": payload["industry"],
                "site_type": payload["site_type"],
                "brand_name": payload["brand"],
                "target_audience": payload["target_audience"],
                "primary_goal": payload["primary_goal"],
                "requirements": payload["freeform_request"],
                "sections": payload["required_sections"],
            })
            request_path = f"intake/requests/{request_id}"
            self.assertEqual(saved_config["intake"], {
                "request_id": request_id,
                "request_path": request_path,
                "source_request": f"{request_path}/site-request.json",
                "submitted_at": saved_request["submitted_at"],
            })
            self.assertEqual(saved_config["reference_assets"], [{
                "relative_path": f"{request_path}/references/01-hero.png",
                "original_name": "hero.png",
                "verified_media_type": "image/png",
                "purpose": "hero",
                "usage_note": "首页首屏构图参考",
            }])
            self.assertEqual(saved_config["seo"]["source_document"], {
                "relative_path": f"{request_path}/seo/source.txt",
                "original_name": "seo-notes.txt",
                "verified_media_type": "text/plain",
            })
            for relative_path in (
                saved_config["intake"]["source_request"],
                saved_config["reference_assets"][0]["relative_path"],
                saved_config["seo"]["source_document"]["relative_path"],
            ):
                resolved = (project_root / relative_path).resolve()
                self.assertTrue(resolved.is_file(), relative_path)
                self.assertTrue(resolved.is_relative_to(request_dir.resolve()), relative_path)

    def test_valid_png_with_purpose_is_atomically_saved_with_both_json_outputs(self):
        payload = valid_payload()
        payload["references"] = [{
            "client_id": "ref-1",
            "field_name": "reference:ref-1",
            "purpose": "hero",
            "notes": "首页首屏构图参考",
            "original_name": "hero.png",
            "size": len(PNG_1X1),
            "media_type": "image/png"
        }]
        body, content_type = multipart_body(
            {"payload": json.dumps(payload, ensure_ascii=False)},
            [("reference:ref-1", "hero.png", "image/png", PNG_1X1)]
        )
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type,
                    "Content-Length": str(len(body)),
                    "Origin": f"http://127.0.0.1:{httpd.server_port}",
                })
            self.assertEqual(status, 201)
            result = json.loads(raw)
            request_dir = requests_root / result["request_id"]
            self.assertTrue(request_dir.is_dir())
            self.assertFalse(any(p.name.startswith(".staging-") for p in requests_root.iterdir()))
            site_request_path = request_dir / "site-request.json"
            site_config_path = request_dir / "site-config.json"
            self.assertTrue(site_request_path.is_file())
            self.assertTrue(site_config_path.is_file())
            saved_request = json.loads(site_request_path.read_text(encoding="utf-8"))
            saved_config = json.loads(site_config_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_request["references"][0]["purpose"], "hero")
            stored_path = saved_request["references"][0]["stored_path"]
            self.assertEqual((request_dir / stored_path).read_bytes(), PNG_1X1)
            self.assertEqual(saved_config["reference_assets"][0]["purpose"], "hero")
            self.assertEqual(
                saved_config["intake"]["source_request"],
                f"intake/requests/{result['request_id']}/site-request.json",
            )
            self.assertEqual(Path(result["absolute_path"]), request_dir.resolve())
            self.assertEqual(result["relative_path"], f"intake/requests/{result['request_id']}")


class IntakeBoundaryTests(unittest.TestCase):
    def test_actions_align_with_section_content_without_mobile_breakpoint(self):
        styles = (INTAKE_ROOT / "src" / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".actions{margin-top:20px;padding:20px 28px;", styles)
        self.assertNotIn("@media", styles)

    def test_static_index_declares_inline_data_favicon(self):
        index = (INTAKE_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('<link rel="icon" href="data:,">', index)

    def test_static_index_and_vite_hashed_assets_are_served_from_dist(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            with running_server(Path(temp_dir) / "requests") as httpd:
                for index_path in ("/", "/index.html"):
                    status, headers, raw = request(httpd, "GET", index_path)
                    self.assertEqual(status, 200)
                    self.assertIn(b"Site Intake", raw)
                    self.assertIn(("X-Content-Type-Options", "nosniff"), headers)
                asset_paths = re.findall(rb'(?:src|href)="(/assets/[^"]+)"', raw)
                self.assertGreaterEqual(len(asset_paths), 2)
                for asset_path in asset_paths:
                    status, headers, asset = request(httpd, "GET", asset_path.decode("ascii"))
                    self.assertEqual(status, 200)
                    self.assertTrue(asset)
                    self.assertIn(("X-Content-Type-Options", "nosniff"), headers)
                status, _, _ = request(httpd, "GET", "/app.js")
                self.assertEqual(status, 404)

    def test_non_local_origin_is_rejected_before_writes(self):
        body, content_type = multipart_body({"payload": json.dumps(valid_payload())})
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type, "Content-Length": str(len(body)),
                    "Origin": "https://evil.example"
                })
            self.assertFalse(requests_root.exists())
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(raw)["error"], "origin_rejected")

    def test_fake_jpeg_gif_and_webp_structures_are_rejected(self):
        fake_jpeg_29 = b"\xff\xd8\xff\xe0" + b"x" * 23 + b"\xff\xd9"
        self.assertEqual(len(fake_jpeg_29), 29)
        self.assertIsNone(server.detect_image(fake_jpeg_29))
        self.assertIsNone(server.detect_image(b"GIF89a" + b"x" * 20))
        self.assertIsNone(server.detect_image(b"RIFF" + (16).to_bytes(4, "little") + b"WEBPVP8 " + b"x" * 12))
        self.assertIsNone(server.detect_image(b"image.jpg but fake"))

    def test_invalid_project_id_is_rejected_before_writes(self):
        for invalid_project_id in ("Acme-Site", "-leading-hyphen", "a" * 50, "中文项目"):
            with self.subTest(project_id=invalid_project_id):
                payload = canonical_ui_payload()
                payload["project_id"] = invalid_project_id
                payload["references"] = []
                payload["seo"]["upload"] = None
                body, content_type = multipart_body({
                    "payload": json.dumps(payload, ensure_ascii=False)
                })
                with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
                    requests_root = Path(temp_dir) / "requests"
                    with running_server(requests_root) as httpd:
                        status, _, raw = request(httpd, "POST", "/api/requests", body, {
                            "Content-Type": content_type,
                            "Content-Length": str(len(body)),
                        })
                    self.assertFalse(requests_root.exists())
                self.assertEqual(status, 400)
                response = json.loads(raw)
                self.assertEqual(response["error"], "validation_error")
                self.assertIn("project_id", response["message"])

    def test_more_than_six_references_are_rejected_without_writes(self):
        payload = valid_payload()
        payload["references"] = [{"client_id": f"r{i}", "field_name": f"reference:r{i}", "purpose": "hero"} for i in range(7)]
        files = [(f"reference:r{i}", f"{i}.png", "image/png", PNG_1X1) for i in range(7)]
        body, content_type = multipart_body({"payload": json.dumps(payload)}, files)
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type, "Content-Length": str(len(body))})
            self.assertFalse(requests_root.exists())
        self.assertEqual(status, 400)
        self.assertIn("six", json.loads(raw)["message"].lower())

    def test_filename_traversal_is_rejected(self):
        payload = valid_payload()
        payload["references"] = [{"client_id": "r1", "field_name": "reference:r1", "purpose": "hero"}]
        body, content_type = multipart_body({"payload": json.dumps(payload)}, [
            ("reference:r1", "../escape.png", "image/png", PNG_1X1)])
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type, "Content-Length": str(len(body))})
            self.assertFalse(requests_root.exists())
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw)["error"], "validation_error")

    def test_valid_jpeg_is_saved_with_sniffed_extension(self):
        payload = valid_payload()
        payload["references"] = [{"client_id": "photo", "field_name": "reference:photo", "purpose": "about"}]
        jpeg = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAABD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EH//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/EH//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EH//2Q==")
        body, content_type = multipart_body({"payload": json.dumps(payload)}, [
            ("reference:photo", "team.jpeg", "image/jpeg", jpeg)])
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type, "Content-Length": str(len(body))})
            self.assertEqual(status, 201)
            result = json.loads(raw)
            saved = json.loads((requests_root / result["request_id"] / "site-request.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["references"][0]["stored_path"], "references/01-about.jpg")
            self.assertEqual((requests_root / result["request_id"] / "references" / "01-about.jpg").read_bytes(), jpeg)

    def test_non_utf8_seo_is_rejected_without_writes(self):
        payload = valid_payload()
        payload["seo"]["upload"] = {"original_name": "bad.txt", "size": 2, "media_type": "text/plain", "field_name": "seo_file"}
        body, content_type = multipart_body({"payload": json.dumps(payload)}, [
            ("seo_file", "bad.txt", "text/plain", b"\xff\xfe")])
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, raw = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type, "Content-Length": str(len(body))})
            self.assertFalse(requests_root.exists())
        self.assertEqual(status, 400)
        self.assertIn("UTF-8", json.loads(raw)["message"])

    def test_static_traversal_is_not_served(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            with running_server(Path(temp_dir) / "requests") as httpd:
                status, _, _ = request(httpd, "GET", "/../server.py")
        self.assertEqual(status, 404)


class IntakeAdditionalSecurityTests(unittest.TestCase):
    def test_health_alias_and_unknown_static_paths(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            with running_server(Path(temp_dir) / "requests") as httpd:
                status, _, raw = request(httpd, "GET", "/health")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(raw)["status"], "ok")
                for path in ("/missing.js", "/some/spa/route"):
                    status, _, raw = request(httpd, "GET", path)
                    self.assertEqual(status, 404)
                    self.assertEqual(json.loads(raw)["error"], "not_found")

    def test_static_dist_root_and_asset_symlink_escapes_are_rejected(self):
        if not hasattr(Path, "symlink_to"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            base = Path(temp_dir)
            outside = base / "outside"
            outside.mkdir()
            (outside / "secret.js").write_text("secret", encoding="utf-8")
            linked_root = base / "linked-dist"
            try:
                linked_root.symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaises(ValueError):
                server.create_server(port=0, requests_root=base / "requests", dist_root=linked_root)

            dist = base / "dist"
            assets = dist / "assets"
            dist.mkdir()
            (dist / "index.html").write_text("ok", encoding="utf-8")
            assets.symlink_to(outside, target_is_directory=True)
            httpd = server.create_server(port=0, requests_root=base / "requests", dist_root=dist)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                status, _, _ = request(httpd, "GET", "/assets/secret.js")
                self.assertEqual(status, 404)
            finally:
                httpd.shutdown()
                thread.join(timeout=3)
                httpd.server_close()

    def test_symlink_requests_root_is_rejected_without_target_writes(self):
        if not hasattr(Path, "symlink_to"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            base = Path(temp_dir)
            target = base / "target"
            target.mkdir()
            link = base / "requests-link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaises(ValueError):
                server.save_submission(valid_payload(), [], link)
            self.assertEqual(list(target.iterdir()), [])

    def test_seo_filename_traversal_is_rejected_without_writes(self):
        payload = valid_payload()
        payload["seo"]["upload"] = {"original_name": "bad.txt", "size": 2, "media_type": "text/plain", "field_name": "seo_file"}
        body, content_type = multipart_body({"payload": json.dumps(payload)}, [
            ("seo_file", "..\\bad.txt", "text/plain", b"ok")])
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            requests_root = Path(temp_dir) / "requests"
            with running_server(requests_root) as httpd:
                status, _, _ = request(httpd, "POST", "/api/requests", body, {
                    "Content-Type": content_type, "Content-Length": str(len(body))})
            self.assertFalse(requests_root.exists())
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class IntakeFinalReviewRegressionTests(unittest.TestCase):
    def post_payload(self, payload, files=(), origin=None):
        body, content_type = multipart_body({"payload": json.dumps(payload, ensure_ascii=False)}, files)
        temp = tempfile.TemporaryDirectory(dir=TMP_ROOT)
        requests_root = Path(temp.name) / "fresh" / "requests"
        httpd_context = running_server(requests_root)
        httpd = httpd_context.__enter__()
        headers = {"Content-Type": content_type, "Content-Length": str(len(body))}
        if origin is not None:
            headers["Origin"] = origin.format(port=httpd.server_port)
        status, _, raw = request(httpd, "POST", "/api/requests", body, headers)
        httpd_context.__exit__(None, None, None)
        return temp, requests_root, status, raw

    def assert_rejected_without_root(self, payload, files=()):
        temp, requests_root, status, raw = self.post_payload(payload, files)
        try:
            self.assertGreaterEqual(status, 400, raw.decode("utf-8", "replace"))
            self.assertLess(status, 500, raw.decode("utf-8", "replace"))
            self.assertFalse(requests_root.exists())
            self.assertIn("error", json.loads(raw))
        finally:
            temp.cleanup()

    def test_missing_or_empty_seo_object_is_preflight_rejected_without_root(self):
        for mutation in ("missing", "empty"):
            with self.subTest(mutation=mutation):
                payload = valid_payload()
                if mutation == "missing":
                    del payload["seo"]
                else:
                    payload["seo"] = {}
                self.assert_rejected_without_root(payload)

    def test_six_sections_and_all_schema_limit_overflows_are_rejected_without_root(self):
        cases = []
        p = valid_payload(); p["required_sections"] = [str(i) for i in range(6)]; cases.append(p)
        p = valid_payload(); p["faq"]["items"] = p["faq"]["items"] * 3; cases.append(p)
        p = valid_payload(); p["faq"]["items"][0]["question"] = "q" * 301; cases.append(p)
        p = valid_payload(); p["faq"]["items"][0]["answer"] = "a" * 1001; cases.append(p)
        p = valid_payload(); p["seo"]["title"] = "t" * 121; cases.append(p)
        p = valid_payload(); p["seo"]["description"] = "d" * 301; cases.append(p)
        p = valid_payload(); p["seo"]["keywords"] = ["k"] * 21; cases.append(p)
        p = valid_payload(); p["seo"]["keywords"] = ["k" * 41]; cases.append(p)
        p = valid_payload(); p["industry"] = "i" * 121; cases.append(p)
        p = valid_payload(); p["target_audience"] = "a" * 1001; cases.append(p)
        p = valid_payload(); p["primary_goal"] = "g" * 501; cases.append(p)
        p = valid_payload(); p["freeform_request"] = "r" * 4001; cases.append(p)
        for index, payload in enumerate(cases):
            with self.subTest(case=index): self.assert_rejected_without_root(payload)

    def test_blank_optional_seo_strings_are_omitted_not_serialized_as_empty(self):
        payload = valid_payload()
        payload["seo"].update({"title": "   ", "description": "", "keywords": []})
        temp, requests_root, status, raw = self.post_payload(payload)
        try:
            self.assertEqual(status, 201, raw.decode("utf-8", "replace"))
            config = json.loads((requests_root / json.loads(raw)["request_id"] / "site-config.json").read_text("utf-8"))
            for name in ("title", "description"):
                self.assertNotIn(name, config)
                self.assertNotIn(name, config["seo"])
            WORKFLOW_VALIDATOR.validate(config)
        finally: temp.cleanup()

    def test_projection_preserves_canonical_industry_site_type_and_brand(self):
        payload = valid_payload()
        payload.update({"industry": "精密仪器", "site_type": "产品目录站", "brand": "北辰"})
        temp, requests_root, status, raw = self.post_payload(payload)
        try:
            self.assertEqual(status, 201)
            config = json.loads((requests_root / json.loads(raw)["request_id"] / "site-config.json").read_text("utf-8"))
            self.assertEqual(config["website_intent"]["industry"], "精密仪器")
            self.assertEqual(config["website_intent"]["site_type"], "产品目录站")
            self.assertEqual(config["website_intent"]["brand_name"], "北辰")
        finally: temp.cleanup()

    def test_multipart_requires_exact_unique_declared_file_fields(self):
        base = valid_payload()
        scenarios = []
        p = deepcopy(base); p["references"] = [{"client_id":"r1","field_name":"reference:r1","purpose":"hero"}]
        scenarios.append((p, [("unknown", "x.png", "image/png", PNG_1X1)]))
        scenarios.append((p, [("reference:r1", "a.png", "image/png", PNG_1X1), ("reference:r1", "b.png", "image/png", PNG_1X1)]))
        p2 = deepcopy(base); p2["references"] = [{"client_id":"same","field_name":"reference:a","purpose":"hero"},{"client_id":"same","field_name":"reference:b","purpose":"about"}]
        scenarios.append((p2, [("reference:a","a.png","image/png",PNG_1X1),("reference:b","b.png","image/png",PNG_1X1)]))
        scenarios.append((deepcopy(base), [("seo_file", "orphan.csv", "text/csv", b"a,b\n")]))
        p3 = deepcopy(base); p3["references"] = [{"client_id":"r1","field_name":"reference:r1","purpose":"hero"}]
        scenarios.append((p3, []))
        for payload, files in scenarios:
            with self.subTest(files=[x[0] for x in files]): self.assert_rejected_without_root(payload, files)

    def test_fifty_unknown_parts_are_rejected_without_root(self):
        files = [(f"junk-{i}", f"{i}.txt", "text/plain", b"x") for i in range(50)]
        self.assert_rejected_without_root(valid_payload(), files)

    def test_fake_image_structures_are_rejected_without_root(self):
        fakes = [
            ("x.jpg", "image/jpeg", b"\xff\xd8\xff\xe0" + b"x" * 23 + b"\xff\xd9"),
            ("x.gif", "image/gif", b"GIF89a" + b"x" * 20),
            ("x.webp", "image/webp", b"RIFF" + (16).to_bytes(4,"little") + b"WEBPVP8 " + b"x" * 12),
        ]
        for filename, media_type, content in fakes:
            payload = valid_payload()
            payload["references"] = [{"client_id":"r1","field_name":"reference:r1","purpose":"hero"}]
            with self.subTest(filename=filename):
                self.assert_rejected_without_root(payload, [("reference:r1", filename, media_type, content)])

    def test_publish_conflict_never_overwrites_existing_directory(self):
        payload = valid_payload()
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            root = Path(temp_dir) / "requests"
            root.mkdir()
            conflict_id = "req-20260823T000000Z-conflict01"
            final = root / conflict_id
            final.mkdir()
            sentinel = final / "sentinel.txt"
            sentinel.write_text("immutable", encoding="utf-8")
            original = server._request_id
            server._request_id = lambda: conflict_id
            try:
                with self.assertRaises(FileExistsError): server.save_submission(payload, [], root)
            finally:
                server._request_id = original
            self.assertEqual(sentinel.read_text("utf-8"), "immutable")
            self.assertEqual(sorted(p.name for p in final.iterdir()), ["sentinel.txt"])
            self.assertFalse(any(p.name.startswith(".staging-") for p in root.iterdir()))

    def test_preflight_direct_call_missing_seo_raises_valueerror_without_root(self):
        payload = valid_payload(); del payload["seo"]
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            root = Path(temp_dir) / "fresh" / "requests"
            with self.assertRaises(ValueError): server.save_submission(payload, [], root)
            self.assertFalse(root.exists())


    def test_http_publish_conflict_returns_409_without_overwrite(self):
        conflict_id = "req-20260823T000000Z-httpconflict"
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            root = Path(temp_dir) / "requests"; root.mkdir()
            final = root / conflict_id; final.mkdir()
            sentinel = final / "sentinel.txt"; sentinel.write_text("immutable", encoding="utf-8")
            body, content_type = multipart_body({"payload": json.dumps(valid_payload(), ensure_ascii=False)})
            original = server._request_id; server._request_id = lambda: conflict_id
            try:
                with running_server(root) as httpd:
                    status, _, raw = request(httpd, "POST", "/api/requests", body, {
                        "Content-Type": content_type, "Content-Length": str(len(body))})
            finally:
                server._request_id = original
            self.assertEqual(status, 409, raw.decode("utf-8", "replace"))
            self.assertEqual(json.loads(raw)["error"], "request_conflict")
            self.assertEqual(sentinel.read_text("utf-8"), "immutable")
            self.assertEqual(sorted(p.name for p in final.iterdir()), ["sentinel.txt"])


class IntakeOwnerBlockingRegressionTests(unittest.TestCase):
    def test_handoff_docs_use_artifact_specific_path_anchors_and_require_request_containment(self):
        prompt = (INTAKE_ROOT / "PROMPT.md").read_text(encoding="utf-8")
        self.assertIn("site-request.json", prompt)
        self.assertIn("relative to the immutable request directory", prompt)
        self.assertIn("site-config.json", prompt)
        self.assertIn("relative to the project root", prompt)
        self.assertIn("contained within the selected immutable `intake/requests/<request_id>/` directory", prompt)
        self.assertIn("must not be joined to the request directory again", prompt)

    def test_publish_docs_describe_atomic_no_replace_and_fail_closed_fallback(self):
        prompt = (INTAKE_ROOT / "PROMPT.md").read_text(encoding="utf-8")
        index = (INTAKE_ROOT / "INDEX.md").read_text(encoding="utf-8")
        for document in (prompt, index):
            self.assertIn("same-parent staging", document)
            self.assertIn("platform atomic no-replace primitive", document)
            self.assertIn("never overwrite", document)
            self.assertNotIn("os.replace", document)
        self.assertIn("MoveFileW", index)
        self.assertIn("renameat2(RENAME_NOREPLACE)", index)
        self.assertIn("fails closed", index)

    def test_latest_submitted_snapshot_matches_schemas_and_project_root_path_contract(self):
        request_dirs = sorted(
            path for path in (INTAKE_ROOT / "requests").iterdir()
            if path.is_dir() and path.name.startswith("req-")
        )
        self.assertTrue(request_dirs, "expected at least one submitted request snapshot")
        request_dir = request_dirs[-1].resolve()
        site_request = json.loads((request_dir / "site-request.json").read_text(encoding="utf-8"))
        site_config = json.loads((request_dir / "site-config.json").read_text(encoding="utf-8"))
        REQUEST_VALIDATOR.validate(site_request)
        WORKFLOW_VALIDATOR.validate(site_config)
        self.assertEqual(site_request["request_id"], request_dir.name)
        self.assertEqual(site_config["intake"]["request_id"], request_dir.name)

        referenced_paths = [
            site_config["intake"]["request_path"],
            site_config["intake"]["source_request"],
            *(asset["relative_path"] for asset in site_config.get("reference_assets", [])),
        ]
        source_document = site_config.get("seo", {}).get("source_document")
        if source_document:
            referenced_paths.append(source_document["relative_path"])
        for relative_path in referenced_paths:
            with self.subTest(relative_path=relative_path):
                self.assertNotIn("\\", relative_path)
                self.assertFalse(relative_path.startswith("/"))
                self.assertNotIn("..", relative_path.split("/"))
                resolved = (PROJECT_ROOT / relative_path).resolve(strict=True)
                self.assertTrue(resolved.is_relative_to(request_dir), relative_path)

    def test_unavailable_platform_publish_fails_closed_without_fallback_overwrite(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temp_dir:
            parent = Path(temp_dir)
            stage = parent / ".staging-request"
            final = parent / "req-existing"
            stage.mkdir()
            final.mkdir()
            (stage / "new.txt").write_text("new", encoding="utf-8")
            sentinel = final / "sentinel.txt"
            sentinel.write_text("immutable", encoding="utf-8")
            with unittest.mock.patch.object(server.os, "name", "posix"), \
                    unittest.mock.patch.object(server.sys, "platform", "darwin"):
                with self.assertRaisesRegex(OSError, "atomic no-replace publish is unavailable"):
                    server._atomic_publish_no_replace(stage, final)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "immutable")
            self.assertEqual(sorted(path.name for path in final.iterdir()), ["sentinel.txt"])
            self.assertTrue((stage / "new.txt").is_file())
