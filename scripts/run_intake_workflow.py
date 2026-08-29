#!/usr/bin/env python
"""Promote one immutable Intake request and execute the repository workflow."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.adapters.codex_executor import CodexExecutor
from orchestrator.adapters.hermes_executor import HermesExecutor
from orchestrator.browser import PlaywrightBrowserEvidenceCollector
from orchestrator.runner import WorkflowRunner
from scripts.archive_run import archive_run


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=True)
    resolved.relative_to(root.resolve(strict=True))
    return resolved


def load_launch_manifest(project_root: Path, manifest_path: Path) -> tuple[dict, Path, Path]:
    project_root = project_root.resolve(strict=True)
    runtime_root = (project_root / "intake/run-status").resolve(strict=True)
    manifest_path = _inside(manifest_path, runtime_root)
    if manifest_path.name != "launch-manifest.json":
        raise ValueError("launch manifest has an unexpected filename")
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "run_id", "request_id", "request_path", "source_request",
        "source_config", "trust", "allowed_reads", "allowed_write_root",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("launch manifest fields do not match the execution contract")
    run_id, request_id = value.get("run_id"), value.get("request_id")
    if not isinstance(run_id, str) or manifest_path.parent.name != run_id:
        raise ValueError("launch manifest run_id does not match its directory")
    if not isinstance(request_id, str) or not request_id.startswith("req-"):
        raise ValueError("launch manifest request_id is invalid")
    expected_request_path = f"intake/requests/{request_id}"
    expected_reads = [
        f"{expected_request_path}/site-request.json",
        f"{expected_request_path}/site-config.json",
        f"{expected_request_path}/references",
        f"{expected_request_path}/seo",
    ]
    if value != {
        "schema_version": "1.0",
        "run_id": run_id,
        "request_id": request_id,
        "request_path": expected_request_path,
        "source_request": f"{expected_request_path}/site-request.json",
        "source_config": f"{expected_request_path}/site-config.json",
        "trust": "untrusted-user-data",
        "allowed_reads": expected_reads,
        "allowed_write_root": f"runs/{run_id}",
    }:
        raise ValueError("launch manifest values do not match the immutable request contract")
    request_dir = _inside(project_root / expected_request_path, project_root / "intake/requests")
    request_path = _inside(project_root / value["source_request"], request_dir)
    config_path = _inside(project_root / value["source_config"], request_dir)
    return value, request_path, config_path


def validate_request(project_root: Path, request_id: str, request_path: Path, config_path: Path) -> None:
    request_schema = json.loads((project_root / "intake/request.schema.json").read_text(encoding="utf-8"))
    config_schema = json.loads((project_root / "config/site-config.schema.json").read_text(encoding="utf-8"))
    request = json.loads(request_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    Draft202012Validator(request_schema, format_checker=FormatChecker()).validate(request)
    Draft202012Validator(config_schema, format_checker=FormatChecker()).validate(config)
    if request.get("request_id") != request_id:
        raise ValueError("immutable request identity mismatch")
    intake = config.get("intake", {})
    if intake.get("request_id") != request_id or intake.get("source_request") != str(request_path.relative_to(project_root)).replace("\\", "/"):
        raise ValueError("site-config identity does not match immutable request")


def _json_command(variable: str) -> list[str] | None:
    raw = os.environ.get(variable, "").strip()
    if not raw:
        return None
    command = json.loads(raw)
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise ValueError(f"{variable} must be a non-empty JSON string array")
    return command


def build_executor(project_root: Path):
    provider = os.environ.get("SITE_AGENT_PROVIDER", "codex").strip().lower()
    timeout_value = os.environ.get("SITE_NODE_TIMEOUT_SECONDS", "").strip()
    timeout = float(timeout_value) if timeout_value else None
    if provider == "codex":
        executor = CodexExecutor(
            project_root,
            command=_json_command("SITE_CODEX_COMMAND_JSON"),
            timeout=timeout,
        )
        executor.preflight()
        return executor
    if provider == "hermes":
        command = _json_command("SITE_NODE_AGENT_COMMAND_JSON")
        if not command:
            raise RuntimeError("Hermes provider requires SITE_NODE_AGENT_COMMAND_JSON")
        return HermesExecutor(command, cwd=project_root, timeout=timeout)
    raise ValueError("SITE_AGENT_PROVIDER must be codex or hermes")


def promote_config(project_root: Path, source: Path) -> None:
    destination = project_root / "config/site-config.json"
    data = source.read_bytes()
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=destination.parent, prefix=".site-config-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def execute(project_root: Path, manifest_path: Path) -> dict:
    manifest, request_path, config_path = load_launch_manifest(project_root, manifest_path)
    validate_request(project_root, manifest["request_id"], request_path, config_path)
    executor = build_executor(project_root)
    browser = PlaywrightBrowserEvidenceCollector(project_root)
    browser.preflight()
    # Archive and promotion happen only after both execution providers pass preflight.
    archive_run(project_root, project_root, manifest["run_id"])
    promote_config(project_root, config_path)
    return WorkflowRunner(project_root, executor, browser).run(run_id=manifest["run_id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one selected immutable Site Intake request")
    parser.add_argument("--intake-manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        state = execute(PROJECT_ROOT, args.intake_manifest)
    except Exception as error:
        print(json.dumps({"status": "failed", "error": {"type": type(error).__name__, "detail": str(error)}}, ensure_ascii=False))
        return 1
    print(json.dumps(state, ensure_ascii=False))
    return 0 if state.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
