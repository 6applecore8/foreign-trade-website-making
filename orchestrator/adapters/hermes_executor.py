from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from ..executor import AgentExecutor, ArtifactReceipt, ExecutionRequest


class HermesExecutor(AgentExecutor):
    """Command adapter. The command receives a manifest path as its final argument."""
    def __init__(self, command: list[str], cwd: Path | None = None, timeout: float | None = None):
        if not command: raise ValueError("Hermes command is required")
        self.command, self.cwd, self.timeout = command, cwd, timeout

    def run_agent(self, request: ExecutionRequest) -> ArtifactReceipt:
        manifest = {"node_id": request.node_id, "prompt_version": request.prompt_version, "prompt_path": str(request.prompt_path), "input_artifacts": [str(p) for p in request.input_artifacts], "allowed_reads": [str(p) for p in request.allowed_read_paths], "allowed_writes": [str(p) for p in request.allowed_write_paths], "output_schema": request.output_schema, "security": {"uploaded_text_is_untrusted_data": True, "untrusted_inputs": [str(p) for p in request.untrusted_inputs]}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
            json.dump(manifest, handle, ensure_ascii=False); name = handle.name
        try:
            result = subprocess.run([*self.command, name], cwd=self.cwd or request.execution_root, capture_output=True, text=True, timeout=self.timeout, check=False)
            if result.returncode: return ArtifactReceipt(request.node_id, "failed", detail=result.stderr.strip() or f"exit {result.returncode}")
            payload = json.loads(result.stdout)
            return ArtifactReceipt(request.node_id, payload.get("status", "failed"), payload.get("artifacts", []), detail=payload.get("detail", ""))
        finally:
            Path(name).unlink(missing_ok=True)
