from __future__ import annotations

import os
from pathlib import Path

from .artifact_registry import sha256


class PermissionViolation(RuntimeError):
    pass


def resolve_inside(root: Path, value: str) -> Path:
    if "<run_id>" in value:
        raise PermissionViolation("unexpanded <run_id> path")
    candidate = root / value
    if candidate.is_symlink():
        raise PermissionViolation(f"symbolic links are forbidden: {value}")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise PermissionViolation(f"path escapes project root: {value}") from exc
    current = root.resolve()
    for part in Path(value).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise PermissionViolation(f"symbolic-link ancestor is forbidden: {value}")
    return resolved


def snapshot(root: Path, ignored: set[Path] | None = None) -> dict[str, str]:
    ignored = {item.resolve() for item in (ignored or set())}
    result = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__"}]
        for name in files:
            path = (Path(base) / name).resolve()
            if path not in ignored:
                result[path.relative_to(root.resolve()).as_posix()] = sha256(path)
    return result


def reject_unauthorized_changes(before: dict[str, str], after: dict[str, str], allowed_writes: set[str]) -> None:
    changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    unauthorized = sorted(changed - allowed_writes)
    if unauthorized:
        raise PermissionViolation(f"unauthorized filesystem changes: {unauthorized}")
