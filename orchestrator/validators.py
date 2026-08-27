from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class Check:
    name: str
    status: str
    detail: str


class _HTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = []
        self._title = False
        self.meta = {}
        self.ids = set()
        self.links = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title": self._title = True
        if tag == "meta" and attrs.get("name"): self.meta.setdefault(attrs["name"].lower(), []).append(attrs.get("content", ""))
        if attrs.get("id"): self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if attrs.get(key): self.links.append(attrs[key])

    def handle_endtag(self, tag):
        if tag == "title": self._title = False

    def handle_data(self, data):
        value = " ".join(data.split())
        if value:
            self.text.append(value)
            if self._title: self.title.append(value)


class DeterministicValidator:
    REQUIRED = {
        "index.html",
        "shoes.html",
        "apparel.html",
        "looks.html",
        "styles.css",
        "site-spec.json",
        "hero-campaign.png",
        "product-footwear.png",
        "product-apparel.png",
        "catalog-shoes.png",
        "catalog-apparel.png",
        "catalog-looks.png",
    }

    def validate(self, root: Path) -> dict:
        site = root / "artifacts/04-implementation/site"
        config = json.loads((root / "config/site-config.json").read_text(encoding="utf-8"))
        metadata = json.loads((root / "artifacts/02-metadata/metadata.json").read_text(encoding="utf-8"))
        requirements = json.loads((root / "artifacts/01-requirements/requirements.json").read_text(encoding="utf-8"))
        content = json.loads((root / "artifacts/03-content/home-content.json").read_text(encoding="utf-8"))
        html_pages = ["index.html", "shoes.html", "apparel.html", "looks.html"]
        parsers = {}
        html_sources = {}
        for page in html_pages:
            source = (site / page).read_text(encoding="utf-8")
            parser = _HTML(); parser.feed(source)
            parsers[page], html_sources[page] = parser, source
        parser = parsers["index.html"]
        checks = []
        def add(name, ok, detail): checks.append(Check(name, "passed" if ok else "failed", detail))
        files = {p.name for p in site.iterdir() if p.is_file()}
        add("文件集合", files == self.REQUIRED, f"actual={sorted(files)}")
        add("metadata 一致性", parser.title == [metadata["title"]] and parser.meta.get("description") == [metadata["description"]] and parser.meta.get("keywords") == [",".join(metadata["keywords"])], "title/description/keywords exact match")
        local_missing, external = [], []
        for page, page_parser in parsers.items():
            for link in page_parser.links:
                parsed = urlparse(link)
                if parsed.scheme in {"http", "https"} or link.startswith("//"): external.append(f"{page}:{link}")
                elif link.startswith("#"):
                    if link[1:] not in page_parser.ids: local_missing.append(f"{page}:{link}")
                elif parsed.path:
                    target = site / parsed.path
                    if not target.resolve().is_file(): local_missing.append(f"{page}:{link}")
                    elif parsed.fragment and target.name in parsers and parsed.fragment not in parsers[target.name].ids:
                        local_missing.append(f"{page}:{link}")
        add("路径与引用", not local_missing, f"missing={local_missing}")
        has_script = any(re.search(r"<script\b", source, re.I) for source in html_sources.values())
        add("禁止外部依赖", not external and not has_script, f"external={external}")
        page_texts = {page: " ".join(item.text) for page, item in parsers.items()}
        page_text = " ".join(page_texts.values())
        required_phrases = [section["name"] for section in requirements.get("sections", [])]
        required_phrases += [content.get("hero", {}).get(key, "") for key in ("headline", "summary", "cta_label")]
        required_phrases += [section.get(key, "") for section in content.get("sections", []) for key in ("heading", "body")]
        missing = [phrase for phrase in required_phrases if phrase and phrase not in page_text]
        add("requirements/content 覆盖率", not missing, f"missing_phrases={missing}")
        catalog_errors = []
        for catalog in content.get("catalogs", []):
            path = catalog.get("path", "")
            if path not in parsers:
                catalog_errors.append(f"missing_page={path}")
                continue
            catalog_text = page_texts[path]
            phrases = [catalog.get("name", ""), catalog.get("summary", "")]
            phrases += [item.get(key, "") for item in catalog.get("items", []) for key in ("title", "description")]
            missing_catalog = [phrase for phrase in phrases if phrase and phrase not in catalog_text]
            card_count = len(re.findall(r'class="catalog-card"', html_sources[path]))
            if missing_catalog or card_count != 5:
                catalog_errors.append(f"{path}:cards={card_count},missing={missing_catalog}")
        add("分类页面与商品数据", requirements.get("page_count") == 4 and len(content.get("catalogs", [])) == 3 and not catalog_errors, f"errors={catalog_errors}")
        faq_items = config.get("faq", {}).get("items", [])
        faq_phrases = [item.get(key, "") for item in faq_items for key in ("question", "answer")]
        faq_positions = [page_text.find(phrase) for phrase in faq_phrases if phrase]
        faq_ok = all(position >= 0 for position in faq_positions) and faq_positions == sorted(faq_positions)
        add("FAQ 保真", faq_ok, f"ordered_positions={faq_positions}")
        forbidden = [value.removesuffix("：待补充") for value in requirements.get("unknowns", []) if value.removesuffix("：待补充") and value.removesuffix("：待补充") in page_text and "待补充" not in page_text]
        add("禁止字段/事实", not forbidden, f"risky_unknowns={forbidden}")
        failed = [item for item in checks if item.status == "failed"]
        return {"node_id": "deterministic-validator", "status": "failed" if failed else "passed", "checks": [item.__dict__ for item in checks], "errors": [item.detail for item in failed]}


class BrowserEvidenceValidator:
    """Validates persisted browser evidence; collection belongs to a browser adapter."""
    def validate(self, evidence_path: Path) -> dict:
        if not evidence_path.is_file():
            return {"status": "failed", "errors": ["browser evidence artifact is missing"]}
        data = json.loads(evidence_path.read_text(encoding="utf-8"))
        required = {"url", "viewport", "document", "dom", "overflow", "cta", "console_errors", "screenshot_path", "screenshot_sha256", "headings"}
        missing = sorted(required - data.keys())
        errors = []
        if missing: errors.append(f"missing fields: {missing}")
        if data.get("viewport", {}).get("width", 0) < 1280: errors.append("desktop viewport must be at least 1280px wide")
        if data.get("overflow") is not False or data.get("document", {}).get("scroll_width") != data.get("document", {}).get("client_width"): errors.append("horizontal overflow detected")
        if data.get("cta") is not True: errors.append("primary CTA is missing")
        if data.get("console_errors") != []: errors.append("browser console contains errors or warnings")
        for heading in data.get("headings", []):
            bounds, container, lines = heading.get("bounds", {}), heading.get("container", {}), heading.get("lines", [])
            if bounds.get("left", 0) < container.get("left", 0) - 1 or bounds.get("right", 0) > container.get("right", 0) + 1:
                errors.append(f"heading escapes container: {heading.get('id')}")
            for previous, current in zip(lines, lines[1:]):
                if current.get("top", 0) < previous.get("bottom", 0) - 1:
                    errors.append(f"heading line boxes overlap: {heading.get('id')}")
        screenshot = Path(data.get("screenshot_path", ""))
        if not screenshot.is_absolute():
            root = next((parent for parent in evidence_path.resolve().parents if (parent / "workflow.json").is_file()), evidence_path.parent)
            screenshot = root / screenshot
        if not screenshot.is_file(): errors.append("screenshot artifact is missing")
        elif hashlib.sha256(screenshot.read_bytes()).hexdigest() != data.get("screenshot_sha256"): errors.append("screenshot hash mismatch")
        return {"status": "passed" if not errors else "failed", "errors": errors}


class LLMReviewValidator:
    """Keeps subjective review separate and never overrides deterministic failures."""
    def validate_receipt(self, receipt: dict) -> dict:
        valid = receipt.get("status") in {"passed", "failed"} and all(key in receipt for key in ("readability", "style_consistency", "fact_risk"))
        return receipt if valid else {"status": "failed", "errors": ["invalid LLM review receipt"]}
