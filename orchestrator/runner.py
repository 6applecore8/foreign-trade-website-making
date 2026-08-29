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

    def run(self, workflow_path: str = "workflow.json", run_id: str | None = None, start_from: str | None = None) -> dict:
        workflow = json.loads(resolve_inside(self.root, workflow_path).read_text(encoding="utf-8"))
        graph = WorkflowGraph(workflow)
        shared_input = workflow.get("shared_input")
        declared_inputs = {}
        if isinstance(shared_input, str) and shared_input:
            config_path = resolve_inside(self.root, shared_input)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            declared_inputs = self._declared_inputs(config)
        run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id): raise ValueError("invalid run_id")
        registry = ArtifactRegistry(self.root)
        ordered_nodes = graph.topological_order()
        reused_hashes = None
        if start_from is not None:
            if start_from not in ordered_nodes:
                raise ValueError(f"start_from must be an executable node: {start_from}")
            skipped_nodes = ordered_nodes[:ordered_nodes.index(start_from)]
            reused = [config_path] if isinstance(shared_input, str) and shared_input else []
            for skipped_id in skipped_nodes:
                reused.extend(resolve_inside(self.root, path.replace("<run_id>", run_id)) for path in graph.nodes[skipped_id].data.get("writes", []))
            missing_reused = [path for path in reused if not path.is_file() or path.stat().st_size == 0]
            if missing_reused:
                raise FileNotFoundError(f"cannot start from {start_from}; reusable artifacts missing: {[str(path.relative_to(self.root)) for path in missing_reused]}")
            reused_hashes = registry.receipt_hashes(reused)
            ordered_nodes = ordered_nodes[ordered_nodes.index(start_from):]
        state = StateStore(self.root, run_id)
        if reused_hashes is not None:
            state.update_node("reused-upstream-artifacts", "success", artifacts=list(reused_hashes), hashes=reused_hashes)
        sandbox_root = self.root / "runs" / ".sandboxes"
        sandbox_root.mkdir(parents=True, exist_ok=True)
        try:
            for node_id in ordered_nodes:
                if node_id == "validation":
                    self._run_pre_validation_gate(run_id, state, registry)
                node = graph.nodes[node_id].data
                reads_list = [resolve_inside(self.root, p.replace("<run_id>", run_id)) for p in node.get("reads", [])]
                for declared in declared_inputs.get(node_id, ()):
                    if declared not in reads_list:
                        reads_list.append(declared)
                reads = tuple(reads_list)
                writes = tuple(resolve_inside(self.root, p.replace("<run_id>", run_id)) for p in node.get("writes", []))
                for path in reads:
                    if not path.exists(): raise FileNotFoundError(f"{node_id} input missing: {path.relative_to(self.root)}")
                allowed = {p.relative_to(self.root).as_posix() for p in writes}
                before = snapshot(self.root, {state.path})
                with tempfile.TemporaryDirectory(prefix=f"site-workflow-{node_id}-", dir=sandbox_root) as temp:
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
                        target.parent.mkdir(parents=True, exist_ok=True)
                        # Pre-create caller-owned placeholders. Native Windows
                        # elevated sandboxes can otherwise create outputs owned
                        # solely by the sandbox identity, preventing the Runner
                        # from validating and copying them after the process exits.
                        target.touch(exist_ok=False)
                        sandbox_writes.append(target)
                    untrusted = tuple(
                        path for path in sandbox_reads
                        if "intake" in path.parts or path.name == "site-config.json"
                    )
                    request = ExecutionRequest(node_id, str(node.get("prompt_version", workflow.get("version", "1"))), sandbox, prompt_target, tuple(sandbox_reads), tuple(sandbox_reads), tuple(sandbox_writes), node.get("output_schema"), untrusted)
                    receipt = self.executor.run_agent(request)
                    staged_produced = [path for path in sandbox_writes if path.is_file() and path.stat().st_size > 0]
                    if receipt.status != "success" or len(staged_produced) != len(sandbox_writes):
                        raise RuntimeError(receipt.detail or f"{node_id} did not produce every declared artifact")
                    for staged in staged_produced:
                        if staged.suffix == ".json":
                            try:
                                payload = json.loads(staged.read_text(encoding="utf-8"))
                            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                                raise RuntimeError(f"{node_id} produced invalid JSON: {staged.relative_to(sandbox)}") from exc
                            if node_id == "validation" and payload.get("status") != "passed":
                                raise RuntimeError("validation report did not pass")
                    for staged, destination in zip(sandbox_writes, writes):
                        if staged.is_symlink(): raise PermissionViolation(f"executor produced symbolic link: {staged}")
                        destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(staged, destination)
                after = snapshot(self.root, {state.path})
                reject_unauthorized_changes(before, after, allowed)
                produced = [p for p in writes if p.is_file() and p.stat().st_size > 0]
                if len(produced) != len(writes): raise RuntimeError(f"{node_id} did not promote every declared artifact")
                for artifact in produced:
                    if artifact.suffix == ".json":
                        try: json.loads(artifact.read_text(encoding="utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise RuntimeError(f"{node_id} produced invalid JSON: {artifact.relative_to(self.root)}") from exc
                hashes = registry.receipt_hashes(produced)
                state.update_node(node_id, "success", artifacts=list(hashes), hashes=hashes)
            state.finish("success")
            return state.state
        except Exception as exc:
            state.finish("failed")
            state.state["error"] = {"type": type(exc).__name__, "detail": str(exc)}; state.flush()
            return state.state

    def _run_pre_validation_gate(self, run_id: str, state: StateStore, registry: ArtifactRegistry) -> None:
        if self.browser_collector is None:
            raise RuntimeError("desktop browser evidence collector is required before validation")
        evidence = self.root / "runs" / run_id / "artifacts" / "browser-evidence.json"
        screenshot = self.root / "runs" / run_id / "artifacts" / "desktop-1440x900.png"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        gate_before = snapshot(self.root, {state.path})
        browser_receipt = self.browser_collector.collect(self.root / "artifacts/04-implementation/site", evidence, screenshot)
        gate_after = snapshot(self.root, {state.path})
        gate_allowed = {path.relative_to(self.root).as_posix() for path in (evidence, screenshot)}
        reject_unauthorized_changes(gate_before, gate_after, gate_allowed)
        if browser_receipt.status != "success" or not evidence.is_file() or not screenshot.is_file():
            raise RuntimeError(browser_receipt.detail or "browser evidence collection failed")
        deterministic = DeterministicValidator().validate(self.root)
        browser_gate = BrowserEvidenceValidator().validate(evidence)
        if deterministic["status"] != "passed" or browser_gate["status"] != "passed":
            raise RuntimeError(f"pre-validation gate failed: deterministic={deterministic['errors']}; browser={browser_gate['errors']}")
        browser_hashes = registry.receipt_hashes([evidence, screenshot])
        state.update_node("desktop-browser-validation", "success", artifacts=list(browser_hashes), hashes=browser_hashes)

    def _declared_inputs(self, config: dict) -> dict[str, tuple[Path, ...]]:
        """Resolve only schema-declared immutable Intake sources with least privilege."""
        intake = config.get("intake") if isinstance(config.get("intake"), dict) else {}
        request_value = intake.get("request_path")
        if not request_value:
            return {}
        request_root = resolve_inside(self.root, request_value)
        if not request_root.is_dir():
            raise FileNotFoundError(f"immutable Intake request missing: {request_value}")

        def declared_file(value: str) -> Path:
            path = resolve_inside(self.root, value)
            try:
                path.relative_to(request_root)
            except ValueError as error:
                raise PermissionViolation(f"declared Intake source escapes request: {value}") from error
            if not path.is_file():
                raise FileNotFoundError(f"declared Intake source missing: {value}")
            return path

        references = tuple(
            declared_file(item["relative_path"])
            for item in config.get("reference_assets", [])
            if isinstance(item, dict) and isinstance(item.get("relative_path"), str)
        )
        seo_value = config.get("seo", {})
        source_document = seo_value.get("source_document") if isinstance(seo_value, dict) else None
        seo = ()
        if isinstance(source_document, dict) and isinstance(source_document.get("relative_path"), str):
            seo = (declared_file(source_document["relative_path"]),)
        return {
            "metadata": seo,
            "implementation": references,
            "validation": (*references, *seo),
        }
