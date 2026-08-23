#!/usr/bin/env python
"""Dependency-free localhost server for the site intake MVP."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from email import policy
from email.parser import BytesParser
from copy import deepcopy
import base64
import binascii
from datetime import datetime, timezone
import json
import os
import ctypes
import errno
import sys
from pathlib import Path
import re
import shutil
import stat
from typing import Any
import uuid
from urllib.parse import unquote, urlsplit
import zlib

from jsonschema import Draft202012Validator, FormatChecker

SERVICE_VERSION = "1.0"
MAX_POST_BYTES = 60 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_SEO_BYTES = 2 * 1024 * 1024
INTAKE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = INTAKE_ROOT.parent
REQUEST_SCHEMA = json.loads((INTAKE_ROOT / "request.schema.json").read_text(encoding="utf-8"))
SITE_CONFIG_SCHEMA = json.loads((PROJECT_ROOT / "config" / "site-config.schema.json").read_text(encoding="utf-8"))
FORMAT_CHECKER = FormatChecker()
REQUEST_VALIDATOR = Draft202012Validator(REQUEST_SCHEMA, format_checker=FORMAT_CHECKER)
SITE_CONFIG_VALIDATOR = Draft202012Validator(SITE_CONFIG_SCHEMA, format_checker=FORMAT_CHECKER)
ALLOWED_PURPOSES = {
    "hero", "product-service", "about", "faq", "background-style", "custom"
}
PROJECT_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")

class InvalidImage(ValueError):
    pass


REQUIRED_FIELDS = (
    ("project.name", ("project", "name")),
    ("business.name", ("business", "name")),
    ("business.industry", ("business", "industry")),
    ("website.primary_goal", ("website", "primary_goal")),
    ("website.requirements", ("website", "requirements")),
)


def _nested_text(value: Any, path: tuple[str, ...]) -> str:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current.strip() if isinstance(current, str) else ""


def validate_required(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return [name for name, _ in REQUIRED_FIELDS]
    return [name for name, path in REQUIRED_FIELDS if not _nested_text(payload, path)]


def parse_multipart(content_type: str, body: bytes) -> dict[str, Any]:
    envelope = (
        b"Content-Type: " + content_type.encode("ascii", "strict")
        + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    message = BytesParser(policy=policy.default).parsebytes(envelope)
    if not message.is_multipart():
        raise ValueError("Expected multipart/form-data")
    fields: dict[str, str] = {}
    files: list[dict[str, Any]] = []
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            raise ValueError("Every multipart part must have a field name")
        data = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is None:
            if name != "payload":
                raise ValueError("Unknown multipart field")
            if name in fields:
                raise ValueError("Duplicate multipart field")
            fields[name] = data.decode("utf-8", "strict")
        else:
            files.append({
                "field_name": name,
                "filename": filename,
                "content_type": part.get_content_type(),
                "data": data,
            })
            if len(files) > 7:
                raise ValueError("No more than seven uploaded files are allowed")
    if set(fields) != {"payload"}:
        raise ValueError("Exactly one payload field is required")
    return {"fields": fields, "files": files}


def _reasonable_image_dimensions(width: int, height: int) -> bool:
    return 0 < width <= 100_000 and 0 < height <= 100_000 and width * height <= 100_000_000


def detect_png(data: bytes) -> bool:
    if len(data) < 58 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return False

    offset = 8
    first_chunk = True
    color_type = None
    saw_palette = False
    saw_idat = False
    idat_ended = False
    while offset < len(data):
        if len(data) - offset < 12:
            return False
        length = int.from_bytes(data[offset:offset + 4], "big")
        if length > len(data) - offset - 12:
            return False
        chunk_type = data[offset + 4:offset + 8]
        if len(chunk_type) != 4 or any(not (65 <= byte <= 90 or 97 <= byte <= 122) for byte in chunk_type):
            return False
        if not 65 <= chunk_type[2] <= 90:  # PNG's reserved chunk-name bit must be zero.
            return False
        chunk_data_end = offset + 8 + length
        chunk_data = data[offset + 8:chunk_data_end]
        expected_crc = int.from_bytes(data[chunk_data_end:chunk_data_end + 4], "big")
        if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != expected_crc:
            return False

        if first_chunk:
            if chunk_type != b"IHDR" or length != 13:
                return False
            width = int.from_bytes(chunk_data[0:4], "big")
            height = int.from_bytes(chunk_data[4:8], "big")
            bit_depth, color_type, compression, filtering, interlace = chunk_data[8:13]
            valid_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if (
                not _reasonable_image_dimensions(width, height)
                or bit_depth not in valid_depths.get(color_type, set())
                or compression != 0
                or filtering != 0
                or interlace not in (0, 1)
            ):
                return False
            first_chunk = False
        elif chunk_type == b"IHDR":
            return False
        elif chunk_type == b"PLTE":
            if saw_palette or saw_idat or color_type in (0, 4) or not 3 <= length <= 768 or length % 3:
                return False
            saw_palette = True
        elif chunk_type == b"IDAT":
            if length == 0 or idat_ended or (color_type == 3 and not saw_palette):
                return False
            saw_idat = True
        elif chunk_type == b"IEND":
            return length == 0 and saw_idat and offset + 12 == len(data)
        else:
            if chunk_type[0] & 0x20 == 0:  # Unknown critical chunks cannot be safely accepted.
                return False
            if saw_idat:
                idat_ended = True

        if saw_idat and chunk_type != b"IDAT":
            idat_ended = True
        offset = chunk_data_end + 4

    return False


def _detect_jpeg(data: bytes) -> bool:
    if len(data) < 12 or data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
        return False
    offset = 2
    frame_components: set[int] | None = None
    saw_scan = False
    saw_entropy_data = False
    frame_markers = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
    while offset < len(data):
        if data[offset] != 0xFF:
            return False
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            return False
        marker = data[offset]
        offset += 1
        if marker == 0xD9:
            return frame_components is not None and saw_scan and saw_entropy_data and offset == len(data)
        if marker == 0x00 or marker == 0xD8 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            return False
        if offset + 2 > len(data):
            return False
        segment_length = int.from_bytes(data[offset:offset + 2], "big")
        segment_end = offset + segment_length
        if segment_length < 2 or segment_end > len(data):
            return False
        payload = data[offset + 2:segment_end]

        if marker in frame_markers:
            if frame_components is not None or len(payload) < 6:
                return False
            precision = payload[0]
            height = int.from_bytes(payload[1:3], "big")
            width = int.from_bytes(payload[3:5], "big")
            component_count = payload[5]
            if (precision not in (8, 12, 16)
                    or not 1 <= component_count <= 4
                    or len(payload) != 6 + 3 * component_count
                    or not _reasonable_image_dimensions(width, height)):
                return False
            components: set[int] = set()
            for component_offset in range(6, len(payload), 3):
                component_id, sampling, table = payload[component_offset:component_offset + 3]
                if component_id in components or sampling >> 4 == 0 or sampling & 0x0F == 0 or table > 3:
                    return False
                components.add(component_id)
            frame_components = components

        if marker == 0xDA:
            if frame_components is None or len(payload) < 4:
                return False
            component_count = payload[0]
            if (not 1 <= component_count <= len(frame_components)
                    or len(payload) != 1 + 2 * component_count + 3):
                return False
            scan_components: set[int] = set()
            for component_offset in range(1, 1 + 2 * component_count, 2):
                component_id = payload[component_offset]
                selectors = payload[component_offset + 1]
                if (component_id not in frame_components or component_id in scan_components
                        or selectors >> 4 > 3 or selectors & 0x0F > 3):
                    return False
                scan_components.add(component_id)
            spectral_start, spectral_end, approximation = payload[-3:]
            if spectral_start > spectral_end or spectral_end > 63 or approximation >> 4 > 13 or approximation & 0x0F > 13:
                return False
            saw_scan = True
            offset = segment_end
            scan_has_data = False
            while offset < len(data):
                if data[offset] != 0xFF:
                    scan_has_data = True
                    offset += 1
                    continue
                marker_offset = offset
                while offset < len(data) and data[offset] == 0xFF:
                    offset += 1
                if offset >= len(data):
                    return False
                following = data[offset]
                if following == 0x00:
                    scan_has_data = True
                    offset += 1
                    continue
                if 0xD0 <= following <= 0xD7:
                    offset += 1
                    continue
                offset = marker_offset
                break
            if scan_has_data:
                saw_entropy_data = True
            continue
        offset = segment_end
    return False


def _skip_gif_sub_blocks(data: bytes, offset: int) -> int | None:
    while offset < len(data):
        size = data[offset]
        offset += 1
        if size == 0:
            return offset
        if offset + size > len(data):
            return None
        offset += size
    return None


def _detect_gif(data: bytes) -> bool:
    if len(data) < 14 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return False
    if int.from_bytes(data[6:8], "little") == 0 or int.from_bytes(data[8:10], "little") == 0:
        return False
    offset = 13
    packed = data[10]
    if packed & 0x80:
        offset += 3 * (2 ** ((packed & 0x07) + 1))
    saw_image = False
    while offset < len(data):
        introducer = data[offset]
        offset += 1
        if introducer == 0x3B:
            return saw_image and offset == len(data)
        if introducer == 0x21:
            if offset >= len(data): return False
            offset += 1
            next_offset = _skip_gif_sub_blocks(data, offset)
            if next_offset is None: return False
            offset = next_offset
        elif introducer == 0x2C:
            if offset + 9 > len(data): return False
            image_packed = data[offset + 8]
            offset += 9
            if image_packed & 0x80:
                offset += 3 * (2 ** ((image_packed & 0x07) + 1))
            if offset >= len(data): return False
            offset += 1
            next_offset = _skip_gif_sub_blocks(data, offset)
            if next_offset is None: return False
            offset = next_offset
            saw_image = True
        else:
            return False
    return False


def _valid_vp8(payload: bytes) -> bool:
    if len(payload) <= 10 or payload[3:6] != b"\x9d\x01\x2a":
        return False
    frame_tag = int.from_bytes(payload[:3], "little")
    first_partition_size = frame_tag >> 5
    if (frame_tag & 1 or (frame_tag >> 1) & 0x07 > 3 or not frame_tag & 0x10
            or first_partition_size <= 7 or 3 + first_partition_size >= len(payload)):
        return False
    width = int.from_bytes(payload[6:8], "little") & 0x3FFF
    height = int.from_bytes(payload[8:10], "little") & 0x3FFF
    return _reasonable_image_dimensions(width, height)


def _valid_vp8l(payload: bytes) -> bool:
    if len(payload) <= 5 or payload[0] != 0x2F:
        return False
    bits = int.from_bytes(payload[1:5], "little")
    if bits >> 29 != 0:
        return False
    width = (bits & 0x3FFF) + 1
    height = ((bits >> 14) & 0x3FFF) + 1
    return _reasonable_image_dimensions(width, height)


def _valid_vp8x(payload: bytes) -> bool:
    if len(payload) != 10 or payload[0] & 0xC1 or payload[1:4] != b"\x00\x00\x00":
        return False
    width = int.from_bytes(payload[4:7], "little") + 1
    height = int.from_bytes(payload[7:10], "little") + 1
    return _reasonable_image_dimensions(width, height)


def _detect_webp(data: bytes) -> bool:
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return False
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        return False

    offset = 12
    saw_primary = False
    saw_bitstream = False
    saw_vp8x = False
    while offset < len(data):
        if len(data) - offset < 8:
            return False
        chunk_type = data[offset:offset + 4]
        chunk_size = int.from_bytes(data[offset + 4:offset + 8], "little")
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        padded_end = payload_end + (chunk_size & 1)
        if payload_end > len(data) or padded_end > len(data):
            return False
        if chunk_size & 1 and data[payload_end] != 0:
            return False
        payload = data[payload_start:payload_end]

        if chunk_type == b"VP8 ":
            if saw_bitstream or not _valid_vp8(payload):
                return False
            saw_bitstream = True
            saw_primary = True
        elif chunk_type == b"VP8L":
            if saw_bitstream or not _valid_vp8l(payload):
                return False
            saw_bitstream = True
            saw_primary = True
        elif chunk_type == b"VP8X":
            if saw_vp8x or offset != 12 or not _valid_vp8x(payload) or payload[0] & 0x02:
                return False
            saw_vp8x = True
            saw_primary = True
        elif chunk_type in (b"ANIM", b"ANMF"):
            return False

        offset = padded_end

    return offset == len(data) and saw_primary and saw_bitstream


def detect_image(data: bytes) -> tuple[str, str] | None:
    """Return a trusted media type/extension from structurally valid bytes."""
    if detect_png(data): return ("image/png", ".png")
    if _detect_jpeg(data): return ("image/jpeg", ".jpg")
    if _detect_gif(data): return ("image/gif", ".gif")
    if _detect_webp(data): return ("image/webp", ".webp")
    return None


def _safe_upload_name(name: Any) -> str:
    value = str(name or "")
    if (not value or value.startswith("..") or value in (".", "..") or "/" in value or "\\" in value
            or "\x00" in value or any(ord(char) < 32 for char in value)):
        raise ValueError("Unsafe upload filename")
    return value


def _is_reparse_point(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _validate_requests_root(requests_root: Path) -> Path:
    root = Path(requests_root).absolute()
    intake = INTAKE_ROOT.resolve(strict=True)
    root.resolve(strict=False).relative_to(intake)
    current = root
    while True:
        if current.exists() and _is_reparse_point(current):
            raise ValueError("Requests path must not contain a symlink or junction")
        if current == intake:
            break
        current = current.parent
    if root.exists() and not root.is_dir():
        raise ValueError("Requests root must be a directory")
    return root


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_fsync(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _request_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"req-{stamp}-{uuid.uuid4().hex[:10]}"


def _project_name(payload: dict[str, Any]) -> str:
    value = payload.get("project_id")
    if not isinstance(value, str) or PROJECT_NAME_PATTERN.fullmatch(value) is None:
        raise ValueError("project_id must match ^[a-z0-9][a-z0-9-]{0,48}$")
    return value


def _site_config(payload: dict[str, Any]) -> dict[str, Any]:
    request_id = payload["request_id"]
    request_path = f"intake/requests/{request_id}"
    source_seo = payload["seo"]
    seo: dict[str, Any] = {}
    for field in ("title", "description"):
        value = source_seo.get(field)
        if isinstance(value, str) and value.strip():
            seo[field] = deepcopy(value.strip())
    if "keywords" in source_seo:
        seo["keywords"] = deepcopy(source_seo["keywords"])
    seo_upload = source_seo.get("upload")
    if isinstance(seo_upload, dict):
        seo["source_document"] = {
            "relative_path": f"{request_path}/{seo_upload['stored_path']}",
            "original_name": seo_upload["original_name"],
            "verified_media_type": seo_upload["media_type"],
        }
    config: dict[str, Any] = {
        "project_name": _project_name(payload),
        "language": "zh-CN",
        "user_request": payload["freeform_request"],
        "intake": {
            "request_id": request_id,
            "request_path": request_path,
            "source_request": f"{request_path}/site-request.json",
            "submitted_at": payload["submitted_at"],
        },
        "website_intent": {
            "industry": deepcopy(payload["industry"]),
            "site_type": deepcopy(payload["site_type"]),
            "brand_name": deepcopy(payload["brand"]),
            "target_audience": payload["target_audience"],
            "primary_goal": payload["primary_goal"],
            "requirements": payload["freeform_request"],
            "sections": deepcopy(payload["required_sections"]),
        },
        "reference_assets": [
            {
                "relative_path": f"{request_path}/{item['stored_path']}",
                "original_name": item["original_name"],
                "verified_media_type": item["media_type"],
                "purpose": item["purpose"],
                "usage_note": item.get("notes", ""),
            }
            for item in payload.get("references", [])
        ],
        "faq": deepcopy(payload["faq"]),
        "seo": seo,
    }
    for field in ("title", "description", "keywords"):
        if field in seo:
            config[field] = deepcopy(seo[field])
    return config


def _schema_error(validator: Draft202012Validator, value: Any, label: str) -> None:
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        path = ".".join(str(item) for item in error.absolute_path) or "$"
        raise ValueError(f"{label} schema validation failed at {path}: {error.message}")


def _atomic_publish_no_replace(stage: Path, final: Path) -> None:
    """Atomically publish a directory and fail if final already exists."""
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file = kernel32.MoveFileW
        move_file.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
        move_file.restype = ctypes.c_int
        if move_file(str(stage), str(final)):
            return
        code = ctypes.get_last_error()
        if code in (80, 183) or final.exists():
            raise FileExistsError(errno.EEXIST, "Request already exists", str(final))
        raise OSError(code, ctypes.FormatError(code), str(final))
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise OSError(errno.ENOSYS, "atomic no-replace publish is unavailable")
        renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
        renameat2.restype = ctypes.c_int
        if renameat2(-100, os.fsencode(stage), -100, os.fsencode(final), 1) == 0:
            return
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise FileExistsError(code, "Request already exists", str(final))
        raise OSError(code, os.strerror(code), str(final))
    raise OSError(errno.ENOSYS, "atomic no-replace publish is unavailable on this platform")


INPUT_TOP_LEVEL_FIELDS = {
    "schema_version", "project_id", "industry", "site_type", "brand",
    "target_audience", "primary_goal", "required_sections", "freeform_request",
    "project", "business", "website", "faq", "seo", "references",
}


def _looks_like_embedded_base64(value: str) -> bool:
    compact = "".join(value.split())
    if len(compact) < 32 or len(compact) % 4 or re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", compact) is None:
        return False
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError):
        return False
    signatures = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"RIFF", b"%PDF")
    if decoded.startswith(signatures):
        return True
    if len(decoded) < 64:
        return False
    binary = sum(byte == 0 or (byte < 9) or (13 < byte < 32) for byte in decoded)
    return binary * 4 > len(decoded)


def _reject_embedded_file_payload(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if "filebytes" in normalized or "base64" in normalized or normalized == "datauri":
                raise ValueError(f"Embedded file payload key is not allowed at {path}.{key}")
            _reject_embedded_file_payload(item, f"{path}.{key}")
    elif isinstance(value, list):
        if len(value) >= 16 and all(isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 255 for item in value):
            raise ValueError(f"Embedded file byte array is not allowed at {path}")
        for index, item in enumerate(value):
            _reject_embedded_file_payload(item, f"{path}[{index}]")
    elif isinstance(value, str):
        if re.match(r"^\s*data:[^,]{0,512},", value, re.IGNORECASE) or _looks_like_embedded_base64(value):
            raise ValueError(f"Embedded file string is not allowed at {path}")


def _contract_object(source: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: deepcopy(source[field]) for field in fields if field in source}


def _canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    unknown = set(payload) - INPUT_TOP_LEVEL_FIELDS
    if unknown:
        raise ValueError(f"Unknown payload field: {sorted(unknown)[0]}")
    canonical = _contract_object(payload, (
        "schema_version", "project_id", "industry", "site_type", "brand",
        "target_audience", "primary_goal", "required_sections", "freeform_request",
    ))
    canonical["project"] = _contract_object(payload["project"], ("name",))
    canonical["business"] = _contract_object(
        payload["business"], ("name", "industry", "target_audience", "facts")
    )
    canonical["website"] = _contract_object(
        payload["website"], ("primary_goal", "requirements", "pages", "style_notes")
    )
    canonical["faq"] = {
        "mode": deepcopy(payload["faq"]["mode"]),
        "items": [
            _contract_object(item, ("question", "answer", "source", "generation_note"))
            for item in payload["faq"]["items"]
        ],
    }
    canonical["seo"] = _contract_object(payload["seo"], ("title", "description", "keywords"))
    upload = payload["seo"].get("upload")
    canonical["seo"]["upload"] = (
        None if upload is None else _contract_object(upload, ("field_name", "original_name", "size", "media_type"))
    )
    canonical["references"] = [
        _contract_object(item, (
            "client_id", "field_name", "purpose", "notes", "original_name", "size", "media_type"
        ))
        for item in payload["references"]
    ]
    return canonical


def save_submission(payload: dict[str, Any], files: list[dict[str, Any]], requests_root: Path) -> dict[str, str]:
    # Complete preflight happens before requests_root, staging, or final is created.
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    _reject_embedded_file_payload(payload)
    references_value = payload.get("references")
    if isinstance(references_value, list) and len(references_value) > 6:
        raise ValueError("No more than six reference images are allowed")
    _schema_error(REQUEST_VALIDATOR, payload, "site-request")
    payload = _canonical_payload(payload)
    _project_name(payload)
    references = payload["references"]
    if len(files) > 7:
        raise ValueError("No more than seven uploaded files are allowed")

    actual_fields: list[str] = []
    for upload in files:
        field_name = upload.get("field_name")
        if not isinstance(field_name, str) or not field_name:
            raise ValueError("Every upload must have a field name")
        _safe_upload_name(upload.get("filename"))
        actual_fields.append(field_name)
    if len(actual_fields) != len(set(actual_fields)):
        raise ValueError("Duplicate upload field_name")
    by_field = {item["field_name"]: item for item in files}

    client_ids: set[str] = set()
    declared_fields: set[str] = set()
    planned: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for index, reference in enumerate(references, 1):
        client_id = reference["client_id"]
        field_name = reference["field_name"]
        if client_id in client_ids:
            raise ValueError("Duplicate reference client_id")
        if field_name in declared_fields:
            raise ValueError("Duplicate reference field_name")
        if field_name != f"reference:{client_id}":
            raise ValueError("Reference field_name must match its client_id")
        client_ids.add(client_id)
        declared_fields.add(field_name)
        if reference.get("original_name") is not None:
            _safe_upload_name(reference.get("original_name"))
        purpose = reference["purpose"]
        if purpose not in ALLOWED_PURPOSES:
            raise ValueError("Invalid reference purpose")
        upload = by_field.get(field_name)
        if upload is None:
            raise ValueError("Missing reference upload")
        data = upload["data"]
        if len(data) > MAX_IMAGE_BYTES:
            raise InvalidImage("Reference image is too large")
        detected = detect_image(data)
        if detected is None:
            raise InvalidImage("File content does not match a supported image")
        media_type, suffix = detected
        upload["content_type"] = media_type
        planned.append((reference, upload, f"{index:02d}-{purpose}{suffix}"))

    seo = payload["seo"]
    seo_meta = seo.get("upload")
    seo_upload = None
    seo_stored_name = None
    if seo_meta is not None:
        field_name = seo_meta["field_name"]
        if field_name != "seo_file":
            raise ValueError("SEO field_name must be seo_file")
        if field_name in declared_fields:
            raise ValueError("Duplicate upload field_name declaration")
        declared_fields.add(field_name)
        _safe_upload_name(seo_meta.get("original_name"))
        seo_upload = by_field.get(field_name)
        if seo_upload is None:
            raise ValueError("Missing SEO source upload")
        if len(seo_upload["data"]) > MAX_SEO_BYTES:
            raise ValueError("SEO source file is too large")
        suffix = Path(seo_upload["filename"]).suffix.lower()
        allowed_types = {
            ".txt": {"text/plain"},
            ".csv": {"text/csv", "application/csv", "text/plain"},
            ".json": {"application/json", "text/json", "text/plain"},
        }
        if suffix not in allowed_types or seo_upload["content_type"] not in allowed_types[suffix]:
            raise ValueError("SEO source must be a txt, csv, or json file")
        try:
            seo_upload["data"].decode("utf-8", "strict")
        except UnicodeDecodeError as error:
            raise ValueError("SEO source must be UTF-8") from error
        seo_stored_name = f"source{suffix}"
    if set(actual_fields) != declared_fields:
        raise ValueError("Uploads must exactly match declared metadata field_name values")

    request_id = _request_id()
    submitted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    saved = _canonical_payload(payload)
    saved["request_id"] = request_id
    saved["submitted_at"] = submitted_at
    saved_references = []
    for reference, upload, stored_name in planned:
        item = deepcopy(reference)
        item["original_name"] = upload["filename"]
        item["media_type"] = upload["content_type"]
        item["size"] = len(upload["data"])
        item["stored_path"] = f"references/{stored_name}"
        saved_references.append(item)
    saved["references"] = saved_references
    if seo_upload is not None and seo_stored_name is not None:
        saved["seo"]["upload"] = {
            "field_name": "seo_file",
            "original_name": seo_upload["filename"],
            "media_type": seo_upload["content_type"],
            "size": len(seo_upload["data"]),
            "stored_path": f"seo/{seo_stored_name}",
        }
    _schema_error(REQUEST_VALIDATOR, saved, "site-request")
    config = _site_config(saved)
    _schema_error(SITE_CONFIG_VALIDATOR, config, "site-config")
    request_bytes = _json_bytes(saved)
    config_bytes = _json_bytes(config)

    root = _validate_requests_root(requests_root)
    root.mkdir(parents=True, exist_ok=True)
    stage = root / f".staging-{request_id}-{uuid.uuid4().hex[:8]}"
    final = root / request_id
    stage.mkdir(exist_ok=False)
    try:
        if planned:
            references_dir = stage / "references"
            references_dir.mkdir()
            for _reference, upload, stored_name in planned:
                _write_fsync(references_dir / stored_name, upload["data"])
        if seo_upload is not None and seo_stored_name is not None:
            seo_dir = stage / "seo"
            seo_dir.mkdir()
            _write_fsync(seo_dir / seo_stored_name, seo_upload["data"])
        _write_fsync(stage / "site-request.json", request_bytes)
        _write_fsync(stage / "site-config.json", config_bytes)
        _atomic_publish_no_replace(stage, final)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return {
        "request_id": request_id,
        "absolute_path": str(final.resolve()),
        "relative_path": f"intake/requests/{request_id}",
    }


def _validate_dist_root(dist_root: Path) -> Path:
    root = Path(dist_root).absolute()
    if not root.exists() or not root.is_dir() or _is_reparse_point(root):
        raise ValueError("dist root must be an existing real directory")
    return root.resolve(strict=True)


class IntakeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], requests_root: Path, dist_root: Path):
        self.requests_root = Path(requests_root)
        self.dist_root = _validate_dist_root(dist_root)
        super().__init__(address, handler)


class IntakeHandler(BaseHTTPRequestHandler):
    server_version = "LocalSiteIntake/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, path: Path, content_type: str) -> None:
        try:
            relative = path.relative_to(self.server.dist_root)
            current = self.server.dist_root
            for part in relative.parts:
                current = current / part
                if _is_reparse_point(current):
                    raise ValueError("static path contains a symlink or junction")
            resolved = path.resolve(strict=True)
            resolved.relative_to(self.server.dist_root)
            if not resolved.is_file():
                raise ValueError("static path is not a file")
            body = resolved.read_bytes()
        except (OSError, ValueError):
            self._send_json(404, {"error": "not_found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        raw_path = urlsplit(self.path).path
        if raw_path in ("/api/health", "/health"):
            self._send_json(200, {
                "status": "ok",
                "service": "local-site-intake",
                "version": SERVICE_VERSION,
            })
            return
        try:
            decoded = unquote(raw_path, errors="strict")
            if decoded in ("/", "/index.html"):
                relative = Path("index.html")
            elif decoded.startswith("/assets/"):
                parts = decoded.lstrip("/").split("/")
                if any(part in ("", ".", "..") for part in parts):
                    raise ValueError("unsafe static path")
                relative = Path(*parts)
            else:
                raise ValueError("unknown static path")
            suffix = relative.suffix.lower()
            content_types = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".json": "application/json; charset=utf-8",
                ".svg": "image/svg+xml",
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".woff2": "font/woff2",
            }
            content_type = content_types.get(suffix)
            if content_type is None:
                raise ValueError("unsupported static type")
        except (UnicodeError, ValueError):
            self._send_json(404, {"error": "not_found"})
            return
        self._send_static(self.server.dist_root / relative, content_type)

    def do_POST(self) -> None:
        if self.path != "/api/requests":
            self._send_json(404, {"error": "not_found"})
            return
        origin = self.headers.get("Origin")
        if origin:
            parsed = urlsplit(origin)
            if (parsed.scheme not in ("http", "https")
                    or parsed.hostname not in ("127.0.0.1", "localhost", "::1")):
                try:
                    rejected_length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    rejected_length = 0
                if 0 < rejected_length <= MAX_POST_BYTES:
                    self.rfile.read(rejected_length)
                self._send_json(403, {"error": "origin_rejected"})
                return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(411, {"error": "content_length_required"})
            return
        if length < 0 or length > MAX_POST_BYTES:
            self._send_json(413, {"error": "body_too_large", "max_bytes": MAX_POST_BYTES})
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data;"):
            self._send_json(415, {"error": "multipart_required"})
            return
        try:
            form = parse_multipart(content_type, self.rfile.read(length))
            payload_text = form["fields"].get("payload", "")
            payload = json.loads(payload_text)
        except (UnicodeError, ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid_payload"})
            return
        missing = validate_required(payload)
        if missing:
            self._send_json(400, {"error": "validation_error", "fields": missing})
            return
        try:
            result = save_submission(payload, form["files"], self.server.requests_root)
        except FileExistsError:
            self._send_json(409, {"error": "request_conflict"})
            return
        except InvalidImage as error:
            self._send_json(415, {"error": "invalid_image", "message": str(error)})
            return
        except ValueError as error:
            self._send_json(400, {"error": "validation_error", "message": str(error)})
            return
        self._send_json(201, result)


def create_server(*, port: int = 4180, requests_root: Path | None = None,
                  dist_root: Path | None = None) -> IntakeHTTPServer:
    root = Path(requests_root) if requests_root is not None else INTAKE_ROOT / "requests"
    static_root = Path(dist_root) if dist_root is not None else INTAKE_ROOT / "dist"
    return IntakeHTTPServer(("127.0.0.1", int(port)), IntakeHandler, root, static_root)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Local desktop site-intake server")
    parser.add_argument("--port", type=int, default=4180)
    parser.add_argument("--requests-root", type=Path, default=INTAKE_ROOT / "requests")
    args = parser.parse_args()
    httpd = create_server(port=args.port, requests_root=args.requests_root)
    print(f"Site Intake listening on http://127.0.0.1:{httpd.server_port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
