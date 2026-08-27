from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class StateStore:
    def __init__(self, root: Path, run_id: str):
        self.path = root / "runs" / run_id / "run-state.json"
        self.path.parent.mkdir(parents=True, exist_ok=False)
        self.state = {"run_id": run_id, "status": "running", "created_at": datetime.now(timezone.utc).isoformat(), "nodes": {}}
        self.flush()

    def update_node(self, node_id: str, status: str, **extra) -> None:
        self.state["nodes"][node_id] = {"status": status, **extra}
        self.flush()

    def finish(self, status: str) -> None:
        self.state["status"] = status
        self.state["finished_at"] = datetime.now(timezone.utc).isoformat()
        self.flush()

    def flush(self) -> None:
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
