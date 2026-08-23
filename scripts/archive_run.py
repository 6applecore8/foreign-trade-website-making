#!/usr/bin/env python
"""Archive one workflow run without altering its source tree."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
RUN_ID_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._+-]{0,126}[A-Za-z0-9])?$")
TEMP_SUFFIXES = {".tmp", ".temp", ".pyc", ".pyo"}

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def is_excluded(relative_path: Path) -> bool:
    if "__pycache__" in relative_path.parts:
        return True
    lower = relative_path.name.lower()
    return (relative_path.suffix.lower() in TEMP_SUFFIXES or lower.endswith("~")
            or lower.startswith(".~") or lower.startswith(".tmp"))

def selected_files(source_root: Path) -> list[Path]:
    config = source_root / "config" / "site-config.json"
    artifacts = source_root / "artifacts"
    if not config.is_file():
        raise FileNotFoundError(f"required source file is missing: {config}")
    if not artifacts.is_dir():
        raise FileNotFoundError(f"required source directory is missing: {artifacts}")
    files = [config]
    files.extend(path for path in sorted(artifacts.rglob("*"))
                 if path.is_file() and not is_excluded(path.relative_to(source_root)))
    return files

def validation_status(source_root: Path) -> str:
    report = source_root / "artifacts" / "05-validation" / "validation-report.json"
    if not report.is_file():
        return "unknown"
    try:
        value = json.loads(report.read_text(encoding="utf-8")).get("status", "unknown")
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "unknown"
    return value if isinstance(value, str) and value else "unknown"

def archive_run(project_root: Path, source_root: Path, run_id: str) -> tuple[Path, dict]:
    if not RUN_ID_RE.fullmatch(run_id) or run_id in {".", ".."}:
        raise ValueError("unsafe run-id: use 1-128 ASCII letters, digits, '.', '_', '+', or '-', starting and ending with a letter or digit")
    project_root = project_root.resolve(strict=True)
    source_root = source_root.resolve(strict=True)
    runs_root = project_root / "archive" / "runs"
    if not runs_root.is_dir():
        raise FileNotFoundError(f"archive parent is missing: {runs_root}")
    destination = runs_root / run_id
    if destination.exists():
        raise FileExistsError(f"archive destination already exists: {destination}")
    files = selected_files(source_root)
    stage = Path(tempfile.mkdtemp(prefix=f".{run_id}.tmp-", dir=runs_root))
    manifest_files = []
    try:
        for source in files:
            relative = source.relative_to(source_root)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            manifest_files.append({"path": relative.as_posix(), "bytes": target.stat().st_size,
                                   "sha256": sha256_file(target)})
        manifest = {"source": str(source_root),
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "status": validation_status(source_root), "files": manifest_files}
        manifest_path = stage / "run-manifest.json"
        with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if destination.exists():
            raise FileExistsError(f"archive destination appeared during staging: {destination}")
        os.rename(stage, destination)
        return destination, manifest
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an immutable archive of a site-workflow-mvp run.")
    parser.add_argument("run_id", help="safe unique archive id")
    parser.add_argument("--source-root", type=Path, default=None,
                        help="run root to copy (default: current site-workflow-mvp root)")
    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(__file__).resolve().parent.parent
    source_root = args.source_root if args.source_root is not None else project_root
    try:
        destination, manifest = archive_run(project_root, source_root, args.run_id)
    except (OSError, ValueError) as exc:
        print(f"archive failed: {exc}", file=sys.stderr); return 1
    print(json.dumps({"destination": str(destination), "status": manifest["status"],
                      "file_count": len(manifest["files"])}, ensure_ascii=False))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
