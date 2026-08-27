from __future__ import annotations

import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .acl import PermissionViolation, reject_unauthorized_changes, resolve_inside, snapshot
from .artifact_registry import ArtifactRegistry
from .browser import BrowserEvidenceCollector
from .executor import AgentExecutor, ExecutionRequest
from .graph import WorkflowGraph
from .state_store import StateStore
from .validators import BrowserEvidenceValidator, DeterministicValidator


class WorkflowRunner:
    def __init__(self, root: Path, executor: AgentExecutor, browser_collector: BrowserEvidenceCollector | None = None):
        self.root, self.executor, self.browser_collector = root.resolve(), executor, browser_collector

    def run(self, workflow_path: str = "workflow.json", run_id: str | None = None) -> dict:
        workflow = json.loads(resolve_inside(self.root, workflow_path).read_text(encoding="utf-8"))
        graph = WorkflowGraph(workflow)
        run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id): raise ValueError("invalid run_id")
        state, registry = StateStore(self.root, run_id), ArtifactRegistry(self.root)
        try:
            for node_id in graph.topological_order():
                node = graph.nodes[node_id].data
                reads = tuple(resolve_inside(self.root, p.replace("<run_id>", run_id)) for p in node.get("reads", []))
                writes = tuple(resolve_inside(self.root, p.replace("<run_id>", run_id)) for p in node.get("writes", []))
                for path in reads:
                    if not path.exists(): raise FileNotFoundError(f"{node_id} input missing: {path.relative_to(self.root)}")
                allowed = {p.relative_to(self.root).as_posix() for p in writes}
                before = snapshot(self.root, {state.path})
                with tempfile.TemporaryDirectory(prefix=f"site-workflow-{node_id}-") as temp:
                    sandbox = Path(temp).resolve()
                    sandbox_reads, sandbox_writes = [], []
                    prompt_source = resolve_inside(self.root, node["prompt"])
                    prompt_target = sandbox / prompt_source.relative_to(self.root)
                    prompt_target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(prompt_source, prompt_target)
                    for source in reads:
                        target = sandbox / source.relative_to(self.root)
                        if source.is_dir(): shutil.copytree(source, target, symlinks=False)
                        else: target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
                        sandbox_reads.append(target)
                    for destination in writes:
                        target = sandbox / destination.relative_to(self.root)
                        target.parent.mkdir(parents=True, exist_ok=True); sandbox_writes.append(target)
                    request = ExecutionRequest(node_id, str(node.get("prompt_version", workflow.get("version", "1"))), sandbox, prompt_target, tuple(sandbox_reads), tuple(sandbox_reads), tuple(sandbox_writes), node.get("output_schema"), tuple(p for p in sandbox_reads if "intake" in p.parts))
                    receipt = self.executor.run_agent(request)
                    for staged, destination in zip(sandbox_writes, writes):
                        if staged.is_symlink(): raise PermissionViolation(f"executor produced symbolic link: {staged}")
                        if staged.is_file(): destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(staged, destination)
                after = snapshot(self.root, {state.path})
                reject_unauthorized_changes(before, after, allowed)
                produced = [p for p in writes if p.is_file()]
                if receipt.status != "success" or len(produced) != len(writes): raise RuntimeError(receipt.detail or f"{node_id} did not produce every declared artifact")
                for artifact in produced:
                    if artifact.suffix == ".json":
                        try: json.loads(artifact.read_text(encoding="utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise RuntimeError(f"{node_id} produced invalid JSON: {artifact.relative_to(self.root)}") from exc
                hashes = registry.receipt_hashes(produced)
                state.update_node(node_id, "success", artifacts=list(hashes), hashes=hashes)
                if node_id == "implementation":
                    if self.browser_collector is None:
                        raise RuntimeError("desktop browser evidence collector is required before validation")
                    evidence = self.root / "runs" / run_id / "artifacts" / "browser-evidence.json"
                    screenshot = self.root / "runs" / run_id / "artifacts" / "desktop-1440x900.png"
                    evidence.parent.mkdir(parents=True, exist_ok=True)
                    gate_before = snapshot(self.root, {state.path})
                    browser_receipt = self.browser_collector.collect(self.root / "artifacts/04-implementation/site", evidence, screenshot)
                    gate_after = snapshot(self.root, {state.path})
                    gate_allowed = {p.relative_to(self.root).as_posix() for p in (evidence, screenshot)}
                    reject_unauthorized_changes(gate_before, gate_after, gate_allowed)
                    if browser_receipt.status != "success" or not evidence.is_file() or not screenshot.is_file():
                        raise RuntimeError(browser_receipt.detail or "browser evidence collection failed")
                    deterministic = DeterministicValidator().validate(self.root)
                    browser_gate = BrowserEvidenceValidator().validate(evidence)
                    if deterministic["status"] != "passed" or browser_gate["status"] != "passed":
                        raise RuntimeError(f"pre-validation gate failed: deterministic={deterministic['errors']}; browser={browser_gate['errors']}")
                    browser_hashes = registry.receipt_hashes([evidence, screenshot])
                    state.update_node("desktop-browser-validation", "success", artifacts=list(browser_hashes), hashes=browser_hashes)
            state.finish("success")
            return state.state
        except Exception as exc:
            state.finish("failed")
            state.state["error"] = {"type": type(exc).__name__, "detail": str(exc)}; state.flush()
            return state.state
